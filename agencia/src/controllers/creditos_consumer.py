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


def _inteiro(valor) -> bool:
    return isinstance(valor, int) and not isinstance(valor, bool)


def criar_handler(app: FastAPI):
    def _rejeitar(estado, vetor, detalhes, tentativa, motivo, permanente=False):
        detalhes = {**detalhes, "motivo": motivo, "tentativa": tentativa + 1}
        estado.registro.registrar("CREDITO_REMOTO_FALHOU", vetor, detalhes)
        if permanente or tentativa + 1 >= MAX_TENTATIVAS:
            estado.registro.registrar("CREDITO_REMOTO_DLQ", estado.relogio.evento_local(), detalhes)
        raise CreditoRejeitado(motivo, permanente)

    async def handler(mensagem: dict, tentativa: int = 0) -> None:
        estado = app.state
        id_conta = mensagem["idConta"]
        centavos = mensagem["valorCentavos"]
        message_id = mensagem["messageId"]
        detalhes = {
            "idConta": id_conta,
            "valor": centavos_para_reais(centavos) if _inteiro(centavos) else centavos,
            "origemAgencia": mensagem["origemAgencia"],
            "messageId": message_id,
        }
        vetor_recebido = mensagem["vetorEnvio"]
        # Quem publica na exchange não passa por JWT, então o conteúdo é validado aqui.
        if (
            not isinstance(vetor_recebido, list)
            or len(vetor_recebido) != config.NUMERO_AGENCIAS
            or not all(_inteiro(x) and x >= 0 for x in vetor_recebido)
        ):
            vetor = estado.relogio.evento_local()  # nao da para confiar no vetor recebido
            _rejeitar(estado, vetor, detalhes, tentativa, "vetor invalido", permanente=True)
        vetor = estado.relogio.ao_receber(vetor_recebido)
        if not _inteiro(centavos) or centavos <= 0:
            _rejeitar(estado, vetor, detalhes, tentativa, "valor invalido", permanente=True)

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
