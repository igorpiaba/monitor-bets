"""Gera dados/casas.csv a partir das listas oficiais da SPA/Ministério da Fazenda.

Rodar manualmente quando a SPA atualizar a lista:
    python importar_lista.py
"""

import csv
import re
from pathlib import Path

import httpx

from monitor.arquivos import Casa, escrever_casas, ler_casas
from monitor.checar import USER_AGENT

BASE = (
    "https://www.gov.br/fazenda/pt-br/composicao/orgaos/secretaria-de-premios-e-apostas/"
    "transparencia-ativa-processos-de-autorizacao-de-apostas-de-quota-fixa/"
)
URL_SPA = BASE + "planilha-de-autorizacoes-1.csv"
URL_JUDICIAL = BASE + "ProcessosjudiciaisSPA04.02.26.csv"

CAMINHO = Path("dados/casas.csv")
MINIMO_CASAS = 100
FORMATO_DOMINIO = re.compile(r"^[a-z0-9-]+(\.[a-z0-9-]+)+$")


def extrair_pares(texto: str) -> list[tuple[str, str]]:
    pares = []
    col_marca = col_dominio = None
    for linha in csv.reader(texto.splitlines(), delimiter=";"):
        celulas = [c.strip() for c in linha]
        # Cada bloco da planilha começa com seu próprio cabeçalho.
        if "MARCAS" in celulas and "DOMÍNIOS" in celulas:
            col_marca, col_dominio = celulas.index("MARCAS"), celulas.index("DOMÍNIOS")
            continue
        if col_marca is None or len(celulas) <= max(col_marca, col_dominio):
            continue
        marca, dominio = celulas[col_marca], celulas[col_dominio].lower()
        if marca and dominio and dominio != "a definir":
            pares.append((marca, dominio))
    if col_marca is None:
        raise ValueError("cabeçalho MARCAS/DOMÍNIOS não encontrado")
    return pares


def montar_casas(
    spa: list[tuple[str, str]], judicial: list[tuple[str, str]]
) -> list[Casa]:
    casas = {}
    for pares, liminar in ((spa, False), (judicial, True)):
        for marca, dominio in pares:
            casas.setdefault(dominio, Casa(marca.title(), dominio, liminar))
    return sorted(casas.values(), key=lambda c: (c.casa, c.site))


def validar(casas: list[Casa]) -> None:
    if len(casas) < MINIMO_CASAS:
        raise ValueError(f"só {len(casas)} casas; esperado ao menos {MINIMO_CASAS}")
    invalidos = [c.site for c in casas if not FORMATO_DOMINIO.match(c.site)]
    if invalidos:
        raise ValueError(f"domínios com formato inválido: {invalidos}")


def _baixar(url: str) -> str:
    resp = httpx.get(
        url, timeout=30, headers={"User-Agent": USER_AGENT}, follow_redirects=True
    )
    resp.raise_for_status()
    return resp.content.decode("utf-8-sig")


def main() -> None:
    casas = montar_casas(
        extrair_pares(_baixar(URL_SPA)), extrair_pares(_baixar(URL_JUDICIAL))
    )
    validar(casas)

    anteriores = {c.site for c in ler_casas(CAMINHO)} if CAMINHO.exists() else set()
    atuais = {c.site for c in casas}
    for site in sorted(atuais - anteriores):
        print(f"+ {site}")
    for site in sorted(anteriores - atuais):
        print(f"- {site}")

    CAMINHO.parent.mkdir(exist_ok=True)
    escrever_casas(CAMINHO, casas)
    liminares = sum(c.liminar for c in casas)
    print(f"{len(casas)} casas gravadas em {CAMINHO} ({liminares} por liminar)")


if __name__ == "__main__":
    main()
