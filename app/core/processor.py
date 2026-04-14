import pdfplumber
from dataclasses import dataclass
from pathlib import Path

@dataclass
class ProcessingResult:
    caminho_original: Path
    novo_nome: str | None = None
    erro: str | None = None

    @property
    def sucesso(self) -> bool:
        return self.erro is None

class ProcessadorProcuracoes:

    def __init__(self, modelo):
        self.modelo = modelo

    def processar_pdf(self, caminho: Path) -> ProcessingResult:
        try:
            with pdfplumber.open(caminho) as pdf:
                proc = self.modelo(pdf)
                novo_nome = proc.gerar_nome_arquivo()

            novo_caminho = caminho.with_name(novo_nome)
            caminho.rename(novo_caminho)
            return ProcessingResult(caminho, novo_nome=novo_nome)

        except Exception as e:
            return ProcessingResult(caminho, erro=str(e))