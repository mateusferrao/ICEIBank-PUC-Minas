"""F5 — Linha do tempo unificada ordenada por Lamport."""
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from mesclar_logs import mesclar  # noqa: E402


def _escrever(pasta, nome, eventos):
    with open(pasta / nome, "w", encoding="utf-8") as f:
        for e in eventos:
            f.write(json.dumps(e) + "\n")


def test_ordena_por_timestamp_lamport_entre_agencias(tmp_path):
    _escrever(tmp_path, "eventos-agencia-0.jsonl", [
        {"agencia": "agencia-0", "tipo": "CRIAR_CONTA", "timestampLamport": 1, "horaParede": "t", "detalhes": {}},
        {"agencia": "agencia-0", "tipo": "DEPOSITO", "timestampLamport": 5, "horaParede": "t", "detalhes": {}},
    ])
    _escrever(tmp_path, "eventos-agencia-1.jsonl", [
        {"agencia": "agencia-1", "tipo": "CRIAR_CONTA", "timestampLamport": 2, "horaParede": "t", "detalhes": {}},
        {"agencia": "agencia-1", "tipo": "TRANSFERENCIA_CREDITO_REMOTO", "timestampLamport": 4, "horaParede": "t", "detalhes": {}},
    ])

    eventos = mesclar(str(tmp_path))
    assert [e["timestampLamport"] for e in eventos] == [1, 2, 4, 5]


def test_pasta_vazia_retorna_lista_vazia(tmp_path):
    assert mesclar(str(tmp_path)) == []
