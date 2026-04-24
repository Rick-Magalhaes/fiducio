import re
import unicodedata
from app.models.base_model import ProcuracaoBase
from app.utils.text_utils import texto_completo

# CPF via extract_text (quando o Docusign alinha com o label)
CPF_LINHA_RE = re.compile(r"^CPF:\s*([\d][.\d]*[\d][\/\-]?\d{2})", re.IGNORECASE)

# Cabeçalho romano: "(i)", "(ii)"...
CABECALHO_ROMANO_RE = re.compile(
    r"^\s*\(\s*(i{1,3}|iv|vi{0,3}|vii|viii|ix)\s*\)\s+\S",
    re.IGNORECASE,
)
ROMANO_MAP = {"i": 1, "ii": 2, "iii": 3, "iv": 4, "vi": 6, "vii": 7, "viii": 8, "ix": 9}

# Fontes do template base — NÃO são overlay Docusign
FONTES_TEMPLATE = re.compile(r"Verdana|MS.Gothic|Calibri|Arial-Bold", re.IGNORECASE)

# x0 ranges fixos das opções no template Itaú
OPCAO_X = {
    "A":  (145, 215),   # Aprovar  ≈ 165
    "R":  (250, 330),   # Rejeitar ≈ 272
    "AB": (355, 440),   # Abster-se ≈ 386
}

# Label "CPF:" no template — usado para localizar o valor via chars
CPF_LABEL_RE = re.compile(r"CPF", re.IGNORECASE)


def _romano_para_int(s: str) -> int:
    return ROMANO_MAP.get(s.lower().strip(), 0)


def _classificar_por_x0(x0: float) -> str | None:
    for sigla, (xmin, xmax) in OPCAO_X.items():
        if xmin <= x0 <= xmax:
            return sigla
    return None


def _extrair_cpf(pdf) -> str | None:
    """
    Tenta dois métodos:
    1. extract_text() linha "CPF: XXXXXXXXXXX" (Docusign alinhado)
    2. Chars numéricos próximos ao label "CPF:" (Docusign em overlay separado)
    """
    pagina = pdf.pages[0]
    texto = pagina.extract_text() or ""

    # Método 1: linha completa no texto extraído
    for linha in texto.splitlines():
        m = CPF_LINHA_RE.match(linha.strip())
        if m:
            return re.sub(r"[.\-\/\s]", "", m.group(1))

    # Método 2: achar o top do label "CPF:" nos chars e pegar dígitos próximos
    cpf_top = None
    for c in pagina.chars:
        if c["text"] == "C" and CPF_LABEL_RE.match(c["text"]):
            # Verificar se é de fato o label CPF
            pass

    # Mais robusto: achar todos os chars "C","P","F",":" na mesma linha
    chars_por_top: dict[int, list] = {}
    for c in pagina.chars:
        key = round(c["top"])
        chars_por_top.setdefault(key, []).append(c)

    for top_key in sorted(chars_por_top):
        ws = sorted(chars_por_top[top_key], key=lambda c: c["x0"])
        texto_linha = "".join(c["text"] for c in ws).strip()
        if re.match(r"^CPF\s*:", texto_linha, re.IGNORECASE):
            cpf_top = top_key
            break

    if cpf_top is None:
        return None

    # Pegar chars com dígitos/pontos/traços em top próximo (±30px)
    digitos = []
    for top_key, chars in chars_por_top.items():
        if abs(top_key - cpf_top) <= 30:
            for c in sorted(chars, key=lambda c: c["x0"]):
                if re.match(r"[\d.\-\/]", c["text"]):
                    digitos.append((c["x0"], c["top"], c["text"]))

    if not digitos:
        return None

    # Agrupar por linha (top), pegar a linha com mais dígitos
    linhas: dict[int, list] = {}
    for x0, top, txt in digitos:
        key = round(top)
        linhas.setdefault(key, []).append((x0, txt))

    melhor = max(linhas.values(), key=len)
    raw = "".join(t for _, t in sorted(melhor, key=lambda x: x[0]))
    digits = re.sub(r"[.\-\/\s]", "", raw)

    return digits if len(digits) == 11 else None


def _extrair_votos_overlay(pdf) -> dict[int, str]:
    """
    Detecta X do Docusign pelo critério: fonte NÃO é do template base
    (Verdana/MS-Gothic/Calibri) e texto é 'X' ou 'x'.
    """
    resultados: dict[int, str] = {}
    cabecalhos: list[tuple[float, int]] = []
    xs_overlay: list[tuple[float, float]] = []
    offset = 0.0

    for pagina in pdf.pages:
        altura = float(pagina.height or 842)

        words = pagina.extract_words(keep_blank_chars=True) or []
        grupos: dict[int, list] = {}
        for w in words:
            grupos.setdefault(round(w["top"]), []).append(w)

        for top_key in sorted(grupos):
            ws    = sorted(grupos[top_key], key=lambda w: w["x0"])
            linha = " ".join(w["text"] for w in ws).strip()
            m_rom = CABECALHO_ROMANO_RE.match(linha)
            if m_rom:
                num = _romano_para_int(m_rom.group(1))
                if num > 0:
                    cabecalhos.append((top_key + offset, num))

        for c in pagina.chars:
            if c["text"] not in ("X", "x"):
                continue
            fonte = c.get("fontname", "")
            # X de overlay: fonte NÃO é do template base
            if not FONTES_TEMPLATE.search(fonte):
                xs_overlay.append((c["top"] + offset, c["x0"]))

        offset += altura

    for x_top, x_x0 in xs_overlay:
        antes  = [(t, n) for t, n in cabecalhos if t <= x_top + 10]
        depois = [(t, n) for t, n in cabecalhos if t > x_top]

        if antes:
            _, num = max(antes, key=lambda tn: tn[0])
        elif depois:
            _, num_prox = min(depois, key=lambda tn: tn[0])
            num = num_prox - 1
            if num <= 0:
                num = 1
        else:
            num = 1

        if num in resultados:
            continue
        sigla = _classificar_por_x0(x_x0)
        if sigla:
            resultados[num] = sigla

    return resultados


class ProcuracaoItau(ProcuracaoBase):
    """
    Procuração Itaú Unibanco (Docusign) — Neoenergia e similares.

    - CPF: linha "CPF: XXXXXXXXXXX" ou overlay em LucidaConsole próximo ao label
    - Deliberações: cabeçalho romano (i), (ii)...
    - Checkboxes: ☐ Aprovar  ☐ Rejeitar  ☐ Abster-se
    - X: overlay Docusign (qualquer fonte não-Verdana/Calibri/MS-Gothic)
    - Classificação pelo x0: Aprovar ≈ 165 | Rejeitar ≈ 272 | Abster-se ≈ 386
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
        return _extrair_cpf(self.pdf)

    def extrair_votos(self) -> list[str]:
        votos = _extrair_votos_overlay(self.pdf)
        if not votos:
            return []
        max_delib = max(votos.keys())
        return [votos.get(i, "NV") for i in range(1, max_delib + 1)]

    def gerar_nome_arquivo(self) -> str:
        cpf   = self.extrair_cpf() or "SEM_CPF"
        votos = self.extrair_votos()
        votos_str = ", ".join(votos) if votos else "SEM_VOTO"
        return f"{cpf} - {votos_str}.pdf"