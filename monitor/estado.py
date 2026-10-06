"""Regra de confirmação: transforma observações de uma rodada em mudanças.

Função pura, sem rede nem arquivos — por isso é fácil de testar.
"""

import copy
from dataclasses import asdict, dataclass
from datetime import datetime

from monitor.arquivos import Casa
from monitor.checar import BLOQUEADO, INDETERMINADO, RESPONDENDO, Resultado

LIMITE_DESCARTE = 0.5
# Motivos que indicam falha de rede do nosso lado (não anti-robô nem página de erro).
FALHA_DE_REDE = ("timeout", "erro de conexão", "erro:", "navegador:")


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


def _alertar(para: str, ultimo: str | None) -> bool:
    # Avisa a volta (🟢) e o novo bloqueio de quem estava no ar (🟢 → 🔴).
    # Passagens por ⚪ não contam: 🔴 → ⚪ → 🔴 e ⚪ → 🔴 não são notícia.
    if para == RESPONDENDO:
        return ultimo != RESPONDENDO
    return para == BLOQUEADO and ultimo == RESPONDENDO


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

    # Muita falha de rede ao mesmo tempo = problema do nosso lado: descarta a rodada.
    falhas = sum(
        r.status == INDETERMINADO and r.motivo.startswith(FALHA_DE_REDE)
        for r in observados.values()
    )
    if observados and falhas / len(observados) > LIMITE_DESCARTE:
        novo.setdefault("sites", {})
        novo.setdefault("totais", _totais(novo["sites"]))
        return novo, []

    novo["ultima_rodada_valida"] = agora_iso
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

        atual.update(casa=casa.casa, liminar=casa.liminar, ultima_checagem=agora_iso)
        pendente = atual.get("pendente")
        if r.status == atual["status"]:
            atual.update(motivo=r.motivo, pendente=None)
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
                    alertar=_alertar(r.status, ultimo),
                )
            )
            atual.update(status=r.status, desde=agora_iso, motivo=r.motivo, pendente=None)
            if r.status != INDETERMINADO:
                atual["ultimo_definido"] = r.status
        elif r.status == INDETERMINADO and pendente and pendente["status"] != INDETERMINADO:
            pass  # ⚪ é "sem informação": não apaga uma mudança 🟢/🔴 em confirmação
        else:
            atual["pendente"] = {"status": r.status, "visto_em": agora_iso, "motivo": r.motivo}
        sites[casa.site] = atual

    novo["sites"] = sites
    novo["totais"] = _totais(sites)
    return novo, mudancas
