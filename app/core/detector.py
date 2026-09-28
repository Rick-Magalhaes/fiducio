"""
Deteccao automatica do modelo a partir do conteudo do PDF.

A pontuacao olha MARCAS ESTRUTURAIS do layout (rotulo do CPF, estilo do
cabecalho, formato da marcacao, frases caracteristicas) — nunca o resultado
dos votos. Um modelo que "acha" votos onde nao existem nao pode ganhar nota
por isso; foi exatamente assim que o modelo XP devolveu seis deliberacoes
inexistentes para um PDF da Raizen.

Cada assinatura tem:
  ancoras   — pelo menos UMA precisa casar, senao a nota e zero
  sinais    — somam pontos
  negativos — subtraem pontos (marcas de OUTRO layout parecido)

O vencedor so e aceito se passar de NOTA_MINIMA e abrir MARGEM_MINIMA sobre o
segundo colocado. Caso contrario o arquivo e marcado para revisao manual, que
e o comportamento seguro: melhor uma fila curta de excecoes do que um nome
plausivel e errado entrando na planilha.
"""

import re

from app.utils.text_utils import normalizar_marcadores

NOTA_MINIMA = 45
MARGEM_MINIMA = 15

M = re.MULTILINE | re.IGNORECASE


def _rx(p: str) -> re.Pattern:
    return re.compile(p, M)


# --- marcas reutilizadas ----------------------------------------------------

CAB_ROMANO = _rx(r"^\s*\(\s*(i{1,3}|iv|vi{0,3}|vii|viii|ix)\s*\)\s+\S")
CAB_NUMERO_PONTO = _rx(r"^\s*\d+\.\s+[A-ZÁÉÍÓÚ]")
CAB_NUMERO_PAREN = _rx(r"^\s*\d+\)\s+[A-ZÁÉÍÓÚ]")
CAB_LETRA = _rx(r"^\s*[a-z]\)\s+[A-ZÁÉÍÓÚ]")

MARCA_PAREN = _rx(r"\(\s*[xX]\s*\)\s*\S")
MARCA_COLCHETE = _rx(r"\[\s*[xX]?\s*\]\s*\S")


def _conta_distintos(padrao: re.Pattern, texto: str) -> int:
    return len({m.group(1).lower() for m in padrao.finditer(texto) if m.groups()})


def _delibs_xp(texto: str) -> int:
    """Quantas das 6 deliberacoes que o modelo XP espera aparecem no texto."""
    n = 0
    for num in range(1, 7):
        if (
            re.search(rf"\(\s*{num}\s*\)", texto)
            or re.search(rf"\({{2,}}\s*{num}\s*\){{2,}}", texto)
            or re.search(rf"^\s*{num}\.\s+(?:Quanto|Em\s+rela)", texto, M)
        ):
            n += 1
    return n


# --- assinaturas ------------------------------------------------------------
# A ordem nao importa; o que separa modelos parecidos sao os negativos.

