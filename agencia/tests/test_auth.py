"""F6: autenticação JWT e autorização de posse."""
from src.services import auth_service


def test_login_valido_retorna_token(app_agencia):
    cliente = app_agencia(0, usuario=None)
    r = cliente.post("/auth/login", json={"usuario": "ana", "senha": "senha-ana"})
    assert r.status_code == 200
    assert "token" in r.json()


def test_login_invalido_retorna_401(app_agencia):
    cliente = app_agencia(0, usuario=None)
    r = cliente.post("/auth/login", json={"usuario": "ana", "senha": "errada"})
    assert r.status_code == 401


def test_rota_protegida_sem_token_retorna_401(app_agencia):
    cliente = app_agencia(0, usuario=None)
    assert cliente.post("/contas", json={"id": 0}).status_code == 401


def test_rota_protegida_com_token_funciona(cliente):
    assert cliente.post("/contas", json={"id": 0}).status_code == 201


def test_token_expirado_retorna_401(app_agencia):
    cliente = app_agencia(0, usuario=None)
    token = auth_service.emitir_token_usuario("ana", minutos=-1)  # já nasce expirado
    cliente.headers.update({"Authorization": f"Bearer {token}"})
    assert cliente.get("/contas/0").status_code == 401


def test_dono_diferente_recebe_403_no_mesmo_app(app_agencia):
    cliente = app_agencia(0, usuario="ana", senha="senha-ana")
    cliente.post("/contas", json={"id": 0, "saldoInicial": 100})

    # troca o token para o de bruno, no MESMO app/estado
    token_bruno = auth_service.emitir_token_usuario("bruno")
    cliente.headers.update({"Authorization": f"Bearer {token_bruno}"})
    assert cliente.post("/contas/0/sacar", json={"valor": 10}).status_code == 403
