"""Fixtures de teste: cria apps de agência isolados (event log em diretório
temporário) e já autenticados via JWT.

A partir da Parte F todas as rotas de conta exigem token. Por isso os clientes
de teste fazem login e passam a enviar o cabeçalho Authorization automaticamente.
Passe usuario=None para obter um cliente SEM autenticação (testes de 401).
"""
import pytest
from fastapi.testclient import TestClient

import src.services.event_log as event_log
from src.main import criar_app


def autenticar(client: TestClient, usuario: str, senha: str) -> TestClient:
    r = client.post("/auth/login", json={"usuario": usuario, "senha": senha})
    assert r.status_code == 200, r.text
    client.headers.update({"Authorization": f"Bearer {r.json()['token']}"})
    return client


@pytest.fixture
def app_agencia(tmp_path, monkeypatch):
    """Fábrica: app_agencia(id, usuario, senha) -> TestClient (autenticado)."""
    monkeypatch.setattr(event_log, "_DIR_DADOS", str(tmp_path))

    def _criar(id_agencia: int = 0, usuario: str | None = "ana", senha: str = "senha-ana") -> TestClient:
        from tests.fakes import FakeBroker, FakeBus

        client = TestClient(criar_app(id_agencia=id_agencia, criar_broker=lambda: FakeBroker(FakeBus())))
        if usuario is not None:
            autenticar(client, usuario, senha)
        return client

    return _criar


@pytest.fixture
def cliente(app_agencia):
    """TestClient da agência 0, autenticado como 'ana'."""
    return app_agencia(0)


class Rede:
    """Três agências ligadas pelo mesmo FakeBus. `subir` roda o lifespan (como o
    uvicorn faria) e `derrubar` encerra, deixando as mensagens retidas na fila."""

    def __init__(self) -> None:
        from tests.fakes import FakeBus

        self.bus = FakeBus()
        self._abertos: list[TestClient] = []

    def subir(self, id_agencia: int, usuario: str = "ana", senha: str = "senha-ana") -> TestClient:
        from tests.fakes import FakeBroker

        client = TestClient(criar_app(id_agencia=id_agencia, criar_broker=lambda: FakeBroker(self.bus)))
        client.__enter__()
        self._abertos.append(client)
        autenticar(client, usuario, senha)
        return client

    def derrubar(self, client: TestClient) -> None:
        self._abertos.remove(client)
        client.__exit__(None, None, None)

    def fechar_tudo(self) -> None:
        while self._abertos:
            self.derrubar(self._abertos[-1])


@pytest.fixture
def rede(tmp_path, monkeypatch):
    monkeypatch.setattr(event_log, "_DIR_DADOS", str(tmp_path))
    r = Rede()
    yield r
    r.fechar_tudo()
