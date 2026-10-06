from monitor.arquivos import (
    Casa,
    anexar_historico,
    escrever_casas,
    ler_casas,
    ler_estado,
    salvar_estado,
)


def test_casas_ida_e_volta(tmp_path):
    caminho = tmp_path / "casas.csv"
    casas = [
        Casa("Betano", "betano.bet.br", False),
        Casa("Zeroum", "zeroum.bet", True),
    ]

    escrever_casas(caminho, casas)

    assert ler_casas(caminho) == casas
    linhas = caminho.read_text(encoding="utf-8").splitlines()
    assert linhas[0] == "casa,site,liminar"
    assert linhas[2] == "Zeroum,zeroum.bet,sim"


def test_ler_estado_inexistente(tmp_path):
    assert ler_estado(tmp_path / "x.json") == {}


def test_salvar_estado_utf8(tmp_path):
    caminho = tmp_path / "status.json"
    estado = {"sites": {"betao.bet.br": {"casa": "Betão"}}}

    salvar_estado(caminho, estado)

    assert "Betão" in caminho.read_text(encoding="utf-8")
    assert ler_estado(caminho) == estado


def test_anexar_historico_cria_cabecalho_uma_vez(tmp_path):
    caminho = tmp_path / "historico.csv"
    linha = {
        "data_hora": "2026-10-06T14:30:00-03:00",
        "casa": "Betano",
        "site": "betano.bet.br",
        "de": "bloqueado",
        "para": "respondendo",
        "motivo": "200",
        "alertar": True,  # chave extra: deve ser ignorada
    }

    anexar_historico(caminho, [linha])
    anexar_historico(caminho, [linha])

    linhas = caminho.read_text(encoding="utf-8").splitlines()
    assert len(linhas) == 3
    assert linhas[0] == "data_hora,casa,site,de,para,motivo"
    assert linhas[1] == "2026-10-06T14:30:00-03:00,Betano,betano.bet.br,bloqueado,respondendo,200"
