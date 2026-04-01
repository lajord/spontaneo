# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# AGENT 3 â€” ENRICHISSEMENT DES ENTREPRISES
#
# Role : Pour chaque entreprise, trouver les contacts decideurs
#        (noms, emails, titres, telephones, LinkedIn).
# Input : Liste d'entreprises collectees/verifiees.
# Output : Entreprises enrichies avec contacts.
#
# Processing : UN run d'agent ReAct par entreprise.
# L'agent est autonome : il decide quelles pages crawler, quand
# utiliser Perplexity, quand utiliser Apollo, quand verifier
# les emails avec NeverBounce.
#
# Outils : crawl_url, perplexity_search, apollo_people_search,
#           neverbounce_verify, save_enrichment, read_enrichment_summary
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from langgraph.prebuilt import create_react_agent
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_anthropic import ChatAnthropic

from config import AGENT3_RECURSION_LIMIT, AGENT3_TRIM_MAX_CHARS, AGENT3_TARGET_CONTACTS
from pipeline.engine import build_llm, emit, stream_agent, emit_csv_update
from pipeline.prompts import build_enrich_prompt, build_enrich_user_message
from tools.crawl4ai_tool import crawl_url
from tools.perplexity_search import perplexity_search
from tools.apollo_people import apollo_people_search
from tools.neverbounce_verify import neverbounce_verify
from tools.enrichment_store import save_enrichment, read_enrichment_summary, get_enriched_rows
from tools.buffer_store import save_to_buffer, evaluate_findings, cleanup_buffer, _read_buffer

if TYPE_CHECKING:
    from typing import Callable


def _compact_messages(state: dict) -> list:
    """Compacte les vieux resultats de tools pour economiser drastiquement les tokens.

    Tous les ToolMessage qui ont deja ete lus et traites par une reponse IA
    (c'est-a-dire qu'un AIMessage apparait apres eux) voient leur contenu brut
    completement supprime. L'Agent se repose uniquement sur ses propres conclusions
    et sur les donnees du buffer.
    """
    messages = state["messages"]
    result = []

    # Trouver l'index du dernier AIMessage.
    # Tous les messages outils avant cet index ont deja ete vus et penses par l'IA.
    last_ai_idx = -1
    for i in range(len(messages) - 1, -1, -1):
        if messages[i].type == "ai":
            last_ai_idx = i
            break

    for i, msg in enumerate(messages):
        if msg.type == "tool" and i < last_ai_idx:
            # Ce tool_message a deja ete "lu" par le LLM. On reduit a neant le contenu.
            result.append(ToolMessage(
                content="[CONTENU SUPPRIME POUR ECONOMISER LES TOKENS - L'agent a deja traite cette information a l'etape precedente.]",
                tool_call_id=msg.tool_call_id,
                name=msg.name if hasattr(msg, "name") else "",
            ))
        else:
            result.append(msg)

    try:
        with open("debug_prompt.txt", "a", encoding="utf-8") as f:
            f.write(f"\n{'-'*40}\nITERATION AGENT 3 (Appel LLM)\n{'-'*40}\n")
            for m in result:
                content = str(m.content)
                if len(content) > 1500:
                    content = content[:1500] + "\n... [TRONQUÃ‰ POUR LE DEBUG]"
                f.write(f"[{m.type.upper()}]\n{content}\n\n")
    except Exception:
        pass

    return result

_QUALITY_CHECK_PROMPT = """Tu es un expert en recrutement et prospection B2B.

On vient de faire une phase de collecte de contacts pour une entreprise.
Tu dois evaluer la QUALITE des contacts trouves et decider si l'objectif est atteint.

## CRITERES DE QUALITE (NON NEGOCIABLES)
1. DECIDEUR : Le contact doit etre un decideur (associe, partner, directeur, chef de departement, DG, DRH).
   Les stagiaires, assistants, charges de mission ne comptent PAS.
2. EMAIL NOMINATIF : L'email doit etre nominatif (prenom.nom@...). Les emails generiques (contact@, info@, rh@, cabinet@) ne comptent PAS.
3. EMAIL VERIFIE : L'email doit etre "valid" ou "catchall" (via NeverBounce). Les emails non verifies ou "invalid" ne comptent PAS.

## BRIEF CONTACTS DE REFERENCE
Ce brief decrit exactement qui on cherche :
{contact_brief}

## CONTACTS TROUVES (BUFFER)
{buffer_summary}

## TA REPONSE
Reponds UNIQUEMENT avec un JSON valide, sans explication supplÃ©mentaire :
{{
  "qualified_count": <nombre de contacts qui respectent LES TROIS CRITERES ci-dessus>,
  "qualified_contacts": ["Nom â€” Titre â€” Email â€” Status"],
  "verdict": "ok" ou "insuffisant",
  "reason": "<explication courte en 1 ligne>"
}}

Si qualified_count >= {target}, verdict = "ok". Sinon verdict = "insuffisant".
"""


