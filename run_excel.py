from pathlib import Path
from tkinter import Tk, filedialog

from app.services.excel_services import carregar_arquivos, preencher_excel


def selecionar_pasta(titulo: str) -> Path | None:
    root = Tk()
    root.withdraw()
    pasta = filedialog.askdirectory(title=titulo)
    root.destroy()
    return Path(pasta) if pasta else None


def selecionar_arquivo(titulo: str) -> Path | None:
    root = Tk()
    root.withdraw()
    arquivo = filedialog.askopenfilename(
        title=titulo,
        filetypes=[("Excel", "*.xlsx")]
    )
    root.destroy()
    return Path(arquivo) if arquivo else None


if __name__ == "__main__":
    pasta = selecionar_pasta("Selecione a pasta com as procurações renomeadas")
    if not pasta:
        print("Nenhuma pasta selecionada.")
        exit()

    excel = selecionar_arquivo("Selecione a planilha Excel")
    if not excel:
        print("Nenhum arquivo selecionado.")
        exit()

    print(f"\nCarregando arquivos de: {pasta}")
    mapa = carregar_arquivos(pasta)
    print(f"{len(mapa)} CPF(s) encontrado(s) nos arquivos.\n")

    print("Preenchendo planilha...")
    resultado = preencher_excel(excel, mapa)

    print(f"\n✓ Preenchidos:  {resultado.preenchidos}")
    print(f"  Já existiam:  {resultado.pulados}")

    if resultado.nao_encontrados:
        print(f"\n⚠  {len(resultado.nao_encontrados)} CPF(s) dos arquivos não encontrados na planilha:")
        for d in resultado.nao_encontrados:
            print(f"   • {d.cpf} — {d.arquivo.name}")
    else:
        print("\n✓ Todos os CPFs foram encontrados na planilha.")