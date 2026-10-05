"""Funcionalidade adicional do Sprint 2: dead-letter queue com retry.

Quando o crédito não pode ser aplicado (conta não encontrada, por exemplo), o
consumidor tenta de novo até 3 vezes. Esgotadas as tentativas, a mensagem vai
para a DLQ da agência em vez de ser descartada. Mensagem inválida vai direto.
"""
import asyncio

from src.services.mensageria import MAX_TENTATIVAS, CreditoRejeitado, processar_com_politica


def _rodar(handler, tentativas_iniciais=0):
    """Executa a política e devolve (republicacoes, dlq)."""
    republicadas: list[int] = []
    dlq: list[str] = []

    async def republicar(tentativa):
        republicadas.append(tentativa)

    async def enviar_dlq(motivo):
        dlq.append(motivo)

    asyncio.run(processar_com_politica({"x": 1}, tentativas_iniciais, handler, republicar, enviar_dlq))
    return republicadas, dlq


def test_sucesso_nao_republica_nem_vai_para_dlq():
    async def handler(mensagem, tentativa):
        return None

    assert _rodar(handler) == ([], [])


def test_falha_de_negocio_e_republicada_com_contador_incrementado():
    async def handler(mensagem, tentativa):
        raise CreditoRejeitado("conta nao encontrada")

    assert _rodar(handler, tentativas_iniciais=0) == ([1], [])
    assert _rodar(handler, tentativas_iniciais=1) == ([2], [])


def test_ultima_tentativa_vai_para_a_dlq_com_o_motivo():
    async def handler(mensagem, tentativa):
        raise CreditoRejeitado("conta nao encontrada")

    republicadas, dlq = _rodar(handler, tentativas_iniciais=MAX_TENTATIVAS - 1)
    assert republicadas == []
    assert dlq == ["conta nao encontrada"]


def test_falha_permanente_vai_direto_para_a_dlq():
    async def handler(mensagem, tentativa):
        raise CreditoRejeitado("conta nao pertence a esta agencia", permanente=True)

    assert _rodar(handler) == ([], ["conta nao pertence a esta agencia"])


def test_mensagem_invalida_vai_direto_para_a_dlq():
    async def handler(mensagem, tentativa):
        raise KeyError("idConta")

    republicadas, dlq = _rodar(handler)
    assert republicadas == []
    assert len(dlq) == 1 and "mensagem invalida" in dlq[0]


def test_handler_recebe_o_numero_da_tentativa():
    vistas = []

    async def handler(mensagem, tentativa):
        vistas.append(tentativa)

    _rodar(handler, tentativas_iniciais=2)
    assert vistas == [2]


# --- ponta a ponta com o broker em memória -------------------------------------

def _transferir(origem, valor=20):
    return origem.post("/transferencias", json={"idOrigem": 0, "idDestino": 1, "valor": valor})


def test_conta_ausente_apos_reinicio_tenta_3_vezes_e_vai_para_a_dlq(rede):
    a0, a1 = rede.subir(0), rede.subir(1)
    a0.post("/contas", json={"id": 0, "saldoInicial": 100})
    a1.post("/contas", json={"id": 1, "saldoInicial": 0})
    rede.derrubar(a1)
    _transferir(a0)

    a1_nova = rede.subir(1)  # sem contas: o crédito não pode ser aplicado

    eventos = a1_nova.app.state.registro.ler_eventos()
    tipos = [e["tipo"] for e in eventos]
    assert tipos.count("CREDITO_REMOTO_FALHOU") == MAX_TENTATIVAS
    assert tipos.count("CREDITO_REMOTO_DLQ") == 1
    assert [e["detalhes"]["tentativa"] for e in eventos if e["tipo"] == "CREDITO_REMOTO_FALHOU"] == [1, 2, 3]
    assert rede.bus.filas[1] == []  # saiu da fila principal
    assert len(rede.bus.dlq[1]) == 1  # e ficou guardada na DLQ, não sumiu
    assert rede.bus.dlq[1][0]["idConta"] == 1
    assert a0.get("/contas/0").json()["saldo"] == 80.0  # sem estorno automático


def test_credito_aplicado_nao_gera_dlq(rede):
    a0, a1 = rede.subir(0), rede.subir(1)
    a0.post("/contas", json={"id": 0, "saldoInicial": 100})
    a1.post("/contas", json={"id": 1, "saldoInicial": 0})

    _transferir(a0)

    assert rede.bus.dlq[1] == []
    assert a1.get("/contas/1").json()["saldo"] == 20.0


def test_conta_de_outra_agencia_vai_direto_para_a_dlq(rede):
    a1 = rede.subir(1)
    mensagem = {
        "messageId": "x", "idConta": 0, "valorCentavos": 1000,
        "vetorEnvio": [1, 0, 0], "origemAgencia": 0, "idOrigem": 3, "idDestino": 0,
    }
    asyncio.run(rede.bus.entregar(1, mensagem))

    tipos = [e["tipo"] for e in a1.app.state.registro.ler_eventos()]
    assert tipos == ["CREDITO_REMOTO_FALHOU", "CREDITO_REMOTO_DLQ"]  # sem retry
    assert len(rede.bus.dlq[1]) == 1


def test_mensagem_forjada_com_valor_invalido_vai_para_a_dlq_sem_mexer_no_saldo(rede):
    """Quem publica na exchange não passa por JWT: o consumidor valida o conteúdo."""
    a1 = rede.subir(1)
    a1.post("/contas", json={"id": 1, "saldoInicial": 50})
    base = {"messageId": "forjada", "idConta": 1, "vetorEnvio": [1, 0, 0], "origemAgencia": 0}

    for valor in (-500, 0, "1000", 10.5, True):
        asyncio.run(rede.bus.entregar(1, {**base, "valorCentavos": valor, "messageId": f"forjada-{valor}"}))

    assert a1.get("/contas/1").json()["saldo"] == 50.0
    assert len(rede.bus.dlq[1]) == 5


def test_mensagem_com_vetor_de_tamanho_errado_vai_para_a_dlq(rede):
    a1 = rede.subir(1)
    a1.post("/contas", json={"id": 1, "saldoInicial": 0})
    msg = {"messageId": "v", "idConta": 1, "valorCentavos": 100, "vetorEnvio": [1], "origemAgencia": 0}

    asyncio.run(rede.bus.entregar(1, msg))

    assert a1.get("/contas/1").json()["saldo"] == 0.0
    assert len(rede.bus.dlq[1]) == 1
