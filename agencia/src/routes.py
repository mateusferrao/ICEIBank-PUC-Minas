"""Tabela de rotas (espelha o routes.js do roteiro).

Mantém as rotas separadas dos controllers: aqui só o mapeamento
caminho -> handler; a lógica vive em controllers/.
"""
from fastapi import FastAPI, Request

from .controllers import contas_controller


async def health(request: Request) -> dict:
    """Status da agência: relógio de Lamport atual e nº de contas."""
    estado = request.app.state
    return {
        "agencia": estado.id_agencia,
        "lamport": estado.relogio.contador,
        "contas": estado.contas.quantidade(),
    }


def registrar_rotas(app: FastAPI) -> None:
    app.add_api_route("/health", health, methods=["GET"])

    # Contas (Parte C)
    app.add_api_route("/contas", contas_controller.criar_conta, methods=["POST"], status_code=201)
    app.add_api_route("/contas/{id}", contas_controller.consultar_saldo, methods=["GET"])
    app.add_api_route("/contas/{id}/depositar", contas_controller.depositar, methods=["POST"])
    app.add_api_route("/contas/{id}/sacar", contas_controller.sacar, methods=["POST"])
