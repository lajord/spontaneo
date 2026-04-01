# ──────────────────────────────────────────────────────────────────
# AGENT 3 — ENRICHISSEMENT DES ENTREPRISES
#
# Role : Pour chaque entreprise, trouver les contacts decideurs
#        (noms, prenoms, emails).
# Input : Liste d'entreprises collectees.
# Output : Entreprises enrichies avec contacts.
#
# Processing : UN run d'agent ReAct par entreprise.
# Pipeline lineaire : crawl site → perplexity → genere/verifie emails → sauvegarde.
# Pas de boucle, pas de second tour.
#
# Outils : crawl_url, perplexity_search, apollo_people_search,
#           neverbounce_verify, save_enrichment, read_enrichment_summary
# ──────────────────────────────────────────────────────────────────

from __future__ import annotations

from typing import TYPE_CHECKING

from langgraph.prebuilt import create_react_agent
from langchain_core.messages import ToolMessage

from config import AGENT3_RECURSION_LIMIT
from pipeline.engine import build_llm, emit, stream_agent, emit_csv_update
from pipeline.prompts import build_enrich_prompt, build_enrich_user_message
from tools.crawl4ai_tool import crawl_url
from tools.perplexity_search import perplexity_search
from tools.apollo_people import apollo_people_search
from tools.neverbounce_verify import neverbounce_verify
from tools.enrichment_store import save_enrichment, read_enrichment_summary, get_enriched_rows
from tools.buffer_store import save_to_buffer, evaluate_findings, cleanup_buffer

if TYPE_CHECKING:
    from typing import Callable


def _compact_messages(state: dict) -> list:
    """Compacte les vieux resultats de tools pour economiser les tokens."""
    messages = state["messages"]
    result = []

    last_ai_idx = -1
    for i in range(len(messages) - 1, -1, -1):
        if messages[i].type == "ai":
            last_ai_idx = i
            break

    for i, msg in enumerate(messages):
        if msg.type == "tool" and i < last_ai_idx:
            result.append(ToolMessage(
                content="[SUPPRIME - deja traite]",
                tool_call_id=msg.tool_call_id,
                name=msg.name if hasattr(msg, "name") else "",
            ))
        else:
            result.append(msg)

    return result


def _read_enriched_for_company(company_name: str) -> list[dict]:
    """Lit les contacts enrichis pour une entreprise donnee."""
    normalized = company_name.lower().strip()
    return [
        row for row in get_enriched_rows()
        if row.get("company_name", "").lower().strip() == normalized
    ]


def enrich(
    candidates: list[dict],
    log_callback: Callable | None = None,
    contact_brief: str = "",
    **kwargs,
) -> list[dict]:
    """Enrichit les entreprises avec les contacts decideurs.

    Pipeline lineaire par entreprise : crawl → perplexity → emails → sauvegarde.
    Pas de quality check ni de second tour.
    """
    emit(
        {"type": "phase", "name": "ENRICHISSEMENT", "message": "AGENT 3 — ENRICHISSEMENT"},
        log_callback,
    )

    if not candidates:
        emit(
            {"type": "log", "phase": "ENRICHISSEMENT", "message": "Aucune entreprise a enrichir."},
            log_callback,
        )
        return []

    llm = build_llm()
    tools = [
        crawl_url,
        perplexity_search,
        apollo_people_search,
        neverbounce_verify,
        save_to_buffer,
        evaluate_findings,
        save_enrichment,
        read_enrichment_summary,
    ]
    agent = create_react_agent(
        model=llm,
        tools=tools,
        prompt=_compact_messages,
    )

    all_enriched = []

    for i, company in enumerate(candidates):
        company_name = company.get("name", "Inconnu")

        emit(
            {
                "type": "progress",
                "phase": "enrichissement",
                "current": i + 1,
                "target": len(candidates),
                "message": f"Enrichissement de {company_name} ({i + 1}/{len(candidates)})...",
            },
            log_callback,
        )

        system_prompt = build_enrich_prompt(
            company=company,
            contact_brief=contact_brief,
        )
        user_message = build_enrich_user_message(company)

        # Un seul passage, pipeline lineaire
        stream_agent(
            agent=agent,
            system_prompt=system_prompt,
            user_message=user_message,
            recursion_limit=AGENT3_RECURSION_LIMIT,
            phase_name="ENRICHISSEMENT",
            log_callback=log_callback,
        )

        # Nettoyer le buffer
        cleanup_buffer(company_name)

        # Lire les contacts sauvegardes
        company_contacts = _read_enriched_for_company(company_name)

        enriched_company = dict(company)
        enriched_company["contacts"] = company_contacts
        enriched_company["contact_count"] = len(company_contacts)
        all_enriched.append(enriched_company)

        emit(
            {
                "type": "log",
                "phase": "ENRICHISSEMENT",
                "message": f"{company_name}: {len(company_contacts)} contacts trouves.",
            },
            log_callback,
        )

    emit_csv_update(log_callback, "enriched")

    total_contacts = sum(c.get("contact_count", 0) for c in all_enriched)
    emit(
        {
            "type": "progress",
            "phase": "enrichissement",
            "current": len(candidates),
            "target": len(candidates),
            "message": f"Enrichissement termine : {total_contacts} contacts pour {len(candidates)} entreprises.",
        },
        log_callback,
    )

    return all_enriched
