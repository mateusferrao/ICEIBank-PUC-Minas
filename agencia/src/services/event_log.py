"""Registro de eventos em arquivo .jsonl (Parte B).

Cada agência grava cada evento numa linha JSON (`eventos-<agencia>.jsonl`). Esses
arquivos são a base da linha do tempo unificada (mesclar_logs.py).

Cada evento guarda dois tempos:
- timestampVetorial: o relógio vetorial, usado para ordenar a linha do tempo e
  descobrir quais eventos são concorrentes;
- horaParede: o relógio físico da máquina, só para comparação. Ele nunca é usado
  para nenhuma decisão do sistema.
"""
import json
import os
import threading
from datetime import datetime, timezone

_DIR_DADOS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "data")


class RegistroEventos:
    def __init__(self, nome_agencia: str) -> None:
        self.nome_agencia = nome_agencia
        os.makedirs(_DIR_DADOS, exist_ok=True)
        self.caminho_arquivo = os.path.join(_DIR_DADOS, f"eventos-{nome_agencia}.jsonl")
        self._lock = threading.Lock()

    def registrar(self, tipo: str, timestamp_vetorial: list[int], detalhes: dict) -> dict:
        evento = {
            "agencia": self.nome_agencia,
            "tipo": tipo,
            "timestampVetorial": timestamp_vetorial,
            "horaParede": datetime.now(timezone.utc).isoformat(),
            "detalhes": detalhes,
        }
        linha = json.dumps(evento, ensure_ascii=False) + "\n"
        with self._lock:
            with open(self.caminho_arquivo, "a", encoding="utf-8") as arquivo:
                arquivo.write(linha)
        print(f"[Vetor {timestamp_vetorial}] {tipo} {detalhes}")
        return evento

    def ler_eventos(self) -> list[dict]:
        """Lê todos os eventos já registrados por esta agência (o próprio .jsonl)."""
        if not os.path.exists(self.caminho_arquivo):
            return []
        eventos: list[dict] = []
        with open(self.caminho_arquivo, encoding="utf-8") as arquivo:
            for linha in arquivo:
                linha = linha.strip()
                if linha:
                    eventos.append(json.loads(linha))
        return eventos
