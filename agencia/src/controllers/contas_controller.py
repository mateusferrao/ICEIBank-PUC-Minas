"""Controller de contas (Parte C): criar, consultar, depositar, sacar.

Toda operação que muda o estado ganha um timestamp do relógio vetorial e é
gravada no event log. As contas ficam em memória (no ContaRepository dentro do
app.state).

Deixei os endpoints como `async def` de propósito. Assim eles rodam no event loop
único do Uvicorn, sem threadpool, e como não tem `await` entre ler e escrever o
saldo, uma operação numa conta não é interrompida por outra requisição.
"""
from fastapi import HTTPException, Request

from .. import config
from ..models import CriarContaIn, ValorIn, centavos_para_reais, reais_para_centavos
from ..security import UsuarioAutenticado, garantir_posse


def conta_para_resposta(conta: dict) -> dict:
    """Monta a versão pública da conta: saldo em reais, sem os campos internos."""
    resposta = {
        "id": conta["id"],
        "nomeAluno": conta.get("nomeAluno"),
        "saldo": centavos_para_reais(conta["saldo_centavos"]),
    }
    if conta.get("dono") is not None:
        resposta["dono"] = conta["dono"]
    return resposta


async def criar_conta(request: Request, body: CriarContaIn, usuario: UsuarioAutenticado) -> dict:
    estado = request.app.state
    if config.agencia_responsavel(body.id) != estado.id_agencia:
        raise HTTPException(
            status_code=400,
            detail=f"Conta {body.id} não pertence a esta agência (responsável: agência {config.agencia_responsavel(body.id)}).",
        )
    if estado.contas.existe(body.id):
        raise HTTPException(status_code=409, detail="Conta já existe.")

    ts = estado.relogio.evento_local()
    # O dono é sempre o usuário logado, cada um só cria conta para si mesmo.
    conta = {
        "id": body.id,
        "nomeAluno": body.nomeAluno or config.USUARIOS.get(usuario, {}).get("nome", usuario),
        "dono": usuario,
        "saldo_centavos": reais_para_centavos(body.saldoInicial),
    }
    estado.contas.salvar(conta)
    estado.registro.registrar(
        "CRIAR_CONTA", ts, {"id": body.id, "nomeAluno": body.nomeAluno, "saldoInicial": body.saldoInicial}
    )
    return conta_para_resposta(conta)


async def extrato(request: Request, id: int, usuario: UsuarioAutenticado) -> dict:
    """Histórico dos eventos de uma conta (nesta agência).

    É um endpoint só de leitura, para o frontend. Ele reaproveita o event log que
    já está gravado e filtra os eventos que citam essa conta.
    """
    estado = request.app.state
    conta = estado.contas.obter(id)
    if conta is None:
        raise HTTPException(status_code=404, detail="Conta não encontrada nesta agência.")
    garantir_posse(conta, usuario)

    def referencia(detalhes: dict) -> bool:
        return id in (
            detalhes.get("id"),
            detalhes.get("idConta"),
            detalhes.get("idOrigem"),
            detalhes.get("idDestino"),
        )

    eventos = [e for e in estado.registro.ler_eventos() if referencia(e.get("detalhes", {}))]
    return {"conta": id, "eventos": eventos}


async def consultar_saldo(request: Request, id: int, usuario: UsuarioAutenticado) -> dict:
    conta = request.app.state.contas.obter(id)
    if conta is None:
        raise HTTPException(status_code=404, detail="Conta não encontrada nesta agência.")
    garantir_posse(conta, usuario)
    return conta_para_resposta(conta)


async def depositar(request: Request, id: int, body: ValorIn, usuario: UsuarioAutenticado) -> dict:
    estado = request.app.state
    conta = estado.contas.obter(id)
    if conta is None:
        raise HTTPException(status_code=404, detail="Conta não encontrada nesta agência.")
    garantir_posse(conta, usuario)

    ts = estado.relogio.evento_local()
    conta["saldo_centavos"] += reais_para_centavos(body.valor)
    estado.registro.registrar(
        "DEPOSITO", ts, {"id": id, "valor": body.valor, "novoSaldo": centavos_para_reais(conta["saldo_centavos"])}
    )
    return conta_para_resposta(conta)


async def sacar(request: Request, id: int, body: ValorIn, usuario: UsuarioAutenticado) -> dict:
    estado = request.app.state
    conta = estado.contas.obter(id)
    if conta is None:
        raise HTTPException(status_code=404, detail="Conta não encontrada nesta agência.")
    garantir_posse(conta, usuario)

    valor_centavos = reais_para_centavos(body.valor)
    if conta["saldo_centavos"] < valor_centavos:
        raise HTTPException(status_code=400, detail="Saldo insuficiente.")

    ts = estado.relogio.evento_local()
    conta["saldo_centavos"] -= valor_centavos
    estado.registro.registrar(
        "SAQUE", ts, {"id": id, "valor": body.valor, "novoSaldo": centavos_para_reais(conta["saldo_centavos"])}
    )
    return conta_para_resposta(conta)
