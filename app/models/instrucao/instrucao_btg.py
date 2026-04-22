import re
import unicodedata
from app.models.base_model import ProcuracaoBase
from app.utils.cpf_utils import extrair_cpf
from app.utils.text_utils import texto_completo


def norm(texto: str) -> str:
    return unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().lower().strip()


OPCAO_MARCADA_RE = re.compile(r"^\s*\(\s*[xX]\s*\)\s*(.*)")
OPCAO_VAZIA_RE   = re.compile(r"^\s*\(\s*\)\s*(.*)")

# cabeçalho romano — exige letra maiúscula após, evita casar "(x) da Escritura"
CABECALHO_ROMANO_RE = re.compile(
    r"^\s*\(\s*(i{1,3}|ii|iii|iv|vi{0,3}|vii|viii|ix)\s*\)\s+[A-ZÁÉÍÓÚ]",
    re.IGNORECASE,
)

CABECALHO_NUMERICO_RE = re.compile(
    r"^\s*(\d+)\.\s+[A-ZÁÉÍÓÚ]",
    re.IGNORECASE,
)

CPF_BLOCO_RE = re.compile(
    r"inscrito\(a\)\s+no\s+CPF[/\\]?CNPJ\s+sob\s+o\s+n[°oº]?\s*(\d{11})",
    re.IGNORECASE,
)

ROMANO_MAP = {
    "i": 1, "ii": 2, "iii": 3, "iv": 4,
    "vi": 6, "vii": 7, "viii": 8, "ix": 9,
}


def _romano_para_int(s: str) -> int:
    return ROMANO_MAP.get(s.lower().strip(), 0)


def _classificar_voto(texto: str) -> str | None:
    t = norm(texto)
    if "nao aprovar" in t or "nao aprova" in t or "reprova" in t or "rejeita" in t:
        return "R"
    if "abster" in t or "abstencao" in t or "abstem" in t:
        return "AB"
    if "aprovar" in t or "aprova" in t:
        return "A"
    return None


def _verificar_conflito(linhas: list[str]) -> bool:
    """
    True  → tem conflito (não pode votar)
    False → sem conflito (pode votar)
    """
    for linha in linhas:
        m = OPCAO_MARCADA_RE.match(linha)
        if not m:
            continue
        conteudo = norm(m.group(1))
        if conteudo == "declara":
            return False  # (X) DECLARA = sem conflito
        if "nao declara" in conteudo or "não declara" in conteudo:
            return True   # (X) NÃO DECLARA = conflito
    return True  # nenhum marcado = conflito


def _extrair_votos_instrucao(linhas: list[str]) -> list[str]:
    resultados: dict[int, str] = {}
    delib_atual: int | None = None
    max_delib = 0
    aguardando_conteudo = False

    for linha in linhas:
        if not linha:
            continue

        # cabeçalho romano
        m_rom = CABECALHO_ROMANO_RE.match(linha)
        if m_rom:
            num = _romano_para_int(m_rom.group(1))
            if num > 0:
                delib_atual = num
                max_delib = max(max_delib, num)
                aguardando_conteudo = False
                continue

        # cabeçalho numérico
        m_num = CABECALHO_NUMERICO_RE.match(linha)
        if m_num:
            num = int(m_num.group(1))
            delib_atual = num
            max_delib = max(max_delib, num)
            aguardando_conteudo = False
            continue

        if aguardando_conteudo and delib_atual is not None:
            aguardando_conteudo = False
            if delib_atual not in resultados:
                sigla = _classificar_voto(linha)
                if sigla:
                    resultados[delib_atual] = sigla
            continue

        m_opc = OPCAO_MARCADA_RE.match(linha)
        if m_opc and delib_atual is not None and delib_atual not in resultados:
            conteudo = m_opc.group(1).strip()
            cn = norm(conteudo)

            # ignora declaração de conflito
            if "declara" in cn:
                continue

            if conteudo:
                sigla = _classificar_voto(conteudo)
                if sigla:
                    resultados[delib_atual] = sigla
                else:
                    aguardando_conteudo = True
            else:
                aguardando_conteudo = True

    return [resultados.get(i, "NV") for i in range(1, max_delib + 1)]


def _dividir_blocos(texto: str) -> list[tuple[str, list[str]]]:
    """
    Divide o texto em blocos por investidor usando o CPF como separador.
    """
    blocos = []
    cpf_atual = None
    linhas_bloco: list[str] = []

    for linha in texto.splitlines():
        m_cpf = CPF_BLOCO_RE.search(linha)
        if m_cpf:
            if cpf_atual and linhas_bloco:
                blocos.append((cpf_atual, linhas_bloco))
            cpf_atual = m_cpf.group(1)
            linhas_bloco = [linha]
        elif cpf_atual is not None:
            linhas_bloco.append(linha.strip())

    if cpf_atual and linhas_bloco:
        blocos.append((cpf_atual, linhas_bloco))

    return blocos


class InstrucaoVoto(ProcuracaoBase):

    def __init__(self, pdf):
        super().__init__(pdf)
        self._texto = None
        self._blocos = None

    @property
    def texto(self):
        if self._texto is None:
            self._texto = texto_completo(self.pdf)
        return self._texto

    def _get_blocos(self) -> list[tuple[str, list[str]]]:
        if self._blocos is None:
            self._blocos = _dividir_blocos(self.texto)
        return self._blocos

    def extrair_cpf(self):
        blocos = self._get_blocos()
        if blocos:
            return blocos[0][0]
        return extrair_cpf(self.texto)

    def extrair_votos(self):
        blocos = self._get_blocos()
        if blocos:
            return _extrair_votos_instrucao(blocos[0][1])
        return []

    def gerar_nome_arquivo(self):
        blocos = self._get_blocos()

        if not blocos:
            cpf = extrair_cpf(self.texto) or "SEM_CPF"
            return f"{cpf} - SEM_VOTO.pdf"

        resultados = []
        for cpf, linhas in blocos:
            if _verificar_conflito(linhas):
                resultados.append(f"{cpf} - CONFLITO DE INTERESSE")
            else:
                votos = _extrair_votos_instrucao(linhas)
                votos_str = ", ".join(votos) if votos else "SEM_VOTO"
                resultados.append(f"{cpf} - {votos_str}")

        if len(resultados) == 1:
            return f"{resultados[0]}.pdf"
        else:
            primeiro = resultados[0]
            return f"{primeiro} (+{len(resultados)-1}).pdf"