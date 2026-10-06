"""Regra de confirmação: transforma observações de uma rodada em mudanças.

Função pura, sem rede nem arquivos — por isso é fácil de testar.
"""

import copy
from dataclasses import asdict, dataclass
from datetime import datetime

from monitor.arquivos import Casa
from monitor.checar import BLOQUEADO, INDETERMINADO, RESPONDENDO, Resultado

LIMITE_DESCARTE = 0.5


@dataclass(frozen=True)
class Mudanca:
    data_hora: str
    casa: str
    site: str
    de: str
    para: str
    motivo: str
    desde_anterior: str
    alertar: bool

    def para_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def de_dict(cls, d: dict) -> "Mudanca":
        return cls(**d)


def _definido(status: str) -> str | None:
    return None if status == INDETERMINADO else status


def _totais(sites: dict) -> dict:
    totais = {BLOQUEADO: 0, RESPONDENDO: 0, INDETERMINADO: 0}
    for s in sites.values():
        totais[s["status"]] += 1
    return totais


def aplicar_rodada(
    estado: dict, casas: list[Casa], observados: dict[str, Resultado], agora: datetime
) -> tuple[dict, list[Mudanca]]:
    novo = copy.deepcopy(estado)
    agora_iso = agora.isoformat(timespec="seconds")
    novo["ultima_rodada"] = agora_iso
    novo.setdefault("avisos_pendentes", [])
    anteriores = novo.get("sites", {})

    # Muita coisa indeterminada ao mesmo tempo = problema de rede do nosso lado.
    indeterminados = sum(r.status == INDETERMINADO for r in observados.values())
    if observados and indeterminados / len(observados) > LIMITE_DESCARTE:
        novo.setdefault("sites", {})
        novo.setdefault("totais", _totais(novo["sites"]))
        return novo, []

    sites = {}
    mudancas = []
    for casa in casas:
        r = observados.get(casa.site)
        atual = anteriores.get(casa.site)
        if r is None:
            if atual is not None:
                sites[casa.site] = atual
            continue

        if atual is None:
            sites[casa.site] = {
                "casa": casa.casa,
                "liminar": casa.liminar,
                "status": r.status,
                "desde": agora_iso,
                "motivo": r.motivo,
                "ultima_checagem": agora_iso,
                "ultimo_definido": _definido(r.status),
                "pendente": None,
            }
            continue

        atual.update(
            casa=casa.casa, liminar=casa.liminar, motivo=r.motivo, ultima_checagem=agora_iso
        )
        pendente = atual.get("pendente")
        if r.status == atual["status"]:
            atual["pendente"] = None
        elif pendente and pendente["status"] == r.status:
            ultimo = atual.get("ultimo_definido")
            mudancas.append(
                Mudanca(
                    data_hora=agora_iso,
                    casa=casa.casa,
                    site=casa.site,
                    de=atual["status"],
                    para=r.status,
                    motivo=r.motivo,
                    desde_anterior=atual["desde"],
                    alertar=r.status != INDETERMINADO and r.status != ultimo,
                )
            )
            atual.update(status=r.status, desde=agora_iso, pendente=None)
            if r.status != INDETERMINADO:
                atual["ultimo_definido"] = r.status
        else:
            atual["pendente"] = {"status": r.status, "visto_em": agora_iso}
        sites[casa.site] = atual

    novo["sites"] = sites
    novo["totais"] = _totais(sites)
    return novo, mudancas
