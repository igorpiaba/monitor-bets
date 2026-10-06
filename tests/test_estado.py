import copy
from datetime import datetime
from zoneinfo import ZoneInfo

from monitor.arquivos import Casa
from monitor.checar import Resultado
from monitor.estado import Mudanca, aplicar_rodada

SITES = ["a.bet.br", "b.bet.br", "c.bet.br"]


def casas_de(sites):
    return [Casa(s.split(".")[0].upper(), s, False) for s in sites]


def rodada(estado, obs=None, minuto=0, sites=SITES):
    """Uma rodada em que todo site está bloqueado, salvo o que `obs` disser."""
    obs = obs or {}
    motivos = {"indeterminado": "navegador: TimeoutError"}
    observados = {
        s: Resultado(obs.get(s, "bloqueado"), motivos.get(obs.get(s, "bloqueado"), "motivo"))
        for s in sites
    }
    agora = datetime(2026, 10, 6, 14, minuto, tzinfo=ZoneInfo("America/Sao_Paulo"))
    return aplicar_rodada(estado, casas_de(sites), observados, agora)


def test_primeira_rodada_sem_mudancas():
    estado, mudancas = rodada({})

    assert mudancas == []
    assert set(estado["sites"]) == set(SITES)
    assert estado["totais"] == {"bloqueado": 3, "respondendo": 0, "indeterminado": 0}
    assert estado["ultima_rodada"] == "2026-10-06T14:00:00-03:00"
    assert estado["avisos_pendentes"] == []
    a = estado["sites"]["a.bet.br"]
    assert a["status"] == "bloqueado"
    assert a["desde"] == "2026-10-06T14:00:00-03:00"
    assert a["ultimo_definido"] == "bloqueado"
    assert a["pendente"] is None


def test_uma_observacao_so_marca_pendente():
    estado, _ = rodada({})
    estado, mudancas = rodada(estado, {"a.bet.br": "respondendo"}, minuto=10)

    a = estado["sites"]["a.bet.br"]
    assert mudancas == []
    assert a["status"] == "bloqueado"
    assert a["pendente"]["status"] == "respondendo"


def test_duas_observacoes_confirmam():
    estado, _ = rodada({})
    estado, _ = rodada(estado, {"a.bet.br": "respondendo"}, minuto=10)
    estado, mudancas = rodada(estado, {"a.bet.br": "respondendo"}, minuto=20)

    assert mudancas == [
        Mudanca(
            data_hora="2026-10-06T14:20:00-03:00",
            casa="A",
            site="a.bet.br",
            de="bloqueado",
            para="respondendo",
            motivo="motivo",
            desde_anterior="2026-10-06T14:00:00-03:00",
            alertar=True,
        )
    ]
    a = estado["sites"]["a.bet.br"]
    assert a["status"] == "respondendo"
    assert a["desde"] == "2026-10-06T14:20:00-03:00"
    assert a["pendente"] is None
    assert estado["totais"] == {"bloqueado": 2, "respondendo": 1, "indeterminado": 0}


def test_oscilacao_nao_confirma():
    estado, _ = rodada({})
    estado, m1 = rodada(estado, {"a.bet.br": "respondendo"}, minuto=10)
    estado, m2 = rodada(estado, {}, minuto=20)

    assert m1 == m2 == []
    assert estado["sites"]["a.bet.br"]["pendente"] is None


def test_ida_e_volta_por_indeterminado_nao_gera_alerta():
    estado, _ = rodada({})
    estado, _ = rodada(estado, {"a.bet.br": "indeterminado"}, minuto=10)
    estado, ida = rodada(estado, {"a.bet.br": "indeterminado"}, minuto=20)
    estado, _ = rodada(estado, {}, minuto=30)
    estado, volta = rodada(estado, {}, minuto=40)

    assert [(m.para, m.alertar) for m in ida] == [("indeterminado", False)]
    assert [(m.para, m.alertar) for m in volta] == [("bloqueado", False)]


def test_indeterminado_para_respondendo_alerta():
    estado, _ = rodada({})
    estado, _ = rodada(estado, {"a.bet.br": "indeterminado"}, minuto=10)
    estado, _ = rodada(estado, {"a.bet.br": "indeterminado"}, minuto=20)
    estado, _ = rodada(estado, {"a.bet.br": "respondendo"}, minuto=30)
    estado, mudancas = rodada(estado, {"a.bet.br": "respondendo"}, minuto=40)

    assert len(mudancas) == 1
    assert (mudancas[0].de, mudancas[0].para, mudancas[0].alertar) == (
        "indeterminado",
        "respondendo",
        True,
    )


