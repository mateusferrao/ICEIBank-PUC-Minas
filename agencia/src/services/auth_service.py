"""Emite e valida os tokens JWT (Parte F).

O token é do tipo "usuario": identifica uma pessoa logada (o campo `sub` é o
username) e é o que as requisições do frontend usam. No Sprint 1 existia também um
token de serviço para a chamada REST entre agências. Ele saiu no Sprint 2, porque o
crédito remoto agora chega por mensagem no RabbitMQ, sem passar pela API HTTP.
"""
from datetime import datetime, timedelta, timezone

import jwt

from .. import config


def _agora() -> datetime:
    return datetime.now(tz=timezone.utc)


def emitir_token_usuario(usuario: str, minutos: int | None = None) -> str:
    if minutos is None:
        minutos = config.TOKEN_USUARIO_MINUTOS
    payload = {
        "sub": usuario,
        "tipo": "usuario",
        "iat": _agora(),
        "exp": _agora() + timedelta(minutes=minutos),
    }
    return jwt.encode(payload, config.JWT_SECRET, algorithm=config.JWT_ALGORITMO)


def decodificar_token(token: str) -> dict | None:
    """Devolve o conteúdo do token se ele for válido, ou None se for inválido ou
    estiver expirado."""
    try:
        return jwt.decode(token, config.JWT_SECRET, algorithms=[config.JWT_ALGORITMO])
    except jwt.PyJWTError:
        return None