def _quality_check(
    company_name: str,
    contact_brief: str,
    log_callback=None,
) -> dict:
    """Evalue la qualite des contacts dans le buffer via un petit LLM.

    Args:
        company_name: Nom de l'entreprise
        contact_brief: Brief de ciblage produit par Agent 0
        log_callback: Callback SSE

    Returns:
        Dict avec : qualified_count, verdict ("ok" ou "insuffisant"), reason
    """
    from tools.buffer_store import _read_buffer  # import local pour eviter circulaire

    entries = _read_buffer(company_name)

    if not entries:
        return {"qualified_count": 0, "verdict": "insuffisant", "reason": "Buffer vide."}

    # Formater le buffer en texte lisible
    lines = []
    for e in entries:
        line = f"- {e.get('name', '?')} | {e.get('title', '?')} | {e.get('email', 'pas d email')} [{e.get('email_status', '?')}]"
        lines.append(line)
    buffer_summary = "\n".join(lines) if lines else "Aucune entree."

    prompt = _QUALITY_CHECK_PROMPT.format(
        contact_brief=contact_brief or "Decideurs generaux : associes, partners, DG, directeurs.",
        buffer_summary=buffer_summary,
        target=AGENT3_TARGET_CONTACTS,
    )

    import os
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    fast_llm = ChatAnthropic(
        model="claude-haiku-4-20250514",
        api_key=api_key,
        max_tokens=512,
        max_retries=2,
    )

    try:
        resp = fast_llm.invoke([
            SystemMessage(content=prompt),
            HumanMessage(content=f"Evalue les contacts trouves pour '{company_name}'."),
        ])
        raw = resp.content if isinstance(resp.content, str) else str(resp.content)
        # Extraire le JSON (l'IA peut ajouter du texte autour)
        import re
        match = re.search(r'\{.*\}', raw, re.DOTALL)
        if match:
            result = json.loads(match.group())
            emit(
                {
                    "type": "log",
                    "phase": "ENRICHISSEMENT",
                    "message": f"[QUALITY CHECK] {company_name} â€” verdict: {result.get('verdict')} ({result.get('qualified_count')} qualifies). {result.get('reason')}",
                },
                log_callback,
            )
            return result
    except Exception as e:
        emit(
            {"type": "log", "phase": "ENRICHISSEMENT", "message": f"[QUALITY CHECK] Erreur LLM: {e}"},
            log_callback,
        )

    return {"qualified_count": 0, "verdict": "insuffisant", "reason": "Erreur quality check."}


def _count_enriched() -> int:
    """Compte le nombre total de contacts du job courant."""
    return len(get_enriched_rows())


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
    second_tour: bool = False,
) -> list[dict]:
    """Enrichit les entreprises avec les contacts decideurs.

    Itere sur chaque entreprise et lance un agent ReAct autonome
    qui crawle, cherche, et verifie les contacts.

    Args:
        candidates: Entreprises a enrichir (issues de collect)
        log_callback: Callback pour le streaming d'events
        contact_brief: Brief de ciblage contacts produit par Agent 0
        second_tour: Si True, skip le crawl du site et la verif specialite
                     (utile quand on fait un deuxieme passage sur des entreprises
                     deja partiellement enrichies).

    Returns:
        Liste des entreprises enrichies avec contacts trouves.
        Chaque dict contient les champs originaux + "contacts" + "contact_count".
    """
    emit(
        {"type": "phase", "name": "ENRICHISSEMENT", "message": "AGENT 3 â€” ENRICHISSEMENT"},
        log_callback,
    )

    if not candidates:
        emit(
            {"type": "log", "phase": "ENRICHISSEMENT", "message": "Aucune entreprise a enrichir."},
            log_callback,
        )
        return []

    # Build LLM + tools (partages entre tous les runs)
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

        # Build prompts specifiques a cette entreprise
        system_prompt = build_enrich_prompt(
            company=company,
            contact_brief=contact_brief,
            second_tour=second_tour,
        )
        user_message = build_enrich_user_message(company, second_tour=second_tour)

        # Run l'agent (Premier Tour)
        stream_agent(
            agent=agent,
            system_prompt=system_prompt,
            user_message=user_message,
            recursion_limit=AGENT3_RECURSION_LIMIT,
            phase_name="ENRICHISSEMENT",
            log_callback=log_callback,
        )

        # â”€â”€â”€ Quality Gate â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        # Evaluer la qualite des contacts trouves via un petit LLM
        qc = _quality_check(
            company_name=company_name,
            contact_brief=contact_brief,
            log_callback=log_callback,
        )

        if qc.get("verdict") == "insuffisant":
            emit(
                {
                    "type": "log",
                    "phase": "ENRICHISSEMENT",
                    "message": f"{company_name}: qualite insuffisante ({qc.get('qualified_count')} qualifies). Lancement du Second Tour...",
                },
                log_callback,
            )
            # Second Tour : on skipe le crawl et la verif specialite
            system_prompt_2 = build_enrich_prompt(
                company=company,
                contact_brief=contact_brief,
                second_tour=True,
            )
            user_message_2 = build_enrich_user_message(company, second_tour=True)
            stream_agent(
                agent=agent,
                system_prompt=system_prompt_2,
                user_message=user_message_2,
                recursion_limit=AGENT3_RECURSION_LIMIT,
                phase_name="ENRICHISSEMENT_T2",
                log_callback=log_callback,
            )
        else:
            emit(
                {
                    "type": "log",
                    "phase": "ENRICHISSEMENT",
                    "message": f"{company_name}: qualite OK ({qc.get('qualified_count')} contacts qualifies). Second Tour inutile.",
                },
                log_callback,
            )
        # â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

        # Nettoyer le buffer de cette entreprise
        cleanup_buffer(company_name)

        # Lire les contacts ajoutes pour cette entreprise
        company_contacts = _read_enriched_for_company(company_name)

        # Construire le dict enrichi (champs originaux + contacts)
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

    # Mise a jour CSV finale
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
