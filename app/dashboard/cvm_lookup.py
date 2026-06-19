"""
Busca de gestor de fundo via base cadastral pública da CVM.

Réplica da lógica já validada no ETL.py existente do usuário — mesma
fonte de dados (registro_fundo.csv), mesma normalização de CNPJ, mesmo
cruzamento. A diferença: mantém um cache local em disco (atualizado no
máximo 1x/dia) em vez de baixar tudo a cada execução, e nunca apaga a
pasta de cache ao final (o ETL original fazia shutil.rmtree('data')).

Importante: esta busca só é necessária para Pessoa Jurídica (fundos).
Pessoa física não tem "gestor" — ela é a própria titular.

Se o download falhar (rede, mudança de URL/schema na CVM, etc.), o
módulo nunca trava o restante do sistema: levanta CVMIndisponivel e
quem chama decide o fallback (deixar o campo de gestor em branco para
preenchimento manual, ou orientar o uso do .exe externo como hoje).
"""
import re
import time
from dataclasses import dataclass
from pathlib import Path
from zipfile import ZipFile

import requests
import pandas as pd

CACHE_DIR = Path.home() / ".fiducio" / "cvm_cache"
CACHE_MAX_IDADE_SEGUNDOS = 24 * 60 * 60  # 1 dia

URL_REGISTRO_FUNDO_CLASSE = "https://dados.cvm.gov.br/dados/FI/CAD/DADOS/registro_fundo_classe.zip"

# nomes de arquivo possíveis dentro do zip / após extração — a CVM tem
# migrado o schema (RCVM175); checamos os candidatos mais conhecidos
# em ordem de preferência.
CANDIDATOS_REGISTRO_FUNDO = ["registro_fundo.csv", "registro_fundo_classe.csv"]


class CVMIndisponivel(Exception):
    """Levantada quando não foi possível obter ou ler a base da CVM."""


@dataclass
class ResultadoBuscaGestor:
    cnpj: str
    encontrado: bool
    nome_gestor: str | None = None
    codigo_cvm: str | None = None
    erro: str | None = None


def normalizar_cnpj(valor: str) -> str:
    """Remove pontuação e garante 14 dígitos com zeros à esquerda — mesma
    regra do ETL.py original."""
    digitos = re.sub(r"\D", "", str(valor or ""))
    return digitos.zfill(14)


def _cache_valido() -> Path | None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    for nome in CANDIDATOS_REGISTRO_FUNDO:
        caminho = CACHE_DIR / nome
        if caminho.exists():
            idade = time.time() - caminho.stat().st_mtime
            if idade < CACHE_MAX_IDADE_SEGUNDOS:
                return caminho
    return None


def _baixar_base(timeout: int = 60) -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    destino_zip = CACHE_DIR / "registro_fundo_classe.zip"

    try:
        resp = requests.get(URL_REGISTRO_FUNDO_CLASSE, timeout=timeout)
        resp.raise_for_status()
        destino_zip.write_bytes(resp.content)
    except Exception as e:
        raise CVMIndisponivel(
            f"Não foi possível baixar a base da CVM: {e}"
        ) from e

    try:
        with ZipFile(destino_zip, "r") as z:
            z.extractall(CACHE_DIR)
    except Exception as e:
        raise CVMIndisponivel(
            f"Arquivo da CVM baixado, mas não foi possível extrair: {e}"
        ) from e
    finally:
        destino_zip.unlink(missing_ok=True)

    for nome in CANDIDATOS_REGISTRO_FUNDO:
        caminho = CACHE_DIR / nome
        if caminho.exists():
            return caminho

    raise CVMIndisponivel(
        "Base da CVM baixada, mas nenhum arquivo de registro de fundo "
        f"reconhecido foi encontrado (esperado um de: {CANDIDATOS_REGISTRO_FUNDO}). "
        "O schema da CVM pode ter mudado."
    )


def garantir_base_local(forcar_atualizacao: bool = False) -> Path:
    """Retorna o caminho do CSV local, baixando/atualizando se necessário."""
    if not forcar_atualizacao:
        caminho = _cache_valido()
        if caminho:
            return caminho
    return _baixar_base()


def _carregar_dataframe(caminho_csv: Path) -> pd.DataFrame:
    try:
        df = pd.read_csv(caminho_csv, sep=";", encoding="ISO-8859-1", low_memory=False)
    except Exception as e:
        raise CVMIndisponivel(f"Não foi possível ler a base local da CVM: {e}") from e

    if "CNPJ_Fundo" not in df.columns:
        raise CVMIndisponivel(
            "A base local da CVM não tem a coluna 'CNPJ_Fundo' esperada — "
            "o schema pode ter mudado."
        )

    if "Situacao" in df.columns:
        df["Situacao"] = df["Situacao"].astype(str).str.strip()
        df = df[df["Situacao"].str.lower() != "cancelado"].copy()

    return df


def buscar_gestores(cnpjs: list[str], forcar_atualizacao: bool = False) -> list[ResultadoBuscaGestor]:
    """
    Busca o gestor de cada CNPJ informado na base da CVM.
    Levanta CVMIndisponivel se a base não puder ser obtida/lida —
    quem chama decide o fallback (não interrompe o restante do fluxo).
    """
    caminho_csv = garantir_base_local(forcar_atualizacao=forcar_atualizacao)
    df = _carregar_dataframe(caminho_csv)

    resultados = []
    for cnpj_original in cnpjs:
        cnpj_norm = normalizar_cnpj(cnpj_original)
        try:
            cnpj_int = int(cnpj_norm)
            linha = df.loc[df["CNPJ_Fundo"] == cnpj_int]
        except ValueError:
            linha = df.iloc[0:0]

        if not linha.empty:
            gestor = linha["Gestor"].iloc[0]
            codigo_cvm = linha["Codigo_CVM"].iloc[0]
            resultados.append(ResultadoBuscaGestor(
                cnpj=cnpj_original,
                encontrado=True,
                nome_gestor=str(gestor).strip() if pd.notna(gestor) else None,
                codigo_cvm=str(codigo_cvm).strip() if pd.notna(codigo_cvm) else None,
            ))
        else:
            resultados.append(ResultadoBuscaGestor(
                cnpj=cnpj_original,
                encontrado=False,
            ))

    return resultados
