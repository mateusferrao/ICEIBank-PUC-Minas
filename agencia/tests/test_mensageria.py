"""Sprint 2, Parte C: transferência entre agências via publish/subscribe.

Os testes usam o FakeBroker (tests/fakes.py), que imita a fila por agência do
RabbitMQ: retém mensagens quando a agência está fora do ar e entrega na hora
quando ela está consumindo.
"""
import asyncio

from src.services.vetorial import comparar


def _eventos(rede_cliente):
    return rede_cliente.app.state.registro.ler_eventos()


def _tipos(rede_cliente):
    return [e["tipo"] for e in _eventos(rede_cliente)]


def _transferir(origem, id_origem, id_destino, valor, **headers):
    return origem.post(
        "/transferencias",
        json={"idOrigem": id_origem, "idDestino": id_destino, "valor": valor},
        headers=headers,
    )


def test_transferencia_entre_agencias_chega_por_mensagem(rede):
    a0, a1 = rede.subir(0), rede.subir(1)
    a0.post("/contas", json={"id": 0, "saldoInicial": 100})
    a1.post("/contas", json={"id": 1, "saldoInicial": 0})

    r = _transferir(a0, 0, 1, 30)

    assert r.status_code == 200
    assert "assíncrona" in r.json()["mensagem"]
    assert a0.get("/contas/0").json()["saldo"] == 70.0
    assert a1.get("/contas/1").json()["saldo"] == 30.0
    # foi publicada na routing key da agência de destino
    assert [rk for rk, _ in rede.bus.publicadas] == ["agencia.1.creditar"]


def test_vetor_do_destino_absorve_o_da_origem(rede):
    a0, a1 = rede.subir(0), rede.subir(1)
    a0.post("/contas", json={"id": 0, "saldoInicial": 100})
    a1.post("/contas", json={"id": 1, "saldoInicial": 0})
    antes = a1.get("/health").json()["vetor"]

    _transferir(a0, 0, 1, 10)

    depois = a1.get("/health").json()["vetor"]
    assert depois[0] > antes[0]  # absorveu a posição da origem (max)
    assert depois[1] > antes[1]  # e incrementou a própria posição


def test_debito_aconteceu_antes_do_credito_remoto(rede):
    a0, a1 = rede.subir(0), rede.subir(1)
    a0.post("/contas", json={"id": 0, "saldoInicial": 100})
    a1.post("/contas", json={"id": 1, "saldoInicial": 0})

    _transferir(a0, 0, 1, 10)

    debito = next(e for e in _eventos(a0) if e["tipo"] == "TRANSFERENCIA_DEBITO")
    credito = next(e for e in _eventos(a1) if e["tipo"] == "TRANSFERENCIA_CREDITO_REMOTO")
    assert comparar(debito["timestampVetorial"], credito["timestampVetorial"]) == "ANTES"
    assert debito["detalhes"]["messageId"] == credito["detalhes"]["messageId"]


def test_agencia_fora_do_ar_mensagem_fica_retida_e_resposta_e_200(rede):
    a0, a1 = rede.subir(0), rede.subir(1)
    a0.post("/contas", json={"id": 0, "saldoInicial": 100})
    a1.post("/contas", json={"id": 1, "saldoInicial": 0})
    rede.derrubar(a1)

    r = _transferir(a0, 0, 1, 30)

    assert r.status_code == 200  # só significa "publicada"
    assert a0.get("/contas/0").json()["saldo"] == 70.0
    assert len(rede.bus.filas[1]) == 1  # retida na fila da agência 1


def test_agencia_reiniciada_recebe_mensagem_mas_conta_nao_existe_mais(rede):
    """O cenário da seção 7.4: as contas vivem em memória e somem no reinício."""
    a0, a1 = rede.subir(0), rede.subir(1)
    a0.post("/contas", json={"id": 0, "saldoInicial": 100})
    a1.post("/contas", json={"id": 1, "saldoInicial": 0})
    rede.derrubar(a1)
    _transferir(a0, 0, 1, 30)

    a1_nova = rede.subir(1)  # reinicia: estado em memória zerado, consome a fila

    assert rede.bus.filas[1] == []  # a mensagem FOI entregue
    assert "CREDITO_REMOTO_FALHOU" in _tipos(a1_nova)
    falha = next(e for e in _eventos(a1_nova) if e["tipo"] == "CREDITO_REMOTO_FALHOU")
    assert falha["detalhes"]["motivo"] == "conta nao encontrada"
    assert a0.get("/contas/0").json()["saldo"] == 70.0  # débito da origem continua


