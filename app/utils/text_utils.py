import re


def texto_completo(pdf) -> str:
    return "\n".join(page.extract_text() or "" for page in pdf.pages)


# ── marcadores de caixa de selecao ────────────────────────────────────────────
# Alguns PDFs (Docusign, Word) usam caixas Unicode no lugar de [ ] ou ( ).
# O X quase nunca fica DENTRO da caixa: o assinante digita ao lado, e a posicao
# varia conforme quem gerou o documento:
#     "☑ Aprovar"                        marcador proprio
#     "☐X Aprovar ☐ Rejeitar"            X depois da caixa, colado
#     "☐ X Aprovar ☐ Rejeitar"           X depois da caixa, com espaco
#     "X☐ Aprovar ☐ Rejeitar"            X ANTES da caixa
# Normalizar tudo para [X] / [] deixa um unico formato para os modelos lerem.

CAIXA_VAZIA_CHARS = "☐□▢❑⬜〼"
CAIXA_MARCADA_CHARS = "☑☒⬛"

_MARCADA = re.compile(f"[{CAIXA_MARCADA_CHARS}]")

# caixa seguida de um X solto. O \b impede casar "☐ Xerox".
_CAIXA_COM_X = re.compile(f"[{CAIXA_VAZIA_CHARS}]\\s*[xX]\\b")

# X solto seguido de caixa. O lookbehind impede casar o final de uma
# palavra ("MATRIX ☐ Aprovar" nao vira voto).
_X_COM_CAIXA = re.compile(f"(?<![0-9A-Za-zÀ-ÿ])[xX]\\s*[{CAIXA_VAZIA_CHARS}]")

_VAZIA = re.compile(f"[{CAIXA_VAZIA_CHARS}]")


def normalizar_marcadores(texto: str) -> str:
    """Converte caixas Unicode em [X] (marcada) ou [] (vazia)."""
    if not texto:
        return texto
    texto = _MARCADA.sub("[X]", texto)
    # os dois casos de X fora da caixa ANTES de zerar as caixas vazias
    texto = _CAIXA_COM_X.sub("[X]", texto)
    texto = _X_COM_CAIXA.sub("[X]", texto)
    texto = _VAZIA.sub("[]", texto)
    return texto


def tem_caixa_unicode(texto: str) -> bool:
    return bool(re.search(f"[{CAIXA_VAZIA_CHARS}{CAIXA_MARCADA_CHARS}]", texto or ""))
