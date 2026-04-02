# ──────────────────────────────────────────────────────────────────
# CONFIG — HYPERPARAMETRES CENTRALISES DE L'AGENT
#
# TOUT ce qui est tunable est ici. Un seul fichier a modifier
# pour ajuster le comportement de l'ensemble du pipeline.
#
# Organisation :
#   1. LLM           — modele, tokens, timeout
#   2. STREAM/RETRY   — retry sur rate limit Claude
#   3. AGENTS         — recursion limits, batch sizes
#   4. RATE LIMITS    — delais entre appels API par outil
#   5. RETRIES        — retry par outil externe
#   6. CONTENT        — troncature, limites de contenu
#   7. LOGGING        — troncature des logs
# ──────────────────────────────────────────────────────────────────


# ─── 1. LLM ─────────────────────────────────────────────────────

LLM_MODEL = "claude-sonnet-4-20250514"
LLM_MAX_TOKENS = 16384
LLM_INTERNAL_RETRIES = 5          # retries internes LangChain
LLM_REQUEST_TIMEOUT = 120         # timeout HTTP (secondes)


# ─── 2. STREAM / RETRY (rate limit Claude) ──────────────────────

STREAM_MAX_RETRIES = 3            # tentatives sur 429
STREAM_RETRY_DELAY = 65           # base en secondes (x attempt)


# ─── 3. AGENTS ──────────────────────────────────────────────────

# Agent 1 — Collecte
AGENT1_RECURSION_LIMIT = 25       # steps LangGraph max
AGENT1_DEFAULT_BATCH_SIZE = 100   # candidats cibles par iteration

# Agent 3 — Enrichissement (4 sous-agents)
AGENT3A_RECURSION_LIMIT = 15      # 3A : Crawl site web
AGENT3B_RECURSION_LIMIT = 10   # 3B : Recherche Perplexity/Apollo
AGENT3C_RECURSION_LIMIT = 20      # 3C : Verification emails
AGENT3D_RECURSION_LIMIT = 15      # 3D : Qualification + sauvegarde
AGENT3_TARGET_CONTACTS = 3        # objectif de contacts qualifies par entreprise

# Pipeline global

# ─── 4. RATE LIMITS (delai entre appels, en secondes) ───────────

RATE_LIMIT_APOLLO = 1.2           # apollo_search + apollo_people
RATE_LIMIT_PERPLEXITY = 2.0       # web_search_legal + perplexity_search
RATE_LIMIT_CRAWL = 2.0            # crawl4ai (crawl_url)
RATE_LIMIT_GOOGLE_MAPS = 3.0      # google_maps_search (Apify)
RATE_LIMIT_ENTREPRISE_API = 0.2   # API gouv.fr SIREN
RATE_LIMIT_NEVERBOUNCE = 0.5      # neverbounce_verify


# ─── 5. RETRIES PAR OUTIL EXTERNE ──────────────────────────────

TOOL_MAX_RETRIES = 3              # retries sur erreur/rate limit
TOOL_RETRY_BASE_DELAY = 5         # base backoff (secondes)

# Crawl4AI analyse (appel Claude pour analyser une page)
CRAWL_ANALYZE_MAX_RETRIES = 3
CRAWL_ANALYZE_RETRY_DELAY = 60    # base (secondes, x attempt)
CRAWL_ANALYZE_MAX_TOKENS = 1024   # tokens pour l'analyse de page


# ─── 6. CONTENT ─────────────────────────────────────────────────

MAX_CONTENT_CHARS = 15_000        # troncature du contenu crawle
MAX_STRATEGIC_LINKS = 5           # liens strategiques a suivre par domaine


# ─── 7. HTTP TIMEOUTS PAR OUTIL ─────────────────────────────────

HTTP_TIMEOUT_APOLLO = 30          # secondes
HTTP_TIMEOUT_PERPLEXITY = 30      # secondes
HTTP_TIMEOUT_CRAWL = 15           # secondes
HTTP_TIMEOUT_GOOGLE_MAPS = 30     # secondes
HTTP_TIMEOUT_ENTREPRISE = 10      # secondes
HTTP_TIMEOUT_NEVERBOUNCE = 35     # secondes


# ─── 8. LOGGING ─────────────────────────────────────────────────

LOG_TOOL_ARGS_MAX_CHARS = 500     # troncature args dans les logs
LOG_TOOL_RESULT_MAX_CHARS = 500   # troncature resultats dans les logs
