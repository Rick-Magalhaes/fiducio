"""
Servidor do Painel de Quórum / Conciliação.

Sobe um Flask + Socket.IO local com três telas:
  - Importar: seleciona 1+ arquivos ListagemB3.xlsx e monta a sessão
  - Conciliação: busca comitentes/gestores, marca OK/Fora
  - Quórum: visão ao vivo do quórum calculado a partir da sessão

O servidor roda em uma thread (não em multiprocessing.Process). Em um
.exe gerado pelo PyInstaller no Windows, um processo filho de
multiprocessing pode reexecutar o programa inteiro do zero — incluindo
abrir uma segunda janela completa do Tkinter — mesmo com
freeze_support() chamado, quando o entry point importa módulos que
disparam a inicialização da UI. Isso foi observado na prática: uma
segunda janela do Fiducio abrindo em branco e o servidor nunca subindo
na porta.

O encerramento é feito via werkzeug.serving.make_server, que devolve
um objeto servidor com .shutdown() — diferente de socketio.run()/
app.run(), que não expõem um jeito de parar de fora (o mecanismo antigo
environ['werkzeug.server.shutdown'] foi removido no Werkzeug 3.x).

Modo legado: se aberto com um caminho de Excel existente (Template já
preenchido), mantém o comportamento anterior de só exibir o quórum
lendo aquele arquivo, sem a etapa de importação/conciliação.
"""
import threading
import time
import webbrowser
from pathlib import Path

from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO
from werkzeug.serving import make_server

from app.dashboard.excel_reader import ler_quorum, ler_investidores
from app.dashboard.b3_importer import importar_arquivos
from app.dashboard.store import SessaoAssembleia
from app.dashboard.template_writer import gerar_template
from app.dashboard.cvm_lookup import buscar_gestores, CVMIndisponivel
from app.dashboard.paths import caminho_recurso

PORTA = 5151
_TEMPLATE_DIR = str(caminho_recurso("templates"))
_STATIC_DIR = str(caminho_recurso("static"))


def _montar_payload_legado(caminho_excel: Path) -> dict:
    quorum = ler_quorum(caminho_excel)
    investidores = ler_investidores(caminho_excel)
    return {
        "quorum": quorum.__dict__,
        "investidores": [i.__dict__ for i in investidores],
        "arquivo": caminho_excel.name,
    }


def _montar_payload_sessao(sessao: SessaoAssembleia) -> dict:
    if not sessao.carregada:
        return {"carregada": False}
    q = sessao.calcular_quorum()
    return {
        "carregada": True,
        "quorum": q.__dict__,
        "contagem": sessao.contagem_status(),
        "arquivos": sessao.base.arquivos,
    }


def _watcher_loop_legado(socketio: SocketIO, caminho_excel: Path):
    last_mtime = 0.0
    while True:
        try:
            mtime = caminho_excel.stat().st_mtime
            if mtime != last_mtime:
                last_mtime = mtime
                payload = None
                for _ in range(10):
                    time.sleep(0.5)
                    try:
                        payload = _montar_payload_legado(caminho_excel)
                        break
                    except Exception:
                        continue
                if payload is not None:
                    socketio.emit("update_legado", payload)
        except FileNotFoundError:
            pass
        except Exception as e:
            print(f"[painel_quorum] erro no watcher: {e}")
        time.sleep(1)


