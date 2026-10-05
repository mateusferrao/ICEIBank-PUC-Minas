"""Broker em memória para os testes (sem rede, sem RabbitMQ).

Imita o que importa do RabbitMQ para este projeto:
- uma "fila" por agência, que retém as mensagens enquanto não há consumidor
  (é o que acontece quando a agência está fora do ar);
- entrega imediata quando a agência de destino está consumindo;
- falha de publicação injetável (broker indisponível).

Várias agências compartilham o mesmo `FakeBus`, como compartilhariam o broker.
"""
from src.services.mensageria import FalhaPublicacao, processar_com_politica


class FakeBus:
    def __init__(self, numero_agencias: int = 3) -> None:
        self.handlers: dict[int, object] = {}
        self.filas: dict[int, list[dict]] = {i: [] for i in range(numero_agencias)}
        self.dlq: dict[int, list[dict]] = {i: [] for i in range(numero_agencias)}
        self.publicadas: list[tuple[str, dict]] = []
        self.publicacao_indisponivel = False


    async def entregar(self, id_agencia: int, mensagem: dict) -> None:
        """Entrega a mensagem ao consumidor da agência, com a mesma política de
        retry + DLQ do broker real."""
        handler = self.handlers[id_agencia]
        tentativas = 0

        async def republicar(proxima: int) -> None:
            nonlocal tentativas
            tentativas = proxima

        async def enviar_dlq(motivo: str) -> None:
            self.dlq[id_agencia].append(mensagem)

        while True:
            antes = tentativas
            await processar_com_politica(mensagem, tentativas, handler, republicar, enviar_dlq)
            if tentativas == antes:  # não houve republicação: terminou (ack ou DLQ)
                return


class FakeBroker:
    def __init__(self, bus: FakeBus) -> None:
        self.bus = bus
        self._id_agencia: int | None = None

    async def iniciar(self, id_agencia: int, handler) -> None:
        self._id_agencia = id_agencia
        self.bus.handlers[id_agencia] = handler
        pendentes, self.bus.filas[id_agencia] = self.bus.filas[id_agencia], []
        for mensagem in pendentes:
            await self.bus.entregar(id_agencia, mensagem)

    async def publicar(self, routing_key: str, mensagem: dict, message_id: str) -> None:
        if self.bus.publicacao_indisponivel:
            raise FalhaPublicacao("broker indisponivel")
        id_destino = int(routing_key.split(".")[1])
        self.bus.publicadas.append((routing_key, mensagem))
        handler = self.bus.handlers.get(id_destino)
        if handler is None:
            self.bus.filas[id_destino].append(mensagem)
        else:
            await self.bus.entregar(id_destino, mensagem)

    async def fechar(self) -> None:
        if self._id_agencia is not None:
            self.bus.handlers.pop(self._id_agencia, None)
