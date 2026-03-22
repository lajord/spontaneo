import csv
import json
import os
import time
from datetime import datetime
from typing import Callable

from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langgraph.prebuilt import create_react_agent

from agent.prompts import format_collector_prompt, format_verifier_prompts
from tools.apollo_search import apollo_search
from tools.web_search import web_search_legal
from tools.google_maps_search import google_maps_search
from tools.crawl4ai_tool import crawl_url
from tools.entreprise_api import check_company_size
from tools.candidate_store import (
    save_candidates, save_verification,
    VERIFIED_CSV, CANDIDATES_CSV, OUTPUT_DIR,
    VERIFIED_COLUMNS, CANDIDATES_COLUMNS,
)

load_dotenv()


# ─── Helper : emit log ou print ────────────────────────────────────

def _emit(event: dict, callback: Callable | None = None):
    """Émet un event via callback ou print selon le mode."""
    if callback:
        callback(event)
    else:
        # Mode CLI : print comme avant
        t = event.get("type", "")
        msg = event.get("message", "")
        if t == "phase":
            print()
            print("=" * 60)
            print(f"   {msg}")
            print("=" * 60)
            print()
        elif t == "verif_result":
            confirmed = event.get("confirmed", False)
            color = "\033[92m" if confirmed else "\033[91m"
            reset = "\033[0m"
            icon = "✓" if confirmed else "✗"
            headline = event.get("headline", msg)
            reason = event.get("reason", "")
            print(f"  {color}[VERIF] {icon} {headline}{reset}")
            if reason:
                print(f"         {reason}\n")
            else:
                print()
        elif t == "log":
            phase = event.get("phase", "")
            print(f"  [{phase}] {msg}\n")
        elif t == "tool_call":
            print(f"  [TOOL] {event.get('name', '')}({event.get('args', '')})")
        elif t == "tool_result":
            print(f"  [RESULT] {msg}\n")
        elif t == "progress":
            print(f"  {msg}")
        elif t == "error":
            print(f"  [ERREUR] {msg}")
        elif t == "done":
            print(f"  {msg}")
        else:
            if msg:
                print(f"  {msg}")


# ─── CSV read helpers ───────────────────────────────────────────────

def _read_csv_rows(path: str, delimiter: str = ";") -> list[dict]:
    """Lit un CSV et retourne la liste de dicts."""
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f, delimiter=delimiter))


def _emit_csv_update(callback: Callable | None, csv_type: str):
    """Envoie le contenu actuel d'un CSV via callback."""
    if not callback:
        return
    path = CANDIDATES_CSV if csv_type == "candidates" else VERIFIED_CSV
    rows = _read_csv_rows(path)
    callback({"type": "csv_update", "csv_type": csv_type, "rows": rows})


# ─── LLM & Agents ──────────────────────────────────────────────────

