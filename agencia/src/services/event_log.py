"""Registro de eventos em arquivo .jsonl (Parte B).

Cada agência grava todo evento em uma linha JSON (`eventos-<agencia>.jsonl`).
Esses arquivos são a matéria-prima da linha do tempo unificada (mesclar_logs.py).

Cada evento guarda dois carimbos de tempo:
- timestampLamport: o relógio lógico (usado para ordenar a linha do tempo);
- horaParede: o relógio físico da máquina, apenas para comparação — nunca é
  usado para nenhuma decisão do sistema.
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

    def registrar(self, tipo: str, timestamp_lamport: int, detalhes: dict) -> dict:
        evento = {
            "agencia": self.nome_agencia,
            "tipo": tipo,
            "timestampLamport": timestamp_lamport,
            "horaParede": datetime.now(timezone.utc).isoformat(),
            "detalhes": detalhes,
        }
        linha = json.dumps(evento, ensure_ascii=False) + "\n"
        with self._lock:
            with open(self.caminho_arquivo, "a", encoding="utf-8") as arquivo:
                arquivo.write(linha)
        print(f"[Lamport {timestamp_lamport}] {tipo} {detalhes}")
        return evento
