import json

import httpx

from monitor.estado import Mudanca
from monitor.telegram import LIMITE, enviar, montar_mensagens

PAINEL = "https://x"


def mudanca(site="betano.bet.br", casa="Betano", de="bloqueado", para="respondendo",
            alertar=True):
    return Mudanca("2026-10-06T14:20:00-03:00", casa, site, de, para, "200",
                   "2026-09-25T00:10:00-03:00", alertar)


def test_mensagem_verde_com_desde():
    [msg] = montar_mensagens([mudanca()], PAINEL)
    assert msg.splitlines()[0] == (
        "🟢 Betano (betano.bet.br) parou de redirecionar para o gov.br e está "
        "respondendo. Bloqueada desde 25/09 00:10."
    )


def test_verde_vindo_de_indeterminado_sem_desde():
    [msg] = montar_mensagens([mudanca(de="indeterminado")], PAINEL)
    assert "Bloqueada desde" not in msg


def test_agrupa_numa_mensagem_verdes_primeiro():
    mudancas = [
        mudanca("a.bet.br", "A", de="respondendo", para="bloqueado"),
        mudanca("b.bet.br", "B"),
        mudanca("c.bet.br", "C"),
    ]

    [msg] = montar_mensagens(mudancas, PAINEL)

    linhas = msg.splitlines()
    assert [l[0] for l in linhas[:3]] == ["🟢", "🟢", "🔴"]
    assert linhas[2] == "🔴 A (a.bet.br) voltou a redirecionar para o gov.br."
    assert linhas[3] == ""
    assert linhas[4] == "Painel: https://x"


def test_ignora_nao_alertaveis():
    assert montar_mensagens([mudanca(alertar=False)], PAINEL) == []


def test_divide_mensagens_longas():
    # Linhas de 112 caracteres: cabem 36 por mensagem pelo len() do Python,
    # mas aí a contagem do Telegram passa de 4096.
    mudancas = [mudanca(f"casa{i:03d}.bet.br", f"Casa {i:03d}") for i in range(200)]

    mensagens = montar_mensagens(mudancas, PAINEL)

    assert len(mensagens) > 1
    linhas_de_mudanca = []
    for msg in mensagens:
        # O Telegram mede em unidades UTF-16: cada emoji 🟢 conta 2.
        assert len(msg.encode("utf-16-le")) // 2 <= LIMITE
        assert msg.endswith("\n\nPainel: https://x")
        linhas_de_mudanca += msg.split("\n\n")[0].splitlines()
    assert len(linhas_de_mudanca) == 200
    assert all(l.startswith("🟢 Casa ") and l.endswith("00:10.") for l in linhas_de_mudanca)


def test_enviar_sucesso_e_falha():
    pedidos = []

    def ok(req):
        pedidos.append(req)
        return httpx.Response(200, json={"ok": True})

    assert enviar(["oi"], "TOKEN", "-100", httpx.Client(transport=httpx.MockTransport(ok)))
    assert pedidos[0].url.path == "/botTOKEN/sendMessage"
    corpo = json.loads(pedidos[0].content)
    assert corpo["chat_id"] == "-100" and corpo["text"] == "oi"

    falha = httpx.MockTransport(lambda req: httpx.Response(400, json={"ok": False}))
    assert enviar(["oi"], "T", "C", httpx.Client(transport=falha)) is False

    def sem_rede(req):
        raise httpx.ConnectError("sem rede", request=req)

    assert enviar(["oi"], "T", "C", httpx.Client(transport=httpx.MockTransport(sem_rede))) is False
