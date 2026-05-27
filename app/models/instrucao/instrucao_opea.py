import re
import unicodedata
from app.models.base_model import ProcuracaoBase
from app.utils.text_utils import texto_completo


def norm(texto: str) -> str:
    return unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().lower().strip()


# CPF: "inscrito(a) no [CPF/CNPJ] sob o nº 00448378795"
CPF_RE = re.compile(
    r"inscrito\(a\)\s+no\s+\[?CPF[/\\]?CNPJ\]?\s+sob\s+o\s+n[°oº]?\s*(\d{11})",
    re.IGNORECASE,
)

# Cabeçalho romano — exige letra maiúscula após
CABECALHO_ROMANO_RE = re.compile(
    r"^\s*\(\s*(i{1,3}|iv|v|vi{0,3}|vii|viii|ix)\s*\)\s+[A-ZÁÉÍÓÚ]",
    re.IGNORECASE,
)

# Opção marcada: "(X) APROVAR" / "(X) NÃO APROVAR" / "(X) ABSTER-SE"
OPCAO_MARCADA_RE = re.compile(r"^\s*\(\s*[xX]\s*\)\s+(.*)")
OPCAO_VAZIA_RE   = re.compile(r"^\s*\(\s*\)\s+(.*)")

ROMANO_MAP = {
    "i": 1, "ii": 2, "iii": 3, "iv": 4, "v": 5,
    "vi": 6, "vii": 7, "viii": 8, "ix": 9,
}

# Conflito: "(X) DECLARA" = sem conflito | "(X) NÃO DECLARA" = conflito
DECLARA_RE = re.compile(
    r"declara\s+a\s+inexist[êe]ncia",
    re.IGNORECASE,
)


def _romano_para_int(s: str) -> int:
    return ROMANO_MAP.get(s.lower().strip(), 0)


def _classificar_voto(texto: str) -> str | None:
    t = norm(texto)
    if "nao aprovar" in t or "nao aprova" in t or "reprova" in t or "rejeita" in t:
        return "R"
    if "abster" in t or "abstencao" in t:
        return "AB"
    if "aprovar" in t or "aprova" in t:
        return "A"
    return None


def _extrair_votos(linhas: list[str]) -> list[str]:
    resultados: dict[int, str] = {}
    delib_atual: int | None = None
    max_delib = 0

    for linha in linhas:
        if not linha.strip():
            continue

        # Cabeçalho romano
        m_cab = CABECALHO_ROMANO_RE.match(linha)
        if m_cab:
            num = _romano_para_int(m_cab.group(1))
            if num > 0:
                delib_atual = num
                max_delib = max(max_delib, num)
            continue

        if delib_atual is None or delib_atual in resultados:
            continue

        # Opção marcada
        m_marc = OPCAO_MARCADA_RE.match(linha)
        if m_marc:
            conteudo = m_marc.group(1).strip()
            # Ignorar DECLARA (conflito de interesse)
            if "declara" in norm(conteudo):
                continue
            sigla = _classificar_voto(conteudo)
            if sigla:
                resultados[delib_atual] = sigla

    return [resultados.get(i, "NV") for i in range(1, max_delib + 1)]


def _verificar_conflito(texto: str) -> bool:
    """
    True  → tem conflito (não pode votar)
    False → sem conflito (pode votar)

    Lógica: após "declara a inexistência... conflito"
    (X) DECLARA     = confirma inexistência → sem conflito → False
    (X) NÃO DECLARA = tem conflito → True
    """
    m = DECLARA_RE.search(texto)
    if not m:
        return False

    trecho = texto[m.start():]

    for linha in trecho.splitlines():
        m_marc = OPCAO_MARCADA_RE.match(linha.strip())
        if not m_marc:
            continue
        conteudo = norm(m_marc.group(1))
        if "nao declara" in conteudo or "não declara" in conteudo:
            return True   # (X) NÃO DECLARA = conflito
        if conteudo == "declara":
            return False  # (X) DECLARA = sem conflito
    return False


class InstrucaoOpea(ProcuracaoBase):
    """
    Instrução de Voto à Distância — OPEA Securitizadora (ALFM Easy Voting / BTG).

    Características:
    - CPF: "inscrito(a) no [CPF/CNPJ] sob o nº XXXXXXXXXXX"
    - Deliberações: cabeçalho romano (i), (ii)... com texto longo
    - Votos: (X) APROVAR / () NÃO APROVAR / () ABSTER-SE
    - Conflito: (X) DECLARA = sem conflito | (X) NÃO DECLARA = CONFLITO DE INTERESSE
    - N deliberações dinâmicas (não fixo)
    """

    def __init__(self, pdf):
        super().__init__(pdf)
        self._texto = None
        self._linhas = None

    @property
    def texto(self):
        if self._texto is None:
            self._texto = texto_completo(self.pdf)
        return self._texto

    @property
    def linhas(self):
        if self._linhas is None:
            self._linhas = [l.strip() for l in self.texto.splitlines()]
        return self._linhas

    def extrair_cpf(self) -> str | None:
        m = CPF_RE.search(self.texto)
        return m.group(1) if m else None

    def extrair_votos(self) -> list[str]:
        return _extrair_votos(self.linhas)

    def gerar_nome_arquivo(self) -> str:
        cpf = self.extrair_cpf() or "SEM_CPF"

        if _verificar_conflito(self.texto):
            return f"{cpf} - CONFLITO DE INTERESSE.pdf"

        votos = self.extrair_votos()
        votos_str = ", ".join(votos) if votos else "SEM_VOTO"
        return f"{cpf} - {votos_str}.pdf"