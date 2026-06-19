"""
Servidor do Painel de Quórum.

Sobe um Flask + Socket.IO local apontando para um arquivo .xlsx
específico, observa esse arquivo (mtime) e empurra atualizações para
o navegador sempre que ele for salvo. Pensado para ser controlado pela
UI do Fiducio: uma assembleia por vez — abrir um novo arquivo encerra
o servidor anterior antes de subir o novo.

O servidor roda em um processo separado (multiprocessing), não em
thread: assim conseguimos encerrá-lo de forma confiável a partir da UI
(thread.join() não garante parar um servidor Werkzeug rodando dentro
dela; process.terminate() sim).
"""
import time
import webbrowser
from multiprocessing import Process
from pathlib import Path

from flask import Flask, render_template
from flask_socketio import SocketIO

from app.dashboard.excel_reader import ler_quorum, ler_investidores

PORTA = 5151
_TEMPLATE_DIR = str(Path(__file__).parent / "templates")
_STATIC_DIR = str(Path(__file__).parent / "static")


def _montar_payload(caminho_excel: Path) -> dict:
    quorum = ler_quorum(caminho_excel)
    investidores = ler_investidores(caminho_excel)
    return {
        "quorum": quorum.__dict__,
        "investidores": [i.__dict__ for i in investidores],
        "arquivo": caminho_excel.name,
    }


def _watcher_loop(socketio: SocketIO, caminho_excel: Path):
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
                        payload = _montar_payload(caminho_excel)
                        break
                    except Exception:
                        continue
                if payload is not None:
                    socketio.emit("update", payload)
        except FileNotFoundError:
            pass
        except Exception as e:
            print(f"[painel_quorum] erro no watcher: {e}")
        time.sleep(1)


def _processo_servidor(caminho_excel_str: str):
    """Executa em um processo filho — monta a app Flask e roda até ser terminado."""
    import threading

    caminho_excel = Path(caminho_excel_str)

    app = Flask(__name__, template_folder=_TEMPLATE_DIR, static_folder=_STATIC_DIR)
    app.config["SECRET_KEY"] = "fiducio-painel-quorum"
    socketio = SocketIO(app, cors_allowed_origins="*")

    @app.route("/")
    def index():
        return render_template("index.html")

    @socketio.on("connect")
    def on_connect():
        socketio.emit("update", _montar_payload(caminho_excel))

    @socketio.on("request_update")
    def on_request_update():
        socketio.emit("update", _montar_payload(caminho_excel))

    threading.Thread(
        target=_watcher_loop, args=(socketio, caminho_excel), daemon=True
    ).start()

    socketio.run(app, host="127.0.0.1", port=PORTA, allow_unsafe_werkzeug=True)


class PainelQuorum:
    """Controla o ciclo de vida do servidor do painel: um arquivo por vez."""

    def __init__(self):
        self._processo: Process | None = None
        self.caminho_excel: Path | None = None

    @property
    def rodando(self) -> bool:
        return self._processo is not None and self._processo.is_alive()

    def abrir(self, caminho_excel: Path):
        """Encerra um painel anterior (se houver) e abre um novo para o arquivo informado."""
        self.encerrar()

        self.caminho_excel = caminho_excel
        self._processo = Process(
            target=_processo_servidor, args=(str(caminho_excel),), daemon=True
        )
        self._processo.start()

        time.sleep(1.5)  # dá tempo do servidor subir antes de abrir o navegador

        if not self._processo.is_alive():
            raise RuntimeError(
                "O servidor do painel não conseguiu iniciar — verifique se a "
                f"porta {PORTA} já está em uso por outro programa (ou outra "
                "instância do Fiducio aberta)."
            )

        webbrowser.open(f"http://127.0.0.1:{PORTA}")

    def encerrar(self):
        if self._processo is not None and self._processo.is_alive():
            self._processo.terminate()
            self._processo.join(timeout=3)
        self._processo = None
