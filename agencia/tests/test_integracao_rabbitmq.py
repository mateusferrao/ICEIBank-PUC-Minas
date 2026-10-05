"""Integração com o RabbitMQ de verdade (CloudAMQP).

Só roda se RABBITMQ_URL estiver definida (variável de ambiente ou .env na raiz do
repositório). Sem ela, o teste é pulado. Ele usa a fila da agência 2, então não
rode junto com a agência 2 de verdade consumindo a mesma fila.
"""
import asyncio
import os
import uuid

import pytest

import src.main  # noqa: F401  (carrega o .env, se existir)
from src.services.mensageria import (
    EXCHANGE,
    AioPikaBroker,
    nome_dlq,
    nome_fila,
    routing_key_creditar,
)

pytestmark = pytest.mark.skipif(not os.environ.get("RABBITMQ_URL"), reason="RABBITMQ_URL não definida")


def test_publica_e_consome_pela_exchange_real():
    async def cenario():
        recebidas: list[dict] = []
        chegou = asyncio.Event()

        async def handler(mensagem: dict) -> None:
            recebidas.append(mensagem)
            chegou.set()

        broker = AioPikaBroker()
        await broker.iniciar(2, handler)
        try:
            # topologia durável existe no broker
            canal = broker._canal
            fila = await canal.declare_queue(nome_fila(2), passive=True)
            assert fila.name == nome_fila(2)
            await canal.declare_queue(nome_dlq(2), passive=True)
            await canal.declare_exchange(EXCHANGE, passive=True)

            message_id = str(uuid.uuid4())
            await broker.publicar(routing_key_creditar(2), {"messageId": message_id, "teste": True}, message_id)
            await asyncio.wait_for(chegou.wait(), timeout=15)
            assert recebidas[0]["messageId"] == message_id
        finally:
            await broker.fechar()

    asyncio.run(cenario())
