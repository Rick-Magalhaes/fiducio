import threading
import math
from pathlib import Path

import customtkinter as ctk

from app.core.processor import ProcessadorProcuracoes
from app.models.registry import MODELOS
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
        self.geometry("1000x800")
        self.resizable(True, True)
        self.configure(fg_color=BG)

        self.pasta_pdf_path: Path | None = None
        self.pasta_excel_path: Path | None = None
        self.excel_path: Path | None = None
        self.modelo_selecionado: str = list(MODELOS.keys())[0]

        self._build()

    # ── logo ──────────────────────────────────────────────────────────────────

    def _draw_logo(self, parent):
        size = 44
        canvas = ctk.CTkCanvas(
            parent,
            width=size,
            height=size,
            bg=BG,
            highlightthickness=0,
        )
        canvas.pack(side="left", padx=(0, 12))

        cx, cy, r_out, r_in = size / 2, size / 2, 20, 11
        sides = 5
        color = "#e2e8f0"
        gap = 3

        def penta_points(cx, cy, r, offset=0):
            pts = []
            for i in range(sides):
                angle = math.radians(offset + i * 360 / sides)
                pts.append((cx + r * math.sin(angle), cy - r * math.cos(angle)))
            return pts

        def lerp(a, b, t):
            return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)

        outer_pts = penta_points(cx, cy, r_out)
        inner_pts = penta_points(cx, cy, r_in)

        for i in range(sides):
            p1_out = outer_pts[i]
            p2_out = outer_pts[(i + 1) % sides]
            p1_in  = inner_pts[i]
            p2_in  = inner_pts[(i + 1) % sides]

            gap_t = gap / (math.dist(p1_out, p2_out))

            seg_out_start = lerp(p1_out, p2_out, gap_t)
            seg_out_end   = lerp(p2_out, p1_out, gap_t)
            seg_in_start  = lerp(p2_in, p1_in, gap_t)
            seg_in_end    = lerp(p1_in, p2_in, gap_t)

            coords = [
                seg_out_start[0], seg_out_start[1],
                seg_out_end[0],   seg_out_end[1],
                seg_in_start[0],  seg_in_start[1],
                seg_in_end[0],    seg_in_end[1],
            ]
            canvas.create_polygon(coords, fill=color, outline="")

        return canvas

    # ── build ─────────────────────────────────────────────────────────────────

    def _build(self):
        outer = ctk.CTkScrollableFrame(self, fg_color=BG, scrollbar_button_color=BORDER)
        outer.pack(fill="both", expand=True, padx=28, pady=28)

        # cabeçalho
        header = ctk.CTkFrame(outer, fg_color="transparent")
        header.pack(anchor="w", pady=(0, 20))

        self._draw_logo(header)

        text_col = ctk.CTkFrame(header, fg_color="transparent")
        text_col.pack(side="left")

        ctk.CTkLabel(
            text_col, text="Fiducio",
            font=ctk.CTkFont(size=26, weight="bold"),
            text_color=TEXT,
        ).pack(anchor="w")
        ctk.CTkLabel(
            text_col, text="Auxiliar de Assembleias",
            font=ctk.CTkFont(size=13),
            text_color=MUTED,
        ).pack(anchor="w")

        # ── modelo ────────────────────────────────────────────────────────────
        self._section_label(outer, "MODELO")
        self._label(outer, "MODELO DE PROCURAÇÃO")
        self.dropdown_modelo = ctk.CTkOptionMenu(
            outer,
            values=list(MODELOS.keys()),
            fg_color=SURFACE,
            button_color=SURFACE,
            button_hover_color="#252837",
            dropdown_fg_color=SURFACE,
            dropdown_hover_color="#252837",
            text_color=TEXT,
            dropdown_text_color=TEXT,
            font=ctk.CTkFont(size=13),
            height=36,
            command=self._on_modelo_change,
        )
        self.dropdown_modelo.pack(anchor="w", pady=(4, 0))

        self._divider(outer)

        # ── renomear ──────────────────────────────────────────────────────────
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

        # ── excel ─────────────────────────────────────────────────────────────
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

        ctk.CTkButton(
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
        ).pack(anchor="e", pady=(12, 0))

        self._divider(outer)

        # ── log ───────────────────────────────────────────────────────────────
        log_header = ctk.CTkFrame(outer, fg_color="transparent")
        log_header.pack(fill="x", pady=(0, 8))

        ctk.CTkFrame(log_header, fg_color=BORDER, height=1).pack(
            side="left", fill="x", expand=True, pady=(8, 0)
        )
        ctk.CTkLabel(
            log_header, text="  LOG  ",
            font=ctk.CTkFont(size=10),
            text_color=MUTED,
        ).pack(side="left")
        ctk.CTkButton(
            log_header,
            text="Limpar",
            fg_color="transparent",
            hover_color=SURFACE,
            text_color=MUTED,
            font=ctk.CTkFont(size=10),
            height=20,
            width=60,
            command=self._log_clear,
        ).pack(side="left")
        ctk.CTkFrame(log_header, fg_color=BORDER, height=1).pack(
            side="left", fill="x", expand=True, pady=(8, 0)
        )

        self.log_box = ctk.CTkTextbox(
            outer,
            height=220,
            fg_color=BG,
            border_color=BORDER,
            border_width=1,
            font=ctk.CTkFont(family="Courier", size=11),
            text_color=TEXT,
            wrap="none",
            state="disabled",
        )
        self.log_box.pack(fill="x", pady=(0, 0))

        self.resumo_label = ctk.CTkLabel(
            outer,
            text="",
            font=ctk.CTkFont(size=12),
            text_color=MUTED,
            anchor="w",
        )
        self.resumo_label.pack(anchor="w", pady=(6, 0))

    # ── widget helpers ────────────────────────────────────────────────────────

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

    def _on_modelo_change(self, valor: str):
        self.modelo_selecionado = valor

    # ── log ───────────────────────────────────────────────────────────────────

    def _log_add(self, msg: str):
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
        self._log_add(f"Modelo: {self.modelo_selecionado}")
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

        modelo = MODELOS[self.modelo_selecionado]
        processador = ProcessadorProcuracoes(modelo)
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