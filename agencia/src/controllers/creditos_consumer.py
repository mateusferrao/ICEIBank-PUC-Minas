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

Se não der para creditar, o handler registra `CREDITO_REMOTO_FALHOU` e levanta
`CreditoRejeitado`. O broker repete a entrega até MAX_TENTATIVAS e depois manda a
mensagem para a dead-letter queue (`CREDITO_REMOTO_DLQ`). O débito da origem NÃO é
estornado: a mensagem fica guardada na DLQ para compensação manual (a compensação
automática é assunto do Sprint 4).
"""
from fastapi import FastAPI

from .. import config
from ..models import centavos_para_reais
from ..services.idempotencia import Idempotencia
from ..services.mensageria import MAX_TENTATIVAS, CreditoRejeitado


def criar_handler(app: FastAPI):
    def _rejeitar(estado, vetor, detalhes, tentativa, motivo, permanente=False):
        detalhes = {**detalhes, "motivo": motivo, "tentativa": tentativa + 1}
        estado.registro.registrar("CREDITO_REMOTO_FALHOU", vetor, detalhes)
        if permanente or tentativa + 1 >= MAX_TENTATIVAS:
            estado.registro.registrar("CREDITO_REMOTO_DLQ", vetor, detalhes)
        raise CreditoRejeitado(motivo, permanente)

    async def handler(mensagem: dict, tentativa: int = 0) -> None:
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
            _rejeitar(estado, vetor, detalhes, tentativa, "conta nao pertence a esta agencia", permanente=True)

        conta = estado.contas.obter(id_conta)
        if conta is None:
            _rejeitar(estado, vetor, detalhes, tentativa, "conta nao encontrada")

        conta["saldo_centavos"] += centavos
        estado.registro.registrar("TRANSFERENCIA_CREDITO_REMOTO", vetor, detalhes)
        estado.idempotencia.concluir(chave, {"mensagem": "Crédito remoto aplicado."})

    return handler
