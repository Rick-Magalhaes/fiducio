# =============================================================================
# EXTRAÇÃO DE TEXTO
# =============================================================================

def texto_completo(pdf) -> str:
    partes = []
    for page in pdf.pages:
        t = page.extract_text() or ""
        partes.append(t)
    return "\n".join(partes)