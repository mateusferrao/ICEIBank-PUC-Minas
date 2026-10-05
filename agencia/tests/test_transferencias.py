"""F4: transferências local e validações.

A transferência entre agências (publish/subscribe) é testada em
test_mensageria.py, com o broker em memória.
"""


def test_transferencia_local_mesma_agencia(cliente):
    # contas 0 e 3 pertencem ambas à agência 0 (3 % 3 == 0)
    cliente.post("/contas", json={"id": 0, "saldoInicial": 100})
    cliente.post("/contas", json={"id": 3, "saldoInicial": 0})

    r = cliente.post("/transferencias", json={"idOrigem": 0, "idDestino": 3, "valor": 30})
    assert r.status_code == 200
    assert "mesma agência" in r.json()["mensagem"]
    assert cliente.get("/contas/0").json()["saldo"] == 70.0
    assert cliente.get("/contas/3").json()["saldo"] == 30.0


def test_transferencia_local_saldo_insuficiente(cliente):
    cliente.post("/contas", json={"id": 0, "saldoInicial": 10})
    cliente.post("/contas", json={"id": 3, "saldoInicial": 0})
    r = cliente.post("/transferencias", json={"idOrigem": 0, "idDestino": 3, "valor": 50})
    assert r.status_code == 400


def test_destino_inexistente_mesma_agencia_reverte(cliente):
    cliente.post("/contas", json={"id": 0, "saldoInicial": 100})
    # conta 3 é da agência 0 mas não existe -> reverte débito e 404
    r = cliente.post("/transferencias", json={"idOrigem": 0, "idDestino": 3, "valor": 30})
    assert r.status_code == 404
    assert cliente.get("/contas/0").json()["saldo"] == 100.0
