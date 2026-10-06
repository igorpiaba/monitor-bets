import httpx

from monitor.checar import Resultado, checar, checar_todos


def cliente_com(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=False)


def redireciona(destino: str, codigo: int = 302) -> httpx.Response:
    return httpx.Response(codigo, headers={"Location": destino})


def test_redirect_para_gov():
    c = cliente_com(lambda req: redireciona("https://brasilsembets.gov.br/"))
    assert checar("x.bet.br", c) == Resultado("bloqueado", "302 -> brasilsembets.gov.br")


def test_redirect_para_www_gov():
    c = cliente_com(lambda req: redireciona("https://www.brasilsembets.gov.br/"))
    assert checar("x.bet.br", c).status == "bloqueado"


def test_redirecionamento_em_cadeia_ate_gov():
    hosts_pedidos = []

    def handler(req):
        hosts_pedidos.append(req.url.host)
        if req.url.host == "x.bet.br":
            return redireciona("https://www.x.bet.br/", 301)
        if req.url.host == "www.x.bet.br":
            return redireciona("https://brasilsembets.gov.br/")
        return httpx.Response(200)

    assert checar("x.bet.br", cliente_com(handler)).status == "bloqueado"
    assert hosts_pedidos == ["x.bet.br", "www.x.bet.br"]


def test_200_respondendo():
    c = cliente_com(lambda req: httpx.Response(200))
    assert checar("x.bet.br", c) == Resultado("respondendo", "200")

    def handler(req):
        if req.url.host == "x.bet.br":
            return redireciona("https://www.x.bet.br/", 301)
        return httpx.Response(200)

    assert checar("x.bet.br", cliente_com(handler)).status == "respondendo"


def test_codigos_indeterminados():
    for codigo in (403, 429, 503):
        c = cliente_com(lambda req, codigo=codigo: httpx.Response(codigo))
        assert checar("x.bet.br", c) == Resultado("indeterminado", str(codigo))


def test_erros_de_rede():
    def timeout(req):
        raise httpx.ConnectTimeout("demorou", request=req)

    def sem_dns(req):
        raise httpx.ConnectError("[Errno 8] nodename nor servname", request=req)

    assert checar("x.bet.br", cliente_com(timeout)) == Resultado("indeterminado", "timeout")
    r = checar("x.bet.br", cliente_com(sem_dns))
    assert r.status == "indeterminado"
    assert r.motivo.startswith("erro de conexão")


def test_location_relativo_e_ausente():
    def relativo(req):
        if req.url.path == "/":
            return redireciona("/home")
        return httpx.Response(200)

    assert checar("x.bet.br", cliente_com(relativo)).status == "respondendo"

    c = cliente_com(lambda req: httpx.Response(302))
    assert checar("x.bet.br", c) == Resultado("indeterminado", "302 sem Location")


def test_excesso_de_redirecionamentos():
    c = cliente_com(lambda req: redireciona("https://x.bet.br/"))
    assert checar("x.bet.br", c) == Resultado("indeterminado", "redirecionamentos demais")


def test_checar_todos():
    def handler(req):
        if req.url.host == "a.bet.br":
            return redireciona("https://brasilsembets.gov.br/")
        if req.url.host == "b.bet.br":
            return httpx.Response(200)
        return httpx.Response(403)

    resultado = checar_todos(["a.bet.br", "b.bet.br", "c.bet.br"], cliente_com(handler))

    assert {s: r.status for s, r in resultado.items()} == {
        "a.bet.br": "bloqueado",
        "b.bet.br": "respondendo",
        "c.bet.br": "indeterminado",
    }


def test_host_parecido_nao_e_gov():
    def handler(req):
        if req.url.host == "x.bet.br":
            return redireciona("https://brasilsembets.gov.br.golpe.com/")
        return httpx.Response(200)

    assert checar("x.bet.br", cliente_com(handler)).status != "bloqueado"
