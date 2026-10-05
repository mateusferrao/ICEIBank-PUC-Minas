"""Mensageria entre agências (Sprint 2, Parte C), com RabbitMQ via aio-pika.

Topologia (a mesma do roteiro):
- exchange `iceibank.eventos`, do tipo topic e durável: é nela que as agências
  publicam;
- uma fila durável por agência (`fila-agencia-N`), ligada à exchange pela routing
  key `agencia.N.creditar`;
- uma exchange de mensagens mortas (`iceibank.dlx`) e uma fila `fila-agencia-N.dlq`
  por agência, para onde vão as mensagens que o consumidor desiste de processar
  (funcionalidade adicional).

Todas as agências declaram TODAS as filas ao subir. Assim a mensagem para uma
agência que ainda nunca subiu também é retida, em vez de ser descartada por falta
de fila.

O consumidor roda no mesmo event loop do FastAPI (iniciado no lifespan). Isso
mantém a premissa do projeto: o saldo é alterado sem `await` no meio, então não
precisa de lock.

A URL do broker vem da variável de ambiente RABBITMQ_URL e só é lida quando a
agência conecta (`iniciar`), nunca ao importar o módulo.
"""
import asyncio
import json
import os
from typing import Awaitable, Callable, Protocol

import aio_pika

from .. import config

EXCHANGE = "iceibank.eventos"
DLX = "iceibank.dlx"

# O handler recebe a mensagem e o número da tentativa (0 na primeira entrega).
Handler = Callable[[dict, int], Awaitable[None]]

# Funcionalidade adicional (DLQ): tentativas antes de mandar para a fila de mortas.
MAX_TENTATIVAS = 3
ESPERA_ENTRE_TENTATIVAS = float(os.environ.get("RETRY_ESPERA_SEGUNDOS", "1"))


class FalhaPublicacao(Exception):
    """O broker não aceitou a mensagem (fora do ar, sem rota ou timeout)."""


class CreditoRejeitado(Exception):
    """O consumidor não conseguiu aplicar o crédito (ex.: conta não encontrada).

    `permanente=True` indica que repetir não adianta (ex.: a conta não pertence a
    esta agência), e a mensagem vai direto para a DLQ."""

    def __init__(self, motivo: str, permanente: bool = False) -> None:
        super().__init__(motivo)
        self.motivo = motivo
        self.permanente = permanente


async def processar_com_politica(corpo: dict, tentativas: int, handler: Handler, republicar, enviar_dlq) -> None:
    """Política de retry + DLQ, compartilhada pelo broker real e pelo de teste.

    - handler OK: nada mais a fazer (a mensagem é confirmada);
    - CreditoRejeitado: republica com tentativa+1 até MAX_TENTATIVAS, depois DLQ;
      se for permanente, vai direto para a DLQ;
    - qualquer outro erro (mensagem inválida): vai direto para a DLQ.
    """
    try:
        await handler(corpo, tentativas)
        return
    except CreditoRejeitado as erro:
        motivo, permanente = erro.motivo, erro.permanente
    except Exception as erro:  # noqa: BLE001
        motivo, permanente = f"mensagem invalida: {erro!r}", True
    if not permanente and tentativas + 1 < MAX_TENTATIVAS:
        await republicar(tentativas + 1)
    else:
        await enviar_dlq(motivo)


def routing_key_creditar(id_agencia: int) -> str:
    return f"agencia.{id_agencia}.creditar"


def nome_fila(id_agencia: int) -> str:
    return f"fila-agencia-{id_agencia}"


def routing_key_dlq(id_agencia: int) -> str:
    return f"agencia.{id_agencia}.dlq"


def nome_dlq(id_agencia: int) -> str:
    return f"fila-agencia-{id_agencia}.dlq"


class Broker(Protocol):
    async def iniciar(self, id_agencia: int, handler: Handler) -> None: ...

    async def publicar(self, routing_key: str, mensagem: dict, message_id: str) -> None: ...

    async def fechar(self) -> None: ...