def _montar_servidor(caminho_excel_str: str | None, pasta_exportacao_str: str, caminhos_b3_str: list):
    """Monta a app Flask e devolve um objeto servidor (werkzeug BaseWSGIServer)
    já pronto para rodar via .serve_forever() em uma thread, e que pode
    ser encerrado de fora via .shutdown()."""
    sessao = SessaoAssembleia()
    pasta_exportacao = Path(pasta_exportacao_str)
    caminho_excel_legado = Path(caminho_excel_str) if caminho_excel_str else None
    caminhos_b3 = list(caminhos_b3_str or [])

    app = Flask(__name__, template_folder=_TEMPLATE_DIR, static_folder=_STATIC_DIR)
    app.config["SECRET_KEY"] = "fiducio-painel-quorum"
    # async_mode forçado explicitamente: sem isso, a lib tenta
    # autodetectar (eventlet -> gevent -> threading) verificando quais
    # dependências estão instaladas. Dentro do .exe do PyInstaller isso
    # pode detectar eventlet/gevent parcialmente empacotados (via
    # collect_all de outras libs) e falhar com "Invalid async_mode
    # specified" — forçar "threading" (o único modo realmente usado
    # aqui) evita essa ambiguidade.
    socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

    modo_legado = caminho_excel_legado is not None

    # ── páginas ──────────────────────────────────────────────────────────

    @app.route("/")
    def index():
        if modo_legado:
            return render_template("index.html")
        return render_template("importar.html")

    @app.route("/conciliacao")
    def conciliacao():
        return render_template("conciliacao.html")

    @app.route("/quorum")
    def quorum_page():
        return render_template("index.html")

    # ── api: importação ─────────────────────────────────────────────────

    @app.route("/api/arquivos_b3")
    def api_arquivos_b3():
        return jsonify({"caminhos": caminhos_b3})

    @app.route("/api/importar", methods=["POST"])
    def api_importar():
        caminhos = request.json.get("caminhos", [])
        if not caminhos:
            return jsonify({"erro": "Nenhum arquivo informado."}), 400

        base = importar_arquivos([Path(c) for c in caminhos])
        sessao.carregar(base)

        socketio.emit("sessao_atualizada", _montar_payload_sessao(sessao))

        return jsonify({
            "ok": True,
            "total_comitentes": base.total_comitentes,
            "total_pj": len(base.comitentes_pj),
            "total_pf": len(base.comitentes_pf),
            "avisos": base.avisos,
        })

    @app.route("/api/sessao")
    def api_sessao():
        return jsonify(_montar_payload_sessao(sessao))

    # ── api: busca de gestor (cvm) ───────────────────────────────────────

    @app.route("/api/buscar_gestores", methods=["POST"])
    def api_buscar_gestores():
        if not sessao.carregada:
            return jsonify({"erro": "Nenhuma sessão carregada."}), 400

        cnpjs = list({c.documento for c in sessao.base.comitentes_pj})
        if not cnpjs:
            return jsonify({"ok": True, "encontrados": 0, "nao_encontrados": 0})

        try:
            resultados = buscar_gestores(cnpjs)
        except CVMIndisponivel as e:
            return jsonify({
                "erro": str(e),
                "fallback": "Use a busca manual de CNPJs (planilha + executável existente) "
                            "e informe o gestor manualmente na tela de conciliação.",
            }), 503

        mapa_gestor = {r.cnpj: r.nome_gestor for r in resultados if r.encontrado}
        encontrados = 0
        for c in sessao.base.comitentes_pj:
            gestor = mapa_gestor.get(c.documento)
            if gestor:
                c.gestor = gestor
                encontrados += 1

        socketio.emit("sessao_atualizada", _montar_payload_sessao(sessao))
        return jsonify({
            "ok": True,
            "encontrados": encontrados,
            "nao_encontrados": len(cnpjs) - encontrados,
        })

    # ── api: conciliação ─────────────────────────────────────────────────

    @app.route("/api/buscar")
    def api_buscar():
        termo = request.args.get("termo", "")
        tipo = request.args.get("tipo", "todos")
        status = request.args.get("status", "todos")
        if not sessao.carregada:
            return jsonify({"resultados": []})
        return jsonify({"resultados": sessao.buscar(termo, tipo, status)})

    @app.route("/api/marcar", methods=["POST"])
    def api_marcar():
        dados = request.json
        idx = dados.get("idx")
        status = dados.get("status")  # "ok" | "fora" | None
        try:
            sessao.marcar_status(idx, status)
        except IndexError:
            return jsonify({"erro": "Comitente não encontrado."}), 404

        socketio.emit("sessao_atualizada", _montar_payload_sessao(sessao))
        return jsonify({"ok": True})

    @app.route("/api/definir_gestor", methods=["POST"])
    def api_definir_gestor():
        dados = request.json
        idx = dados.get("idx")
        gestor = dados.get("gestor", "")
        try:
            sessao.definir_gestor(idx, gestor)
        except IndexError:
            return jsonify({"erro": "Comitente não encontrado."}), 404
        return jsonify({"ok": True})

    # ── api: exportação ──────────────────────────────────────────────────

    @app.route("/api/exportar", methods=["POST"])
    def api_exportar():
        if not sessao.carregada:
            return jsonify({"erro": "Nenhuma sessão carregada."}), 400
        caminho = gerar_template(sessao.base, pasta_exportacao)
        return jsonify({"ok": True, "caminho": str(caminho)})

    # ── sockets (modo legado e modo sessão) ─────────────────────────────

    @socketio.on("connect")
    def on_connect():
        if modo_legado:
            socketio.emit("update_legado", _montar_payload_legado(caminho_excel_legado))
        else:
            socketio.emit("sessao_atualizada", _montar_payload_sessao(sessao))

    @socketio.on("request_update")
    def on_request_update():
        if modo_legado:
            socketio.emit("update_legado", _montar_payload_legado(caminho_excel_legado))
        else:
            socketio.emit("sessao_atualizada", _montar_payload_sessao(sessao))

    if modo_legado:
        threading.Thread(
            target=_watcher_loop_legado, args=(socketio, caminho_excel_legado), daemon=True
        ).start()

    servidor = make_server("127.0.0.1", PORTA, app, threaded=True)
    return servidor


