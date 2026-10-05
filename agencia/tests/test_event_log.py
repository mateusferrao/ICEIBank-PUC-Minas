"""F2: registro de eventos em .jsonl."""
import json

from src.services.event_log import RegistroEventos


def test_registrar_grava_linha_json_com_campos_esperados(tmp_path, monkeypatch):
    monkeypatch.setattr("src.services.event_log._DIR_DADOS", str(tmp_path))
    registro = RegistroEventos("agencia-teste")

    evento = registro.registrar("DEPOSITO", [0, 5, 0], {"id": 0, "valor": 25})

    assert evento["agencia"] == "agencia-teste"
    assert evento["tipo"] == "DEPOSITO"
    assert evento["timestampVetorial"] == [0, 5, 0]
    assert "horaParede" in evento
    assert evento["detalhes"] == {"id": 0, "valor": 25}

    linhas = (tmp_path / "eventos-agencia-teste.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(linhas) == 1
    gravado = json.loads(linhas[0])
    assert gravado["tipo"] == "DEPOSITO"
    assert gravado["timestampVetorial"] == [0, 5, 0]


def test_registrar_faz_append(tmp_path, monkeypatch):
    monkeypatch.setattr("src.services.event_log._DIR_DADOS", str(tmp_path))
    registro = RegistroEventos("agencia-teste")
    registro.registrar("CRIAR_CONTA", [1, 0, 0], {"id": 0})
    registro.registrar("SAQUE", [2, 0, 0], {"id": 0, "valor": 10})

    linhas = (tmp_path / "eventos-agencia-teste.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(linhas) == 2
