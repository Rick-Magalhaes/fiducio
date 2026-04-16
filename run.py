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

    total = len(arquivos)
    print(f"\nProcessando {total} arquivo(s)...\n")

    contador = [0]

    def on_resultado(resultado):
        contador[0] += 1
        status = "✓" if resultado.sucesso else "✗"
        saida = resultado.novo_nome or resultado.erro
        print(f"[{contador[0]}/{total}] {status} {resultado.caminho_original.name} → {saida}")

    processador = ProcessadorProcuracoes(ProcuracaoXP)
    batch = processador.processar_pasta(pasta, callback=on_resultado)

    print(f"\nFinalizado! {len(batch.sucessos)} processado(s), {len(batch.falhas)} erro(s).")

    if batch.falhas:
        print("\nArquivos que não foram renomeados:")
        for r in batch.falhas:
            print(f"   • {r.caminho_original.name}")
        log_path = batch.salvar_log_erros(pasta)
        print(f"\nLog de erros salvo em: {log_path}")