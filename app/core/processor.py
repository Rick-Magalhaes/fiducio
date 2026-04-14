import pdfplumber
from pathlib import Path

class ProcessadorProcuracoes:

    def __init__(self, modelo):
        self.modelo = modelo

    def processar_pdf(self, caminho: Path):
        try:
            with pdfplumber.open(caminho) as pdf:
                proc = self.modelo(pdf)
                novo_nome = proc.gerar_nome_arquivo()

            novo_caminho = caminho.with_name(novo_nome)
            caminho.rename(novo_caminho)

            print(f"✓ {caminho.name} → {novo_nome}")

        except Exception as e:
            print(f"✗ {caminho.name} → {e}")