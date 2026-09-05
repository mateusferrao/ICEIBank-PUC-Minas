"""Controller de autenticação (Parte F): login e emissão de token JWT."""
from fastapi import HTTPException

from .. import config
from ..models import LoginIn
from ..services import auth_service


async def login(body: LoginIn) -> dict:
    usuario = config.USUARIOS.get(body.usuario)
    if usuario is None or not config.verificar_senha(body.senha, usuario["senha_hash"]):
        raise HTTPException(status_code=401, detail="Usuário ou senha inválidos.")

    token = auth_service.emitir_token_usuario(body.usuario)
    return {
        "token": token,
        "tipo": "Bearer",
        "usuario": body.usuario,
        "expira_em_minutos": config.TOKEN_USUARIO_MINUTOS,
    }
