"""Emite e valida os tokens JWT (Parte F).

São dois tipos de token, os dois assinados com o mesmo segredo:
- "usuario": identifica uma pessoa logada (o campo `sub` é o username). É o que as
  requisições do frontend usam.
- "svc" (serviço): identifica uma agência falando com outra na chamada interna
  creditar-remoto. Separar a identidade de serviço da identidade do usuário deixa
  claro que o crédito remoto é uma confiança entre sistemas, e não uma ação de um
  usuário específico.
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


def emitir_token_servico(id_agencia: int) -> str:
    payload = {
        "sub": f"agencia-{id_agencia}",
        "tipo": "svc",
        "iat": _agora(),
        "exp": _agora() + timedelta(seconds=config.TOKEN_SERVICO_SEGUNDOS),
    }
    return jwt.encode(payload, config.JWT_SECRET, algorithm=config.JWT_ALGORITMO)


def decodificar_token(token: str) -> dict | None:
    """Devolve o conteúdo do token se ele for válido, ou None se for inválido ou
    estiver expirado."""
    try:
        return jwt.decode(token, config.JWT_SECRET, algorithms=[config.JWT_ALGORITMO])
    except jwt.PyJWTError:
        return None
