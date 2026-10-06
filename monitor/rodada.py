"""Uma rodada completa: checa todos os sites, atualiza os dados e avisa.

Uso: python -m monitor.rodada
"""

import os
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx

from monitor.arquivos import anexar_historico, ler_casas, ler_estado, salvar_estado
from monitor.checar import checar_todos, novo_cliente
from monitor.estado import Mudanca, aplicar_rodada
from monitor.telegram import enviar, montar_mensagens


def executar(
    pasta_dados: Path,
    cliente: httpx.Client,
    agora: datetime,
    enviar_fn: Callable[[list[str]], bool] | None,
    painel_url: str,
) -> list[Mudanca]:
    casas = ler_casas(pasta_dados / "casas.csv")
    estado = ler_estado(pasta_dados / "status.json")

    observados = checar_todos([c.site for c in casas], cliente)
    novo, mudancas = aplicar_rodada(estado, casas, observados, agora)

    if mudancas:
        anexar_historico(pasta_dados / "historico.csv", [m.para_dict() for m in mudancas])

    a_avisar = [Mudanca.de_dict(d) for d in novo["avisos_pendentes"]]
    a_avisar += [m for m in mudancas if m.alertar]
    mensagens = montar_mensagens(a_avisar, painel_url)
    if mensagens and enviar_fn:
        ok = enviar_fn(mensagens)
        novo["avisos_pendentes"] = [] if ok else [m.para_dict() for m in a_avisar]
    else:
        for msg in mensagens:
            print(msg)
        novo["avisos_pendentes"] = []

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

    with novo_cliente() as cliente:
        mudancas = executar(
            Path("dados"),
            cliente,
            datetime.now(ZoneInfo("America/Sao_Paulo")),
            enviar_fn,
            painel_url,
        )

    totais = ler_estado(Path("dados/status.json"))["totais"]
    print(
        f"🔴 {totais['bloqueado']} bloqueadas · 🟢 {totais['respondendo']} respondendo · "
        f"⚪ {totais['indeterminado']} indeterminadas · {len(mudancas)} mudança(s)"
    )


if __name__ == "__main__":
    main()