def _build_llm(model: str = "claude-sonnet-4-20250514", max_tokens: int = 8192):
    """Crée l'instance LLM."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY non trouvée dans le .env")
    return ChatAnthropic(
        model=model,
        api_key=api_key,
        max_tokens=max_tokens,
        max_retries=5,
        default_request_timeout=120,
    )


def build_collector_agent(model: str = "claude-sonnet-4-20250514"):
    """Agent Phase 1 : collecte via Apollo + Perplexity + Google Maps."""
    llm = _build_llm(model)
    tools = [apollo_search, web_search_legal, google_maps_search, save_candidates]
    return create_react_agent(model=llm, tools=tools)


def build_verifier_agent(model: str = "claude-sonnet-4-20250514"):
    """Agent Phase 2 : vérification par crawl."""
    llm = _build_llm(model)
    tools = [crawl_url, check_company_size, save_verification]
    return create_react_agent(model=llm, tools=tools)


# ─── Compteurs CSV ──────────────────────────────────────────────────

def _count_candidates() -> int:
    if not os.path.exists(CANDIDATES_CSV):
        return 0
    with open(CANDIDATES_CSV, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, delimiter=";")
        return sum(1 for _ in reader)


def _count_pending() -> int:
    if not os.path.exists(CANDIDATES_CSV):
        return 0
    with open(CANDIDATES_CSV, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, delimiter=";")
        return sum(1 for row in reader if row.get("status", "").strip() == "pending")


def _read_next_pending() -> dict | None:
    if not os.path.exists(CANDIDATES_CSV):
        return None
    with open(CANDIDATES_CSV, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            if row.get("status", "").strip() == "pending":
                return dict(row)
    return None


def _mark_candidate_done(candidate_name: str):
    if not os.path.exists(CANDIDATES_CSV):
        return
    with open(CANDIDATES_CSV, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, delimiter=";")
        rows = list(reader)

    name_lower = candidate_name.lower().strip()
    for row in rows:
        if row.get("name", "").lower().strip() == name_lower:
            row["status"] = "done"

    with open(CANDIDATES_CSV, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=CANDIDATES_COLUMNS, delimiter=";")
        writer.writeheader()
        writer.writerows(rows)


def _save_verification_direct(name, website_url, city, source,
                              specialty_confirmed, relevance_score,
                              relevance_reason, specialties_found="",
                              siren="", company_activity=""):
    file_exists = os.path.exists(VERIFIED_CSV)
    row = {
        "name": name,
        "website_url": website_url,
        "city": city,
        "source": source,
        "specialty_confirmed": str(specialty_confirmed),
        "specialties_found": specialties_found,
        "relevance_score": str(relevance_score),
        "relevance_reason": relevance_reason,
        "siren": siren,
        "company_activity": company_activity,
        "is_hiring": "",
    }
    with open(VERIFIED_CSV, "a", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=VERIFIED_COLUMNS, delimiter=";")
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)

    _mark_candidate_done(name)


# ─── Stream agent ───────────────────────────────────────────────────

_STREAM_MAX_RETRIES = 3
_STREAM_RETRY_DELAY = 65


def _stream_agent(agent, system_prompt: str, user_message: str,
                  recursion_limit: int, phase_name: str,
                  log_callback: Callable | None = None) -> str:
    """Lance un agent avec streaming. Retourne le dernier message AI texte."""
    inputs = {
        "messages": [
            ("system", system_prompt),
            ("user", user_message),
        ],
    }
    config = {"recursion_limit": recursion_limit}
    last_ai_text = ""
    last_tool_name = None

    for attempt in range(_STREAM_MAX_RETRIES):
        try:
            for event in agent.stream(inputs, config=config, stream_mode="updates"):
                for node_name, node_data in event.items():
                    messages = node_data.get("messages", [])
                    for msg in messages:
                        if msg.type == "ai":
                            if msg.content and isinstance(msg.content, str):
                                last_ai_text = msg.content
                                # Ne pas afficher le raisonnement de l'agent en phase VERIF
                                if phase_name != "VERIF":
                                    _emit({"type": "log", "phase": phase_name, "message": msg.content}, log_callback)
                            elif msg.content and isinstance(msg.content, list):
                                for block in msg.content:
                                    if isinstance(block, dict) and block.get("type") == "text":
                                        last_ai_text = block["text"]
                                        if phase_name != "VERIF":
                                            _emit({"type": "log", "phase": phase_name, "message": block["text"]}, log_callback)
                            if msg.tool_calls:
                                for tc in msg.tool_calls:
                                    last_tool_name = tc["name"]
                                    args_short = str(tc["args"])[:150]
                                    _emit({"type": "tool_call", "name": tc["name"], "args": args_short}, log_callback)
                        elif msg.type == "tool":
                            content = msg.content if isinstance(msg.content, str) else str(msg.content)
                            if last_tool_name == "crawl_url":
                                # Ne pas afficher le résultat brut des crawls
                                pass
                            elif last_tool_name == "save_verification":
                                # Parser le JSON et afficher le verdict en couleur
                                try:
                                    vdata = json.loads(content)
                                    confirmed = vdata.get("status") == "CONFIRMÉ"
                                    headline = f"{vdata.get('name', '?')} → {vdata.get('status', '?')} (score: {vdata.get('score', '?')}/10)"
                                    reason = vdata.get("reason", "")
                                except (json.JSONDecodeError, TypeError):
                                    confirmed = "NON CONFIRMÉ" not in content and "CONFIRMÉ" in content
                                    headline = content
                                    reason = ""
                                _emit({
                                    "type": "verif_result",
                                    "confirmed": confirmed,
                                    "message": content,
                                    "headline": headline,
                                    "reason": reason,
                                }, log_callback)
                            else:
                                _emit({"type": "tool_result", "message": content[:300]}, log_callback)
            return last_ai_text

        except Exception as e:
            if "rate_limit" in str(e).lower() or "429" in str(e):
                wait = _STREAM_RETRY_DELAY * (attempt + 1)
                _emit({"type": "error", "message": f"[RATE LIMIT] {phase_name} — attente {wait}s (tentative {attempt + 1}/{_STREAM_MAX_RETRIES})"}, log_callback)
                time.sleep(wait)
            else:
                _emit({"type": "error", "message": f"{phase_name} — {str(e)}"}, log_callback)
                raise

    _emit({"type": "error", "message": f"{phase_name} — rate limit persistant après {_STREAM_MAX_RETRIES} tentatives"}, log_callback)
    return last_ai_text


# ─── Boucles principales ───────────────────────────────────────────

def _run_collector_loop(collector_prompt: str, target_count: int,
                        max_iterations: int = 5, log_callback: Callable | None = None):
    for i in range(max_iterations):
        current = _count_candidates()
        if current >= target_count:
            _emit({"type": "progress", "phase": "collecte", "current": current, "target": target_count,
                    "message": f"Objectif atteint : {current}/{target_count} candidats."}, log_callback)
            break

        agent = build_collector_agent()

        if i == 0:
            user_msg = "Lance la collecte selon la demande décrite ci-dessus."
        else:
            user_msg = (
                f"Itération {i + 1}/{max_iterations}. "
                f"{current}/{target_count} candidats trouvés jusqu'ici. "
                f"Varie tes recherches (autres keywords, autres angles). "
                f"Sauvegarde ce que tu trouves avec save_candidates."
            )

        _emit({"type": "progress", "phase": "collecte", "current": current, "target": target_count,
                "message": f"--- Itération {i + 1}/{max_iterations} (collecte) — {current}/{target_count} candidats ---"}, log_callback)
        _stream_agent(agent, collector_prompt, user_msg, recursion_limit=15, phase_name="COLLECTE", log_callback=log_callback)

        # Envoyer la mise à jour CSV après chaque itération
        _emit_csv_update(log_callback, "candidates")


def _run_verifier_loop(step1_prompt: str, step2_prompt: str,
                       log_callback: Callable | None = None):
    verified_count = 0

    while True:
        candidate = _read_next_pending()
        if candidate is None:
            _emit({"type": "progress", "phase": "verification", "current": verified_count, "pending": 0,
                    "message": "Tous les candidats ont été vérifiés."}, log_callback)
            break

        name = candidate.get("name", "")
        url = candidate.get("website_url", "")
        city = candidate.get("city", "")
        source = candidate.get("source", "")

        pending = _count_pending()
        verified_count += 1
        _emit({"type": "progress", "phase": "verification", "current": verified_count, "pending": pending,
                "message": f"--- Vérification {verified_count} ({pending} restants) : {name} ---"}, log_callback)

        if not url or not url.startswith("http"):
            _save_verification_direct(
                name, url, city, source,
                specialty_confirmed=False, relevance_score=0,
                relevance_reason="Pas d'URL de site web",
            )
            _emit({"type": "log", "phase": "VERIF", "message": f"[SKIP] {name} — pas d'URL"}, log_callback)
            _emit_csv_update(log_callback, "verified")
            continue

        # ── SESSION 1 : crawl homepage → cabinet ou pas ? ──
        agent = build_verifier_agent()
        user_msg = (
            f"Vérifie le candidat '{name}' (ville: {city}, source: {source}).\n"
            f"URL à crawler : {url}"
        )

        last_msg = _stream_agent(
            agent, step1_prompt, user_msg,
            recursion_limit=10, phase_name="VERIF",
            log_callback=log_callback,
        )

        # Si l'agent a appelé save_verification (rejet) → pas de session 2
        # On détecte ça : si pas de NEXT_URL, c'est terminé pour ce candidat
        if not last_msg or "NEXT_URL:" not in last_msg:
            _emit_csv_update(log_callback, "verified")
            continue

        # Extraire le résumé de la homepage et l'URL suivante
        homepage_summary = ""
        if "SUMMARY:" in last_msg:
            summary_part = last_msg.split("SUMMARY:")[-1]
            if "NEXT_URL:" in summary_part:
                homepage_summary = summary_part.split("NEXT_URL:")[0].strip()
            else:
                homepage_summary = summary_part.strip()

        next_url = last_msg.split("NEXT_URL:")[-1].strip().split()[0].strip()
        if not next_url.startswith("http"):
            _emit_csv_update(log_callback, "verified")
            continue

        # ── SESSION 2 (contexte neuf) : crawl page expertises → spécialité ──
        agent = build_verifier_agent()
        step2_filled = step2_prompt.replace("{candidate_name}", name).replace("{homepage_summary}", homepage_summary)
        user_msg = (
            f"Cabinet : '{name}' (ville: {city}, source: {source}).\n"
            f"URL de la page expertises à crawler : {next_url}"
        )

        _stream_agent(
            agent, step2_filled, user_msg,
            recursion_limit=10, phase_name="VERIF",
            log_callback=log_callback,
        )

        _emit_csv_update(log_callback, "verified")


# ─── Pipeline principal ─────────────────────────────────────────────

def run_pipeline(
    user_query: str,
    target_count: int = 50,
    company_size: str = "",
    specialty: dict = None,
    log_callback: Callable | None = None,
):
    """Lance le pipeline complet : collecte puis vérification."""

    # ─── Phase 1 : Collecte ───────────────────────────────────
    _emit({"type": "phase", "name": "COLLECTE", "message": "PHASE 1 — COLLECTE DES CANDIDATS"}, log_callback)

    collector_prompt = format_collector_prompt(user_query, target_count, specialty)
    _run_collector_loop(collector_prompt, target_count, max_iterations=5, log_callback=log_callback)

    current_count = _count_candidates()
    _emit({"type": "phase", "name": "COLLECTE_FIN", "message": f"PHASE 1 TERMINEE — {current_count} candidats"}, log_callback)

    # ─── Phase 2 : Vérification ───────────────────────────────
    _emit({"type": "phase", "name": "VERIFICATION", "message": "PHASE 2 — VERIFICATION PAR CRAWL"}, log_callback)

    step1_prompt, step2_prompt = format_verifier_prompts(specialty, company_size)
    _run_verifier_loop(step1_prompt, step2_prompt, log_callback=log_callback)

    # ─── Phase 3 : Export final ─────────────────────────────────
    _generate_final_csv(log_callback=log_callback)


def _generate_final_csv(log_callback: Callable | None = None):
    _emit({"type": "phase", "name": "EXPORT", "message": "GENERATION DU RESULTAT FINAL"}, log_callback)

    if not os.path.exists(VERIFIED_CSV):
        _emit({"type": "log", "phase": "EXPORT", "message": "Aucun fichier verified.csv trouvé."}, log_callback)
        return

    with open(VERIFIED_CSV, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, delimiter=";")
        all_rows = list(reader)

    if not all_rows:
        _emit({"type": "log", "phase": "EXPORT", "message": "Aucun cabinet vérifié."}, log_callback)
        return

    kept = []
    rejected = []
    for row in all_rows:
        try:
            score = int(row.get("relevance_score", 0))
        except (ValueError, TypeError):
            score = 0
        if score >= 5:
            kept.append(row)
        else:
            rejected.append(row)

    kept.sort(key=lambda r: int(r.get("relevance_score", 0)), reverse=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    final_path = os.path.join(OUTPUT_DIR, f"resultats_{timestamp}.csv")

    if kept:
        with open(final_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=kept[0].keys(), delimiter=";")
            writer.writeheader()
            writer.writerows(kept)

    summary = (
        f"Total vérifiés: {len(all_rows)} | "
        f"Confirmés (≥5): {len(kept)} | "
        f"Rejetés (<5): {len(rejected)}"
    )
    _emit({"type": "log", "phase": "EXPORT", "message": summary}, log_callback)

    if kept:
        _emit({"type": "log", "phase": "EXPORT", "message": f"Fichier final: {final_path}"}, log_callback)
        top5 = "\n".join(
            f"  {i+1}. {row['name']} — score {row['relevance_score']}/10 — {row.get('specialties_found', '')}"
            for i, row in enumerate(kept[:5])
        )
        _emit({"type": "log", "phase": "EXPORT", "message": f"TOP 5 :\n{top5}"}, log_callback)
    else:
        _emit({"type": "log", "phase": "EXPORT", "message": "Aucun cabinet confirmé avec un score suffisant."}, log_callback)

    _emit({"type": "done", "message": "PIPELINE TERMINE", "results_path": final_path if kept else ""}, log_callback)
