"""Repositório de contas em memória.

O roteiro pede explicitamente contas em memória neste sprint (sem banco de
dados) — se o processo reiniciar, as contas somem, e isso é esperado. Mesmo
assim, mantemos uma abstração fina de repositório: a lógica dos controllers não
conhece a estrutura de armazenamento, então trocar por um banco de verdade no
Sprint 4 não exige reescrever as regras de negócio.

Uma conta é um dict: {"id", "nomeAluno", "dono", "saldo_centavos"}.
O campo "dono" só passa a ser preenchido a partir da Parte F (autenticação).
"""


class ContaRepository:
    def __init__(self) -> None:
        self._contas: dict[int, dict] = {}

    def existe(self, id_conta: int) -> bool:
        return id_conta in self._contas

    def obter(self, id_conta: int) -> dict | None:
        return self._contas.get(id_conta)

    def salvar(self, conta: dict) -> dict:
        self._contas[conta["id"]] = conta
        return conta

    def todas(self) -> list[dict]:
        return list(self._contas.values())

    def quantidade(self) -> int:
        return len(self._contas)
