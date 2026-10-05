"""Sprint 2, Parte D: linha do tempo causal, a partir do relógio vetorial.

Lê os arquivos data/eventos-*.jsonl de todas as agências e faz três coisas:

1. Monta uma única linha do tempo. A ordem usa a soma do vetor (desempate por hora
   de parede e agência). Se um evento causou outro, o vetor do primeiro é menor ou
   igual em todas as posições, então a soma dele é menor e ele sempre aparece antes.
   Ordenar só pela hora de parede não dá essa garantia, porque os relógios das
   máquinas podem divergir.
2. Lista os pares de eventos CONCORRENTES entre agências diferentes: nenhum dos dois
   influenciou o outro. É o que o relógio de Lamport do Sprint 1 não conseguia
   afirmar.
3. Lista os pares CAUSAIS débito -> crédito de transferências entre agências, ligados
   pelo `messageId`, para mostrar o outro lado: esses pares são ANTES/DEPOIS, e nunca
   concorrentes.

A comparação de todos os pares é O(n²) no número de eventos. Serve para este projeto,
mas não para milhões de eventos (ver a resposta 3 da Parte D no RESPOSTAS.md).

Uso:
    python mesclar_logs.py
"""
import json
import os
import sys

from src.services.vetorial import comparar

_DIR_DADOS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

LIMITE_PARES_IMPRESSOS = 50


def mesclar(pasta_dados: str = _DIR_DADOS) -> list[dict]:
    """Lê todos os .jsonl da pasta e devolve os eventos em ordem causal."""
    eventos: list[dict] = []
    if not os.path.isdir(pasta_dados):
        return eventos
    for arquivo in sorted(os.listdir(pasta_dados)):
        if not arquivo.endswith(".jsonl"):
            continue
        caminho = os.path.join(pasta_dados, arquivo)
        with open(caminho, encoding="utf-8") as f:
            for linha in f:
                linha = linha.strip()
                if linha:
                    eventos.append(json.loads(linha))
    eventos.sort(key=lambda e: (sum(e["timestampVetorial"]), e["horaParede"], e["agencia"]))
    return eventos


def pares_concorrentes(eventos: list[dict]) -> list[tuple[dict, dict]]:
    """Pares de eventos de agências diferentes cujos vetores são concorrentes."""
    pares = []
    for i in range(len(eventos)):
        for j in range(i + 1, len(eventos)):
            e1, e2 = eventos[i], eventos[j]
            if e1["agencia"] == e2["agencia"]:
                continue
            if comparar(e1["timestampVetorial"], e2["timestampVetorial"]) == "CONCORRENTES":
                pares.append((e1, e2))
    return pares


def pares_causais(eventos: list[dict]) -> list[tuple[dict, dict]]:
    """Pares (débito, crédito remoto) da mesma transferência, entre agências, em que
    o vetor do débito é comprovadamente ANTES do vetor do crédito."""
    debitos = {
        e["detalhes"].get("messageId"): e
        for e in eventos
        if e["tipo"] == "TRANSFERENCIA_DEBITO" and e["detalhes"].get("messageId")
    }
    pares = []
    for e in eventos:
        if e["tipo"] != "TRANSFERENCIA_CREDITO_REMOTO":
            continue
        debito = debitos.get(e["detalhes"].get("messageId"))
        if debito is None or debito["agencia"] == e["agencia"]:
            continue
        if comparar(debito["timestampVetorial"], e["timestampVetorial"]) == "ANTES":
            pares.append((debito, e))
    return pares


def _descrever(e: dict) -> str:
    return f"[{e['agencia']}] {e['tipo']} {e['timestampVetorial']}"


def main() -> None:
    eventos = mesclar()
    if not eventos:
        print("Nenhum evento encontrado em data/. Rode as agências e gere operações primeiro.")
        sys.exit(0)

    print("=== Linha do tempo causal (ordenada pelo relogio vetorial) ===")
    for evento in eventos:
        print(
            f"[Vetor {evento['timestampVetorial']}] ({evento['horaParede']}) "
            f"{evento['agencia']} - {evento['tipo']} {json.dumps(evento['detalhes'], ensure_ascii=False)}"
        )

    concorrentes = pares_concorrentes(eventos)
    print(f"\n=== Pares de eventos CONCORRENTES entre agencias diferentes ({len(concorrentes)}) ===")
    for e1, e2 in concorrentes[:LIMITE_PARES_IMPRESSOS]:
        print(f"{_descrever(e1)}  x  {_descrever(e2)}")
    if len(concorrentes) > LIMITE_PARES_IMPRESSOS:
        print(f"... e mais {len(concorrentes) - LIMITE_PARES_IMPRESSOS} pares")
    if not concorrentes:
        print("(nenhum par concorrente nesta execucao - gere operacoes independentes em agencias diferentes)")

    causais = pares_causais(eventos)
    print(f"\n=== Pares CAUSAIS debito -> credito entre agencias ({len(causais)}) ===")
    for debito, credito in causais:
        print(f"{_descrever(debito)}  ANTES  {_descrever(credito)}   messageId={debito['detalhes']['messageId']}")
    if not causais:
        print("(nenhuma transferencia entre agencias com debito e credito registrados)")


if __name__ == "__main__":
    main()
