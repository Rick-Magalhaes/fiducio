def texto_completo(pdf) -> str:
    return "\n".join(page.extract_text() or "" for page in pdf.pages)