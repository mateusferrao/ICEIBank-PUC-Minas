"""Mostra as filas do ICEIBank no RabbitMQ (CloudAMQP) e quantas mensagens cada uma tem.

Útil para as evidências do Sprint 2: dá para ver a mensagem retida na fila da agência
fora do ar e as mensagens guardadas nas dead-letter queues, sem abrir o painel web.

Usa a API de gerenciamento do RabbitMQ (HTTPS, mesma credencial da RABBITMQ_URL).

Uso:
    python ver_filas.py
    python ver_filas.py --limpar-dlq   (esvazia as DLQs, útil antes de uma demonstração)
"""
import os
import sys
from urllib.parse import quote, unquote, urlparse

import httpx
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env"))


def _api() -> tuple[str, str, tuple[str, str]]:
    url = os.environ.get("RABBITMQ_URL")
    if not url:
        sys.exit("Defina RABBITMQ_URL (variável de ambiente ou arquivo .env na raiz do repositório).")
    u = urlparse(url)
    vhost = unquote(u.path.lstrip("/")) or "/"
    return f"https://{u.hostname}/api", vhost, (unquote(u.username), unquote(u.password))


def main() -> None:
    base, vhost, auth = _api()
    v = quote(vhost, safe="")
    if "--limpar-dlq" in sys.argv:
        for i in range(3):
            r = httpx.delete(f"{base}/queues/{v}/fila-agencia-{i}.dlq/contents", auth=auth, timeout=15)
            print(f"fila-agencia-{i}.dlq esvaziada (HTTP {r.status_code})")
    r = httpx.get(f"{base}/queues/{v}", auth=auth, timeout=15)
    r.raise_for_status()
    filas = sorted((q for q in r.json() if q["name"].startswith("fila-agencia-")), key=lambda q: q["name"])
    print(f"{'fila':28} {'prontas':>8} {'nao confirmadas':>16} {'consumidores':>13}")
    for q in filas:
        print(
            f"{q['name']:28} {q.get('messages_ready', 0):>8} "
            f"{q.get('messages_unacknowledged', 0):>16} {q.get('consumers', 0):>13}"
        )
    if not filas:
        print("(nenhuma fila fila-agencia-* encontrada: suba uma agência para criar a topologia)")


if __name__ == "__main__":
    main()