class PainelQuorum:
    """Controla o ciclo de vida do servidor do painel: uma sessão por vez."""

    def __init__(self):
        self._servidor = None
        self._thread: threading.Thread | None = None
        self.caminho_excel: Path | None = None

    @property
    def rodando(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def abrir(
        self,
        caminho_excel: Path | None = None,
        pasta_exportacao: Path | None = None,
        caminhos_b3: list[Path] | None = None,
    ):
        """
        Encerra um painel anterior (se houver) e abre um novo.
        - Se caminho_excel for informado: modo legado (lê um Template já existente).
        - Se não: modo sessão (importação B3 → conciliação → exportação).
          caminhos_b3, se informado, já chega pré-selecionado pela UI Tkinter
          (o navegador não tem acesso ao caminho completo de arquivos
          selecionados por um <input type="file">, então a seleção
          precisa acontecer no Tkinter, não na tela web).
        """
        self.encerrar()

        self.caminho_excel = caminho_excel
        pasta_exportacao = pasta_exportacao or (Path.home() / "Documents" / "Fiducio - Exportações")
        caminhos_b3_str = [str(c) for c in (caminhos_b3 or [])]

        try:
            self._servidor = _montar_servidor(
                str(caminho_excel) if caminho_excel else None,
                str(pasta_exportacao),
                caminhos_b3_str,
            )
        except OSError as e:
            self._servidor = None
            raise RuntimeError(
                f"Não foi possível iniciar o servidor na porta {PORTA} — "
                f"verifique se já não há outra instância do Fiducio aberta. ({e})"
            ) from e

        self._thread = threading.Thread(target=self._servidor.serve_forever, daemon=True)
        self._thread.start()

        time.sleep(1)  # dá tempo do servidor aceitar conexões antes de abrir o navegador
        webbrowser.open(f"http://127.0.0.1:{PORTA}")

    def encerrar(self):
        if self._servidor is not None:
            try:
                self._servidor.shutdown()
            except Exception:
                pass
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=3)
        self._servidor = None
        self._thread = None
