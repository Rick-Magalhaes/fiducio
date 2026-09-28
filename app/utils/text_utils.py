import re


def texto_completo(pdf) -> str:
    return "\n".join(page.extract_text() or "" for page in pdf.pages)


# ── marcadores de caixa de selecao ────────────────────────────────────────────
# Alguns PDFs (Docusign, Word) usam caixas Unicode no lugar de [ ] ou ( ),
# e o X costuma vir FORA da caixa:
#     "☐X Aprovar ☐ Rejeitar ☐ Abster-se"
#     "☐ X Aprovar"
#     "☑ Aprovar"
# Normalizar para [X] / [] deixa um unico formato para os modelos lerem.

CAIXA_VAZIA_CHARS = "☐□▢❑⬜〼"
CAIXA_MARCADA_CHARS = "☑☒⬛"

_MARCADA = re.compile(f"[{CAIXA_MARCADA_CHARS}]")
# caixa seguida de um X solto = marcada. O \b impede casar "☐ Xerox".
_CAIXA_COM_X = re.compile(f"[{CAIXA_VAZIA_CHARS}]\\s*[xX]\\b")
_VAZIA = re.compile(f"[{CAIXA_VAZIA_CHARS}]")


def normalizar_marcadores(texto: str) -> str:
    """Converte caixas Unicode em [X] (marcada) ou [] (vazia)."""
    if not texto:
        return texto
    texto = _MARCADA.sub("[X]", texto)
    texto = _CAIXA_COM_X.sub("[X]", texto)
    texto = _VAZIA.sub("[]", texto)
    return texto


def tem_caixa_unicode(texto: str) -> bool:
    return bool(re.search(f"[{CAIXA_VAZIA_CHARS}{CAIXA_MARCADA_CHARS}]", texto or ""))
