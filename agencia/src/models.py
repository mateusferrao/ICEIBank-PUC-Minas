"""Schemas de entrada e saída (Pydantic) e a conversão de dinheiro.

A API fala em reais, do mesmo jeito que os exemplos do roteiro ({"valor": 25}),
mas por dentro tudo é guardado e somado em centavos (inteiro). Assim eu evito o
erro clássico de ponto flutuante em banco (0.1 + 0.2) sem mudar a interface que o
roteiro espera.
"""
from decimal import ROUND_HALF_UP, Decimal

from pydantic import BaseModel, Field


def reais_para_centavos(valor: float) -> int:
    """Converte reais (float) para centavos (int), arredondando para 2 casas."""
    centavos = (Decimal(str(valor)) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return int(centavos)


def centavos_para_reais(centavos: int) -> float:
    """Converte centavos (int) para reais (float com 2 casas)."""
    return float(Decimal(centavos) / 100)


# ---------------------------------------------------------------------------
# Entradas
# ---------------------------------------------------------------------------
class CriarContaIn(BaseModel):
    id: int = Field(..., ge=0, description="Identificador da conta (define a agência por id % 3)")
    nomeAluno: str | None = None
    saldoInicial: float = Field(0, ge=0, description="Saldo inicial em reais")


class ValorIn(BaseModel):
    valor: float = Field(..., gt=0, description="Valor da operação em reais")


class TransferenciaIn(BaseModel):
    idOrigem: int = Field(..., ge=0)
    idDestino: int = Field(..., ge=0)
    valor: float = Field(..., gt=0, description="Valor da transferência em reais")


class LoginIn(BaseModel):
    usuario: str
    senha: str
