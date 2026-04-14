import pdfplumber
from pathlib import Path

class ProcessadorProcuracoes:

    def __init__(self, modelo):
        self.modelo = modelo

    # app/core/processor.py  ← depois da mudança
def processar_pdf(self, caminho: Path) -> ProcessingResult:
    try:
        with pdfplumber.open(caminho) as pdf:
            proc = self.modelo(pdf)
            novo_nome = proc.gerar_nome_arquivo()
        caminho.rename(caminho.with_name(novo_nome))
        return ProcessingResult(caminho, novo_nome=novo_nome)
    except Exception as e:
        return ProcessingResult(caminho, erro=str(e))