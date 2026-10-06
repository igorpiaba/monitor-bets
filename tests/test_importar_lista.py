from pathlib import Path

import pytest

from importar_lista import extrair_pares, montar_casas, validar
from monitor.arquivos import Casa

FIXTURES = Path(__file__).parent / "fixtures"


def texto(nome: str) -> str:
    return (FIXTURES / nome).read_bytes().decode("utf-8-sig")


def test_extrair_spa():
    assert extrair_pares(texto("spa.csv")) == [
        ("VAIDEBET", "vaidebet.bet.br"),
        ("BETPIX365", "betpix365.bet.br"),
        ("OBABET", "obabet.bet.br"),
    ]


def test_extrair_judicial_dois_blocos():
    pares = extrair_pares(texto("judicial.csv"))

    assert len(pares) == 6
    assert ("ZEROUM", "zeroum.bet") in pares
    assert ("ONLYBETS", "onlybets.bet.br") in pares


def test_sem_cabecalho_erro():
    with pytest.raises(ValueError):
        extrair_pares("a;b\n1;2")


def test_montar_casas():
    spa = [("VAIDEBET", "vaidebet.bet.br"), ("ONLYBETS", "onlybets.bet.br")]
    judicial = [("ZEROUM", "zeroum.bet"), ("ONLYBETS", "onlybets.bet.br")]

    casas = montar_casas(spa, judicial)

    assert Casa("Vaidebet", "vaidebet.bet.br", False) in casas
    assert Casa("Zeroum", "zeroum.bet", True) in casas
    assert [c for c in casas if c.site == "onlybets.bet.br"] == [
        Casa("Onlybets", "onlybets.bet.br", False)
    ]
    assert [c.casa for c in casas] == sorted(c.casa for c in casas)


def test_validar():
    validas = [Casa(f"Casa {i}", f"casa{i}.bet.br", False) for i in range(100)]

    with pytest.raises(ValueError):
        validar(validas[:99])
    validar(validas)
    with pytest.raises(ValueError):
        validar(validas + [Casa("X", "a definir", False)])
