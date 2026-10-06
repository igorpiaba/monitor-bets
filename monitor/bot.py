"""Responde comandos no chat privado com o bot (/status, /casa nome).

Fica rodando no Mac (launchd, KeepAlive) e lê dados/status.json a cada pedido.
Uso: python -m monitor.bot
"""

import os
import time
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx

from monitor.arquivos import ler_estado
from monitor.checar import BLOQUEADO, INDETERMINADO, RESPONDENDO
from monitor.telegram import enviar

FUSO = ZoneInfo("America/Sao_Paulo")
MAX_RESULTADOS = 10
ICONE = {BLOQUEADO: "🔴", RESPONDENDO: "🟢", INDETERMINADO: "⚪"}
ROTULO = {BLOQUEADO: "fora do ar", RESPONDENDO: "no ar", INDETERMINADO: "indeterminada"}
AJUDA = (
    "Comandos:\n"
    "/status: placar e casas que estão no ar\n"
    "/casa nome: status de uma casa (ex.: /casa betano)"
)
COMANDOS = [
    {"command": "status", "description": "Placar e casas que estão no ar"},
    {"command": "casa", "description": "Status de uma casa (ex.: /casa betano)"},
]


def _data(iso: str) -> str:
    return datetime.fromisoformat(iso).astimezone(FUSO).strftime("%d/%m %H:%M")


def _ha_quanto(iso: str, agora: datetime) -> str:
    minutos = max(0, round((agora - datetime.fromisoformat(iso)).total_seconds() / 60))
    if minutos < 60:
        return f"há {minutos} min"
    return f"há {round(minutos / 60)} h"


def _status(estado: dict, agora: datetime, painel_url: str) -> str:
    t = estado["totais"]
    ultima = estado.get("ultima_rodada_valida") or estado["ultima_rodada"]
    no_ar = sorted(
        (s for s in estado["sites"].items() if s[1]["status"] == RESPONDENDO),
        key=lambda s: s[1]["casa"],
    )
    linhas = [
        f"🔴 {t[BLOQUEADO]} fora do ar · 🟢 {t[RESPONDENDO]} no ar · "
        f"⚪ {t[INDETERMINADO]} indeterminadas",
        f"Última checagem: {_ha_quanto(ultima, agora)}.",
        "",
    ]
    if no_ar:
        linhas += [f"🟢 {s['casa']} ({site}) desde {_data(s['desde'])}" for site, s in no_ar]
    else:
        linhas.append("Nenhuma casa no ar no momento.")
    linhas += ["", f"Painel: {painel_url}"]
    return "\n".join(linhas)


def _casa(termo: str, estado: dict) -> str:
    if not termo:
        return "Use: /casa nome (ex.: /casa betano)"
    termo = termo.lower()
    achados = sorted(
        (
            (site, s)
            for site, s in estado["sites"].items()
            # Só a primeira parte do domínio: todo site termina em ".bet.br".
            if termo in s["casa"].lower() or termo in site.split(".")[0]
        ),
        key=lambda x: x[1]["casa"],
    )
    if not achados:
        return f"Nenhuma casa encontrada para “{termo}”."
    linhas = []
    for site, s in achados[:MAX_RESULTADOS]:
        linha = f"{ICONE[s['status']]} {s['casa']} ({site}): {ROTULO[s['status']]} desde {_data(s['desde'])}"
        if s["status"] == INDETERMINADO:
            linha += f" ({s['motivo']})"
        linhas.append(linha)
    if len(achados) > MAX_RESULTADOS:
        linhas.append(f"… e mais {len(achados) - MAX_RESULTADOS}; seja mais específico.")
    return "\n".join(linhas)


def responder(texto: str, estado: dict, agora: datetime, painel_url: str) -> str:
    comando, _, resto = texto.strip().partition(" ")
    comando = comando.split("@")[0].lower()
    if comando == "/status":
        return _status(estado, agora, painel_url)
    if comando == "/casa":
        return _casa(resto.strip(), estado)
    return AJUDA


def processar(
    updates: list[dict],
    estado_fn: Callable[[], dict],
    agora: datetime,
    painel_url: str,
    enviar_fn: Callable[[int, str], bool],
) -> int | None:
    """Responde as mensagens privadas e devolve o próximo offset do getUpdates."""
    proximo = None
    for u in updates:
        proximo = u["update_id"] + 1
        msg = u.get("message")
        if not msg or msg["chat"].get("type") != "private" or "text" not in msg:
            continue
        enviar_fn(msg["chat"]["id"], responder(msg["text"], estado_fn(), agora, painel_url))
    return proximo


def main() -> None:
    token = os.environ["TELEGRAM_TOKEN"]
    painel_url = os.environ.get("PAINEL_URL", "")
    api = f"https://api.telegram.org/bot{token}"
    caminho = Path("dados/status.json")
    cliente = httpx.Client(timeout=70)

    try:
        cliente.post(f"{api}/setMyCommands", json={"commands": COMANDOS})
    except httpx.HTTPError:
        pass  # o menu de comandos é só conveniência

    offset = None
    print("Bot ouvindo comandos…", flush=True)
    while True:
        try:
            resp = cliente.get(f"{api}/getUpdates", params={"timeout": 50, "offset": offset})
            updates = resp.json().get("result", [])
            novo = processar(
                updates,
                lambda: ler_estado(caminho),
                datetime.now(FUSO),
                painel_url,
                lambda chat_id, texto: enviar([texto], token, str(chat_id), cliente),
            )
            if novo is not None:
                offset = novo
        except (httpx.HTTPError, ValueError) as e:
            print(f"erro: {type(e).__name__}; tentando de novo em 10 s", flush=True)
            time.sleep(10)


if __name__ == "__main__":
    main()
