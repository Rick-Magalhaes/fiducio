import re
from app.models.base_model import ProcuracaoBase
from app.utils.cpf_utils import extrair_cpf
from app.utils.text_utils import texto_completo
from app.models.xp.votos_utils import extrair_votos


class ProcuracaoXP(ProcuracaoBase):

    def __init__(self, pdf):
        super().__init__(pdf)
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
            self._votos = extrair_votos(self.pdf, texto=self.texto)
        return self._votos

    def gerar_nome_arquivo(self):
        cpf = self.extrair_cpf()
        votos = self.extrair_votos()
        votos_str = ", ".join(votos) if votos else "SEM_VOTO"

        if cpf:
            prefixo = cpf
        else:
            texto_limpo = re.sub(r"_", "", self.texto)
            tem_numero = re.search(
                r"CPF[/\\]?CNPJ\s+SOB\s+O\s+N[°oº]\.?\s*\d{6,}",
                texto_limpo,
                re.IGNORECASE,
            )
            prefixo = "CPF_INVALIDO" if tem_numero else "SEM_CPF"

        return f"{prefixo} - {votos_str}.pdf"