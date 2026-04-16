import csv
import pdfplumber
from dataclasses import dataclass, field
from pathlib import Path
from datetime import datetime


@dataclass
class ProcessingResult:
    caminho_original: Path
    novo_nome: str | None = None
    erro: str | None = None

    @property
    def sucesso(self) -> bool:
        return self.erro is None


@dataclass 
class BatchResult:
    resultados: list[ProcessingResult] = field(default_factory=list)

    @property
    def sucessos(self) -> list[ProcessingResult]:
        return [r for r in self.resultados if r.sucesso]

    @property
    def falhas(self) -> list[ProcessingResult]:
        return [r for r in self.resultados if not r.sucesso]

    def salvar_log_erros(self, pasta: Path) -> Path | None:
        if not self.falhas:
            return None
        caminho = pasta / f"erros_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        with open(caminho, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["arquivo", "erro"])
            for r in self.falhas:
                writer.writerow([r.caminho_original.name, r.erro])
        return caminho


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

    def processar_pasta(self, pasta: Path, callback=None) -> BatchResult:
        arquivos = sorted(pasta.glob("*.pdf"))
        batch = BatchResult()

        for arquivo in arquivos:
            resultado = self.processar_pdf(arquivo)
            batch.resultados.append(resultado)
            if callback:
                callback(resultado)

        return batch