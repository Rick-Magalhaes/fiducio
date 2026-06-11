import re
import unicodedata
from app.models.base_model import ProcuracaoBase
from app.utils.text_utils import texto_completo


# Linha cabeçalho da tabela
HEADER_RE = re.compile(r"Nome\s+do\s+Outorgante\s+CPF\s+n[°º]", re.IGNORECASE)


def _extrair_cpf_safra(texto: str) -> str | None:
    """
    O CPF aparece na linha imediatamente após o header da tabela,
    junto com o nome. Ex: "S A N D RA BARONE 0 3 1 .1 4 9.088-37"
    Extrai removendo espaços internos e normalizando.
    """
    linhas = texto.splitlines()
    for i, linha in enumerate(linhas):
        if HEADER_RE.search(linha):
            # Próxima linha não vazia
            for j in range(i + 1, min(i + 4, len(linhas))):
                prox = linhas[j].strip()
                if not prox:
                    continue
                # Remover espaços internos de grupos de dígitos/pontos/traços
                # Ex: "0 3 1 .1 4 9.088-37" → "031.149.088-37"
                sem_espacos = re.sub(r"(?<=[\d.])\s+(?=[\d.\-])", "", prox)
                sem_espacos = re.sub(r"(?<=[\d\-])\s+(?=[\d])", "", sem_espacos)
                # Buscar CPF no formato xxx.xxx.xxx-xx ou xxxxxxxxx-xx ou 11 dígitos
                m = re.search(r"(\d{3}[\s\.]?\d{3}[\s\.]?\d{3}[\s\-]\d{2}|\d{11})", sem_espacos)
                if m:
                    digits = re.sub(r"\D", "", m.group(1))
                    if len(digits) == 11:
                        return digits
                break
    return None


class ProcuracaoSafra(ProcuracaoBase):
    """
    Procuração de gestão de carteira — Safra Asset (Raízen).

    Não possui campos de voto. Extrai apenas o CPF da tabela
    do cabeçalho ("Nome do Outorgante | CPF nº") e gera o nome
    no formato "CPF - SEM_VOTO.pdf".

    O CPF pode aparecer com espaços entre os dígitos no PDF
    (artefato de PDF gerado por DOM); o modelo normaliza.
    """

    def __init__(self, pdf):
        super().__init__(pdf)
        self._texto = None

    @property
    def texto(self):
        if self._texto is None:
            self._texto = texto_completo(self.pdf)
        return self._texto

    def extrair_cpf(self) -> str | None:
        return _extrair_cpf_safra(self.texto)

    def extrair_votos(self) -> list[str]:
        return []

    def gerar_nome_arquivo(self) -> str:
        cpf = self.extrair_cpf() or "SEM_CPF"
        return f"{cpf} - SEM_VOTO.pdf"