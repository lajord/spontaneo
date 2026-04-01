# ──────────────────────────────────────────────────────────────────
# GRAPH — PIPELINE PRINCIPAL
#
# Orchestre les agents en 3 etapes :
#
#   ┌──────────┐    ┌──────────┐    ┌──────────────────┐
#   │ AGENT 0  │───▶│ AGENT 1  │───▶│     AGENT 3      │
#   │ Planning │    │ Collecte │    │  Enrichissement   │
#   └──────────┘    └──────────┘    └──────────────────┘
#
# Agent 0 analyse le job title et produit 2 briefs :
#   - collect_brief  → guide la recherche d'entreprises
#   - contact_brief  → guide le ciblage de contacts
# ──────────────────────────────────────────────────────────────────

from __future__ import annotations
from typing import TYPE_CHECKING

from pipeline.agent_0_plan import plan
from pipeline.agent_deep_search import collect
from pipeline.agent_verif_enrichissement import enrich
from tools.candidate_store import set_agent_context

if TYPE_CHECKING:
    from typing import Callable


def run_pipeline(
    secteur: str,
    query: str,
    job_title: str = "",
    target_count: int = 50,
    log_callback: Callable | None = None,
    user_id: str = "anonymous",
    job_id: str | None = None,
    campaign_id: str | None = None,
    location: str = "",
) -> list[dict]:
    """Pipeline principal : planning → collecte → enrichissement.

    Args:
        secteur: ID du secteur (cabinets, banques, fonds)
        query: Requete utilisateur (ville, precisions...)
        job_title: Poste vise par l'utilisateur
        target_count: Nombre d'entreprises a trouver
        log_callback: Callback pour le streaming SSE
        user_id: ID de l'utilisateur (pour la BDD)
        job_id: ID du job en cours
        campaign_id: ID de la campagne (optionnel)
        location: Ville / zone de la recherche (pour tracabilite BDD)

    Returns:
        Liste finale d'entreprises enrichies.
    """
    # — Etape 0 : Injection du contexte utilisateur (pour la BDD) —
    set_agent_context(
        user_id=user_id,
        job_id=job_id,
        campaign_id=campaign_id,
        secteur=secteur,
        job_title=job_title,
        location=location,
    )

    # — Etape 1 : Planning (analyse du job title) —
    collect_brief, contact_brief = plan(
        secteur=secteur,
        job_title=job_title,
        location=query,
        log_callback=log_callback,
    )

    # — Etape 1 : Collecte —
    candidates = collect(
        query=query,
        collect_brief=collect_brief,
        log_callback=log_callback,
        batch_size=target_count,
    )

    # — Etape 2 : Enrichissement —
    enriched = enrich(
        candidates=candidates,
        log_callback=log_callback,
        contact_brief=contact_brief,
    )

    return enriched
