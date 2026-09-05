"""Configuração da agência: particionamento de contas e portas.

Todas as agências compartilham este mesmo arquivo (o mesmo código roda 3 vezes,
identificado pela variável de ambiente AGENCIA_ID). O bloco de autenticação
(segredo do JWT e diretório de usuários) é acrescentado na Parte F.
"""
import os

# TODO: substitua pelo seu OFFSET pessoal (dois últimos dígitos da matrícula/RA),
# necessário apenas se for rodar em uma máquina compartilhada do laboratório.
OFFSET = int(os.environ.get("OFFSET", "0"))

NUMERO_AGENCIAS = 3
PORTA_BASE = 4000 + OFFSET

AGENCIAS = [
    {"id": 0, "url": f"http://localhost:{PORTA_BASE}"},
    {"id": 1, "url": f"http://localhost:{PORTA_BASE + 1}"},
    {"id": 2, "url": f"http://localhost:{PORTA_BASE + 2}"},
]


def agencia_responsavel(id_conta: int) -> int:
    """Retorna o id da agência dona da conta (partição, não replicação).

    conta 0 -> Agência 0, conta 1 -> Agência 1, conta 2 -> Agência 2,
    conta 3 -> de volta à Agência 0, e assim por diante.
    """
    return id_conta % NUMERO_AGENCIAS


def url_agencia(id_agencia: int) -> str:
    return next(a["url"] for a in AGENCIAS if a["id"] == id_agencia)
