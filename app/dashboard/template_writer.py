"""
Gera um Template_Posição_Investidores.xlsx novo (do zero) a partir dos
dados da sessão de assembleia em memória.

Cada exportação cria um arquivo novo — nunca sobrescreve ou tenta
mesclar com um Template existente (decisão confirmada: cada assembleia
tem população e quantidades diferentes, então um arquivo novo por
exportação é mais seguro que tentar atualizar um antigo).

As fórmulas de % são escritas exatamente como no Template original
(mesma sintaxe, mesmas referências de célula) — o cálculo de
porcentagem continua sendo feito pelo Excel ao abrir o arquivo, não
pelo Python. Isso preserva o comportamento que o usuário já confia.
"""
from datetime import datetime
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font

from app.dashboard.b3_importer import BaseImportada


def _cabecalho_participantes(ws):
    cabecalhos = ["Gestor", "Razão Social", "CNPJ", "Conta", "Tipo conta",
                  "Quantidade", "%", "Presença \n(OK ou Fora)", "Representante",
                  "Voto 1", "Voto 2", "Voto 3"]
    for col, texto in enumerate(cabecalhos, start=1):
        c = ws.cell(row=1, column=col, value=texto)
        c.font = Font(bold=True)


def _cabecalho_comitentes(ws):
    cabecalhos = ["Agente Custodia", "Documento Participante", "Gestão",
                  "Nome comitente", "CPF/CNPJ Comitente", "Tipo Pessoa",
                  "Quantidade", "%", "Presença\n (OK ou FORA)", "Documentos",
                  "Representante", "Item1", "Item 2", "Item 3", "Item 4",
                  "Item 5", "Séries", "PU ", "Posição $", "Posição %"]
    for col, texto in enumerate(cabecalhos, start=1):
        c = ws.cell(row=1, column=col, value=texto)
        c.font = Font(bold=True)


def _escrever_participantes(ws, base: BaseImportada):
    _cabecalho_participantes(ws)
    for i, p in enumerate(base.participantes, start=2):
        ws.cell(row=i, column=2, value=p.razao_social)              # B Razão Social
        ws.cell(row=i, column=3, value=int(p.cnpj) if p.cnpj.isdigit() else p.cnpj)  # C CNPJ
        ws.cell(row=i, column=4, value=p.conta)                      # D Conta
        ws.cell(row=i, column=5, value=p.tipo_conta)                 # E Tipo conta
        ws.cell(row=i, column=6, value=p.quantidade)                 # F Quantidade
        ws.cell(row=i, column=7, value=(
            f'=IF(OR(MID(D{i},7,2)="10",MID(D{i},7,2)="20",MID(D{i},7,2)="68"),'
            f'SUMIF(COMITENTES!$C:$C,B{i},COMITENTES!$G:$G),'
            f'IF(H{i}="fora",0%,F{i}/QUÓRUM!$H$4))'
        ))  # G %
        ws.cell(row=i, column=8, value=(
            f'=IF(OR(MID(D{i},7,2)="10",MID(D{i},7,2)="20",MID(D{i},7,2)="68"),'
            f'"PREENCHER NA PRÓXIMA ABA","")'
        ))  # H Presença


def _escrever_comitentes(ws, base: BaseImportada):
    _cabecalho_comitentes(ws)
    for i, c in enumerate(base.comitentes, start=2):
        ws.cell(row=i, column=3, value=c.gestor or "")                # C Gestão
        ws.cell(row=i, column=4, value=c.nome)                        # D Nome comitente
        doc = c.documento
        ws.cell(row=i, column=5, value=int(doc) if doc.isdigit() else doc)  # E CPF/CNPJ
        ws.cell(row=i, column=6, value=c.tipo_pessoa)                  # F Tipo Pessoa
        ws.cell(row=i, column=7, value=c.quantidade)                   # G Quantidade
        ws.cell(row=i, column=8, value=f'=IF(I{i}="fora",0%,G{i}/QUÓRUM!$C$6)')  # H %
        if c.status:
            ws.cell(row=i, column=9, value=c.status.upper())           # I Presença
        ws.cell(row=i, column=17, value=c.serie)                       # Q Séries


