import re
import logging

def remover_underlines_docusign(texto: str) -> str:
    return re.sub(r"_", "", texto)

def formatar_cpf(cpf_raw: str) -> str | None:
    digits = re.sub(r"\D", "", cpf_raw)
    if len(digits) != 11:
        return None
    return digits  # sem pontos, sem traço — só 11 dígitos

def extrair_cpf(texto: str) -> str | None:
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
        for m in re.finditer(r"\d[\d\.\-\/\s]{8,13}\d", trecho[:150]):
            digits = re.sub(r"\D", "", m.group())
            if len(digits) == 11 and cpf_valido(digits):
                return formatar_cpf(digits)
        return None

    for t in [texto_limpo, texto]:
        for m in LABEL_CPF_RE.finditer(t):
            cpf = buscar_no_trecho(t[m.end():])
            if cpf:
                return cpf

    logging.warning("Label CPF/CNPJ não encontrado; usando fallback.")

    for t in [texto_limpo, texto]:
        # 1) formato com pontos/traços/barras
        for m in re.finditer(r"\d{3}[\/\.\s]?\d{3}[\/\.\s]?\d{3}[-\/\.\s]?\d{2}", t):
            digits = re.sub(r"\D", "", m.group())
            if len(digits) == 11 and cpf_valido(digits):
                return formatar_cpf(digits)

        # 2) 11 dígitos seguidos
        for m in re.finditer(r"\b\d{11}\b", t):
            digits = m.group()
            if cpf_valido(digits):
                return formatar_cpf(digits)

    return None