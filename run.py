from pathlib import Path
from app.core.processor import ProcessadorProcuracoes
from app.models.xp.xp_model import ProcuracaoXP

from tkinter import Tk, filedialog


def selecionar_pasta() -> Path | None:
    root = Tk()
    root.withdraw()
    pasta = filedialog.askdirectory(title="Selecione a pasta com as procurações")
    root.destroy()
    return Path(pasta) if pasta else None


if __name__ == "__main__":
    pasta = selecionar_pasta()

    if not pasta:
        print("Nenhuma pasta selecionada. Encerrando.")
        exit()

    arquivos = sorted(pasta.glob("*.pdf"))

    if not arquivos:
        print("Nenhum PDF encontrado na pasta selecionada.")
        exit()

    print(f"\nProcessando {len(arquivos)} arquivo(s)...\n")

    processador = ProcessadorProcuracoes(ProcuracaoXP)

    for arquivo in arquivos:
        processador.processar_pdf(arquivo)

    print("\nFinalizado!")