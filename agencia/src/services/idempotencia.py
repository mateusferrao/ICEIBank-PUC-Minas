"""Store de idempotência de transferências (funcionalidade adicional).

Guarda, por chave de idempotência (fornecida pelo cliente), o estado de uma
transferência. Cada agência tem o seu store em memória:
- na agência de ORIGEM, evita aplicar o débito duas vezes se a mesma requisição
  for reenviada;
- na agência de DESTINO, evita aplicar o crédito remoto duas vezes se a chamada
  entre agências for repetida (retry de rede).

Estados possíveis:
- EM_ANDAMENTO: a operação está sendo processada (duplicata concorrente -> 409).
- CONCLUIDA: terminou com sucesso; um replay devolve a resposta guardada.
- FALHOU: a perna de crédito remoto falhou (a "falha conhecida"); um replay não
  redebita, apenas retenta o crédito.
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
