import re
import logging


def remover_underlines_docusign(texto: str) -> str:
    return re.sub(r"_", "", texto)


def formatar_cpf(cpf_raw: str) -> str | None:
    digits = re.sub(r"\D", "", cpf_raw)
    if len(digits) != 11:
        return None
    return digits  # só 11 dígitos, sem formatação


def extrair_cpf(texto: str) -> str | None:
    # sempre opera sobre texto sem underlines
    texto_limpo = remover_underlines_docusign(texto)

    LABEL_CPF_RE = re.compile(
        r"CPF[/\\]?CNPJ\b[^\n]{0,40}?(?:N[°oº]\.?\s*|sob\s+o\s+n[°oº]\.?\s*|:\s*)",
        re.IGNORECASE,
    )

    def cpf_valido(digits: str) -> bool:
        if len(digits) != 11 or len(set(digits)) == 1:
            return False
        soma = sum(int(digits[i]) * (10 - i) for i in range(9))
        r1 = (soma * 10 % 11) % 10
        if r1 != int(digits[9]):
            return False
        soma = sum(int(digits[i]) * (11 - i) for i in range(10))
        r2 = (soma * 10 % 11) % 10
        return r2 == int(digits[10])

    def buscar_no_trecho(trecho: str) -> str | None:
        # remove underlines do trecho também
        trecho = remover_underlines_docusign(trecho)
        for m in re.finditer(r"\d[\d\.\-\/\s]{8,13}\d", trecho[:150]):
            digits = re.sub(r"\D", "", m.group())
            if len(digits) == 11 and cpf_valido(digits):
                return formatar_cpf(digits)
        return None

    # 1ª tentativa: busca pelo label CPF/CNPJ (só no texto limpo)
    for m in LABEL_CPF_RE.finditer(texto_limpo):
        cpf = buscar_no_trecho(texto_limpo[m.end():])
        if cpf:
            return cpf

    logging.warning("Label CPF/CNPJ não encontrado; usando fallback.")

    # 2ª tentativa: fallback só no texto limpo (underlines já removidos)
    # formato com separadores
    for m in re.finditer(r"\d{3}[\/\.\s]?\d{3}[\/\.\s]?\d{3}[-\/\.\s]?\d{2}", texto_limpo):
        digits = re.sub(r"\D", "", m.group())
        if len(digits) == 11 and cpf_valido(digits):
            return formatar_cpf(digits)

    # 3ª tentativa: 11 dígitos colados (caso do docusign sem separadores)
    for m in re.finditer(r"\d{11}", texto_limpo):
        digits = m.group()
        if cpf_valido(digits):
            return formatar_cpf(digits)

    return None