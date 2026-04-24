import re
import unicodedata
from app.models.base_model import ProcuracaoBase
from app.utils.text_utils import texto_completo


def norm(texto: str) -> str:
    return unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().lower().strip()


# CPF na tabela do cabeçalho: "CPF/CNPJ do Debenturista: 86935011949"
CPF_TABELA_RE = re.compile(
    r"CPF[/\\]?CNPJ\s+do\s+Debenturista[:\s]+(\d{11})",
    re.IGNORECASE,
)

# Deliberação: "1. Autorizar..." ou "2. Aprovar..."
DELIB_RE = re.compile(r"^\s*(\d+)\.\s+[A-ZÁÉÍÓÚ]", re.IGNORECASE)

# Voto inline: "[] Aprovar [X] Rejeitar [] Abster-se"
LINHA_VOTO_RE = re.compile(
    r"\[\s*[xX]\s*\]\s*(Aprovar|Rejeitar|Abster-se)",
    re.IGNORECASE,
)


def _classificar_voto_inline(texto: str) -> str | None:
    t = norm(texto)
    if "rejeitar" in t or "rejeita" in t:
        return "R"
    if "abster" in t or "abstem" in t:
        return "AB"
    if "aprovar" in t or "aprova" in t:
        return "A"
    return None


def _extrair_votos_alfm(linhas: list[str]) -> list[str]:
    resultados: dict[int, str] = {}
    delib_atual: int | None = None
    max_delib = 0

    for linha in linhas:
        if not linha.strip():
            continue

        # Detecta nova deliberação
        m_delib = DELIB_RE.match(linha)
        if m_delib:
            delib_atual = int(m_delib.group(1))
            max_delib = max(max_delib, delib_atual)
            continue

        # Linha de voto inline: "[] Aprovar [X] Rejeitar [] Abster-se"
        m_voto = LINHA_VOTO_RE.search(linha)
        if m_voto and delib_atual is not None and delib_atual not in resultados:
            sigla = _classificar_voto_inline(m_voto.group(1))
            if sigla:
                resultados[delib_atual] = sigla

    return [resultados.get(i, "NV") for i in range(1, max_delib + 1)]


class InstrucaoALFM(ProcuracaoBase):
    """
    Instrução de Voto a Distância no formato ALFM Easy Voting (BTG/Oncoclínicas).
    
    Diferenças do BTGVoto (instrução do agente fiduciário):
    - CPF na tabela do cabeçalho: "CPF/CNPJ do Debenturista: XXXXXXXXXXX"
    - Votos inline: "[] Aprovar [X] Rejeitar [] Abster-se"
    - Deliberações numeradas com "1.", "2." etc. (sem cabeçalho romano)
    - Sem bloco de conflito de interesse
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
        m = CPF_TABELA_RE.search(self.texto)
        if m:
            return m.group(1)
        return None

    def extrair_votos(self) -> list[str]:
        return _extrair_votos_alfm(self.linhas)

    def gerar_nome_arquivo(self) -> str:
        cpf   = self.extrair_cpf() or "SEM_CPF"
        votos = self.extrair_votos()
        votos_str = ", ".join(votos) if votos else "SEM_VOTO"
        return f"{cpf} - {votos_str}.pdf"