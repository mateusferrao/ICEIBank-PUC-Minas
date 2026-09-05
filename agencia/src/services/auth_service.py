"""Emissão e validação de tokens JWT (Parte F).

Dois tipos de token, ambos assinados com o mesmo segredo compartilhado:
- "usuario": identifica uma pessoa autenticada (claim `sub` = username). Usado
  pelas requisições vindas do frontend.
- "svc" (serviço): identifica uma agência falando com outra na chamada interna
  creditar-remoto. Separar a identidade de serviço da identidade de usuário deixa
  claro que o crédito remoto é uma confiança sistema-a-sistema, não uma ação de
  um usuário específico.
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
    """Devolve o payload se o token for válido; None se inválido ou expirado."""
    try:
        return jwt.decode(token, config.JWT_SECRET, algorithms=[config.JWT_ALGORITMO])
    except jwt.PyJWTError:
        return None