class AioPikaBroker:
    def __init__(self, url: str | None = None) -> None:
        self._url = url
        self._conexao: aio_pika.abc.AbstractRobustConnection | None = None
        self._canal: aio_pika.abc.AbstractChannel | None = None
        self._exchange: aio_pika.abc.AbstractExchange | None = None

    async def iniciar(self, id_agencia: int, handler: Handler) -> None:
        url = self._url or os.environ.get("RABBITMQ_URL")
        if not url:
            raise RuntimeError(
                "Defina a variável de ambiente RABBITMQ_URL com a URL AMQP da sua instância "
                "CloudAMQP antes de iniciar a agência."
            )
        self._conexao = await aio_pika.connect_robust(url)
        # Canal com publisher confirms (padrão do aio-pika): publicar só termina
        # quando o broker confirma que recebeu a mensagem.
        self._canal = await self._conexao.channel()
        await self._canal.set_qos(prefetch_count=1)
        self._exchange = await self._declarar_topologia()
        fila = await self._canal.get_queue(nome_fila(id_agencia), ensure=False)
        await fila.consume(self._criar_callback(handler))
        print(f"[Agência {id_agencia}] consumindo {nome_fila(id_agencia)}")

    async def _declarar_topologia(self) -> aio_pika.abc.AbstractExchange:
        canal = self._canal
        exchange = await canal.declare_exchange(EXCHANGE, aio_pika.ExchangeType.TOPIC, durable=True)
        dlx = await canal.declare_exchange(DLX, aio_pika.ExchangeType.DIRECT, durable=True)
        for id_agencia in range(config.NUMERO_AGENCIAS):
            fila = await canal.declare_queue(
                nome_fila(id_agencia),
                durable=True,
                arguments={
                    "x-dead-letter-exchange": DLX,
                    "x-dead-letter-routing-key": routing_key_dlq(id_agencia),
                },
            )
            await fila.bind(exchange, routing_key_creditar(id_agencia))
            dlq = await canal.declare_queue(nome_dlq(id_agencia), durable=True)
            await dlq.bind(dlx, routing_key_dlq(id_agencia))
        return exchange

    def _criar_callback(self, handler: Handler):
        async def callback(mensagem: aio_pika.abc.AbstractIncomingMessage) -> None:
            tentativas = int((mensagem.headers or {}).get("x-tentativas", 0))

            async def republicar(proxima: int) -> None:
                # Mesma mensagem, de volta à exchange, com o contador incrementado.
                await asyncio.sleep(ESPERA_ENTRE_TENTATIVAS)
                nova = aio_pika.Message(
                    body=mensagem.body,
                    content_type=mensagem.content_type,
                    delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                    message_id=mensagem.message_id,
                    headers={"x-tentativas": proxima},
                )
                await self._exchange.publish(nova, routing_key=mensagem.routing_key, mandatory=True)
                await mensagem.ack()

            async def enviar_dlq(motivo: str) -> None:
                print(f"[mensageria] {mensagem.message_id} vai para a DLQ: {motivo}")
                # nack sem requeue: o broker encaminha para a DLX da fila (iceibank.dlx)
                # e a mensagem fica em fila-agencia-N.dlq.
                await mensagem.nack(requeue=False)

            try:
                corpo = json.loads(mensagem.body.decode("utf-8"))
            except ValueError:
                await enviar_dlq("mensagem invalida: JSON malformado")
                return
            await processar_com_politica(corpo, tentativas, handler, republicar, enviar_dlq)
            if not mensagem.processed:
                await mensagem.ack()

        return callback

    async def publicar(self, routing_key: str, mensagem: dict, message_id: str) -> None:
        if self._exchange is None:
            raise FalhaPublicacao("agência ainda não conectada ao broker")
        corpo = aio_pika.Message(
            body=json.dumps(mensagem).encode("utf-8"),
            content_type="application/json",
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            message_id=message_id,
        )
        try:
            await self._exchange.publish(corpo, routing_key=routing_key, mandatory=True, timeout=5)
        except Exception as erro:  # noqa: BLE001
            raise FalhaPublicacao(str(erro)) from erro

    async def fechar(self) -> None:
        if self._conexao is not None:
            await self._conexao.close()
            self._conexao = None
