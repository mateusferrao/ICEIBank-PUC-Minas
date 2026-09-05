"""Repositório de contas em memória.

O roteiro pede contas em memória nesta sprint, sem banco de dados. Se o processo
reiniciar, as contas somem, e isso é esperado. Mesmo assim deixei um repositório
bem simples no meio: os controllers não sabem como as contas são guardadas, então
se na Sprint 4 eu trocar por um banco de verdade não preciso reescrever as regras
de negócio.

Uma conta é um dict: {"id", "nomeAluno", "dono", "saldo_centavos"}. O campo "dono"
só começa a ser preenchido na Parte F (autenticação).
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
