# app/models/base.py  ← mover para cá
from abc import ABC, abstractmethod

class ProcuracaoBase(ABC):
    def __init__(self, pdf):
        self.pdf = pdf

    @abstractmethod
    def extrair_cpf(self) -> str | None: ...
    @abstractmethod
    def extrair_votos(self) -> list[str]: ...
    @abstractmethod
    def gerar_nome_arquivo(self) -> str: ...