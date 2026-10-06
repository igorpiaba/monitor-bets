import json
from datetime import datetime
from zoneinfo import ZoneInfo

import httpx
import pytest

from monitor.arquivos import Casa, escrever_casas
from monitor.rodada import executar


class Internet:
    """Simula as casas: cada site redireciona para o gov ou responde 200."""

    def __init__(self):
        self.respondendo = set()

    def cliente(self) -> httpx.Client:
        def handler(req):
            if req.url.host in self.respondendo:
                return httpx.Response(200)
            return httpx.Response(302, headers={"Location": "https://brasilsembets.gov.br/"})

        return httpx.Client(transport=httpx.MockTransport(handler))


class Telegram:
    def __init__(self, resposta=True):
        self.resposta = resposta
        self.chamadas = []

    def __call__(self, mensagens):
        self.chamadas.append(mensagens)
        return self.resposta


@pytest.fixture
def pasta(tmp_path):
    escrever_casas(tmp_path / "casas.csv", [
        Casa("A", "a.bet.br", False),
        Casa("B", "b.bet.br", False),
    ])
    return tmp_path


def rodar(pasta, internet, telegram, minuto):
    agora = datetime(2026, 10, 6, 14, minuto, tzinfo=ZoneInfo("America/Sao_Paulo"))
    return executar(pasta, internet.cliente(), agora, telegram, "https://painel")


def test_primeira_rodada_cria_arquivos(pasta):
    telegram = Telegram()

    rodar(pasta, Internet(), telegram, 0)

    estado = json.loads((pasta / "status.json").read_text(encoding="utf-8"))
    assert estado["totais"]["bloqueado"] == 2
    assert not (pasta / "historico.csv").exists()
    assert telegram.chamadas == []


def test_mudanca_confirmada_avisa_e_registra(pasta):
    internet, telegram = Internet(), Telegram()
    rodar(pasta, internet, telegram, 0)
    internet.respondendo.add("a.bet.br")
    rodar(pasta, internet, telegram, 10)
    mudancas = rodar(pasta, internet, telegram, 20)

    assert [m.site for m in mudancas] == ["a.bet.br"]
    historico = (pasta / "historico.csv").read_text(encoding="utf-8").splitlines()
    assert len(historico) == 2
    assert len(telegram.chamadas) == 1
    assert "parou de redirecionar" in telegram.chamadas[0][0]
    assert "Painel: https://painel" in telegram.chamadas[0][0]


def test_falha_no_envio_guarda_e_reenvia(pasta):
    internet, telegram = Internet(), Telegram(resposta=False)
    rodar(pasta, internet, telegram, 0)
    internet.respondendo.add("a.bet.br")
    rodar(pasta, internet, telegram, 10)
    rodar(pasta, internet, telegram, 20)

    estado = json.loads((pasta / "status.json").read_text(encoding="utf-8"))
    assert len(estado["avisos_pendentes"]) == 1

    telegram.resposta = True
    rodar(pasta, internet, telegram, 30)

    assert len(telegram.chamadas) == 2
    assert telegram.chamadas[1] == telegram.chamadas[0]
    estado = json.loads((pasta / "status.json").read_text(encoding="utf-8"))
    assert estado["avisos_pendentes"] == []
