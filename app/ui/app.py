import threading
from pathlib import Path

import customtkinter as ctk

from app.core.processor import ProcessadorProcuracoes
from app.models.xp.xp_model import ProcuracaoXP
from app.services.excel_services import carregar_arquivos, preencher_excel

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

ACCENT  = "#4f8ef7"
SUCCESS = "#3ecf8e"
ERROR   = "#f56565"
WARNING = "#f6ad55"
MUTED   = "#64748b"
BG      = "#0f1117"
SURFACE = "#1a1d27"
BORDER  = "#2a2d3a"
TEXT    = "#e2e8f0"


class FiducioApp(ctk.CTk):

    def __init__(self):
        super().__init__()
        self.title("Fiducio")
        self.geometry("800x700")
        self.resizable(False, False)
        self.configure(fg_color=BG)

        self.pasta_pdf_path: Path | None = None
        self.pasta_excel_path: Path | None = None
        self.excel_path: Path | None = None

        self._build()

    def _build(self):
        outer = ctk.CTkFrame(self, fg_color=BG)
        outer.pack(fill="both", expand=True, padx=28, pady=28)

        # cabeçalho
        ctk.CTkLabel(
            outer, text="Fiducio",
            font=ctk.CTkFont(size=26, weight="bold"),
            text_color=TEXT,
        ).pack(anchor="w")
        ctk.CTkLabel(
            outer, text="Auxiliar de Assembleias",
            font=ctk.CTkFont(size=13),
            text_color=MUTED,
        ).pack(anchor="w", pady=(0, 20))

        # ── seção renomear ────────────────────────────────────────────────────
        self._section_label(outer, "RENOMEAR PDFs")

        self._label(outer, "PASTA COM OS PDFs")
        row1 = ctk.CTkFrame(outer, fg_color="transparent")
        row1.pack(fill="x", pady=(4, 0))

        self.field_pasta_pdf = self._path_field(row1)
        self.field_pasta_pdf.pack(side="left", fill="x", expand=True)
        self._browse_btn(row1, "Selecionar", self._pick_pasta_pdf).pack(
            side="left", padx=(8, 0)
        )

        ctk.CTkButton(
            outer,
            text="Renomear PDFs",
            fg_color=SURFACE,
            hover_color="#3a7be0",
            text_color="#ffffff",
            font=ctk.CTkFont(size=13, weight="bold"),
            height=40,
            command=lambda: threading.Thread(
                target=self._processar_pdfs, daemon=True
            ).start(),
        ).pack(anchor="e", pady=(12, 0))

        self._divider(outer)

        # ── seção excel ───────────────────────────────────────────────────────
        self._section_label(outer, "PREENCHER EXCEL")

        self._label(outer, "PASTA COM OS PDFs RENOMEADOS")
        row2 = ctk.CTkFrame(outer, fg_color="transparent")
        row2.pack(fill="x", pady=(4, 0))

        self.field_pasta_excel = self._path_field(row2)
        self.field_pasta_excel.pack(side="left", fill="x", expand=True)
        self._browse_btn(row2, "Selecionar", self._pick_pasta_excel).pack(
            side="left", padx=(8, 0)
        )

        self._label(outer, "PLANILHA EXCEL", pady=(10, 0))
        row3 = ctk.CTkFrame(outer, fg_color="transparent")
        row3.pack(fill="x", pady=(4, 0))

        self.field_excel = self._path_field(row3)
        self.field_excel.pack(side="left", fill="x", expand=True)
        self._browse_btn(row3, "Selecionar", self._pick_excel).pack(
            side="left", padx=(8, 0)
        )

        self.btn_excel = ctk.CTkButton(
            outer,
            text="Preencher Excel",
            fg_color=SURFACE,
            hover_color="#243b2f",
            text_color=SUCCESS,
            border_color=SUCCESS,
            border_width=1,
            font=ctk.CTkFont(size=13, weight="bold"),
            height=40,
            command=lambda: threading.Thread(
                target=self._processar_excel, daemon=True
            ).start(),
        )
        self.btn_excel.pack(anchor="e", pady=(12, 0))

        self._divider(outer)

        # ── log ───────────────────────────────────────────────────────────────
        self._section_label(outer, "LOG")

        self.log_box = ctk.CTkTextbox(
            outer,
            height=200,
            fg_color=BG,
            border_color=BORDER,
            border_width=1,
            font=ctk.CTkFont(family="Courier", size=11),
            text_color=TEXT,
            wrap="none",
            state="disabled",
        )
        self.log_box.pack(fill="x", pady=(4, 0))

        footer = ctk.CTkFrame(outer, fg_color="transparent")
        footer.pack(fill="x", pady=(6, 0))
        footer.columnconfigure(0, weight=1)
        footer.columnconfigure(1, weight=0)

        self.resumo_label = ctk.CTkLabel(
            footer, text="", font=ctk.CTkFont(size=40), text_color=MUTED,
            anchor="w",
        )
        self.resumo_label.grid(row=0, column=0, sticky="w")

        ctk.CTkButton(
            footer,
            text="Limpar log",
            fg_color="transparent",
            hover_color=SURFACE,
            text_color=MUTED,
            font=ctk.CTkFont(size=12),
            height=28,
            width=80,
            command=self._log_clear,
        ).grid(row=0, column=1, sticky="e")

    # ── widgets helpers ───────────────────────────────────────────────────────

    def _section_label(self, parent, text):
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(fill="x", pady=(0, 8))
        ctk.CTkFrame(frame, fg_color=BORDER, height=1).pack(
            side="left", fill="x", expand=True, pady=(8, 0)
        )
        ctk.CTkLabel(
            frame, text=f"  {text}  ",
            font=ctk.CTkFont(size=10),
            text_color=MUTED,
        ).pack(side="left")
        ctk.CTkFrame(frame, fg_color=BORDER, height=1).pack(
            side="left", fill="x", expand=True, pady=(8, 0)
        )

    def _label(self, parent, text, pady=(0, 0)):
        ctk.CTkLabel(
            parent, text=text,
            font=ctk.CTkFont(size=11),
            text_color=MUTED,
        ).pack(anchor="w", pady=pady)

    def _path_field(self, parent):
        return ctk.CTkEntry(
            parent,
            placeholder_text="Nenhum selecionado",
            fg_color=BG,
            border_color=BORDER,
            text_color=TEXT,
            placeholder_text_color=MUTED,
            font=ctk.CTkFont(family="Courier", size=11),
            height=36,
            state="readonly",
        )

    def _browse_btn(self, parent, text, command):
        return ctk.CTkButton(
            parent,
            text=text,
            fg_color=SURFACE,
            hover_color="#252837",
            text_color=TEXT,
            border_color=BORDER,
            border_width=1,
            font=ctk.CTkFont(size=12),
            height=36,
            width=100,
            command=command,
        )

    def _divider(self, parent):
        ctk.CTkFrame(parent, fg_color=BORDER, height=1).pack(
            fill="x", pady=20
        )

    # ── file pickers ──────────────────────────────────────────────────────────

    def _pick_pasta_pdf(self):
        path = ctk.filedialog.askdirectory(title="Selecione a pasta com os PDFs")
        if path:
            self.pasta_pdf_path = Path(path)
            self._set_field(self.field_pasta_pdf, path)

    def _pick_pasta_excel(self):
        path = ctk.filedialog.askdirectory(
            title="Selecione a pasta com os PDFs renomeados"
        )
        if path:
            self.pasta_excel_path = Path(path)
            self._set_field(self.field_pasta_excel, path)

    def _pick_excel(self):
        path = ctk.filedialog.askopenfilename(
            title="Selecione a planilha Excel",
            filetypes=[("Excel", "*.xlsx")],
        )
        if path:
            self.excel_path = Path(path)
            self._set_field(self.field_excel, path)

    def _set_field(self, field, value):
        field.configure(state="normal")
        field.delete(0, "end")
        field.insert(0, value)
        field.configure(state="readonly")

    # ── log ───────────────────────────────────────────────────────────────────

    def _log_add(self, msg: str, color: str = TEXT):
        self.log_box.configure(state="normal")
        self.log_box.insert("end", msg + "\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def _log_clear(self):
        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.configure(state="disabled")
        self.resumo_label.configure(text="")

    # ── processamento ─────────────────────────────────────────────────────────

    def _processar_pdfs(self):
        if not self.pasta_pdf_path:
            self._log_add("⚠  Selecione a pasta com os PDFs.")
            return

        self._log_clear()

        pasta = self.pasta_pdf_path
        arquivos = sorted(pasta.glob("*.pdf"))

        if not arquivos:
            self._log_add("⚠  Nenhum PDF encontrado na pasta.")
            return

        total = len(arquivos)
        self._log_add(f"Processando {total} arquivo(s)...")

        contador = [0]
        sucessos = [0]
        falhas   = [0]

        def on_resultado(r):
            contador[0] += 1
            if r.sucesso:
                sucessos[0] += 1
                self._log_add(
                    f"[{contador[0]}/{total}] ✓  {r.caminho_original.name}  →  {r.novo_nome}"
                )
            else:
                falhas[0] += 1
                self._log_add(
                    f"[{contador[0]}/{total}] ✗  {r.caminho_original.name}  →  {r.erro}"
                )

        processador = ProcessadorProcuracoes(ProcuracaoXP)
        batch = processador.processar_pasta(pasta, callback=on_resultado)

        self.resumo_label.configure(
            text=f"Finalizado — {sucessos[0]} renomeado(s)  |  {falhas[0]} erro(s)"
        )

        if batch.falhas:
            log_path = batch.salvar_log_erros(pasta)
            self._log_add(f"Log de erros salvo em: {log_path}")

    def _processar_excel(self):
        if not self.pasta_excel_path:
            self._log_add("⚠  Selecione a pasta com os PDFs renomeados.")
            return
        if not self.excel_path:
            self._log_add("⚠  Selecione o arquivo Excel.")
            return

        self._log_clear()
        self._log_add("Carregando arquivos...")

        mapa = carregar_arquivos(self.pasta_excel_path)
        self._log_add(f"{len(mapa)} CPF(s) encontrado(s) nos arquivos.")
        self._log_add("Preenchendo planilha...")

        resultado = preencher_excel(self.excel_path, mapa)

        self._log_add(f"✓  Preenchidos:  {resultado.preenchidos}")
        self._log_add(f"   Já existiam:  {resultado.pulados}")

        if resultado.nao_encontrados:
            self._log_add(
                f"⚠  {len(resultado.nao_encontrados)} CPF(s) não encontrados na planilha:"
            )
            for d in resultado.nao_encontrados:
                self._log_add(f"   • {d.cpf}  —  {d.arquivo.name}")
        else:
            self._log_add("✓  Todos os CPFs foram encontrados na planilha.")

        self.resumo_label.configure(
            text=(
                f"Finalizado — {resultado.preenchidos} preenchido(s)  |  "
                f"{resultado.pulados} já existiam  |  "
                f"{len(resultado.nao_encontrados)} não encontrado(s)"
            )
        )


if __name__ == "__main__":
    app = FiducioApp()
    app.mainloop()