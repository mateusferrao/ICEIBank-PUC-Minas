"""Configuração da agência: particionamento de contas, portas e autenticação.

As 3 agências usam este mesmo arquivo (o mesmo código roda 3 vezes, identificado
pela variável de ambiente AGENCIA_ID). Por isso o segredo do JWT e a lista de
usuários precisam ser iguais nas três. Só assim um usuário consegue logar em
qualquer agência que ele use como porta de entrada.
"""
import os

from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher

# TODO: substitua pelo seu OFFSET pessoal (dois últimos dígitos da matrícula/RA),
# necessário apenas se for rodar em uma máquina compartilhada do laboratório.
OFFSET = int(os.environ.get("OFFSET", "0"))

NUMERO_AGENCIAS = 3
PORTA_BASE = 4000 + OFFSET


def _host(id_agencia: int) -> str:
    # Deixa cada agência ser alcançada por um host diferente (por exemplo, dentro
    # de containers, pelo nome do serviço). Fora do Docker o padrão é localhost.
    return os.environ.get(f"AGENCIA_{id_agencia}_HOST", "localhost")


AGENCIAS = [
    {"id": i, "url": f"http://{_host(i)}:{PORTA_BASE + i}"} for i in range(NUMERO_AGENCIAS)
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
# segredos. Aqui dá para trocar por variável de ambiente, e tem um valor padrão de
# desenvolvimento para o projeto rodar sem configuração extra.
JWT_SECRET = os.environ.get("JWT_SECRET", "iceibank-sprint1-segredo-compartilhado")
JWT_ALGORITMO = "HS256"

# Expiração do token de usuário (em minutos).
TOKEN_USUARIO_MINUTOS = int(os.environ.get("TOKEN_USUARIO_MINUTOS", "30"))

# Uso Argon2id como único algoritmo de hash de senha (é o que o FastAPI/pwdlib
# recomenda hoje, resistente a ataque com GPU). Coloco ele direto, sem bcrypt,
# porque o projeto nunca gera hash antigo.
_hasher = PasswordHash((Argon2Hasher(),))

# Lista de usuários fixa, igual nas 3 agências. As senhas ficam só como hash,
# nunca em texto puro. Esses usuários são os donos das contas, e é o vínculo
# conta/dono que permite a autorização por posse.
USUARIOS = {
    "ana": {"nome": "Ana", "senha_hash": _hasher.hash("senha-ana")},
    "bruno": {"nome": "Bruno", "senha_hash": _hasher.hash("senha-bruno")},
    "carla": {"nome": "Carla", "senha_hash": _hasher.hash("senha-carla")},
}


def verificar_senha(senha: str, senha_hash: str) -> bool:
    return _hasher.verify(senha, senha_hash)
