"""Consumidor de créditos vindos de outras agências (Sprint 2, Parte C).

Substitui a rota `creditar-remoto` do Sprint 1. Quem entrega a mensagem é o
broker, não uma chamada HTTP, então aqui não existe token JWT: a mensagem só
chega à fila da agência se alguém conseguiu publicar na exchange (ver a resposta
da pergunta 3 da Parte C no RESPOSTAS.md).

Para cada mensagem recebida:
1. atualiza o relógio vetorial (regra 3), porque receber é um evento;
2. ignora a mensagem se esse `messageId` já foi creditado (o broker entrega pelo
   menos uma vez, então pode repetir);
3. confere se a conta pertence a esta agência e se existe;
4. credita e registra o evento.
"""
from fastapi import FastAPI

from .. import config
from ..models import centavos_para_reais
from ..services.idempotencia import Idempotencia


def criar_handler(app: FastAPI):
    async def handler(mensagem: dict) -> None:
        estado = app.state
        id_conta = mensagem["idConta"]
        centavos = mensagem["valorCentavos"]
        message_id = mensagem["messageId"]
        vetor = estado.relogio.ao_receber(mensagem["vetorEnvio"])
        detalhes = {
            "idConta": id_conta,
            "valor": centavos_para_reais(centavos),
            "origemAgencia": mensagem["origemAgencia"],
            "messageId": message_id,
        }

        chave = f"credito:{message_id}"
        anterior = estado.idempotencia.obter(chave)
        if anterior is not None and anterior["status"] == Idempotencia.CONCLUIDA:
            estado.registro.registrar("CREDITO_REMOTO_DUPLICADO_IGNORADO", vetor, detalhes)
            return

        if config.agencia_responsavel(id_conta) != estado.id_agencia:
            estado.registro.registrar(
                "CREDITO_REMOTO_FALHOU", vetor, {**detalhes, "motivo": "conta nao pertence a esta agencia"}
            )
            return

        conta = estado.contas.obter(id_conta)
        if conta is None:
            estado.registro.registrar(
                "CREDITO_REMOTO_FALHOU", vetor, {**detalhes, "motivo": "conta nao encontrada"}
            )
            return

        conta["saldo_centavos"] += centavos
        estado.registro.registrar("TRANSFERENCIA_CREDITO_REMOTO", vetor, detalhes)
        estado.idempotencia.concluir(chave, {"mensagem": "Crédito remoto aplicado."})

    return handler
