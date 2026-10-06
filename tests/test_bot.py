from datetime import datetime
from zoneinfo import ZoneInfo

from monitor.bot import processar, responder

AGORA = datetime(2026, 10, 6, 14, 30, tzinfo=ZoneInfo("America/Sao_Paulo"))
PAINEL = "https://painel"


def site(casa, status, desde="2026-09-25T00:10:00-03:00", motivo="302 -> brasilsembets.gov.br"):
    return {"casa": casa, "status": status, "desde": desde, "motivo": motivo,
            "liminar": False, "pendente": None}


ESTADO = {
    "ultima_rodada": "2026-10-06T14:20:00-03:00",
    "ultima_rodada_valida": "2026-10-06T14:20:00-03:00",
    "totais": {"bloqueado": 2, "respondendo": 1, "indeterminado": 1},
    "sites": {
        "betano.bet.br": site("Betano", "bloqueado"),
        "betpix365.bet.br": site("Betpix365", "bloqueado"),
        "sportvip.bet": site("Sportvip", "respondendo", "2026-10-06T09:47:00-03:00", "sem aviso"),
        "bet365.bet.br": site("Bet365", "indeterminado", motivo="anti-robô"),
    },
}


def test_status():
    texto = responder("/status", ESTADO, AGORA, PAINEL)

    assert "🔴 2 fora do ar · 🟢 1 no ar · ⚪ 1 indeterminadas" in texto
    assert "Última checagem: há 10 min" in texto
    assert "🟢 Sportvip (sportvip.bet) desde 06/10 09:47" in texto
    assert texto.endswith("Painel: https://painel")


def test_status_sem_casas_no_ar():
    estado = {**ESTADO, "sites": {"betano.bet.br": site("Betano", "bloqueado")}}
    assert "Nenhuma casa no ar no momento." in responder("/status", estado, AGORA, PAINEL)


def test_comando_com_nome_do_bot():
    assert responder("/status@DronhaBot", ESTADO, AGORA, PAINEL) == responder(
        "/status", ESTADO, AGORA, PAINEL
    )


def test_casa_encontra_por_nome_ou_site():
    texto = responder("/casa BET", ESTADO, AGORA, PAINEL)

    assert "🔴 Betano (betano.bet.br): fora do ar desde 25/09 00:10" in texto
    assert "⚪ Bet365 (bet365.bet.br): indeterminada desde 25/09 00:10 (anti-robô)" in texto
    assert "Betpix365" in texto
    assert "Sportvip" not in texto


def test_casa_nao_encontrada_e_sem_termo():
    assert "Nenhuma casa encontrada para “xyz”" in responder("/casa xyz", ESTADO, AGORA, PAINEL)
    assert "Use: /casa nome" in responder("/casa", ESTADO, AGORA, PAINEL)


def test_casa_limita_resultados():
    sites = {f"casa{i}.bet.br": site(f"Casa {i}", "bloqueado") for i in range(15)}
    texto = responder("/casa casa", {**ESTADO, "sites": sites}, AGORA, PAINEL)

    assert texto.count("🔴") == 10
    assert "e mais 5" in texto


def test_qualquer_outra_mensagem_mostra_ajuda():
    for msg in ("/start", "/ajuda", "oi"):
        texto = responder(msg, ESTADO, AGORA, PAINEL)
        assert "/status" in texto and "/casa" in texto


def test_processar_responde_mensagens_privadas_e_ignora_canal():
    enviados = []
    updates = [
        {"update_id": 10, "message": {"chat": {"id": 111, "type": "private"}, "text": "/status"}},
        {"update_id": 11, "channel_post": {"chat": {"id": -100, "type": "channel"}, "text": "/status"}},
        {"update_id": 12, "message": {"chat": {"id": 222, "type": "private"}}},  # sem texto (foto)
    ]

    offset = processar(updates, lambda: ESTADO, AGORA, PAINEL,
                       lambda chat_id, texto: enviados.append((chat_id, texto)) or True)

    assert offset == 13
    assert [chat for chat, _ in enviados] == [111]
    assert "fora do ar" in enviados[0][1]
