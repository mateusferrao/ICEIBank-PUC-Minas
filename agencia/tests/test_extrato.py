"""Extrato por conta (endpoint de leitura para o frontend)."""


def test_extrato_lista_eventos_da_conta(cliente):
    cliente.post("/contas", json={"id": 0, "saldoInicial": 100})
    cliente.post("/contas/0/depositar", json={"valor": 50})
    cliente.post("/contas/0/sacar", json={"valor": 20})

    r = cliente.get("/contas/0/extrato")
    assert r.status_code == 200
    tipos = [e["tipo"] for e in r.json()["eventos"]]
    assert "CRIAR_CONTA" in tipos
    assert "DEPOSITO" in tipos
    assert "SAQUE" in tipos


def test_extrato_exige_posse(app_agencia):
    cliente = app_agencia(0, usuario="ana", senha="senha-ana")
    cliente.post("/contas", json={"id": 0, "saldoInicial": 100})
    from src.services import auth_service

    cliente.headers.update({"Authorization": f"Bearer {auth_service.emitir_token_usuario('bruno')}"})
    assert cliente.get("/contas/0/extrato").status_code == 403


def test_extrato_conta_inexistente_404(cliente):
    assert cliente.get("/contas/0/extrato").status_code == 404
