"""Controller de transferências (Parte D) + idempotência (funcionalidade
adicional).

Transferência local vs. entre agências, a limitação conhecida (débito não
revertido sob falha) e a idempotência ponta a ponta:

- O cliente envia um cabeçalho `Idempotency-Key` único por operação.
- Na ORIGEM, a chave garante que um reenvio não aplique um segundo débito.
- A chave é propagada à agência de DESTINO (creditar-remoto), que a usa para não
  aplicar um segundo crédito — tornando seguro o retry de rede ponta a ponta.

Contrato: para uma mesma chave, a transferência é aplicada NO MÁXIMO uma vez.
Isso não resolve a atomicidade da falha conhecida (o débito segue sem rollback
automático — isso é o Sprint 4); apenas impede duplicação.
"""
from typing import Annotated

from fastapi import Header, HTTPException, Request

from .. import config
from ..models import CreditarRemotoIn, TransferenciaIn, centavos_para_reais, reais_para_centavos
from ..security import TokenServico, UsuarioAutenticado, garantir_posse
from ..services import auth_service
from ..services.idempotencia import Idempotencia

ChaveIdempotencia = Annotated[str | None, Header(alias="Idempotency-Key")]


async def _creditar_remoto_em(estado, id_destino: int, valor: float, ts_envio: int, chave: str | None):
    """Chama a agência de destino. Devolve (ok: bool, erro: str | None)."""
    agencia_destino = config.agencia_responsavel(id_destino)
    url_destino = config.url_agencia(agencia_destino)
    token_servico = auth_service.emitir_token_servico(estado.id_agencia)
    cabecalhos = {"Authorization": f"Bearer {token_servico}"}
    if chave:
        cabecalhos["Idempotency-Key"] = chave
    try:
        async with estado.criar_http_client() as client:
            resposta = await client.post(
                f"{url_destino}/contas/{id_destino}/creditar-remoto",
                json={"valor": valor, "timestampLamport": ts_envio, "origemAgencia": estado.id_agencia},
                headers=cabecalhos,
                timeout=5.0,
            )
            resposta.raise_for_status()
        return True, None
    except Exception as erro:  # noqa: BLE001
        return False, str(erro)


async def transferir(
    request: Request,
    body: TransferenciaIn,
    usuario: UsuarioAutenticado,
    idempotency_key: ChaveIdempotencia = None,
) -> dict:
    estado = request.app.state
    store: Idempotencia = estado.idempotencia

    # --- Replay de uma chave já vista -------------------------------------
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
            if registro["status"] == Idempotencia.FALHOU:
                # Recuperação: NÃO redebita; apenas retenta o crédito remoto.
                ctx = registro["contexto"]
                ts_envio = estado.relogio.ao_enviar()
                ok, erro = await _creditar_remoto_em(estado, ctx["idDestino"], ctx["valor"], ts_envio, idempotency_key)
                if ok:
                    resposta = {"mensagem": "Transferência concluída (entre agências, recuperada via idempotência)."}
                    store.concluir(idempotency_key, resposta)
                    return resposta
                estado.registro.registrar(
                    "TRANSFERENCIA_FALHOU", estado.relogio.evento_local(),
                    {"idOrigem": ctx["idOrigem"], "idDestino": ctx["idDestino"], "valor": ctx["valor"], "erro": erro},
                )
                raise HTTPException(status_code=502, detail="Falha ao contatar agência de destino (retry).")

    # --- Validação (deterministas; não precisam de cache) -----------------
    origem = estado.contas.obter(body.idOrigem)
    if origem is None:
        raise HTTPException(status_code=404, detail="Conta de origem não encontrada nesta agência.")
    garantir_posse(origem, usuario)

    valor_centavos = reais_para_centavos(body.valor)
    if origem["saldo_centavos"] < valor_centavos:
        raise HTTPException(status_code=400, detail="Saldo insuficiente.")

    agencia_destino = config.agencia_responsavel(body.idDestino)
    if idempotency_key:
        store.marcar_em_andamento(idempotency_key)

    # --- Débito local (sempre) --------------------------------------------
    ts_debito = estado.relogio.evento_local()
    origem["saldo_centavos"] -= valor_centavos
    estado.registro.registrar(
        "TRANSFERENCIA_DEBITO", ts_debito,
        {"idOrigem": body.idOrigem, "idDestino": body.idDestino, "valor": body.valor},
    )

    # --- Crédito -----------------------------------------------------------
    if agencia_destino == estado.id_agencia:
        destino = estado.contas.obter(body.idDestino)
        if destino is None:
            origem["saldo_centavos"] += valor_centavos  # reverte o débito local
            if idempotency_key:
                store.remover(idempotency_key)  # nada aconteceu -> permite tentar de novo
            raise HTTPException(status_code=404, detail="Conta de destino não encontrada.")
        ts_credito = estado.relogio.evento_local()
        destino["saldo_centavos"] += valor_centavos
        estado.registro.registrar(
            "TRANSFERENCIA_CREDITO", ts_credito,
            {"idOrigem": body.idOrigem, "idDestino": body.idDestino, "valor": body.valor},
        )
        resposta = {"mensagem": "Transferência concluída (mesma agência)."}
        if idempotency_key:
            store.concluir(idempotency_key, resposta)
        return resposta

    # Entre agências
    ts_envio = estado.relogio.ao_enviar()
    ok, erro = await _creditar_remoto_em(estado, body.idDestino, body.valor, ts_envio, idempotency_key)
    if ok:
        resposta = {"mensagem": "Transferência concluída (entre agências)."}
        if idempotency_key:
            store.concluir(idempotency_key, resposta)
        return resposta

    # LIMITAÇÃO CONHECIDA: débito já aplicado NÃO é revertido.
    estado.registro.registrar(
        "TRANSFERENCIA_FALHOU", estado.relogio.evento_local(),
        {"idOrigem": body.idOrigem, "idDestino": body.idDestino, "valor": body.valor, "erro": erro},
    )
    if idempotency_key:
        store.falhar(idempotency_key, {"idOrigem": body.idOrigem, "idDestino": body.idDestino, "valor": body.valor})
    raise HTTPException(
        status_code=502,
        detail="Falha ao contatar agência de destino. Débito já aplicado - inconsistência conhecida (ver Sprint 4).",
    )


async def creditar_remoto(
    request: Request,
    id: int,
    body: CreditarRemotoIn,
    _servico: TokenServico,
    idempotency_key: ChaveIdempotencia = None,
) -> dict:
    estado = request.app.state
    store: Idempotencia = estado.idempotencia

    # Dedup no destino: se esta chave já foi creditada, não credita de novo.
    if idempotency_key:
        registro = store.obter(idempotency_key)
        if registro is not None and registro["status"] == Idempotencia.CONCLUIDA:
            return registro["resposta"]

    # Ao RECEBER, ajusta o relógio de Lamport (regra 3).
    ts = estado.relogio.ao_receber(body.timestampLamport)

    conta = estado.contas.obter(id)
    if conta is None:
        raise HTTPException(status_code=404, detail="Conta não encontrada nesta agência.")

    conta["saldo_centavos"] += reais_para_centavos(body.valor)
    estado.registro.registrar(
        "TRANSFERENCIA_CREDITO_REMOTO", ts,
        {"idConta": id, "valor": body.valor, "origemAgencia": body.origemAgencia},
    )
    resposta = {"mensagem": "Crédito remoto aplicado.", "saldoAtual": centavos_para_reais(conta["saldo_centavos"])}
    if idempotency_key:
        store.concluir(idempotency_key, resposta)
    return resposta
