"""Parte E: linha do tempo unificada, ordenada pelo relógio de Lamport.

Lê os arquivos data/eventos-*.jsonl de todas as agências e monta uma única
sequência ordenada por timestampLamport, para observar o algoritmo na prática
(inclusive empates entre eventos concorrentes de agências diferentes).

Uso:
    python mesclar_logs.py
"""
import json
import os
import sys

_DIR_DADOS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")


def mesclar(pasta_dados: str = _DIR_DADOS) -> list[dict]:
    """Lê todos os .jsonl da pasta e devolve os eventos ordenados por Lamport."""
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


def main() -> None:
    eventos = mesclar()
    if not eventos:
        print("Nenhum evento encontrado em data/. Rode as agências e gere operações primeiro.")
        sys.exit(0)
    print("=== Linha do tempo unificada (ordenada por relogio vetorial) ===")
    for evento in eventos:
        print(
            f"[Vetor {evento['timestampVetorial']}] ({evento['horaParede']}) "
            f"{evento['agencia']} - {evento['tipo']} {json.dumps(evento['detalhes'], ensure_ascii=False)}"
        )


if __name__ == "__main__":
    main()
