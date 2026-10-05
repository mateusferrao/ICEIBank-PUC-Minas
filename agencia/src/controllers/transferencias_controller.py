"""Controller de transferências (Parte D do Sprint 1, mensageria no Sprint 2) e
idempotência (funcionalidade adicional do Sprint 1).

A transferência local continua igual. Na transferência entre agências, o Sprint 1
chamava a outra agência por REST. Agora a origem debita, publica um evento na
exchange do RabbitMQ e responde. Quem aplica o crédito é a agência de destino, de
forma assíncrona, quando consumir a mensagem (ver creditos_consumer.py).

Por isso a resposta 200 significa só "o broker aceitou a mensagem". Se a
publicação falhar, o débito é estornado e a resposta é 503.

A idempotência segue valendo: o cliente manda um cabeçalho `Idempotency-Key`, e a
chave vira o `messageId` da mensagem. Um reenvio com a mesma chave não debita nem
publica de novo, e o consumidor ignora um `messageId` já creditado.
"""
import uuid
from typing import Annotated

from fastapi import Header, HTTPException, Request

from .. import config
from ..models import TransferenciaIn, reais_para_centavos
from ..security import UsuarioAutenticado, garantir_posse
from ..services.idempotencia import Idempotencia
from ..services.mensageria import FalhaPublicacao, routing_key_creditar

ChaveIdempotencia = Annotated[str | None, Header(alias="Idempotency-Key")]


def _estornar(estado, origem: dict, valor_centavos: int, detalhes: dict, motivo: str) -> None:
    """Desfaz o débito local e deixa o estorno registrado no log."""
    origem["saldo_centavos"] += valor_centavos
    estado.registro.registrar(
        "TRANSFERENCIA_ESTORNADA", estado.relogio.evento_local(), {**detalhes, "motivo": motivo}
    )


async def transferir(
    request: Request,
    body: TransferenciaIn,
    usuario: UsuarioAutenticado,
    idempotency_key: ChaveIdempotencia = None,
) -> dict:
    estado = request.app.state
    store: Idempotencia = estado.idempotencia

    # Reenvio de uma chave que já foi vista
    if idempotency_key:
        registro = store.obter(idempotency_key)
        if registro is not None:
            if registro["status"] == Idempotencia.EM_ANDAMENTO:
                raise HTTPException(status_code=409, detail="Transferência com esta chave ainda em andamento.")
            if registro["status"] == Idempotencia.CONCLUIDA:
                estado.registro.registrar(
                    "TRANSFERENCIA_IDEMPOTENTE_REPETIDA", estado.relogio.evento_local(),
                    {"idempotencyKey": idempotency_key},
                )
                return registro["resposta"]

    # Validações. Elas dão sempre o mesmo resultado, então não precisam ser guardadas.
    if body.idOrigem == body.idDestino:
        raise HTTPException(status_code=400, detail="Origem e destino devem ser contas diferentes.")
    origem = estado.contas.obter(body.idOrigem)
    if origem is None:
        raise HTTPException(status_code=404, detail="Conta de origem não encontrada nesta agência.")
    garantir_posse(origem, usuario)

    valor_centavos = reais_para_centavos(body.valor)
    if origem["saldo_centavos"] < valor_centavos:
        raise HTTPException(status_code=400, detail="Saldo insuficiente.")

    message_id = idempotency_key or str(uuid.uuid4())
    if idempotency_key:
        store.marcar_em_andamento(idempotency_key)
    try:
        resposta = await _executar(estado, body, origem, valor_centavos, message_id)
    except BaseException:
        # Nada foi concluído: libera a chave para o cliente poder tentar de novo.
        if idempotency_key:
            store.remover(idempotency_key)
        raise
    if idempotency_key:
        store.concluir(idempotency_key, resposta)
    return resposta


async def _executar(estado, body: TransferenciaIn, origem: dict, valor_centavos: int, message_id: str) -> dict:
    detalhes = {
        "idOrigem": body.idOrigem, "idDestino": body.idDestino, "valor": body.valor, "messageId": message_id,
    }
    agencia_destino = config.agencia_responsavel(body.idDestino)

    # Débito local (acontece sempre)
    vetor_debito = estado.relogio.evento_local()
    origem["saldo_centavos"] -= valor_centavos
    estado.registro.registrar("TRANSFERENCIA_DEBITO", vetor_debito, detalhes)

    # Crédito na mesma agência
    if agencia_destino == estado.id_agencia:
        destino = estado.contas.obter(body.idDestino)
        if destino is None:
            _estornar(estado, origem, valor_centavos, detalhes, "conta de destino nao encontrada")
            raise HTTPException(status_code=404, detail="Conta de destino não encontrada.")
        vetor_credito = estado.relogio.evento_local()
        destino["saldo_centavos"] += valor_centavos
        estado.registro.registrar("TRANSFERENCIA_CREDITO", vetor_credito, detalhes)
        return {"mensagem": "Transferência concluída (mesma agência)."}

    # Entre agências: publica o evento e deixa o destino consumir quando puder.
    vetor_envio = estado.relogio.ao_enviar()
    mensagem = {
        "messageId": message_id,
        "idConta": body.idDestino,
        "valorCentavos": valor_centavos,
        "vetorEnvio": vetor_envio,
        "origemAgencia": estado.id_agencia,
        "idOrigem": body.idOrigem,
        "idDestino": body.idDestino,
    }
    try:
        await estado.broker.publicar(routing_key_creditar(agencia_destino), mensagem, message_id)
    except FalhaPublicacao as erro:
        _estornar(estado, origem, valor_centavos, detalhes, f"falha ao publicar: {erro}")
        raise HTTPException(
            status_code=503,
            detail="Broker indisponível. A transferência não foi realizada e o débito foi estornado.",
        ) from erro
    estado.registro.registrar("TRANSFERENCIA_PUBLICADA", vetor_envio, {**detalhes, "agenciaDestino": agencia_destino})
    return {"mensagem": "Transferência publicada para a agência de destino (entrega assíncrona)."}
