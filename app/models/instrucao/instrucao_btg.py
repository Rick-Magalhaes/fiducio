import re
import unicodedata
from app.models.base_model import ProcuracaoBase
from app.utils.cpf_utils import extrair_cpf
from app.utils.text_utils import texto_completo


def norm(texto: str) -> str:
    return unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().lower().strip()


# =============================================================================
# REGEX
# =============================================================================

# cabeçalhos: (i), (ii), (iii)... ou 1., 2., 3....
CABECALHO_ROMANO_RE = re.compile(
    r"^\s*\(\s*(i{1,3}|iv|vi{0,3}|ix|x)\s*\)\s+\S",
    re.IGNORECASE,
)

CABECALHO_NUMERICO_RE = re.compile(
    r"^\s*(\d+)\.\s+\S",
    re.IGNORECASE,
)

# opção marcada: (X) ou (x)
OPCAO_MARCADA_RE = re.compile(
    r"^\s*\(\s*[xX]\s*\)\s*(.*)",
)

# opção vazia: ()
OPCAO_VAZIA_RE = re.compile(
    r"^\s*\(\s*\)\s*(.*)",
)

# mapa de algarismos romanos para inteiros
ROMANO_MAP = {
    "i": 1, "ii": 2, "iii": 3, "iv": 4, "v": 5,
    "vi": 6, "vii": 7, "viii": 8, "ix": 9, "x": 10,
}


def _romano_para_int(s: str) -> int:
    return ROMANO_MAP.get(s.lower().strip(), 0)


# =============================================================================
# DETECÇÃO DE CONFLITO
# =============================================================================

def _verificar_conflito(texto: str) -> bool | None:
    """
    Retorna:
      True  → DECLARA (sem conflito, pode votar)
      False → NÃO DECLARA ou nenhum marcado (conflito, não pode votar)
    """
    linhas = [l.strip() for l in texto.splitlines()]
    declara_presente = False
    nao_declara_presente = False

    for i, linha in enumerate(linhas):
        ln = norm(linha)

        # detecta bloco de declaração
        if "declara" in ln and "nao" not in ln and "não" not in ln:
            # verifica se tem (X) nessa linha ou na anterior/próxima
            if OPCAO_MARCADA_RE.match(linha):
                return True  # (X) DECLARA

        if ("nao declara" in ln or "não declara" in ln):
            if OPCAO_MARCADA_RE.match(linha):
                return False  # (X) NÃO DECLARA

        # padrão: linha com (X) seguida de DECLARA ou NÃO DECLARA
        m = OPCAO_MARCADA_RE.match(linha)
        if m:
            conteudo = norm(m.group(1))
            if conteudo == "declara":
                return True
            if "nao declara" in conteudo or "não declara" in conteudo:
                return False

        m = OPCAO_VAZIA_RE.match(linha)
        if m:
            conteudo = norm(m.group(1))
            if conteudo == "declara":
                declara_presente = True
            if "nao declara" in conteudo or "não declara" in conteudo:
                nao_declara_presente = True

    # nenhum marcado
    return None


# =============================================================================
# CLASSIFICAÇÃO DE VOTO
# =============================================================================

def _classificar_voto(texto: str) -> str | None:
    t = norm(texto)
    if "nao aprovar" in t or "nao aprova" in t or "reprova" in t or "rejeita" in t:
        return "R"
    if "abster" in t or "abstencao" in t or "abstem" in t:
        return "AB"
    if "aprovar" in t or "aprova" in t:
        return "A"
    return None


# =============================================================================
# EXTRAÇÃO DE VOTOS
# =============================================================================

def _extrair_votos_instrucao(texto: str) -> list[str]:
    linhas = [l.strip() for l in texto.splitlines()]
    resultados: dict[int, str] = {}
    delib_atual: int | None = None
    aguardando_conteudo = False
    max_delib = 0

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

        # linha aguardando conteúdo (X vazio na linha anterior)
        if aguardando_conteudo and delib_atual is not None:
            aguardando_conteudo = False
            if delib_atual not in resultados:
                sigla = _classificar_voto(linha)
                if sigla:
                    resultados[delib_atual] = sigla
            continue

        # opção marcada
        m_opc = OPCAO_MARCADA_RE.match(linha)
        if m_opc and delib_atual is not None and delib_atual not in resultados:
            conteudo = m_opc.group(1).strip()

            # ignora linhas de declaração de conflito
            cn = norm(conteudo)
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

    # monta lista dinâmica — só até max_delib
    return [resultados.get(i, "NV") for i in range(1, max_delib + 1)]


# =============================================================================
# MODEL
# =============================================================================

class InstrucaoVoto(ProcuracaoBase):

    def __init__(self, pdf):
        super().__init__(pdf)
        self._texto = None
        self._cpf = None
        self._votos = None
        self._conflito = None

    @property
    def texto(self):
        if self._texto is None:
            self._texto = texto_completo(self.pdf)
        return self._texto

    def extrair_cpf(self):
        if self._cpf is None:
            self._cpf = extrair_cpf(self.texto)
        return self._cpf

    def extrair_votos(self):
        if self._votos is None:
            self._votos = _extrair_votos_instrucao(self.texto)
        return self._votos

    def _tem_conflito(self) -> bool:
        """
        True  → tem conflito (NÃO DECLARA ou nenhum marcado)
        False → sem conflito (DECLARA)
        """
        if self._conflito is None:
            resultado = _verificar_conflito(self.texto)
            # True = declara = sem conflito
            # False ou None = conflito
            self._conflito = resultado is not True
        return self._conflito

    def gerar_nome_arquivo(self):
        cpf = self.extrair_cpf() or "SEM_CPF"

        if self._tem_conflito():
            return f"{cpf} - CONFLITO DE INTERESSE.pdf"

        votos = self.extrair_votos()
        votos_str = ", ".join(votos) if votos else "SEM_VOTO"
        return f"{cpf} - {votos_str}.pdf"