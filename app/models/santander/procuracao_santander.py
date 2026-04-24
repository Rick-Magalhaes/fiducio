import re
import unicodedata
from app.models.base_model import ProcuracaoBase
from app.utils.text_utils import texto_completo


def norm(texto: str) -> str:
    return unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().lower().strip()


CPF_RE = re.compile(
    r"inscrito\s+no\s+CPF\s+sob\s+o\s+n[°º]?\s*\[?([\d]{3}[\.\s]?[\d]{3}[\.\s]?[\d]{3}[-\.\s]?[\d]{2})\]?",
    re.IGNORECASE,
)

CABECALHO_LETRA_RE = re.compile(r"^\s*([a-z])\)\s+[A-ZÁÉÍÓÚ]", re.IGNORECASE)
OPCAO_MARCADA_RE   = re.compile(r"^\s*\[\s*[xX]\s*\]\s*(.*)")
OPCAO_VAZIA_RE     = re.compile(r"^\s*\[\s*[|\s]*\]\s*(.*)")

# "O Debenturista declara que inexiste..." — ancoragem do 2º Sim/Não
INEXISTE_RE = re.compile(r"declara\s+que\s+inexiste", re.IGNORECASE)

# Linha com Sim/Não: "[X] Sim [ ] Não" ou "[ ] Sim [X] Não"
SIM_NAO_RE = re.compile(
    r"\[\s*([xX\s|]*)\]\s*Sim\s*\[\s*([xX\s|]*)\]\s*N[ãa]o",
    re.IGNORECASE,
)

LETRA_MAP = {"a": 1, "b": 2, "c": 3, "d": 4, "e": 5, "f": 6}


def _tem_x(conteudo: str) -> bool:
    return bool(re.search(r"[xX]", conteudo))


def _classificar_opcao(texto: str) -> str | None:
    t = norm(texto)
    if "reprovar" in t or "rejeitar" in t:
        return "R"
    if "abster" in t:
        return "AB"
    if "aprovar" in t:
        return "A"
    return None


def _extrair_votos_santander(linhas: list[str]) -> list[str]:
    resultados: dict[int, str] = {}
    delib_atual: int | None = None
    max_delib = 0
    aguardando_conteudo = False

    for linha in linhas:
        if not linha.strip():
            continue

        m_cab = CABECALHO_LETRA_RE.match(linha)
        if m_cab:
            letra = m_cab.group(1).lower()
            delib_atual = LETRA_MAP.get(letra)
            if delib_atual:
                max_delib = max(max_delib, delib_atual)
            aguardando_conteudo = False
            continue

        if delib_atual is None:
            continue

        m_marc = OPCAO_MARCADA_RE.match(linha)
        if m_marc and delib_atual not in resultados:
            conteudo = m_marc.group(1).strip()
            if conteudo:
                sigla = _classificar_opcao(conteudo)
                if sigla:
                    resultados[delib_atual] = sigla
                else:
                    aguardando_conteudo = True
            else:
                aguardando_conteudo = True
            continue

        if aguardando_conteudo:
            aguardando_conteudo = False
            sigla = _classificar_opcao(linha)
            if sigla and delib_atual not in resultados:
                resultados[delib_atual] = sigla
            continue

    return [resultados.get(i, "NV") for i in range(1, max_delib + 1)]


def _verificar_conflito(texto: str) -> bool:
    """
    True  → tem conflito de interesse (não deve votar)
    False → sem conflito (pode votar)

    Lógica: após a frase "declara que inexiste qualquer hipótese... conflito",
    o campo é "[X] Sim [ ] Não".
    [X] Sim = confirma que inexiste conflito → pode votar → False
    [X] Não = nega que inexiste conflito    → tem conflito → True
    Se nenhum marcado → assume sem conflito → False
    """
    # Localizar o bloco após "declara que inexiste"
    m = INEXISTE_RE.search(texto)
    if not m:
        return False

    trecho = texto[m.start():]

    # Primeira ocorrência de Sim/Não nesse trecho
    m_sn = SIM_NAO_RE.search(trecho)
    if not m_sn:
        return False

    sim_marcado = _tem_x(m_sn.group(1))
    nao_marcado = _tem_x(m_sn.group(2))

    if nao_marcado and not sim_marcado:
        return True   # [X] Não = tem conflito
    return False      # [X] Sim ou nenhum = sem conflito


def _extrair_cpf(texto: str) -> str | None:
    m = CPF_RE.search(texto)
    if m:
        return re.sub(r"[.\-\s]", "", m.group(1))
    return None


class ProcuracaoSantander(ProcuracaoBase):
    """
    Procuração Santander (FEPWeb) — Neoenergia e similares.

    - CPF: "inscrito no CPF sob o nº [166.557.704-59]" (com ou sem colchetes)
    - Deliberações: cabeçalho a), b), c)...
    - Marcações: [X], [x], [X ], [ X ], [X ]
    - Conflito: campo "[X] Sim [ ] Não" após "declara que inexiste... conflito"
      [X] Sim = sem conflito | [X] Não = CONFLITO DE INTERESSE
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
        return _extrair_cpf(self.texto)

    def extrair_votos(self) -> list[str]:
        return _extrair_votos_santander(self.linhas)

    def gerar_nome_arquivo(self) -> str:
        cpf = self.extrair_cpf() or "SEM_CPF"

        if _verificar_conflito(self.texto):
            return f"{cpf} - CONFLITO DE INTERESSE.pdf"

        votos = self.extrair_votos()
        votos_str = ", ".join(votos) if votos else "SEM_VOTO"
        return f"{cpf} - {votos_str}.pdf"