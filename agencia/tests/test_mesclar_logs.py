"""F5: linha do tempo unificada, ordenada pelo relógio vetorial."""
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from mesclar_logs import mesclar  # noqa: E402


def _escrever(pasta, nome, eventos):
    with open(pasta / nome, "w", encoding="utf-8") as f:
        for e in eventos:
            f.write(json.dumps(e) + "\n")


def test_ordena_por_soma_do_vetor_entre_agencias(tmp_path):
    _escrever(tmp_path, "eventos-agencia-0.jsonl", [
        {"agencia": "agencia-0", "tipo": "CRIAR_CONTA", "timestampVetorial": [1, 0, 0], "horaParede": "t", "detalhes": {}},
        {"agencia": "agencia-0", "tipo": "DEPOSITO", "timestampVetorial": [5, 0, 0], "horaParede": "t", "detalhes": {}},
    ])
    _escrever(tmp_path, "eventos-agencia-1.jsonl", [
        {"agencia": "agencia-1", "tipo": "CRIAR_CONTA", "timestampVetorial": [0, 2, 0], "horaParede": "t", "detalhes": {}},
        {"agencia": "agencia-1", "tipo": "TRANSFERENCIA_CREDITO_REMOTO", "timestampVetorial": [3, 1, 0], "horaParede": "t", "detalhes": {}},
    ])

    eventos = mesclar(str(tmp_path))
    assert [e["timestampVetorial"] for e in eventos] == [[1, 0, 0], [0, 2, 0], [3, 1, 0], [5, 0, 0]]


def test_pasta_vazia_retorna_lista_vazia(tmp_path):
    assert mesclar(str(tmp_path)) == []
