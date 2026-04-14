import flet as ft
from pathlib import Path

from app.core.processor import ProcessadorProcuracoes
from app.models.xp.xp_model import ProcuracaoXP


def main(page: ft.Page):
    page.title = "Renomeador de Procurações"
    page.window_width = 700
    page.window_height = 700

    pasta_selecionada = ft.Text("Nenhuma pasta selecionada")
    log_output = ft.Text("", selectable=True)

    # Dropdown de modelos (escala depois)
    modelo_dropdown = ft.Dropdown(
        label="Modelo de Procuração",
        options=[
            ft.dropdown.Option("XP"),
        ],
        value="XP",
        width=300,
    )

    # FilePicker
    def on_folder_selected(e: ft.FilePickerResultEvent):
        if e.path:
            pasta_selecionada.value = e.path
            page.update()

    file_picker = ft.FilePicker()
    file_picker.on_result = on_folder_selected

    page.overlay.append(file_picker)
    page.update()  # ← ESSENCIAL

    def selecionar_pasta(e):
        file_picker.get_directory_path()

    # Processamento
    def processar(e):
        if not pasta_selecionada.value or pasta_selecionada.value == "Nenhuma pasta selecionada":
            log_output.value = "Selecione uma pasta primeiro."
            page.update()
            return

        pasta = Path(pasta_selecionada.value)

        arquivos = list(pasta.glob("*.pdf"))
        if not arquivos:
            log_output.value = "Nenhum PDF encontrado."
            page.update()
            return

        # Escolha do modelo
        if modelo_dropdown.value == "XP":
            model_class = ProcuracaoXP
        else:
            log_output.value = "Modelo não suportado."
            page.update()
            return

        processador = ProcessadorProcuracoes(model_class)

        logs = []

        for arq in arquivos:
            try:
                processador.processar_pdf(arq)
                logs.append(f"✔ {arq.name}")
            except Exception as ex:
                logs.append(f"✗ {arq.name} → {str(ex)}")

        log_output.value = "\n".join(logs)
        page.update()

    # Layout
    page.add(
        ft.Column(
            [
                ft.Text("Renomeador de Procurações", size=10, weight="bold"),
                modelo_dropdown,
                ft.Row(
                    [
                        ft.ElevatedButton("Selecionar pasta", on_click=selecionar_pasta),
                        pasta_selecionada,
                    ]
                ),
                ft.ElevatedButton("Processar", on_click=processar),
                ft.Divider(),
                ft.Text("Log:"),
                log_output,
            ]
        )
    )


ft.app(target=main)