"""F7: idempotência de transferências (funcionalidade adicional)."""
import httpx

from src.services import auth_service


def _ligar_agencias(origem, destino):
    destino_app = destino.app
    origem.app.state.criar_http_client = lambda: httpx.AsyncClient(
        transport=httpx.ASGITransport(app=destino_app)
    )


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


def test_credito_remoto_dedup_no_destino(cliente):
    cliente.post("/contas", json={"id": 0, "saldoInicial": 0})
    token_svc = auth_service.emitir_token_servico(1)
    corpo = {"valor": 25, "vetorEnvio": [0, 1, 0], "origemAgencia": 1}
    headers = {"Authorization": f"Bearer {token_svc}", "Idempotency-Key": "credito-1"}

    cliente.post("/contas/0/creditar-remoto", json=corpo, headers=headers)
    cliente.post("/contas/0/creditar-remoto", json=corpo, headers=headers)  # retry

    # crédito aplicado uma única vez
    assert cliente.get("/contas/0").json()["saldo"] == 25.0


def test_replay_de_falha_nao_redebita_e_recupera(app_agencia):
    origem = app_agencia(0)
    destino = app_agencia(1)
    destino.post("/contas", json={"id": 1, "saldoInicial": 0})
    origem.post("/contas", json={"id": 0, "saldoInicial": 100})

    # 1) primeira tentativa: destino "fora do ar" -> 502, débito aplicado
    class _ClienteQueFalha:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, *a, **k):
            raise httpx.ConnectError("destino fora do ar")

    origem.app.state.criar_http_client = _ClienteQueFalha
    corpo = {"idOrigem": 0, "idDestino": 1, "valor": 30}
    chave = {"Idempotency-Key": "recuperavel-1"}
    r1 = origem.post("/transferencias", json=corpo, headers=chave)
    assert r1.status_code == 502
    assert origem.get("/contas/0").json()["saldo"] == 70.0  # debitado, não revertido

    # 2) destino volta: replay com a MESMA chave recupera sem redebitar
    _ligar_agencias(origem, destino)
    r2 = origem.post("/transferencias", json=corpo, headers=chave)
    assert r2.status_code == 200
    assert origem.get("/contas/0").json()["saldo"] == 70.0  # continua 70 (sem 2º débito)
    assert destino.get("/contas/1").json()["saldo"] == 30.0  # crédito aplicado 1x