def _escrever_quorum(ws):
    """
    Replica os três blocos paralelos da aba QUÓRUM do Template original:
    - B-E  (Quantidade Circulação): baseado só em COMITENTES
    - G-J  (Quantidade Presentes): combina PARTICIPANTES + COMITENTES —
      é este bloco que as fórmulas de PARTICIPANTES!G referenciam
      (QUÓRUM!$H$4), por isso precisa existir mesmo que a tela do
      sistema só mostre o quórum do bloco B-E.
    - L-O  (Saldo Devedor): baseado na posição em R$ (coluna S de
      COMITENTES) — fica com #DIV/0! se a posição em $ não for
      preenchida, igual ao comportamento original.
    """
    ws.cell(row=1, column=2, value="Quantidade Circulação")
    ws.cell(row=1, column=7, value="Quantidade Presentes")
    ws.cell(row=1, column=12, value="Saldo Devedor")

    # bloco B-E
    ws.cell(row=4, column=2, value="TOTAL")
    ws.cell(row=4, column=3, value="=SUM(COMITENTES!$G:$G)")
    ws.cell(row=5, column=2, value="FORA DE CIRCULAÇÃO")
    ws.cell(row=5, column=3, value='=SUMIF(COMITENTES!$I:$I,"FORA",COMITENTES!$G:$G)')
    ws.cell(row=5, column=4, value="=C5/C4")
    ws.cell(row=6, column=2, value="EM CIRCULAÇÃO")
    ws.cell(row=6, column=3, value="=C4-C5")
    ws.cell(row=7, column=2, value="QUÓRUM")
    ws.cell(row=7, column=3, value='=SUMIF(COMITENTES!$I:$I,"OK",COMITENTES!$G:$G)')
    ws.cell(row=7, column=4, value="=C7/C6")

    # bloco G-J — combina PARTICIPANTES + COMITENTES (referenciado por
    # PARTICIPANTES!G via QUÓRUM!$H$4)
    ws.cell(row=4, column=7, value="TOTAL")
    ws.cell(row=4, column=8, value="=SUM(COMITENTES!$G:$G)")
    ws.cell(row=5, column=7, value="FORA DE CIRCULAÇÃO")
    ws.cell(row=5, column=8, value=(
        '=SUMIF(PARTICIPANTES!$H:$H,"FORA",PARTICIPANTES!$F:$F)'
        '+SUMIF(COMITENTES!$I:$I,"FORA",COMITENTES!$G:$G)'
    ))
    ws.cell(row=5, column=9, value="=H5/H4")
    ws.cell(row=6, column=7, value="EM CIRCULAÇÃO")
    ws.cell(row=6, column=8, value="=H4-H5")
    ws.cell(row=7, column=7, value="QUÓRUM")
    ws.cell(row=7, column=8, value='=SUMIF(COMITENTES!$I:$I,"OK",COMITENTES!$G:$G)')

    # bloco L-O — posição em R$ (fica #DIV/0! se a coluna S não for
    # preenchida, igual ao Template original)
    ws.cell(row=4, column=12, value="TOTAL")
    ws.cell(row=4, column=13, value="=SUM(COMITENTES!S:S)")
    ws.cell(row=5, column=12, value="FORA DE CIRCULAÇÃO")
    ws.cell(row=5, column=13, value='=SUMIF(COMITENTES!$I:$I,"FORA",COMITENTES!$S:$S)')
    ws.cell(row=5, column=14, value="=M5/M4")
    ws.cell(row=6, column=12, value="EM CIRCULAÇÃO")
    ws.cell(row=6, column=13, value="=M4-M5")
    ws.cell(row=7, column=12, value="QUÓRUM")
    ws.cell(row=7, column=13, value='=SUMIF(COMITENTES!$I:$I,"OK",COMITENTES!$S:$S)')
    ws.cell(row=7, column=14, value="=M7/M4")

    for cel in ("B4", "B5", "B6", "B7", "G4", "G5", "G6", "G7", "L4", "L5", "L6", "L7"):
        ws[cel].font = Font(bold=True)


def gerar_template(base: BaseImportada, pasta_destino: Path) -> Path:
    """Gera um novo Template_Posição_Investidores.xlsx e retorna o caminho."""
    wb = Workbook()

    ws_part = wb.active
    ws_part.title = "PARTICIPANTES"
    _escrever_participantes(ws_part, base)

    ws_com = wb.create_sheet("COMITENTES")
    _escrever_comitentes(ws_com, base)

    ws_quorum = wb.create_sheet("QUÓRUM")
    _escrever_quorum(ws_quorum)

    pasta_destino = Path(pasta_destino)
    pasta_destino.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    caminho_saida = pasta_destino / f"Template_Posição_Investidores_{timestamp}.xlsx"

    wb.save(caminho_saida)
    return caminho_saida
