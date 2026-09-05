"""Configuração da agência: particionamento de contas, portas e autenticação.

Todas as agências compartilham este mesmo arquivo (o mesmo código roda 3 vezes,
identificado pela variável de ambiente AGENCIA_ID). Por isso o segredo do JWT e o
diretório de usuários (seed) precisam ser idênticos nas três — só assim um
usuário consegue autenticar em qualquer agência usada como porta de entrada.
"""
import os

from pwdlib import PasswordHash

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


# ---------------------------------------------------------------------------
# Autenticação (Parte F)
# ---------------------------------------------------------------------------

# Segredo compartilhado entre as 3 agências. Em produção viria de um cofre de
# segredos; aqui aceita override por variável de ambiente e tem um fallback de
# desenvolvimento para o projeto rodar sem configuração extra.
JWT_SECRET = os.environ.get("JWT_SECRET", "iceibank-sprint1-segredo-compartilhado")
JWT_ALGORITMO = "HS256"

# Expiração do token de usuário (minutos) e do token de serviço (segundos, curto
# pois é gerado por chamada entre agências).
TOKEN_USUARIO_MINUTOS = int(os.environ.get("TOKEN_USUARIO_MINUTOS", "30"))
TOKEN_SERVICO_SEGUNDOS = int(os.environ.get("TOKEN_SERVICO_SEGUNDOS", "60"))

# Argon2id como algoritmo principal (recomendação atual do FastAPI/pwdlib:
# resistente a ataques com GPU), com bcrypt disponível para verificar hashes
# legados. PasswordHash.recommended() já monta essa combinação.
_hasher = PasswordHash.recommended()

# Diretório de usuários (seed fixo, igual nas 3 agências). As senhas ficam apenas
# como hash — nunca em texto puro. Estes usuários são os "donos" das contas; o
# vínculo conta<->dono é o que habilita a autorização de posse.
USUARIOS = {
    "ana": {"nome": "Ana", "senha_hash": _hasher.hash("senha-ana")},
    "bruno": {"nome": "Bruno", "senha_hash": _hasher.hash("senha-bruno")},
    "carla": {"nome": "Carla", "senha_hash": _hasher.hash("senha-carla")},
}


def verificar_senha(senha: str, senha_hash: str) -> bool:
    return _hasher.verify(senha, senha_hash)
