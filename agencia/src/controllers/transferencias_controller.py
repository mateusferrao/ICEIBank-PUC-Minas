"""Controller de transferências (Parte D): local, entre agências e a limitação
conhecida.

- Transferência local (mesma agência): débito e crédito são ambos eventos locais
  do relógio de Lamport — não há troca de mensagem, então não se usa
  ao_enviar()/ao_receber().
- Transferência entre agências: o débito é local; o crédito é feito na agência de
  destino via chamada REST (creditar-remoto). Aqui entram as regras 2 (ao_enviar)
  e 3 (ao_receber) do relógio de Lamport.

LIMITAÇÃO CONHECIDA (intencional): se a chamada à agência de destino falhar, o
débito já aplicado NÃO é revertido — o dinheiro "some" temporariamente. Resolver
isso com atomicidade sob falha é o assunto do Sprint 4 (2PC/Saga). Por enquanto,
apenas registramos a inconsistência no log (TRANSFERENCIA_FALHOU).
"""
from fastapi import HTTPException, Request

from .. import config
from ..models import CreditarRemotoIn, TransferenciaIn, centavos_para_reais, reais_para_centavos
from ..security import TokenServico, UsuarioAutenticado, garantir_posse
from ..services import auth_service


async def transferir(request: Request, body: TransferenciaIn, usuario: UsuarioAutenticado) -> dict:
    estado = request.app.state
    origem = estado.contas.obter(body.idOrigem)
    if origem is None:
        raise HTTPException(status_code=404, detail="Conta de origem não encontrada nesta agência.")
    # Autorização: só o dono pode transferir da conta de origem.
    garantir_posse(origem, usuario)

    valor_centavos = reais_para_centavos(body.valor)
    if origem["saldo_centavos"] < valor_centavos:
        raise HTTPException(status_code=400, detail="Saldo insuficiente.")

    agencia_destino = config.agencia_responsavel(body.idDestino)

    # O débito é sempre local, pois esta agência é a dona da conta de origem.
    ts_debito = estado.relogio.evento_local()
    origem["saldo_centavos"] -= valor_centavos
    estado.registro.registrar(
        "TRANSFERENCIA_DEBITO", ts_debito,
        {"idOrigem": body.idOrigem, "idDestino": body.idDestino, "valor": body.valor},
    )

    if agencia_destino == estado.id_agencia:
        # Caso simples: mesma agência, credita direto.
        destino = estado.contas.obter(body.idDestino)
        if destino is None:
            origem["saldo_centavos"] += valor_centavos  # reverte o débito local
            raise HTTPException(status_code=404, detail="Conta de destino não encontrada.")
        ts_credito = estado.relogio.evento_local()
        destino["saldo_centavos"] += valor_centavos
        estado.registro.registrar(
            "TRANSFERENCIA_CREDITO", ts_credito,
            {"idOrigem": body.idOrigem, "idDestino": body.idDestino, "valor": body.valor},
        )
        return {"mensagem": "Transferência concluída (mesma agência)."}

    # Caso entre agências: chama a agência de destino via REST.
    ts_envio = estado.relogio.ao_enviar()
    url_destino = config.url_agencia(agencia_destino)
    try:
        token_servico = auth_service.emitir_token_servico(estado.id_agencia)
        async with estado.criar_http_client() as client:
            resposta = await client.post(
                f"{url_destino}/contas/{body.idDestino}/creditar-remoto",
                json={
                    "valor": body.valor,
                    "timestampLamport": ts_envio,
                    "origemAgencia": estado.id_agencia,
                },
                headers={"Authorization": f"Bearer {token_servico}"},
                timeout=5.0,
            )
            resposta.raise_for_status()
        return {"mensagem": "Transferência concluída (entre agências)."}
    except Exception as erro:  # noqa: BLE001 - queremos capturar qualquer falha de rede
        estado.registro.registrar(
            "TRANSFERENCIA_FALHOU", estado.relogio.evento_local(),
            {"idOrigem": body.idOrigem, "idDestino": body.idDestino, "valor": body.valor, "erro": str(erro)},
        )
        raise HTTPException(
            status_code=502,
            detail="Falha ao contatar agência de destino. Débito já aplicado - inconsistência conhecida (ver Sprint 4).",
        )


async def creditar_remoto(request: Request, id: int, body: CreditarRemotoIn, _servico: TokenServico) -> dict:
    estado = request.app.state
    # Ao RECEBER uma mensagem de outra agência, o relógio de Lamport é ajustado
    # com base no timestamp recebido (regra 3 do algoritmo).
    ts = estado.relogio.ao_receber(body.timestampLamport)

    conta = estado.contas.obter(id)
    if conta is None:
        raise HTTPException(status_code=404, detail="Conta não encontrada nesta agência.")

    conta["saldo_centavos"] += reais_para_centavos(body.valor)
    estado.registro.registrar(
        "TRANSFERENCIA_CREDITO_REMOTO", ts,
        {"idConta": id, "valor": body.valor, "origemAgencia": body.origemAgencia},
    )
    return {"mensagem": "Crédito remoto aplicado.", "saldoAtual": centavos_para_reais(conta["saldo_centavos"])}
