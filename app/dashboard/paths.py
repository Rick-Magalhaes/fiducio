"""
Resolve caminhos de recursos (templates, static, assets) de um jeito
que funciona tanto rodando com `python run_ui.py` quanto dentro de um
.exe gerado pelo PyInstaller.

Por quê isso é necessário: o PyInstaller extrai os arquivos listados em
`datas` (no .spec) para uma pasta temporária em tempo de execução
(sys._MEIPASS), não para o caminho original do .py no disco. Usar
Path(__file__).parent funciona em desenvolvimento mas resolve para o
lugar errado dentro do executável empacotado.
"""
import sys
from pathlib import Path


def caminho_recurso(*partes: str) -> Path:
    """
    Resolve um caminho dentro de app/dashboard/, relativo à raiz do
    projeto (dev) ou à pasta temporária do PyInstaller (.exe).

    Uso: caminho_recurso("templates") -> .../app/dashboard/templates
         caminho_recurso("assets", "Template_Posição_Investidores_modelo.xlsx")
    """
    base_meipass = getattr(sys, "_MEIPASS", None)
    if base_meipass:
        # dentro do .exe: os datas foram extraídos preservando a
        # estrutura "app/dashboard/..." declarada no .spec
        base = Path(base_meipass) / "app" / "dashboard"
    else:
        # em desenvolvimento: este arquivo já está em app/dashboard/
        base = Path(__file__).parent

    return base.joinpath(*partes)