ASSINATURAS: dict[str, dict] = {

    "XP": {
        "ancoras": [
            _rx(r"^\s*\(\s*[1-6]\s*\)\s+\S"),
            _rx(r"^\s*[1-6]\.\s+(?:Quanto|Em\s+rela)"),
        ],
        "sinais": [
            (_rx(r"^\s*[1-6]\.\s+(?:Quanto|Em\s+rela)"), 40),
            (lambda t: _delibs_xp(t) >= 4, 35),
            (lambda t: _delibs_xp(t) == 3, 15),
            (_rx(r"kinea|g5\s+partners|vinci|sob\b"), 15),
            (MARCA_PAREN, 10),
        ],
        "negativos": [
            (_rx(r"CPF[/\\]?CNPJ\s+do\s+Debenturista"), 30),
            (_rx(r"declara\s+a\s+inexist[êe]ncia"), 25),
            (_rx(r"^\s*CPF:\s*\d"), 30),
        ],
    },

    "BTG Instrução 1": {
        "ancoras": [
            _rx(r"inscrito\(a\)\s+no\s+CPF[/\\]?CNPJ\s+sob\s+o\s+n[°ºo]?\s*\d{11}"),
        ],
        "sinais": [
            (_rx(r"inscrito\(a\)\s+no\s+CPF[/\\]?CNPJ\s+sob\s+o\s+n[°ºo]?\s*\d{11}"), 35),
            (MARCA_PAREN, 20),
            (_rx(r"\(\s*[xX]?\s*\)\s*(n[ãa]o\s+)?declara\b"), 25),
            (CAB_ROMANO, 15),
            (CAB_NUMERO_PONTO, 10),
        ],
        "negativos": [
            # Opea usa o MESMO texto mas com colchetes no rotulo
            (_rx(r"inscrito\(a\)\s+no\s+\[CPF[/\\]?CNPJ\]"), 45),
            (_rx(r"declara\s+a\s+inexist[êe]ncia"), 35),
            (_rx(r"CPF[/\\]?CNPJ\s+do\s+Debenturista"), 25),
        ],
    },

    "BTG Instrução 2": {
        "ancoras": [
            _rx(r"CPF[/\\]?CNPJ\s+do\s+Debenturista[:\s]+\d{11}"),
            _rx(r"\[\s*[xX]\s*\]\s*(Aprovar|Rejeitar|Abster-se)"),
        ],
        "sinais": [
            (_rx(r"CPF[/\\]?CNPJ\s+do\s+Debenturista[:\s]+\d{11}"), 40),
            (_rx(r"\[\s*[xX]?\s*\]\s*Aprovar\s*\[\s*[xX]?\s*\]\s*Rejeitar"), 35),
            (_rx(r"\[\s*[xX]\s*\]\s*(Aprovar|Rejeitar|Abster-se)"), 20),
            (CAB_NUMERO_PONTO, 10),
        ],
        "negativos": [
            (_rx(r"declara\s+a\s+inexist[êe]ncia"), 20),
            (_rx(r"\[\s*[xX\s|]*\]\s*Sim\s*\[" ), 30),
        ],
    },

    "Opea": {
        "ancoras": [
            _rx(r"inscrito\(a\)\s+no\s+\[?CPF[/\\]?CNPJ\]?\s+sob\s+o\s+n[°ºo]?\s*\d{11}"),
            _rx(r"declara\s+a\s+inexist[êe]ncia"),
        ],
        "sinais": [
            (_rx(r"inscrito\(a\)\s+no\s+\[CPF[/\\]?CNPJ\]"), 40),
            (_rx(r"declara\s+a\s+inexist[êe]ncia"), 35),
            (_rx(r"\(\s*[xX]?\s*\)\s*(N[ÃA]O\s+)?APROVAR"), 20),
            (CAB_ROMANO, 15),
        ],
        "negativos": [
            (_rx(r"CPF[/\\]?CNPJ\s+do\s+Debenturista"), 30),
            (_rx(r"declara\s+que\s+inexiste"), 25),
        ],
    },

    "Instrução [X]": {
        "ancoras": [
            _rx(r"[\[(]\s*[xX]?\s*[\])]\s*(aprova|reprova|rejeit|abst|n[ãa]o\s+aprova)"),
        ],
        "sinais": [
            # tres opcoes seguidas, uma por linha = bloco de deliberacao
            (_rx(r"[\[(]\s*[xX]?\s*[\])]\s*(?:se\s+)?abst\w*"), 25),
            (_rx(r"[\[(]\s*[xX]?\s*[\])]\s*(aprova|reprova|rejeit)\w*"), 25),
            (CAB_NUMERO_PAREN, 20),
            (CAB_ROMANO, 10),
            (_rx(r"instru[çc][ãa]o\s+de\s+voto|voto\s+fechado"), 15),
        ],
        "negativos": [
            # layouts que tem dono proprio e tambem usam marcacao de voto
            (_rx(r"CPF[/\\]?CNPJ\s+do\s+Debenturista[:\s]+\d{11}"), 35),
            (_rx(r"declara\s+a\s+inexist[êe]ncia"), 35),
            (_rx(r"\(\s*[xX]?\s*\)\s*(n[ãa]o\s+)?declara\b"), 30),
            (_rx(r"\[\s*[xX\s|]*\]\s*Sim\s*\["), 30),
            (_rx(r"^\s*CPF:\s*\d"), 30),
            (lambda t: _delibs_xp(t) >= 4, 25),
        ],
    },

    "Santander": {
        "ancoras": [
            _rx(r"inscrito\s+no\s+CPF\s+sob\s+o\s+n[°º]?\s*\[?\d"),
            _rx(r"\[\s*[xX\s|]*\]\s*Sim\s*\[\s*[xX\s|]*\]\s*N[ãa]o"),
        ],
        "sinais": [
            (_rx(r"\[\s*[xX\s|]*\]\s*Sim\s*\[\s*[xX\s|]*\]\s*N[ãa]o"), 40),
            (_rx(r"inscrito\s+no\s+CPF\s+sob\s+o\s+n[°º]?\s*\[?\d"), 30),
            (_rx(r"declara\s+que\s+inexiste"), 25),
            (CAB_LETRA, 15),
        ],
        "negativos": [
            (_rx(r"CPF[/\\]?CNPJ\s+do\s+Debenturista"), 25),
            (_rx(r"declara\s+a\s+inexist[êe]ncia"), 20),
        ],
    },

    "Itaú": {
        "ancoras": [
            _rx(r"^\s*CPF:\s*\d"),
        ],
        "sinais": [
            (_rx(r"^\s*CPF:\s*\d"), 45),
            (CAB_ROMANO, 20),
            (_rx(r"aprovar|abster|rejeitar"), 10),
        ],
        "negativos": [
            (_rx(r"inscrito\(a\)\s+no\s+\[?CPF"), 25),
            (_rx(r"CPF[/\\]?CNPJ\s+do\s+Debenturista"), 25),
        ],
    },

    "Safra": {
        "ancoras": [
            _rx(r"Nome\s+do\s+Outorgante\s+CPF\s+n[°º]"),
        ],
        "sinais": [
            (_rx(r"Nome\s+do\s+Outorgante\s+CPF\s+n[°º]"), 55),
            (_rx(r"procura[çc][ãa]o|outorga|poderes"), 15),
        ],
        "negativos": [
            (MARCA_PAREN, 15),
            (_rx(r"\[\s*[xX]\s*\]"), 15),
        ],
    },
}


