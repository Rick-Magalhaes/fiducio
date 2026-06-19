"""
Leitura da aba QUÓRUM / COMITENTES para o painel ao vivo.

Não recalcula nada: lê os valores já calculados pelo Excel/LibreOffice
(data_only=True). O motor de cálculo continua sendo 100% as fórmulas
da planilha — este módulo só projeta esses números para o painel.
"""
from dataclasses import dataclass
from pathlib import Path
from openpyxl import load_workbook

ABA_QUORUM = "QUÓRUM"
ABA_COMITENTES = "COMITENTES"


@dataclass
class DadosQuorum:
    total: float
    fora_circulacao: float
    fora_circulacao_pct: float
    em_circulacao: float
    quorum_qtd: float
    quorum_pct: float
    presentes_pct_sobre_total: float


@dataclass
class Investidor:
    nome: str
    quantidade: float
    percentual: float
    status: str | None


def _num(valor) -> float:
    return valor if isinstance(valor, (int, float)) else 0


def ler_quorum(caminho_excel: Path) -> DadosQuorum:
    wb = load_workbook(caminho_excel, data_only=True)
    ws = wb[ABA_QUORUM]

    total = _num(ws["C4"].value)
    fora = _num(ws["C5"].value)
    quorum_qtd = _num(ws["C7"].value)

    return DadosQuorum(
        total=total,
        fora_circulacao=fora,
        fora_circulacao_pct=_num(ws["D5"].value),
        em_circulacao=_num(ws["C6"].value),
        quorum_qtd=quorum_qtd,
        quorum_pct=_num(ws["D7"].value),
        presentes_pct_sobre_total=(quorum_qtd / total) if total else 0,
    )


def ler_investidores(caminho_excel: Path) -> list[Investidor]:
    wb = load_workbook(caminho_excel, data_only=True)
    ws = wb[ABA_COMITENTES]

    investidores = []
    for row in ws.iter_rows(min_row=2, max_row=ws.max_row):
        nome = row[3].value  # coluna D
        if nome is None:
            continue
        status = row[8].value  # coluna I
        investidores.append(Investidor(
            nome=str(nome),
            quantidade=_num(row[6].value),   # coluna G
            percentual=_num(row[7].value),   # coluna H
            status=status.strip().upper() if isinstance(status, str) else None,
        ))
    return investidores
