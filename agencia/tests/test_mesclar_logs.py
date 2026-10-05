"""F5/Sprint 2 Parte D: linha do tempo causal a partir dos vetores."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from mesclar_logs import mesclar, pares_causais, pares_concorrentes  # noqa: E402


def _evento(agencia, tipo, vetor, hora="2026-01-01T00:00:00+00:00", **detalhes):
    return {"agencia": agencia, "tipo": tipo, "timestampVetorial": vetor, "horaParede": hora, "detalhes": detalhes}


def _escrever(pasta, nome, eventos):
    with open(pasta / nome, "w", encoding="utf-8") as f:
        for e in eventos:
            f.write(json.dumps(e) + "\n")


def test_ordena_por_soma_do_vetor_entre_agencias(tmp_path):
    _escrever(tmp_path, "eventos-agencia-0.jsonl", [
        _evento("agencia-0", "CRIAR_CONTA", [1, 0, 0]),
        _evento("agencia-0", "DEPOSITO", [5, 0, 0]),
    ])
    _escrever(tmp_path, "eventos-agencia-1.jsonl", [
        _evento("agencia-1", "CRIAR_CONTA", [0, 2, 0]),
        _evento("agencia-1", "TRANSFERENCIA_CREDITO_REMOTO", [3, 1, 0]),
    ])

    eventos = mesclar(str(tmp_path))
    assert [e["timestampVetorial"] for e in eventos] == [[1, 0, 0], [0, 2, 0], [3, 1, 0], [5, 0, 0]]


def test_causa_sempre_vem_antes_do_efeito_mesmo_com_hora_de_parede_invertida(tmp_path):
    # o relógio da máquina 1 está adiantado: o crédito "aconteceu" às 09:00 e o débito às 10:00
    _escrever(tmp_path, "eventos-agencia-0.jsonl", [
        _evento("agencia-0", "TRANSFERENCIA_DEBITO", [1, 0, 0], hora="2026-01-01T10:00:00+00:00"),
    ])
    _escrever(tmp_path, "eventos-agencia-1.jsonl", [
        _evento("agencia-1", "TRANSFERENCIA_CREDITO_REMOTO", [1, 1, 0], hora="2026-01-01T09:00:00+00:00"),
    ])

    tipos = [e["tipo"] for e in mesclar(str(tmp_path))]
    assert tipos == ["TRANSFERENCIA_DEBITO", "TRANSFERENCIA_CREDITO_REMOTO"]


def test_pasta_vazia_retorna_lista_vazia(tmp_path):
    assert mesclar(str(tmp_path)) == []


def test_pares_concorrentes_so_entre_agencias_diferentes():
    eventos = [
        _evento("agencia-0", "CRIAR_CONTA", [1, 0, 0]),
        _evento("agencia-0", "DEPOSITO", [2, 0, 0]),   # mesma agência: nunca entra
        _evento("agencia-1", "CRIAR_CONTA", [0, 1, 0]),  # concorrente com os da agência 0
    ]
    pares = pares_concorrentes(eventos)
    assert len(pares) == 2
    assert all(a["agencia"] != b["agencia"] for a, b in pares)


def test_par_debito_credito_e_causal_e_nao_concorrente():
    debito = _evento("agencia-0", "TRANSFERENCIA_DEBITO", [1, 0, 0], messageId="m1")
    credito = _evento("agencia-1", "TRANSFERENCIA_CREDITO_REMOTO", [2, 1, 0], messageId="m1")

    assert pares_concorrentes([debito, credito]) == []
    assert pares_causais([debito, credito]) == [(debito, credito)]


def test_credito_sem_debito_correspondente_nao_gera_par_causal():
    credito = _evento("agencia-1", "TRANSFERENCIA_CREDITO_REMOTO", [2, 1, 0], messageId="solto")
    assert pares_causais([credito]) == []
