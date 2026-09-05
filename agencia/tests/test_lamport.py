"""F2 — Relógio de Lamport (testado isoladamente, antes de plugar na API)."""
from src.services.lamport import RelogioLamport


def test_evento_local_incrementa_de_um_em_um():
    r = RelogioLamport()
    assert r.evento_local() == 1
    assert r.evento_local() == 2
    assert r.evento_local() == 3


def test_ao_enviar_tambem_incrementa():
    r = RelogioLamport()
    r.evento_local()  # 1
    assert r.ao_enviar() == 2


def test_ao_receber_usa_max_mais_um_quando_recebido_e_maior():
    r = RelogioLamport()
    r.evento_local()  # contador = 1
    # recebe timestamp 10 -> max(1, 10) + 1 = 11
    assert r.ao_receber(10) == 11


def test_ao_receber_usa_max_mais_um_quando_local_e_maior():
    r = RelogioLamport()
    for _ in range(10):
        r.evento_local()  # contador = 10
    # recebe timestamp 3 (agência mais "atrasada") -> max(10, 3) + 1 = 11
    assert r.ao_receber(3) == 11


def test_sequencia_causal_preserva_ordem():
    # A envia (ts) e B recebe -> timestamp(B) > timestamp(A)
    a = RelogioLamport()
    b = RelogioLamport()
    ts_envio = a.ao_enviar()
    ts_recebido = b.ao_receber(ts_envio)
    assert ts_recebido > ts_envio
