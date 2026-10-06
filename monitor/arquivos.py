"""Leitura e escrita dos arquivos de dados (dados/*.csv e dados/status.json)."""

import csv
import json
from dataclasses import dataclass
from pathlib import Path

CABECALHO_CASAS = ["casa", "site", "liminar"]
CABECALHO_HISTORICO = ["data_hora", "casa", "site", "de", "para", "motivo"]


@dataclass(frozen=True)
class Casa:
    casa: str
    site: str
    liminar: bool


def ler_casas(caminho: Path) -> list[Casa]:
    with open(caminho, encoding="utf-8", newline="") as f:
        return [
            Casa(linha["casa"], linha["site"], linha["liminar"] == "sim")
            for linha in csv.DictReader(f)
        ]


def escrever_casas(caminho: Path, casas: list[Casa]) -> None:
    with open(caminho, "w", encoding="utf-8", newline="") as f:
        escritor = csv.writer(f, lineterminator="\n")
        escritor.writerow(CABECALHO_CASAS)
        for c in casas:
            escritor.writerow([c.casa, c.site, "sim" if c.liminar else "nao"])


def ler_marcadores(caminho: Path) -> list[str]:
    if not caminho.exists():
        return []
    linhas = (l.strip().lower() for l in caminho.read_text(encoding="utf-8").splitlines())
    return [l for l in linhas if l and not l.startswith("#")]


def ler_estado(caminho: Path) -> dict:
    if not caminho.exists():
        return {}
    return json.loads(caminho.read_text(encoding="utf-8"))


def salvar_estado(caminho: Path, estado: dict) -> None:
    estado = dict(estado)
    if "sites" in estado:
        estado["sites"] = dict(sorted(estado["sites"].items()))
    caminho.write_text(
        json.dumps(estado, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def anexar_historico(caminho: Path, linhas: list[dict]) -> None:
    novo = not caminho.exists()
    with open(caminho, "a", encoding="utf-8", newline="") as f:
        escritor = csv.DictWriter(
            f, CABECALHO_HISTORICO, extrasaction="ignore", lineterminator="\n"
        )
        if novo:
            escritor.writeheader()
        escritor.writerows(linhas)
