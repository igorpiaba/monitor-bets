from monitor.checar import Resultado
from monitor.navegador import classificar_texto, refinar

MARCADORES = ["1.394", "brasilsembets", "indispon", "acreditamos na regulamentação"]
URL = "https://x.bet.br/"
TEXTO_CASSINO = (
    "Cassino Esportes Entrar Cadastre-se Jogos Cassino ao vivo Crash Slots "
    "Promoções Bônus de boas-vindas"
)


def test_classificar_js_para_gov():
    r = classificar_texto("Acesso bloqueado", "https://www.brasilsembets.gov.br/", MARCADORES)
    assert r == Resultado("bloqueado", "js -> www.brasilsembets.gov.br")


def test_classificar_anti_robo():
    texto = "x.bet.br Executando verificação de segurança. Este site utiliza um serviço de segurança"
    assert classificar_texto(texto, URL, MARCADORES) == Resultado("indeterminado", "anti-robô")


def test_classificar_paginas_de_erro():
    erros = [
        "Error 1000 Ray ID: a4647c34bf39af29 • 2026-10-06 11:56:51 UTC DNS points to prohibited IP",
        "Connection timed out Error code 522 Visit cloudflare.com for more information.",
        "Sorry, you have been blocked You are unable to access x.bet.br Why have I been blocked?",
        "This page doesn’t exist It may have been moved, removed, or never existed. 404 DEPLOYMENT_NOT_FOUND",
    ]
    for texto in erros:
        assert classificar_texto(texto, URL, MARCADORES) == Resultado(
            "indeterminado", "página de erro"
        ), texto


def test_classificar_pagina_vazia():
    assert classificar_texto("  ", URL, MARCADORES) == Resultado("indeterminado", "página vazia")


def test_classificar_aviso():
    texto = "Plataforma inativa. O site está indisponível em cumprimento à Medida Provisória nº 1.394/2026."
    assert classificar_texto(texto, URL, MARCADORES) == Resultado("bloqueado", "aviso: 1.394")


def test_classificar_manifesto_por_cima_do_cassino():
    texto = TEXTO_CASSINO + " Manifesto Nós acreditamos no Brasil, e acreditamos na regulamentação."
    assert classificar_texto(texto, URL, MARCADORES).status == "bloqueado"


def test_classificar_sem_aviso():
    assert classificar_texto(TEXTO_CASSINO, URL, MARCADORES) == Resultado("respondendo", "sem aviso")


def test_refinar_so_nao_bloqueados():
    chamadas = []

    def renderizar(sites):
        chamadas.append(sites)
        return {s: (TEXTO_CASSINO, f"https://{s}/") for s in sites}

    observados = {
        "a.bet.br": Resultado("bloqueado", "302 -> brasilsembets.gov.br"),
        "b.bet.br": Resultado("respondendo", "200"),
        "c.bet.br": Resultado("indeterminado", "403"),
    }

    refinado = refinar(observados, renderizar, MARCADORES)

    assert chamadas == [["b.bet.br", "c.bet.br"]]
    assert refinado["a.bet.br"] == observados["a.bet.br"]
    assert refinado["b.bet.br"] == Resultado("respondendo", "sem aviso")
    assert refinado["c.bet.br"] == Resultado("respondendo", "sem aviso")


def test_refinar_erro_do_navegador():
    observados = {"b.bet.br": Resultado("respondendo", "200")}

    refinado = refinar(observados, lambda sites: {"b.bet.br": "TimeoutError"}, MARCADORES)

    assert refinado["b.bet.br"] == Resultado("indeterminado", "navegador: TimeoutError")
