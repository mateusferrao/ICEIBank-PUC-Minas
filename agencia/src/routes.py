"""Tabela de rotas (igual ao routes.js do roteiro).

Deixo as rotas separadas dos controllers. Aqui fica só o mapa de caminho para o
handler, e a lógica fica em controllers/.
"""
from fastapi import FastAPI, Request

from .controllers import auth_controller, contas_controller, transferencias_controller


async def health(request: Request) -> dict:
    """Status da agência: valor atual do relógio de Lamport e quantidade de contas."""
    estado = request.app.state
    return {
        "agencia": estado.id_agencia,
        "lamport": estado.relogio.contador,
        "contas": estado.contas.quantidade(),
    }


def registrar_rotas(app: FastAPI) -> None:
    app.add_api_route("/health", health, methods=["GET"])

    # Autenticação (Parte F)
    app.add_api_route("/auth/login", auth_controller.login, methods=["POST"])

    # Contas (Parte C)
    app.add_api_route("/contas", contas_controller.criar_conta, methods=["POST"], status_code=201)
    app.add_api_route("/contas/{id}", contas_controller.consultar_saldo, methods=["GET"])
    app.add_api_route("/contas/{id}/extrato", contas_controller.extrato, methods=["GET"])
    app.add_api_route("/contas/{id}/depositar", contas_controller.depositar, methods=["POST"])
    app.add_api_route("/contas/{id}/sacar", contas_controller.sacar, methods=["POST"])

    # Transferências (Parte D)
    app.add_api_route("/transferencias", transferencias_controller.transferir, methods=["POST"])
    app.add_api_route(
        "/contas/{id}/creditar-remoto", transferencias_controller.creditar_remoto, methods=["POST"]
    )
