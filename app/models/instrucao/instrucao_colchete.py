import re
import unicodedata
from app.models.base_model import ProcuracaoBase
from app.utils.text_utils import texto_completo


def norm(texto: str) -> str:
    return unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().lower().strip()


# Uma opcao de voto marcada com colchete OU parentese, seguida da palavra do voto:
#   "[] APROVAR"      "[X] ABSTER-SE"      (BRK / Pentagono)
#   "(X) aprova; ou"  "() se abstem."      (Raizen)
# O miolo do marcador so aceita x/X ou vazio, entao cabecalhos como "(I) Aprovar"
# ou citacoes como "(i) do caixa" nunca sao confundidos com voto.
OPCAO_RE = re.compile(
    r"[\[(]\s*([xX]?)\s*[\])]\s*"
    r"(n[aã]o\s+aprova\w*|reprova\w*|rejeit\w*|aprova\w*|(?:se\s+)?abst\w*|absten[cç]\w*)",
    re.IGNORECASE,
)

# Rotulos onde o CPF/CNPJ costuma aparecer
LABEL_DOC_RE = re.compile(
    r"CPF\s*[/\\]?\s*CNPJ(?:\s+do\s+Debenturista)?|inscrit[oa]\(?a?\)?\s+no\s+CPF",
    re.IGNORECASE,
)
DOC_RE = re.compile(r"(?<!\d)(\d{2,3}\.?\d{3}\.?\d{3}(?:/?\d{4})?-?\d{2})(?!\d)")


def _cpf_valido(d: str) -> bool:
    if len(d) != 11 or len(set(d)) == 1:
        return False
    for n in (9, 10):
        soma = sum(int(d[i]) * (n + 1 - i) for i in range(n))
        if (soma * 10 % 11) % 10 != int(d[n]):
            return False
    return True


def _cnpj_valido(d: str) -> bool:
    if len(d) != 14 or len(set(d)) == 1:
        return False
    pesos1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    pesos2 = [6] + pesos1
    for pesos, pos in ((pesos1, 12), (pesos2, 13)):
        r = sum(int(d[i]) * p for i, p in enumerate(pesos)) % 11
        if (0 if r < 2 else 11 - r) != int(d[pos]):
            return False
    return True


def _doc_valido(d: str) -> bool:
    return _cpf_valido(d) or _cnpj_valido(d)


def extrair_documento(texto: str) -> str | None:
    """CPF (11) ou CNPJ (14) do debenturista, procurando perto dos rotulos."""
    for m in LABEL_DOC_RE.finditer(texto):
        trecho = texto[m.end(): m.end() + 250]
        for d in DOC_RE.finditer(trecho):
            digits = re.sub(r"\D", "", d.group(1))
            if _doc_valido(digits):
                return digits
    for d in DOC_RE.finditer(texto):
        digits = re.sub(r"\D", "", d.group(1))
        if _doc_valido(digits):
            return digits
    return None


def _sigla(opcao: str) -> str:
    t = norm(opcao)
    if t.startswith(("nao aprova", "reprova", "rejeit")):
        return "R"
    if t.startswith(("abst", "se abst", "absten")):
        return "AB"
    return "A"


def extrair_votos_colchete(linhas: list[str]) -> list[str]:
    """
    Cada deliberacao e um BLOCO de opcoes consecutivas (uma por linha ou na mesma linha).
    Nao depende do cabecalho — que varia entre "(I)", "1.", "1)" e as vezes sai
    embaralhado no PDF, ex.: "(AIIp)rovar". A ordem dos blocos define a deliberacao.
    """
    votos: list[str] = []
    bloco_aberto = False
    voto_bloco: str | None = None
    marcadas_bloco = 0

    def fechar():
        nonlocal bloco_aberto, voto_bloco, marcadas_bloco
        if bloco_aberto:
            votos.append("INV" if marcadas_bloco > 1 else (voto_bloco or "NV"))
        bloco_aberto, voto_bloco, marcadas_bloco = False, None, 0

    for linha in linhas:
        opcoes = OPCAO_RE.findall(linha)
        if not opcoes:
            if linha.strip():
                fechar()
            continue

        if len(opcoes) >= 3:
            fechar()

        bloco_aberto = True
        for marca, opcao in opcoes:
            if marca:
                marcadas_bloco += 1
                voto_bloco = _sigla(opcao)

        if len(opcoes) >= 3:
            fechar()

    fechar()
    return votos


class InstrucaoColchete(ProcuracaoBase):
    """
    Instrucao de voto com opcoes marcadas em colchete ou parentese, uma por linha.

    BRK / Pentagono:        (I) Aprovar ...      Raizen:   1) Aprovar ...
                            [] APROVAR                     (X) aprova; ou
                            [] REJEITAR                    () reprova; ou
                            [X] ABSTER-SE                  () se abstem.

    Aceita CPF ou CNPJ (fundos). Nao usa o cabecalho da deliberacao.
    """

    def __init__(self, pdf):
        super().__init__(pdf)
        self._texto = None

    @property
    def texto(self):
        if self._texto is None:
            self._texto = texto_completo(self.pdf)
        return self._texto

    def extrair_cpf(self) -> str | None:
        return extrair_documento(self.texto)

    def extrair_votos(self) -> list[str]:
        return extrair_votos_colchete(self.texto.splitlines())

    def gerar_nome_arquivo(self) -> str:
        doc = self.extrair_cpf() or "SEM_CPF"
        votos = self.extrair_votos()
        votos_str = ", ".join(votos) if votos else "SEM_VOTO"
        return f"{doc} - {votos_str}.pdf"
