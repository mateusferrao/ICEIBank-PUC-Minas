"""Guarda o estado das transferências por chave de idempotência (funcionalidade
adicional).

A chave vem do cliente. Cada agência tem o seu registro em memória:
- na agência de origem, evita aplicar o débito duas vezes se a requisição for
  reenviada;
- na agência de destino, evita aplicar o crédito remoto duas vezes se a chamada
  entre agências for repetida por causa de um retry de rede.

Estados possíveis:
- EM_ANDAMENTO: a operação está sendo processada (uma cópia concorrente recebe 409).
- CONCLUIDA: terminou bem, e um reenvio devolve a resposta guardada.
- FALHOU: o crédito remoto falhou (a falha conhecida). Um reenvio não debita de
  novo, só tenta o crédito outra vez.
"""


class Idempotencia:
    EM_ANDAMENTO = "EM_ANDAMENTO"
    CONCLUIDA = "CONCLUIDA"
    FALHOU = "FALHOU"

    def __init__(self) -> None:
        self._registros: dict[str, dict] = {}

    def obter(self, chave: str) -> dict | None:
        return self._registros.get(chave)

    def marcar_em_andamento(self, chave: str, contexto: dict | None = None) -> None:
        self._registros[chave] = {"status": self.EM_ANDAMENTO, "contexto": contexto}

    def concluir(self, chave: str, resposta: dict) -> None:
        self._registros[chave] = {"status": self.CONCLUIDA, "resposta": resposta}

    def falhar(self, chave: str, contexto: dict) -> None:
        self._registros[chave] = {"status": self.FALHOU, "contexto": contexto}

    def remover(self, chave: str) -> None:
        self._registros.pop(chave, None)
