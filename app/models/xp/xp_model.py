from app.models.base_model import ProcuracaoBase
from app.utils.cpf_utils import extrair_cpf
from app.models.xp.votos_utils import extrair_votos
from app.utils.text_utils import texto_completo

class ProcuracaoXP(ProcuracaoBase):

    def __init__(self, pdf):
        self.pdf = pdf
        self._texto = None
        self._cpf = None
        self._votos = None

    @property
    def texto(self):
        if self._texto is None:
            self._texto = texto_completo(self.pdf)
        return self._texto

    def extrair_cpf(self):
        if self._cpf is None:
            self._cpf = extrair_cpf(self.texto)
        return self._cpf

    def extrair_votos(self):
        if self._votos is None:
            self._votos = extrair_votos(self.pdf)
        return self._votos

    def gerar_nome_arquivo(self):
        cpf = self.extrair_cpf() or "SEM_CPF"
        votos = self.extrair_votos()

        votos_str = ", ".join(votos) if votos else "SEM_VOTO"
        return f"{cpf} - {votos_str}.pdf"