def test_falha_ao_publicar_estorna_debito_e_responde_503(rede):
    a0 = rede.subir(0)
    a0.post("/contas", json={"id": 0, "saldoInicial": 100})
    rede.bus.publicacao_indisponivel = True

    r = _transferir(a0, 0, 1, 30)

    assert r.status_code == 503
    assert a0.get("/contas/0").json()["saldo"] == 100.0  # débito estornado
    assert "TRANSFERENCIA_ESTORNADA" in _tipos(a0)


def test_chave_de_idempotencia_e_liberada_apos_falha_ao_publicar(rede):
    a0, a1 = rede.subir(0), rede.subir(1)
    a0.post("/contas", json={"id": 0, "saldoInicial": 100})
    a1.post("/contas", json={"id": 1, "saldoInicial": 0})
    rede.bus.publicacao_indisponivel = True
    assert _transferir(a0, 0, 1, 30, **{"Idempotency-Key": "k1"}).status_code == 503

    rede.bus.publicacao_indisponivel = False
    r = _transferir(a0, 0, 1, 30, **{"Idempotency-Key": "k1"})

    assert r.status_code == 200
    assert a0.get("/contas/0").json()["saldo"] == 70.0
    assert a1.get("/contas/1").json()["saldo"] == 30.0


def test_replay_com_mesma_chave_nao_republica_nem_redebita(rede):
    a0, a1 = rede.subir(0), rede.subir(1)
    a0.post("/contas", json={"id": 0, "saldoInicial": 100})
    a1.post("/contas", json={"id": 1, "saldoInicial": 0})

    _transferir(a0, 0, 1, 30, **{"Idempotency-Key": "abc"})
    _transferir(a0, 0, 1, 30, **{"Idempotency-Key": "abc"})

    assert len(rede.bus.publicadas) == 1
    assert a0.get("/contas/0").json()["saldo"] == 70.0
    assert a1.get("/contas/1").json()["saldo"] == 30.0


def test_consumidor_nao_credita_duas_vezes_a_mesma_mensagem(rede):
    a0, a1 = rede.subir(0), rede.subir(1)
    a0.post("/contas", json={"id": 0, "saldoInicial": 100})
    a1.post("/contas", json={"id": 1, "saldoInicial": 0})
    _transferir(a0, 0, 1, 30, **{"Idempotency-Key": "msg-1"})
    _, mensagem = rede.bus.publicadas[0]

    # o broker reentrega a mesma mensagem (at-least-once)
    asyncio.run(a1.app.state.handler_credito(mensagem))

    assert a1.get("/contas/1").json()["saldo"] == 30.0


def test_consumidor_recusa_conta_de_outra_agencia(rede):
    a1 = rede.subir(1)
    mensagem = {
        "messageId": "x", "idConta": 0, "valorCentavos": 1000,
        "vetorEnvio": [1, 0, 0], "origemAgencia": 0, "idOrigem": 3, "idDestino": 0,
    }  # conta 0 pertence à agência 0, não à 1

    asyncio.run(rede.bus.entregar(1, mensagem))

    falha = next(e for e in _eventos(a1) if e["tipo"] == "CREDITO_REMOTO_FALHOU")
    assert falha["detalhes"]["motivo"] == "conta nao pertence a esta agencia"


def test_origem_igual_ao_destino_e_rejeitada(cliente):
    cliente.post("/contas", json={"id": 0, "saldoInicial": 100})
    r = cliente.post("/transferencias", json={"idOrigem": 0, "idDestino": 0, "valor": 10})
    assert r.status_code == 400
    assert cliente.get("/contas/0").json()["saldo"] == 100.0


def test_rota_creditar_remoto_do_sprint_1_nao_existe_mais(cliente):
    r = cliente.post("/contas/0/creditar-remoto", json={"valor": 1, "vetorEnvio": [0, 0, 0], "origemAgencia": 1})
    assert r.status_code in (404, 405)


def test_destino_local_inexistente_registra_estorno(cliente):
    cliente.post("/contas", json={"id": 0, "saldoInicial": 100})
    cliente.post("/transferencias", json={"idOrigem": 0, "idDestino": 3, "valor": 30})
    assert "TRANSFERENCIA_ESTORNADA" in [e["tipo"] for e in cliente.app.state.registro.ler_eventos()]


def test_agencia_reiniciada_nao_volta_atras_no_proprio_contador(rede):
    """O relógio é reconstruído a partir do log, que sobrevive ao reinício. Sem
    isso, um evento novo da agência pareceria concorrente com os antigos dela."""
    a1 = rede.subir(1)
    a1.post("/contas", json={"id": 1, "saldoInicial": 0})
    a1.post("/contas", json={"id": 4, "saldoInicial": 0})
    vetor_antes = a1.get("/health").json()["vetor"]
    rede.derrubar(a1)

    a1_nova = rede.subir(1)

    assert a1_nova.get("/health").json()["vetor"] == vetor_antes
