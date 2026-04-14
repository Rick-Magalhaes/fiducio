# app/core/result.py
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