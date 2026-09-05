"""F3 — API de contas: criar, consultar, depositar, sacar (sem auth ainda)."""


def test_criar_conta_na_agencia_certa(cliente):
    r = cliente.post("/contas", json={"id": 0, "nomeAluno": "Ana", "saldoInicial": 100})
    assert r.status_code == 201
    corpo = r.json()
    assert corpo["id"] == 0
    assert corpo["saldo"] == 100.0


def test_recusa_conta_de_outra_agencia(cliente):
    # conta 1 pertence à agência 1, não à 0
    r = cliente.post("/contas", json={"id": 1, "nomeAluno": "Bruno"})
    assert r.status_code == 400


def test_conta_duplicada_retorna_409(cliente):
    cliente.post("/contas", json={"id": 0, "nomeAluno": "Ana"})
    r = cliente.post("/contas", json={"id": 0, "nomeAluno": "Ana"})
    assert r.status_code == 409


def test_consultar_conta_inexistente_retorna_404(cliente):
    assert cliente.get("/contas/0").status_code == 404


def test_deposito_soma_ao_saldo(cliente):
    cliente.post("/contas", json={"id": 0, "saldoInicial": 100})
    r = cliente.post("/contas/0/depositar", json={"valor": 25.50})
    assert r.status_code == 200
    assert r.json()["saldo"] == 125.50


def test_saque_debita_saldo(cliente):
    cliente.post("/contas", json={"id": 0, "saldoInicial": 100})
    r = cliente.post("/contas/0/sacar", json={"valor": 30})
    assert r.status_code == 200
    assert r.json()["saldo"] == 70.0


def test_saque_maior_que_saldo_retorna_400(cliente):
    cliente.post("/contas", json={"id": 0, "saldoInicial": 10})
    r = cliente.post("/contas/0/sacar", json={"valor": 50})
    assert r.status_code == 400
    assert "insuficiente" in r.json()["detail"].lower()


def test_dinheiro_sem_erro_de_ponto_flutuante(cliente):
    # 0.1 + 0.2 deve dar exatamente 0.30 (armazenado em centavos)
    cliente.post("/contas", json={"id": 0, "saldoInicial": 0.1})
    r = cliente.post("/contas/0/depositar", json={"valor": 0.2})
    assert r.json()["saldo"] == 0.30


def test_health_reporta_agencia_e_contagem(cliente):
    cliente.post("/contas", json={"id": 0})
    r = cliente.get("/health")
    assert r.status_code == 200
    assert r.json()["agencia"] == 0
    assert r.json()["contas"] == 1