def test_rodada_descartada_preserva_pendentes():
    estado, _ = rodada({})
    estado, _ = rodada(estado, {"a.bet.br": "respondendo"}, minuto=10)
    antes = copy.deepcopy(estado)

    estado, mudancas = rodada(
        estado, {"b.bet.br": "indeterminado", "c.bet.br": "indeterminado"}, minuto=20
    )

    assert mudancas == []
    assert estado["ultima_rodada"] == "2026-10-06T14:20:00-03:00"
    assert estado["sites"] == antes["sites"]
    assert estado["sites"]["a.bet.br"]["pendente"]["status"] == "respondendo"


def test_casa_nova_entra_sem_alerta_e_removida_sai():
    estado, _ = rodada({})
    novos = ["a.bet.br", "b.bet.br", "d.bet.br"]

    estado, mudancas = rodada(estado, {"d.bet.br": "respondendo"}, minuto=10, sites=novos)

    assert mudancas == []
    assert set(estado["sites"]) == set(novos)
    assert estado["sites"]["d.bet.br"]["status"] == "respondendo"


def test_nao_altera_estado_recebido():
    estado, _ = rodada({})
    original = copy.deepcopy(estado)

    rodada(estado, {"a.bet.br": "respondendo"}, minuto=10)

    assert estado == original


def test_mudanca_dict_ida_e_volta():
    m = Mudanca("2026-10-06T14:20:00-03:00", "A", "a.bet.br", "bloqueado",
                "respondendo", "200", "2026-10-06T14:00:00-03:00", True)
    assert Mudanca.de_dict(m.para_dict()) == m


def test_indeterminado_inicial_para_bloqueado_nao_alerta():
    estado, _ = rodada({}, {"a.bet.br": "indeterminado"})
    estado, _ = rodada(estado, {}, minuto=10)
    estado, mudancas = rodada(estado, {}, minuto=20)

    assert [(m.de, m.para, m.alertar) for m in mudancas] == [
        ("indeterminado", "bloqueado", False)
    ]


def test_indeterminado_inicial_para_respondendo_alerta():
    estado, _ = rodada({}, {"a.bet.br": "indeterminado"})
    estado, _ = rodada(estado, {"a.bet.br": "respondendo"}, minuto=10)
    estado, mudancas = rodada(estado, {"a.bet.br": "respondendo"}, minuto=20)

    assert [m.alertar for m in mudancas] == [True]


def test_indeterminado_no_meio_nao_apaga_pendente():
    estado, _ = rodada({})
    estado, _ = rodada(estado, {"a.bet.br": "respondendo"}, minuto=10)
    estado, _ = rodada(estado, {"a.bet.br": "indeterminado"}, minuto=20)
    estado, mudancas = rodada(estado, {"a.bet.br": "respondendo"}, minuto=30)

    assert [(m.para, m.alertar) for m in mudancas] == [("respondendo", True)]


def test_motivo_so_muda_com_o_status():
    estado, _ = rodada({})
    motivo_original = estado["sites"]["a.bet.br"]["motivo"]

    estado, _ = rodada(estado, {"a.bet.br": "respondendo"}, minuto=10)

    a = estado["sites"]["a.bet.br"]
    assert a["status"] == "bloqueado"
    assert a["motivo"] == motivo_original
    assert a["pendente"]["motivo"] == "motivo"


def test_descarte_conta_so_falhas_de_rede():
    sites = ["a.bet.br", "b.bet.br", "c.bet.br"]
    agora = datetime(2026, 10, 6, 14, 0, tzinfo=ZoneInfo("America/Sao_Paulo"))
    observados = {
        "a.bet.br": Resultado("bloqueado", "302 -> brasilsembets.gov.br"),
        "b.bet.br": Resultado("indeterminado", "anti-robô"),
        "c.bet.br": Resultado("indeterminado", "página de erro"),
    }

    estado, _ = aplicar_rodada({}, casas_de(sites), observados, agora)

    assert set(estado["sites"]) == set(sites)
    assert estado["ultima_rodada_valida"] == "2026-10-06T14:00:00-03:00"


def test_rodada_descartada_nao_atualiza_ultima_valida():
    estado, _ = rodada({})
    estado, _ = rodada(
        estado, {"b.bet.br": "indeterminado", "c.bet.br": "indeterminado"}, minuto=10
    )

    assert estado["ultima_rodada"] == "2026-10-06T14:10:00-03:00"
    assert estado["ultima_rodada_valida"] == "2026-10-06T14:00:00-03:00"
