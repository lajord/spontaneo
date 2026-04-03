import json
import os
import time
from langchain_core.tools import tool
from openai import OpenAI

from config import RATE_LIMIT_PERPLEXITY, TOOL_MAX_RETRIES, TOOL_RETRY_BASE_DELAY


def _get_perplexity_key():
    return os.getenv("PERPLEXITY_API_KEY", "")


# Rate limiting
_last_call_time = 0.0
RATE_LIMIT_DELAY = RATE_LIMIT_PERPLEXITY
_MAX_RETRIES = TOOL_MAX_RETRIES
_BASE_DELAY = TOOL_RETRY_BASE_DELAY


def _rate_limit():
    """Respecte le rate limit Perplexity."""
    global _last_call_time
    elapsed = time.time() - _last_call_time
    if elapsed < RATE_LIMIT_DELAY:
        time.sleep(RATE_LIMIT_DELAY - elapsed)
    _last_call_time = time.time()


@tool
def perplexity_search(query: str) -> str:
    """Recherche sur internet via Perplexity Sonar Pro.

    Outil de recherche GENERIQUE. Tu decides quoi chercher.
    Exemples d'utilisation :
    - "Trouver le profil LinkedIn du directeur de Cabinet X a Paris"
    - "Page equipe du cabinet Y avocats"
    - "Email contact de Jean Dupont avocat Paris"
    - "Annuaire des associes du cabinet X"
    - "decideurs de la banque Z LinkedIn"

    Contrairement a web_search_legal, cet outil ne force PAS de format JSON.
    Il retourne la reponse en texte brut — c'est a toi de parser les infos utiles.

    Args:
        query: La question ou recherche a effectuer (en francais ou anglais)

    Returns:
        Reponse de Perplexity en texte brut avec les informations trouvees.
    """
    api_key = _get_perplexity_key()
    if not api_key:
        return json.dumps({
            "error": "PERPLEXITY_API_KEY non configuree dans le .env",
        })

    if not query or not query.strip():
        return "Erreur: query vide."

    print(f"  [PERPLEXITY] Query: {query}")

    client = OpenAI(
        api_key=api_key,
        base_url="https://api.perplexity.ai",
    )

    system_message = (
        "Tu es un assistant de recherche strictement factuel. "
        "Tu ne dois JAMAIS inventer, deduire, extrapoler ou completer une information manquante. "
        "Tu dois te baser uniquement sur des informations explicitement presentes dans les resultats trouves. "
        "Si une information n'est pas visible noir sur blanc, dis 'NON TROUVE' au lieu de supposer. "
        "N'invente jamais un email a partir d'un pattern, n'invente jamais une ville, un poste, une specialite ou une URL. "
        "Retourne une reponse concise orientee extraction de donnees. "
        "Inclus uniquement les noms, emails, URLs, numeros de telephone et titres/postes explicitement trouves. "
        "Si tu trouves des profils LinkedIn, donne les URLs completes. "
        "Quand c'est possible, associe chaque information a sa source ou a l'URL correspondante. "
        "Ne fais pas de commentaires inutiles."
    )

    for attempt in range(_MAX_RETRIES):
        try:
            _rate_limit()
            response = client.chat.completions.create(
                model="sonar-pro",
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": query},
                ],
                temperature=0.1,
            )

            content = response.choices[0].message.content.strip()
            print(f"  [PERPLEXITY] Reponse: {len(content)} chars")
            return content

        except Exception as e:
            error_str = str(e).lower()
            if "rate" in error_str or "429" in error_str:
                wait = _BASE_DELAY * (attempt + 1)
                print(f"  [PERPLEXITY] Rate limit — retry dans {wait}s (tentative {attempt + 1}/{_MAX_RETRIES})")
                time.sleep(wait)
                continue

            msg = f"Erreur Perplexity: {type(e).__name__}: {e}"
            print(f"  [PERPLEXITY ERROR] {msg}")
            return json.dumps({"error": msg})

    return json.dumps({"error": "Echec apres 3 tentatives (rate limit Perplexity)"})
