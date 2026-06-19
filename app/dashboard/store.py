"""
Estado da "sessão de assembleia" — mantém em memória a base importada
da B3 (uma assembleia por vez, conforme decidido), expõe busca por
comitente/gestor/documento, marcação de OK/Fora, e o cálculo de quórum.

O cálculo de quórum aqui é uma reimplementação deliberada e simples das
mesmas regras da aba QUÓRUM do Template (SOMASE por status OK/FORA) —
não uma leitura de Excel. Isso é seguro porque a regra é a soma de
quantidades por status, exatamente como a fórmula original, e o
resultado final ainda é validável comparando com o Excel exportado.
"""
from dataclasses import dataclass
from threading import Lock

from app.dashboard.b3_importer import BaseImportada, Comitente


@dataclass
class DadosQuorumSessao:
    total: float
    fora_circulacao: float
    em_circulacao: float
    quorum_qtd: float
    quorum_pct_sobre_circulacao: float
    quorum_pct_sobre_total: float


class SessaoAssembleia:
    """Uma assembleia em andamento. Uma instância por vez (sem multi-sessão)."""

    def __init__(self):
        self._lock = Lock()
        self.base: BaseImportada | None = None

    @property
    def carregada(self) -> bool:
        return self.base is not None

    def carregar(self, base: BaseImportada):
        with self._lock:
            self.base = base

    def limpar(self):
        with self._lock:
            self.base = None

    def _comitentes(self) -> list[Comitente]:
        return self.base.comitentes if self.base else []

    def buscar(self, termo: str, tipo: str = "todos", status: str = "todos") -> list[dict]:
        termo_norm = termo.strip().lower()
        comitentes = self._comitentes()
        total = sum(c.quantidade for c in comitentes)
        resultado = []
        for idx, c in enumerate(comitentes):
            if tipo == "PJ" and c.tipo_pessoa != "Jurídica":
                continue
            if tipo == "PF" and c.tipo_pessoa != "Física":
                continue

            status_atual = c.status or "pendente"
            if status == "ok" and status_atual != "ok":
                continue
            if status == "fora" and status_atual != "fora":
                continue
            if status == "pendente" and status_atual != "pendente":
                continue

            if termo_norm:
                campos = [c.nome, c.gestor or "", c.documento]
                if not any(termo_norm in campo.lower() for campo in campos):
                    continue

            resultado.append(self._serializar(idx, c, total))
        return resultado

    def _serializar(self, idx: int, c: Comitente, total: float) -> dict:
        pct = (c.quantidade / total) if total else 0
        return {
            "idx": idx,
            "nome": c.nome,
            "documento": c.documento,
            "tipo_pessoa": c.tipo_pessoa,
            "quantidade": c.quantidade,
            "percentual": pct,
            "serie": c.serie,
            "gestor": c.gestor,
            "status": c.status or "pendente",
        }

    def marcar_status(self, idx: int, status: str | None):
        """status: 'ok' | 'fora' | None (volta a pendente)"""
        with self._lock:
            if self.base is None or not (0 <= idx < len(self.base.comitentes)):
                raise IndexError("Comitente não encontrado")
            self.base.comitentes[idx].status = status

    def definir_gestor(self, idx: int, gestor: str):
        with self._lock:
            if self.base is None or not (0 <= idx < len(self.base.comitentes)):
                raise IndexError("Comitente não encontrado")
            self.base.comitentes[idx].gestor = gestor

    def calcular_quorum(self) -> DadosQuorumSessao:
        comitentes = self._comitentes()
        total = sum(c.quantidade for c in comitentes)
        fora = sum(c.quantidade for c in comitentes if c.status == "fora")
        em_circulacao = total - fora
        ok = sum(c.quantidade for c in comitentes if c.status == "ok")

        return DadosQuorumSessao(
            total=total,
            fora_circulacao=fora,
            em_circulacao=em_circulacao,
            quorum_qtd=ok,
            quorum_pct_sobre_circulacao=(ok / em_circulacao) if em_circulacao else 0,
            quorum_pct_sobre_total=(ok / total) if total else 0,
        )

    def contagem_status(self) -> dict:
        comitentes = self._comitentes()
        ok = sum(1 for c in comitentes if c.status == "ok")
        fora = sum(1 for c in comitentes if c.status == "fora")
        pendente = len(comitentes) - ok - fora
        return {"total": len(comitentes), "ok": ok, "fora": fora, "pendente": pendente}
