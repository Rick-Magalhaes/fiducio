# app/utils/pdf_reader.py  ← preencher o arquivo vazio
def texto_completo(pdf) -> str:
    return "\n".join(p.extract_text() or "" for p in pdf.pages)