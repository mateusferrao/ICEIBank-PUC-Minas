"""Relógio vetorial (Sprint 2, Parte B), testado sozinho antes de ligar na API."""
from src.services.vetorial import RelogioVetorial, comparar


def test_comeca_zerado_com_uma_posicao_por_agencia():
    r = RelogioVetorial(1, 3)
    assert r.vetor == [0, 0, 0]


def test_evento_local_incrementa_so_a_propria_posicao():
    r = RelogioVetorial(1, 3)
    assert r.evento_local() == [0, 1, 0]
    assert r.evento_local() == [0, 2, 0]


def test_ao_enviar_incrementa_a_propria_posicao():
    r = RelogioVetorial(0, 3)
    r.evento_local()
    assert r.ao_enviar() == [2, 0, 0]


def test_ao_receber_faz_max_posicao_a_posicao_e_incrementa_a_propria():
    r = RelogioVetorial(1, 3)
    r.evento_local()  # [0, 1, 0]
    # recebe [3, 0, 2] -> max = [3, 1, 2] -> incrementa a posicao 1 -> [3, 2, 2]
    assert r.ao_receber([3, 0, 2]) == [3, 2, 2]


def test_retorna_copia_e_nao_o_vetor_interno():
    r = RelogioVetorial(0, 3)
    v = r.evento_local()
    v[0] = 99
    assert r.vetor == [1, 0, 0]


def test_envio_seguido_de_recebimento_preserva_causalidade():
    a = RelogioVetorial(0, 3)
    b = RelogioVetorial(1, 3)
    v_envio = a.ao_enviar()
    v_receb = b.ao_receber(v_envio)
    assert comparar(v_envio, v_receb) == "ANTES"
    assert comparar(v_receb, v_envio) == "DEPOIS"


def test_comparar_exemplo_6_4_pergunta_2():
    # V1 = [3,1,0], V2 = [3,2,0] -> V1 aconteceu antes de V2
    assert comparar([3, 1, 0], [3, 2, 0]) == "ANTES"


def test_comparar_exemplo_6_4_pergunta_3():
    # V1 = [3,1,0], V2 = [1,3,0] -> concorrentes
    assert comparar([3, 1, 0], [1, 3, 0]) == "CONCORRENTES"


def test_comparar_iguais():
    assert comparar([1, 2, 3], [1, 2, 3]) == "IGUAIS"


def test_eventos_independentes_em_agencias_diferentes_sao_concorrentes():
    a = RelogioVetorial(0, 3)
    b = RelogioVetorial(1, 3)
    assert comparar(a.evento_local(), b.evento_local()) == "CONCORRENTES"


def test_restaurar_assume_o_maximo_sem_criar_evento():
    r = RelogioVetorial(1, 3)
    r.restaurar([2, 5, 1])
    r.restaurar([4, 3, 0])  # vetor mais antigo não faz o relógio voltar
    assert r.atual() == [4, 5, 1]
    assert r.evento_local() == [4, 6, 1]
