"""Dependências de segurança do FastAPI (Parte F).

- get_current_user: exige um token de usuário válido e devolve o username.
- require_service_token: exige um token de serviço válido (chamada entre agências).
- garantir_posse: é a autorização, a operação só vale para o dono da conta.

Token faltando, inválido ou expirado sempre resulta em HTTP 401.
"""
from typing import Annotated

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .services import auth_service

# Uso auto_error=False para eu mesmo retornar 401 (o padrão do HTTPBearer é 403
# quando o cabeçalho falta).
_bearer = HTTPBearer(auto_error=False)

_CredOpcional = Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)]


def _decodificar_ou_401(cred: HTTPAuthorizationCredentials | None, tipo_esperado: str) -> dict:
    if cred is None:
        raise HTTPException(status_code=401, detail="Token ausente.")
    payload = auth_service.decodificar_token(cred.credentials)
    if payload is None:
        raise HTTPException(status_code=401, detail="Token inválido ou expirado.")
    if payload.get("tipo") != tipo_esperado:
        raise HTTPException(status_code=401, detail="Tipo de token incorreto para esta rota.")
    return payload


async def get_current_user(cred: _CredOpcional) -> str:
    return _decodificar_ou_401(cred, "usuario")["sub"]


async def require_service_token(cred: _CredOpcional) -> dict:
    return _decodificar_ou_401(cred, "svc")


def garantir_posse(conta: dict, usuario: str) -> None:
    if conta.get("dono") != usuario:
        raise HTTPException(
            status_code=403,
            detail="Acesso negado: esta conta não pertence ao usuário autenticado.",
        )


UsuarioAutenticado = Annotated[str, Depends(get_current_user)]
TokenServico = Annotated[dict, Depends(require_service_token)]
