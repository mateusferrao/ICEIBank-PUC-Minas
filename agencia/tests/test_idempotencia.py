"""F7: idempotência de transferências (funcionalidade adicional do Sprint 1).

Os casos entre agências (a chave virando messageId, a deduplicação no consumidor
e a chave liberada após falha de publicação) estão em test_mensageria.py.
"""


def test_replay_local_nao_duplica_debito(cliente):
    cliente.post("/contas", json={"id": 0, "saldoInicial": 100})
    cliente.post("/contas", json={"id": 3, "saldoInicial": 0})
    corpo = {"idOrigem": 0, "idDestino": 3, "valor": 30}
    chave = {"Idempotency-Key": "abc-123"}

    r1 = cliente.post("/transferencias", json=corpo, headers=chave)
    r2 = cliente.post("/transferencias", json=corpo, headers=chave)  # replay

    assert r1.status_code == 200 and r2.status_code == 200
    # débito aplicado uma única vez
    assert cliente.get("/contas/0").json()["saldo"] == 70.0
    assert cliente.get("/contas/3").json()["saldo"] == 30.0


def test_chave_diferente_aplica_de_novo(cliente):
    cliente.post("/contas", json={"id": 0, "saldoInicial": 100})
    cliente.post("/contas", json={"id": 3, "saldoInicial": 0})
    corpo = {"idOrigem": 0, "idDestino": 3, "valor": 30}

    cliente.post("/transferencias", json=corpo, headers={"Idempotency-Key": "k1"})
    cliente.post("/transferencias", json=corpo, headers={"Idempotency-Key": "k2"})

    assert cliente.get("/contas/0").json()["saldo"] == 40.0  # dois débitos


def test_chave_e_liberada_quando_destino_local_nao_existe(cliente):
    cliente.post("/contas", json={"id": 0, "saldoInicial": 100})
    corpo = {"idOrigem": 0, "idDestino": 3, "valor": 30}
    chave = {"Idempotency-Key": "k-erro"}
    assert cliente.post("/transferencias", json=corpo, headers=chave).status_code == 404

    cliente.post("/contas", json={"id": 3, "saldoInicial": 0})
    assert cliente.post("/transferencias", json=corpo, headers=chave).status_code == 200
    assert cliente.get("/contas/0").json()["saldo"] == 70.0
