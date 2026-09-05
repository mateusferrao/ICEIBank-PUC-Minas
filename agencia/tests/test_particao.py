"""F1: particionamento de contas entre 3 agências."""
from src.config import NUMERO_AGENCIAS, agencia_responsavel


def test_numero_de_agencias_fixado_em_tres():
    assert NUMERO_AGENCIAS == 3


def test_conta_mapeia_para_agencia_por_modulo():
    # conta 0->0, 1->1, 2->2, 3->0, 4->1, 5->2 ...
    assert [agencia_responsavel(i) for i in range(6)] == [0, 1, 2, 0, 1, 2]


def test_agencia_responsavel_sempre_no_intervalo_valido():
    for i in range(0, 100):
        assert agencia_responsavel(i) in (0, 1, 2)
