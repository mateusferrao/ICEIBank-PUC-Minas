"""Fixtures de teste: cria um app de agência isolado, com o event log apontando
para um diretório temporário (para não sujar agencia/data/)."""
import pytest
from fastapi.testclient import TestClient

import src.services.event_log as event_log
from src.main import criar_app


@pytest.fixture
def app_agencia(tmp_path, monkeypatch):
    """Fábrica de app: app_agencia(id) devolve um TestClient da agência `id`."""
    monkeypatch.setattr(event_log, "_DIR_DADOS", str(tmp_path))

    def _criar(id_agencia: int = 0) -> TestClient:
        return TestClient(criar_app(id_agencia=id_agencia))

    return _criar


@pytest.fixture
def cliente(app_agencia):
    """TestClient da agência 0 (atalho para os testes mais comuns)."""
    return app_agencia(0)
