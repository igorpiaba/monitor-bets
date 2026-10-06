"""Checa se um site redireciona para a página de bloqueio do governo."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

import httpx

BLOQUEADO = "bloqueado"
RESPONDENDO = "respondendo"
INDETERMINADO = "indeterminado"

HOST_GOV = "brasilsembets.gov.br"
MAX_REDIRECIONAMENTOS = 10
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
)


@dataclass(frozen=True)
class Resultado:
    status: str
    motivo: str


def novo_cliente() -> httpx.Client:
    return httpx.Client(
        follow_redirects=False,
        timeout=15,
        headers={"User-Agent": USER_AGENT, "Accept-Language": "pt-BR"},
    )


def _eh_gov(host: str) -> bool:
    return host == HOST_GOV or host.endswith("." + HOST_GOV)


def checar(site: str, cliente: httpx.Client) -> Resultado:
    url = httpx.URL(f"https://{site}/")
    try:
        # Segue os redirecionamentos à mão: assim reconhecemos o gov.br
        # sem precisar baixar a página do governo.
        for _ in range(MAX_REDIRECIONAMENTOS + 1):
            resp = cliente.get(url)
            codigo = resp.status_code
            if resp.is_redirect:
                destino = resp.headers.get("location")
                if not destino:
                    return Resultado(INDETERMINADO, f"{codigo} sem Location")
                url = resp.url.join(destino)
                if _eh_gov(url.host):
                    return Resultado(BLOQUEADO, f"{codigo} -> {url.host}")
                continue
            if 200 <= codigo < 300:
                return Resultado(RESPONDENDO, str(codigo))
            return Resultado(INDETERMINADO, str(codigo))
    except httpx.TimeoutException:
        return Resultado(INDETERMINADO, "timeout")
    except httpx.ConnectError as e:
        return Resultado(INDETERMINADO, f"erro de conexão: {e}")
    except httpx.HTTPError as e:
        return Resultado(INDETERMINADO, f"erro: {type(e).__name__}")
    return Resultado(INDETERMINADO, "redirecionamentos demais")


def checar_todos(
    sites: list[str], cliente: httpx.Client, paralelo: int = 20
) -> dict[str, Resultado]:
    with ThreadPoolExecutor(max_workers=paralelo) as pool:
        resultados = pool.map(lambda s: checar(s, cliente), sites)
        return dict(zip(sites, resultados))
