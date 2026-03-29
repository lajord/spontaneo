# ──────────────────────────────────────────────────────────────────
# GRAPH — PIPELINE PRINCIPAL
#
# Orchestre les agents en un seul passage :
#
#   ┌──────────┐    ┌──────────────────────────┐
#   │ AGENT 1  │───▶│        AGENT 3            │
#   │ Collecte │    │ Verif (si applicable)     │
#   └──────────┘    │ + Enrichissement          │
#                   └──────────────────────────┘
#
# La verification est integree dans l'Agent 3 : apres le crawl
# de la homepage, l'agent decide si l'entreprise est pertinente.
# Le verify_prompt de la verticale controle si cette verif est active.
# ──────────────────────────────────────────────────────────────────

from __future__ import annotations
from typing import TYPE_CHECKING

from pipeline.agent_1_collect import collect
from pipeline.agent_3_enrich import enrich

if TYPE_CHECKING:
    from typing import Callable
    from domains.base import VerticalConfig, Subspecialty


def run_pipeline(
    vertical: VerticalConfig,
    query: str,
    subspecialty: Subspecialty | None = None,
    target_count: int = 50,
    log_callback: Callable | None = None,
    target_profile: str = "",
) -> list[dict]:
    """Pipeline principal : collecte puis enrichissement en un seul passage.

    Args:
        vertical: Config de la verticale (cabinets, banques, fonds...)
        query: Requete utilisateur (ville, precisions...)
        subspecialty: Sous-specialite ciblee (optionnel)
        target_count: Nombre d'entreprises a trouver
        log_callback: Callback pour le streaming SSE
        target_profile: Profil cible optionnel (ex: "Juriste Compliance")

    Returns:
        Liste finale d'entreprises enrichies.
    """
    # — Etape 1 : Collecte —
    candidates = collect(
        vertical=vertical,
        query=query,
        subspecialty=subspecialty,
        log_callback=log_callback,
        batch_size=target_count,
    )

    # — Etape 2 : Enrichissement (avec verif integree si verify_prompt defini) —
    enriched = enrich(
        vertical=vertical,
        candidates=candidates,
        log_callback=log_callback,
        target_profile=target_profile,
        subspecialty=subspecialty,
    )

    return enriched
