"""Segunda etapa da detecção: abre a página num navegador de verdade e lê o texto.

Muitas casas trocaram o redirecionamento por uma página própria de aviso,
às vezes montada por JavaScript. Só um navegador enxerga esse texto.
"""

import asyncio
from collections.abc import Callable

import httpx

from monitor.checar import BLOQUEADO, INDETERMINADO, RESPONDENDO, USER_AGENT, Resultado, eh_gov

ANTI_ROBO = ["verificação de segurança", "just a moment", "checking your browser"]
# Páginas de erro de infraestrutura (Cloudflare, Vercel...): não dizem nada sobre a casa.
PAGINA_DE_ERRO = [
    "ray id:",
    "error code 5",
    "you have been blocked",
    "deployment_not_found",
    "page doesn’t exist",
]
MINIMO_TEXTO = 50

Pagina = tuple[str, str]  # (texto visível, url final)


def classificar_texto(texto: str, url_final: str, marcadores: list[str]) -> Resultado:
    host = httpx.URL(url_final).host
    if eh_gov(host):
        return Resultado(BLOQUEADO, f"js -> {host}")
    texto = " ".join(texto.split()).lower()
    if any(m in texto for m in ANTI_ROBO):
        return Resultado(INDETERMINADO, "anti-robô")
    if any(m in texto for m in PAGINA_DE_ERRO):
        return Resultado(INDETERMINADO, "página de erro")
    if len(texto) < MINIMO_TEXTO:
        return Resultado(INDETERMINADO, "página vazia")
    for marcador in marcadores:
        if marcador in texto:
            return Resultado(BLOQUEADO, f"aviso: {marcador}")
    return Resultado(RESPONDENDO, "sem aviso")


def refinar(
    observados: dict[str, Resultado],
    renderizar_fn: Callable[[list[str]], dict[str, Pagina | str]],
    marcadores: list[str],
) -> dict[str, Resultado]:
    pendentes = [s for s, r in observados.items() if r.status != BLOQUEADO]
    if not pendentes:
        return dict(observados)
    paginas = renderizar_fn(pendentes)
    refinado = dict(observados)
    for site in pendentes:
        pagina = paginas.get(site, "sem resposta")
        if isinstance(pagina, str):
            refinado[site] = Resultado(INDETERMINADO, f"navegador: {pagina}")
        else:
            refinado[site] = classificar_texto(*pagina, marcadores)
    return refinado


def renderizar(
    sites: list[str], paralelo: int = 8, espera_ms: int = 6000
) -> dict[str, Pagina | str]:
    from playwright.async_api import async_playwright

    async def abrir(navegador, site, limite):
        async with limite:
            pagina = await navegador.new_page(locale="pt-BR", user_agent=USER_AGENT)
            try:
                await pagina.goto(
                    f"https://{site}/", wait_until="domcontentloaded", timeout=30000
                )
                await pagina.wait_for_timeout(espera_ms)
                return site, (await pagina.inner_text("body"), pagina.url)
            except Exception as e:  # qualquer falha do navegador vira "indeterminado"
                return site, type(e).__name__
            finally:
                await pagina.close()

    async def todos():
        async with async_playwright() as pw:
            navegador = await pw.chromium.launch()
            limite = asyncio.Semaphore(paralelo)
            resultados = await asyncio.gather(*(abrir(navegador, s, limite) for s in sites))
            await navegador.close()
            return dict(resultados)

    return asyncio.run(todos())
