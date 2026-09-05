"""Ponto de entrada da agência (app factory).

O mesmo código roda 3 vezes, identificado pela variável de ambiente AGENCIA_ID.
Cada processo mantém seu próprio estado em memória (contas, relógio de Lamport,
registro de eventos), guardado em `app.state`.

Executar:
    AGENCIA_ID=0 uvicorn src.main:app --port 4000
    AGENCIA_ID=1 uvicorn src.main:app --port 4001
    AGENCIA_ID=2 uvicorn src.main:app --port 4002
"""
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import config
from .routes import registrar_rotas
from .services.conta_repository import ContaRepository
from .services.event_log import RegistroEventos
from .services.lamport import RelogioLamport


def criar_app(id_agencia: int | None = None) -> FastAPI:
    if id_agencia is None:
        id_agencia = int(os.environ.get("AGENCIA_ID", "0"))

    if not any(a["id"] == id_agencia for a in config.AGENCIAS):
        raise RuntimeError(f"Agência {id_agencia} não configurada em config.py")

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        print(f"[Agência {id_agencia}] pronta")
        yield

    app = FastAPI(title=f"ICEIBank - Agência {id_agencia}", lifespan=lifespan)

    # Frontend estático é servido de outra origem/porta -> CORS é necessário
    # para o navegador conseguir chamar a API.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Estado por processo (em memória).
    app.state.id_agencia = id_agencia
    app.state.relogio = RelogioLamport()
    app.state.registro = RegistroEventos(f"agencia-{id_agencia}")
    app.state.contas = ContaRepository()

    registrar_rotas(app)
    return app


app = criar_app()
