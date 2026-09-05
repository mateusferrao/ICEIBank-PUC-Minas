"""Relógio lógico de Lamport (Parte B).

Três regras:
1. Antes de qualquer evento local, o processo incrementa seu contador.
2. Ao enviar uma mensagem, o processo incrementa o contador e anexa o valor.
3. Ao receber uma mensagem com timestamp t, ajusta o contador para
   max(contador_local, t) + 1.

Um `Lock` protege as três operações. Neste projeto os endpoints são `async` e
rodam em um único event loop (sem preempção), então o contador já estaria
seguro; o lock é defesa em profundidade caso a agência passe a rodar com várias
threads/workers no futuro — o mesmo cuidado que o roteiro descreve para Java
(`synchronized`) e Flask (`threading.Lock`).
"""
import threading


class RelogioLamport:
    def __init__(self) -> None:
        self.contador = 0
        self._lock = threading.Lock()

    def evento_local(self) -> int:
        with self._lock:
            self.contador += 1
            return self.contador

    def ao_enviar(self) -> int:
        with self._lock:
            self.contador += 1
            return self.contador

    def ao_receber(self, timestamp_recebido: int) -> int:
        with self._lock:
            self.contador = max(self.contador, timestamp_recebido) + 1
            return self.contador
