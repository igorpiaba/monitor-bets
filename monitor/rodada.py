"""Uma rodada completa: checa todos os sites, atualiza os dados e avisa.

Uso: python -m monitor.rodada
"""

import os
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx

from monitor.arquivos import (
    anexar_historico,
    ler_casas,
    ler_estado,
    ler_marcadores,
    salvar_estado,
)
from monitor.checar import checar_todos, novo_cliente
from monitor.estado import Mudanca, aplicar_rodada
from monitor.navegador import Pagina, refinar
from monitor.telegram import enviar, montar_mensagens


def executar(
    pasta_dados: Path,
    cliente: httpx.Client,
    agora: datetime,
    enviar_fn: Callable[[list[str]], bool] | None,
    painel_url: str,
    renderizar_fn: Callable[[list[str]], dict[str, Pagina | str]] | None = None,
) -> list[Mudanca]:
    casas = ler_casas(pasta_dados / "casas.csv")
    estado = ler_estado(pasta_dados / "status.json")

    observados = checar_todos([c.site for c in casas], cliente)
    if renderizar_fn:
        marcadores = ler_marcadores(pasta_dados / "marcadores.txt")
        observados = refinar(observados, renderizar_fn, marcadores)
    novo, mudancas = aplicar_rodada(estado, casas, observados, agora)

    if mudancas:
        anexar_historico(pasta_dados / "historico.csv", [m.para_dict() for m in mudancas])

    a_avisar = [Mudanca.de_dict(d) for d in novo["avisos_pendentes"]]
    a_avisar += [m for m in mudancas if m.alertar]
    mensagens = montar_mensagens(a_avisar, painel_url)
    ok = bool(mensagens) and enviar_fn is not None and enviar_fn(mensagens)
    if mensagens and not ok:
        # Sem Telegram (token ausente) ou falha no envio: guarda para a próxima rodada.
        for msg in mensagens:
            print(msg)
    novo["avisos_pendentes"] = [] if ok or not a_avisar else [m.para_dict() for m in a_avisar]

    salvar_estado(pasta_dados / "status.json", novo)
    return mudancas


def main() -> None:
    token = os.environ.get("TELEGRAM_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    painel_url = os.environ.get("PAINEL_URL", "")

    enviar_fn = None
    if token and chat_id:
        cliente_tg = httpx.Client(timeout=30)
        enviar_fn = lambda msgs: enviar(msgs, token, chat_id, cliente_tg)  # noqa: E731

    # Sem a etapa do navegador, ~50 casas com aviso próprio virariam 🟢 falsas:
    # se o Playwright faltar, a rodada falha em vez de seguir só com o HTTP.
    from monitor.navegador import renderizar

    with novo_cliente() as cliente:
        mudancas = executar(
            Path("dados"),
            cliente,
            datetime.now(ZoneInfo("America/Sao_Paulo")),
            enviar_fn,
            painel_url,
            renderizar,
        )

    estado = ler_estado(Path("dados/status.json"))
    if estado.get("ultima_rodada_valida") != estado["ultima_rodada"]:
        print("Rodada descartada: falhas de rede em mais da metade dos sites.")
    totais = estado["totais"]
    print(
        f"🔴 {totais['bloqueado']} bloqueadas · 🟢 {totais['respondendo']} respondendo · "
        f"⚪ {totais['indeterminado']} indeterminadas · {len(mudancas)} mudança(s)"
    )


if __name__ == "__main__":
    main()
