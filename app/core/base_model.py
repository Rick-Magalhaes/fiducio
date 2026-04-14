from abc import ABC, abstractmethod

class ProcuracaoBase(ABC):

    @abstractmethod
    def extrair_cpf(self):
        pass

    @abstractmethod
    def extrair_votos(self):
        pass

    @abstractmethod
    def gerar_nome_arquivo(self):
        pass