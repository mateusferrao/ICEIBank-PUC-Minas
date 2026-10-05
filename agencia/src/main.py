"""Ponto de entrada da agência (app factory).

O mesmo código roda 3 vezes, identificado pela variável de ambiente AGENCIA_ID.
Cada processo mantém seu próprio estado em memória (contas, relógio vetorial,
registro de eventos), guardado em `app.state`.

Executar:
    AGENCIA_ID=0 uvicorn src.main:app --port 4000
    AGENCIA_ID=1 uvicorn src.main:app --port 4001
    AGENCIA_ID=2 uvicorn src.main:app --port 4002
"""
import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import config
from .controllers.creditos_consumer import criar_handler
from .routes import registrar_rotas
from .services.conta_repository import ContaRepository
from .services.event_log import RegistroEventos
from .services.idempotencia import Idempotencia
from .services.mensageria import AioPikaBroker
from .services.vetorial import RelogioVetorial


# RABBITMQ_URL pode vir de um arquivo .env na raiz do repositório (fora do Git).
load_dotenv(Path(__file__).resolve().parents[2] / ".env")


def criar_app(id_agencia: int | None = None, criar_broker=None) -> FastAPI:
    if id_agencia is None:
        id_agencia = int(os.environ.get("AGENCIA_ID", "0"))

    if not any(a["id"] == id_agencia for a in config.AGENCIAS):
        raise RuntimeError(f"Agência {id_agencia} não configurada em config.py")

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        # Conecta ao broker e começa a consumir a fila desta agência.
        await _app.state.broker.iniciar(id_agencia, _app.state.handler_credito)
        print(f"[Agência {id_agencia}] pronta")
        yield
        await _app.state.broker.fechar()

    app = FastAPI(title=f"ICEIBank - Agência {id_agencia}", lifespan=lifespan)

    # O frontend é servido de outra porta, então preciso do CORS para o navegador
    # conseguir chamar a API.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Estado por processo (em memória).
    app.state.id_agencia = id_agencia
    app.state.relogio = RelogioVetorial(id_agencia, config.NUMERO_AGENCIAS)
    app.state.registro = RegistroEventos(f"agencia-{id_agencia}")
    # O relógio é reconstruído a partir do log (que sobrevive ao reinício).
    for evento in app.state.registro.ler_eventos():
        vetor = evento.get("timestampVetorial")
        if vetor is not None and len(vetor) == config.NUMERO_AGENCIAS:
            app.state.relogio.restaurar(vetor)
    app.state.contas = ContaRepository()
    app.state.idempotencia = Idempotencia()
    # O broker só conecta no lifespan. A fábrica `criar_broker` existe para os
    # testes trocarem o RabbitMQ por um broker em memória.
    app.state.broker = (criar_broker or AioPikaBroker)()
    app.state.handler_credito = criar_handler(app)

    registrar_rotas(app)
    return app


app = criar_app()
