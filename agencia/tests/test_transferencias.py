"""F4 — Transferências: local, entre agências e a falha conhecida.

A chamada entre agências é testada in-process: o cliente HTTP da origem é
substituído por um httpx.AsyncClient com ASGITransport apontando para o app da
agência de destino — sem subir servidor de rede real.
"""
import httpx
import pytest


def _ligar_agencias(origem, destino):
    """Faz a agência de origem falar com a de destino via ASGITransport."""
    destino_app = destino.app
    origem.app.state.criar_http_client = lambda: httpx.AsyncClient(
        transport=httpx.ASGITransport(app=destino_app)
    )


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


def test_transferencia_entre_agencias(app_agencia):
    origem = app_agencia(0)
    destino = app_agencia(1)
    _ligar_agencias(origem, destino)

    origem.post("/contas", json={"id": 0, "saldoInicial": 100})
    destino.post("/contas", json={"id": 1, "saldoInicial": 0})

    r = origem.post("/transferencias", json={"idOrigem": 0, "idDestino": 1, "valor": 30})
    assert r.status_code == 200
    assert "entre agências" in r.json()["mensagem"]
    assert origem.get("/contas/0").json()["saldo"] == 70.0
    assert destino.get("/contas/1").json()["saldo"] == 30.0


def test_credito_remoto_aplica_regra_de_recebimento_do_lamport(app_agencia):
    origem = app_agencia(0)
    destino = app_agencia(1)
    _ligar_agencias(origem, destino)
    origem.post("/contas", json={"id": 0, "saldoInicial": 100})
    destino.post("/contas", json={"id": 1, "saldoInicial": 0})

    lamport_destino_antes = destino.get("/health").json()["lamport"]
    origem.post("/transferencias", json={"idOrigem": 0, "idDestino": 1, "valor": 10})
    # o destino avançou o relógio ao receber (ao_receber = max+1)
    assert destino.get("/health").json()["lamport"] > lamport_destino_antes


def test_falha_conhecida_nao_reverte_debito(app_agencia):
    origem = app_agencia(0)

    class _ClienteQueFalha:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, *a, **k):
            raise httpx.ConnectError("agência de destino fora do ar")

    origem.app.state.criar_http_client = _ClienteQueFalha
    origem.post("/contas", json={"id": 0, "saldoInicial": 100})

    r = origem.post("/transferencias", json={"idOrigem": 0, "idDestino": 1, "valor": 30})
    assert r.status_code == 502
    # LIMITAÇÃO CONHECIDA: o débito NÃO é revertido
    assert origem.get("/contas/0").json()["saldo"] == 70.0


def test_destino_inexistente_mesma_agencia_reverte(cliente):
    cliente.post("/contas", json={"id": 0, "saldoInicial": 100})
    # conta 3 é da agência 0 mas não existe -> reverte débito e 404
    r = cliente.post("/transferencias", json={"idOrigem": 0, "idDestino": 3, "valor": 30})
    assert r.status_code == 404
    assert cliente.get("/contas/0").json()["saldo"] == 100.0
