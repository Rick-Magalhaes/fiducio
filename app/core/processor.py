import csv
import os
import pdfplumber
from dataclasses import dataclass, field
from pathlib import Path
from datetime import datetime

from app.core.detector import pontuar, NOTA_MINIMA, MARGEM_MINIMA
from app.models.registry import MODELOS
from app.utils.text_utils import texto_completo


AUTOMATICO = "Automático"
MAX_CANDIDATOS = 3


def caminho_longo(p: Path) -> Path:
    """
    Windows recusa caminhos com mais de 260 caracteres. O prefixo \\\\?\\ libera
    o limite. As pastas do G: passam disso com facilidade.
    """
    if os.name == "nt" and not str(p).startswith("\\\\?\\"):
        return Path("\\\\?\\" + os.path.abspath(str(p)))
    return p


@dataclass
class ProcessingResult:
    caminho_original: Path
    novo_nome: str | None = None
    erro: str | None = None
    modelo_usado: str | None = None
    nota: int = 0
    motivo: str = ""
    indecidido: bool = False
    simulado: bool = False

    @property
    def sucesso(self) -> bool:
        return self.erro is None and not self.indecidido


@dataclass
class BatchResult:
    resultados: list[ProcessingResult] = field(default_factory=list)

    @property
    def sucessos(self) -> list[ProcessingResult]:
        return [r for r in self.resultados if r.sucesso]

    @property
    def falhas(self) -> list[ProcessingResult]:
        return [r for r in self.resultados if r.erro is not None]

    @property
    def pendentes(self) -> list[ProcessingResult]:
        """Detecção automática não decidiu. Arquivo NÃO foi renomeado."""
        return [r for r in self.resultados if r.indecidido]

    def salvar_log_erros(self, pasta: Path) -> Path | None:
        if not self.falhas and not self.pendentes:
            return None
        caminho = pasta / f"erros_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        with open(caminho, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f, delimiter=";")
            writer.writerow(["arquivo", "situacao", "detalhe"])
            for r in self.falhas:
                writer.writerow([r.caminho_original.name, "ERRO", r.erro])
            for r in self.pendentes:
                writer.writerow([r.caminho_original.name, "NAO_DECIDIDO", r.motivo])
        return caminho


class ProcessadorProcuracoes:
    """
    modelo: a classe do modelo, ou None para detecção automática.
    simular: True processa e devolve o nome que SERIA usado, sem renomear nada.
    """

    def __init__(self, modelo=None, simular: bool = False):
        self.modelo = modelo
        self.simular = simular

    @property
    def automatico(self) -> bool:
        return self.modelo is None

    def _escolher(self, pdf, texto):
        """
        Escolhe o modelo cruzando a pontuação do layout com o que cada
        candidato PRODUZ de fato.

        Duas regras que a nota sozinha não daria:
          1. um modelo que não consegue extrair o CPF é descartado, por mais
             alta que seja a nota — ele reconheceu o layout mas não sabe lê-lo;
          2. o desempate é pela SAÍDA, não pelo placar: dois modelos com notas
             próximas que geram o mesmo nome não são ambiguidade nenhuma.

        Devolve (nome_modelo, nota, motivo, novo_nome); nome_modelo None = não decidiu.
        """
        ranking = pontuar(texto)
        acima = [(n, v) for n, v in ranking if v >= NOTA_MINIMA]
        if not acima:
            melhor_nota = ranking[0][1] if ranking else 0
            return None, melhor_nota, f"nota {melhor_nota} abaixo do mínimo {NOTA_MINIMA}", None

        saidas: dict[str, str] = {}
        for nome, _ in acima[:MAX_CANDIDATOS]:
            try:
                saidas[nome] = MODELOS[nome](pdf).gerar_nome_arquivo()
            except Exception:
                pass

        bons = [
            (n, v) for n, v in acima[:MAX_CANDIDATOS]
            if n in saidas and not saidas[n].startswith("SEM_CPF")
        ]
        if not bons:
            topo = acima[0][0]
            return None, acima[0][1], (
                f"nenhum candidato extraiu o CPF (melhor: {topo} → {saidas.get(topo, 'erro')})"
            ), None

        melhor, nota = bons[0]
        for outro, v in bons[1:]:
            if nota - v < MARGEM_MINIMA and saidas[outro] != saidas[melhor]:
                return None, nota, (
                    f"empate: {melhor} {nota} → {saidas[melhor]}  x  "
                    f"{outro} {v} → {saidas[outro]}"
                ), None

        return melhor, nota, f"{melhor} {nota}", saidas[melhor]

    def processar_pdf(self, caminho: Path) -> ProcessingResult:
        try:
            with pdfplumber.open(caminho_longo(caminho)) as pdf:
                if self.automatico:
                    nome_modelo, nota, motivo, novo_nome = self._escolher(
                        pdf, texto_completo(pdf)
                    )
                    if nome_modelo is None:
                        # Sem confiança suficiente: não renomeia, vira pendência.
                        return ProcessingResult(
                            caminho, indecidido=True, nota=nota,
                            motivo=motivo, simulado=self.simular,
                        )
                else:
                    nome_modelo, nota, motivo = None, 0, ""
                    novo_nome = self.modelo(pdf).gerar_nome_arquivo()

            resultado = ProcessingResult(
                caminho, novo_nome=novo_nome, modelo_usado=nome_modelo,
                nota=nota, motivo=motivo, simulado=self.simular,
            )

            if self.simular:
                return resultado

            novo_caminho = caminho.with_name(novo_nome)

            # evita WinError 183 — se destino já existe, adiciona sufixo
            if novo_caminho.exists() and novo_caminho != caminho:
                stem = novo_caminho.stem
                sufixo = 1
                while novo_caminho.exists():
                    novo_caminho = caminho.with_name(f"{stem}_{sufixo}.pdf")
                    sufixo += 1

            caminho.rename(novo_caminho)
            resultado.novo_nome = novo_caminho.name
            return resultado

        except Exception as e:
            return ProcessingResult(caminho, erro=str(e), simulado=self.simular)

    def processar_pasta(self, pasta: Path, callback=None) -> BatchResult:
        arquivos = sorted(pasta.glob("*.pdf"))
        batch = BatchResult()

        for arquivo in arquivos:
            resultado = self.processar_pdf(arquivo)
            batch.resultados.append(resultado)
            if callback:
                callback(resultado)

        return batch
