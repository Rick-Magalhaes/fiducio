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

    sucessos = 0
    falhas = 0

    for arquivo in arquivos:
        resultado = processador.processar_pdf(arquivo)
        if resultado.sucesso:
            print(f"✓ {resultado.caminho_original.name} → {resultado.novo_nome}")
            sucessos += 1
        else:
            print(f"✗ {resultado.caminho_original.name} → {resultado.erro}")
            falhas += 1

    print(f"\nFinalizado! {sucessos} processado(s), {falhas} erro(s).")