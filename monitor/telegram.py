"""Monta e envia os alertas para o canal do Telegram."""

from datetime import datetime

import httpx

from monitor.checar import BLOQUEADO, RESPONDENDO
from monitor.estado import Mudanca

LIMITE = 4096


def _tamanho(texto: str) -> int:
    # O Telegram conta em unidades UTF-16: um emoji como 🟢 vale 2.
    return len(texto.encode("utf-16-le")) // 2


def _linha(m: Mudanca) -> str:
    if m.para == RESPONDENDO:
        texto = f"🟢 {m.casa} ({m.site}) voltou a abrir sem aviso de bloqueio."
        if m.de == BLOQUEADO:
            desde = datetime.fromisoformat(m.desde_anterior).strftime("%d/%m %H:%M")
            texto += f" Fora do ar desde {desde}."
        return texto
    return f"🔴 {m.casa} ({m.site}) voltou a ficar fora do ar."


def montar_mensagens(mudancas: list[Mudanca], painel_url: str) -> list[str]:
    alertas = [m for m in mudancas if m.alertar]
    linhas = [_linha(m) for m in alertas if m.para == RESPONDENDO]
    linhas += [_linha(m) for m in alertas if m.para != RESPONDENDO]
    if not linhas:
        return []

    rodape = f"\n\nPainel: {painel_url}"
    mensagens, atual = [], []
    for linha in linhas:
        candidata = "\n".join(atual + [linha]) + rodape
        if atual and _tamanho(candidata) > LIMITE:
            mensagens.append("\n".join(atual) + rodape)
            atual = []
        atual.append(linha)
    mensagens.append("\n".join(atual) + rodape)
    return mensagens


def enviar(mensagens: list[str], token: str, chat_id: str, cliente: httpx.Client) -> bool:
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        for texto in mensagens:
            resp = cliente.post(
                url,
                json={"chat_id": chat_id, "text": texto, "disable_web_page_preview": True},
            )
            if resp.status_code != 200 or not resp.json().get("ok"):
                return False
    except httpx.HTTPError:
        return False
    return True