def _aplicar(regras, texto: str) -> int:
    total = 0
    for regra, peso in regras:
        casou = regra(texto) if callable(regra) else bool(regra.search(texto))
        if casou:
            total += peso
    return total


def pontuar(texto: str) -> list[tuple[str, int]]:
    """Nota de cada modelo para este texto, da maior para a menor."""
    # caixas Unicode viram [X]/[] antes de qualquer assinatura olhar o texto
    texto = normalizar_marcadores(texto)
    notas: list[tuple[str, int]] = []
    for nome, sig in ASSINATURAS.items():
        if not any(a.search(texto) for a in sig["ancoras"]):
            notas.append((nome, 0))
            continue
        nota = _aplicar(sig["sinais"], texto) - _aplicar(sig["negativos"], texto)
        notas.append((nome, max(0, nota)))
    return sorted(notas, key=lambda x: -x[1])


def detectar(texto: str) -> tuple[str | None, int, str]:
    """
    Devolve (nome_do_modelo, nota, motivo).
    nome_do_modelo e None quando nao da para decidir com seguranca.
    """
    notas = pontuar(texto)
    if not notas:
        return None, 0, "nenhum modelo avaliado"

    nome, nota = notas[0]
    segundo_nome, segunda = notas[1] if len(notas) > 1 else ("", 0)

    if nota < NOTA_MINIMA:
        return None, nota, f"nota {nota} abaixo do minimo {NOTA_MINIMA}"

    if nota - segunda < MARGEM_MINIMA:
        return None, nota, (
            f"empate: {nome} {nota} x {segundo_nome} {segunda} "
            f"(margem minima {MARGEM_MINIMA})"
        )

    return nome, nota, f"{nome} {nota}, segundo {segundo_nome} {segunda}"
