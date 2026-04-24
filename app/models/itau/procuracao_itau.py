import re
import unicodedata
from app.models.base_model import ProcuracaoBase
from app.utils.text_utils import texto_completo

CPF_LINHA_RE = re.compile(r"^CPF:\s*([\d][.\d]*[\d][\/\-]?\d{2})", re.IGNORECASE)

# Cabeçalho "(ii)" ou "(iii)" etc. — usado como separador entre blocos de voto
CABECALHO_ROMANO_RE = re.compile(
    r"^\s*\(\s*(i{1,3}|iv|vi{0,3}|vii|viii|ix)\s*\)\s+\S",
    re.IGNORECASE,
)
ROMANO_MAP = {"i": 1, "ii": 2, "iii": 3, "iv": 4, "vi": 6, "vii": 7, "viii": 8, "ix": 9}

DOCUSIGN_X_RE = re.compile(r"ArialMT", re.IGNORECASE)

# x0 ranges das opções (fixas no template Itaú)
OPCAO_X = {
    "A":  (145, 215),   # Aprovar  ≈ 165
    "R":  (250, 330),   # Rejeitar ≈ 272
    "AB": (355, 440),   # Abster-se ≈ 386
}


def _romano_para_int(s: str) -> int:
    return ROMANO_MAP.get(s.lower().strip(), 0)


def _classificar_por_x0(x0: float) -> str | None:
    for sigla, (xmin, xmax) in OPCAO_X.items():
        if xmin <= x0 <= xmax:
            return sigla
    return None


def _extrair_cpf(texto: str) -> str | None:
    for linha in texto.splitlines():
        m = CPF_LINHA_RE.match(linha.strip())
        if m:
            return re.sub(r"[.\-\/\s]", "", m.group(1))
    return None


def _extrair_votos_overlay(pdf) -> dict[int, str]:
    """
    Estratégia para o template Itaú:
    - Os checkboxes do item (i) ficam na página onde o texto da deliberação (i) termina
    - O cabeçalho "(ii)" aparece logo abaixo, na mesma página dos checkboxes do item (i)
    - Então: X acima do top do "(ii)" → item 1; X abaixo → item 2; etc.
    
    Para cada página:
    1. Coletar tops dos cabeçalhos romanos visíveis
    2. Coletar X overlays com seus x0 e top
    3. Para cada X, determinar a deliberação pelo intervalo de tops entre cabeçalhos
       (ou antes do primeiro cabeçalho visível = deliberação anterior)
    """
    resultados: dict[int, str] = {}
    # Acumular cabeçalhos e Xs ao longo do documento (com offset de página)
    cabecalhos: list[tuple[float, int]] = []  # (top_absoluto, num)
    xs_overlay: list[tuple[float, float]] = []  # (top_abs, x0)
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
            if (c["text"] in ("X", "x")
                    and DOCUSIGN_X_RE.search(c.get("fontname", ""))):
                xs_overlay.append((c["top"] + offset, c["x0"]))

        offset += altura

    if not cabecalhos:
        return resultados

    # Ordenar cabeçalhos por top
    cabecalhos.sort(key=lambda t: t[0])

    # Inferir o número da deliberação a que pertence cada X:
    # O bloco de checkboxes de deliberação N fica ANTES do cabeçalho N+1
    # e DEPOIS do cabeçalho N (ou antes do primeiro cabeçalho = delib 1)
    #
    # Exemplo com 2 delibsí:
    #   top=700 → cabeçalho (i)   [pág 1]
    #   top=950 → X do item (i)   [pág 2, top_abs = 842+108]
    #   top=1005→ cabeçalho (ii)  [pág 2, top_abs = 842+163]
    #   top=1077→ X do item (ii)  [pág 2, top_abs = 842+235]

    for x_top, x_x0 in xs_overlay:
        # Encontrar o cabeçalho imediatamente APÓS este X
        # Se X está entre cab[N] e cab[N+1], pertence à delib N
        # Se X está antes do primeiro cabeçalho, pertence à delib 1 (improvável)
        # Se X está após o último cabeçalho, pertence ao último cabeçalho

        delib_num = None

        # Achar qual cabeçalho vem logo depois do X
        cabecalhos_depois = [(t, n) for t, n in cabecalhos if t > x_top]
        cabecalhos_antes  = [(t, n) for t, n in cabecalhos if t <= x_top]

        if cabecalhos_antes:
            # A deliberação mais recente antes do X
            _, delib_num = max(cabecalhos_antes, key=lambda tn: tn[0])
        elif cabecalhos_depois:
            # X está antes de todos os cabeçalhos — assume delib 1
            delib_num = 1
        
        if delib_num is None or delib_num in resultados:
            continue

        sigla = _classificar_por_x0(x_x0)
        if sigla:
            resultados[delib_num] = sigla

    return resultados


class ProcuracaoItau(ProcuracaoBase):
    """
    Procuração Itaú Unibanco (Docusign) — Neoenergia e similares.

    - CPF: linha "CPF: XXXXXXXXXXX"
    - Deliberações: cabeçalho romano (i), (ii)...
    - Checkboxes: ☐ Aprovar  ☐ Rejeitar  ☐ Abster-se
    - X: overlay Docusign (ArialMT), classificado pelo x0:
        Aprovar ≈ 165 | Rejeitar ≈ 272 | Abster-se ≈ 386
    - Delimitação: cada X pertence ao cabeçalho romano mais recente antes dele
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
        return _extrair_cpf(self.texto)

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