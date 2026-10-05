"""Relógio vetorial (Sprint 2, Parte B).

Um vetor de contadores, uma posição por agência. Três regras:
1. Antes de um evento local, a agência incrementa a própria posição.
2. Ao enviar uma mensagem, incrementa a própria posição e anexa o vetor inteiro.
3. Ao receber um vetor V, faz vetor[i] = max(vetor[i], V[i]) em todas as posições
   e depois incrementa a própria posição.

`comparar` diz se um evento aconteceu antes, depois, se os vetores são iguais ou
se os eventos são concorrentes (nenhum influenciou o outro). É isso que o Lamport
sozinho não consegue afirmar.

O Lock protege as operações pelo mesmo motivo do relógio de Lamport do Sprint 1:
hoje tudo roda num único event loop, mas o lock deixa o relógio seguro se um dia
houver threads.
"""
import threading
from typing import Sequence


class RelogioVetorial:
    def __init__(self, id_agencia: int, numero_agencias: int) -> None:
        self.id_agencia = id_agencia
        self.vetor = [0] * numero_agencias
        self._lock = threading.Lock()

    def evento_local(self) -> list[int]:
        with self._lock:
            self.vetor[self.id_agencia] += 1
            return list(self.vetor)

    def ao_enviar(self) -> list[int]:
        with self._lock:
            self.vetor[self.id_agencia] += 1
            return list(self.vetor)

    def ao_receber(self, vetor_recebido: Sequence[int]) -> list[int]:
        with self._lock:
            for i in range(len(self.vetor)):
                self.vetor[i] = max(self.vetor[i], vetor_recebido[i])
            self.vetor[self.id_agencia] += 1
            return list(self.vetor)

    def restaurar(self, vetor: Sequence[int]) -> None:
        """Assume o máximo entre o vetor atual e `vetor`, sem criar evento.

        Usado ao subir a agência: o log de eventos sobrevive ao reinício e o vetor
        não, então o relógio é reconstruído a partir dele. Sem isso, a agência
        voltaria a contar do zero e seus eventos novos pareceriam concorrentes com
        os que ela mesma registrou antes de reiniciar."""
        with self._lock:
            for i in range(len(self.vetor)):
                self.vetor[i] = max(self.vetor[i], vetor[i])

    def atual(self) -> list[int]:
        """Cópia do vetor atual, sem criar evento (usado no /health)."""
        with self._lock:
            return list(self.vetor)


def comparar(v1: Sequence[int], v2: Sequence[int]) -> str:
    """Relação entre dois vetores: ANTES, DEPOIS, IGUAIS ou CONCORRENTES.

    ANTES significa que o evento de v1 aconteceu antes do de v2.
    """
    v1_menor_ou_igual = all(a <= b for a, b in zip(v1, v2))
    v2_menor_ou_igual = all(b <= a for a, b in zip(v1, v2))
    if v1_menor_ou_igual and v2_menor_ou_igual:
        return "IGUAIS"
    if v1_menor_ou_igual:
        return "ANTES"
    if v2_menor_ou_igual:
        return "DEPOIS"
    return "CONCORRENTES"
