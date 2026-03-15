import json
import logging

from app.core.model_config import get_models
from app.utils.ai_caller import call_ai


logger = logging.getLogger(__name__)

# ── Secteurs disponibles (miroir du SECTOR_TREE frontend) ─────────────────────

SECTOR_TREE = {
    "Tech & IT": [
        "ESN / services informatiques", "éditeur de logiciel", "startup tech", "SaaS",
        "cybersécurité", "intelligence artificielle", "cloud computing", "data / big data",
        "développement web", "développement mobile", "blockchain", "fintech", "legaltech",
        "healthtech", "insurtech", "proptech", "deeptech", "devops", "infrastructure IT",
        "hébergement web", "éditeur d'applications", "plateforme numérique",
    ],
    "Finance": [
        "banque", "assurance", "gestion d'actifs", "capital risque", "private equity",
        "fintech", "courtage", "audit", "comptabilité", "conseil financier",
        "gestion de patrimoine", "trading", "paiement en ligne", "néobanque",
        "fonds d'investissement", "cabinet fiscal",
    ],
    "Conseil & Services": [
        "cabinet de conseil", "conseil en stratégie", "conseil en management", "conseil IT",
        "conseil data", "cabinet d'audit", "recrutement / RH", "formation professionnelle",
        "conseil juridique", "cabinet d'avocats", "externalisation", "BPO",
        "conseil en innovation", "conseil en transformation digitale", "coaching d'entreprise",
    ],
    "Marketing": [
        "agence marketing", "agence digitale", "agence SEO", "publicité",
        "relations publiques", "média", "production de contenu", "marketing d'influence",
        "branding", "communication corporate", "agence événementielle", "studio créatif",
        "marketing automation", "growth marketing",
    ],
    "Communication": [
        "relations publiques", "communication corporate", "agence événementielle",
        "journalisme", "médias", "édition",
    ],
    "Ressources Humaines": [
        "recrutement", "formation professionnelle", "coaching", "intérim",
        "gestion de la paie",
    ],
    "Droit": [
        "cabinet d'avocats", "conseil juridique", "notariat", "huissier",
        "juriste d'entreprise",
    ],
    "Industrie": [
        "industrie manufacturière", "aéronautique", "automobile", "chimie", "énergie",
        "métallurgie", "électronique", "robotique", "industrie pharmaceutique", "plasturgie",
        "textile", "industrie lourde", "fabrication de machines", "équipements industriels",
        "industrie du verre", "industrie du bois",
    ],
    "Transport & Logistique": [
        "transport", "logistique", "supply chain", "livraison", "transport maritime",
        "transport aérien", "transport ferroviaire", "transport routier",
        "logistique e-commerce", "entreposage", "messagerie", "transport international",
        "gestion de flotte",
    ],
    "Commerce & Retail": [
        "e-commerce", "grande distribution", "retail", "marketplace", "commerce de gros",
        "commerce de détail", "supermarché", "hypermarché", "franchise",
        "magasin spécialisé", "vente en ligne", "vente omnicanale",
    ],
    "Santé": [
        "hôpital", "clinique", "laboratoire", "biotech", "pharmaceutique", "medtech",
        "mutuelle", "assurance santé", "centre de recherche médical", "télémédecine",
        "dispositifs médicaux", "centre de diagnostic", "santé numérique",
    ],
    "Immo & Construction": [
        "immobilier", "promoteur immobilier", "construction", "BTP", "architecture",
        "urbanisme", "agence immobilière", "gestion immobilière", "aménagement urbain",
        "promotion immobilière", "construction durable", "ingénierie bâtiment",
    ],
    "Énergie & Env.": [
        "énergie", "pétrole", "gaz", "énergies renouvelables", "nucléaire",
        "environnement", "recyclage", "gestion des déchets", "efficacité énergétique",
        "énergie solaire", "énergie éolienne", "hydrogène", "transition énergétique",
    ],
    "Agriculture & Agro.": [
        "agriculture", "agroalimentaire", "agritech", "coopérative agricole",
        "industrie alimentaire", "production agricole", "élevage", "viticulture",
        "distribution alimentaire", "transformation alimentaire", "agriculture biologique",
    ],
    "Tourisme & Hôtellerie": [
        "tourisme", "agence de voyage", "hôtel", "hôtellerie", "compagnie aérienne",
        "événementiel", "tour opérateur", "location de vacances", "parc de loisirs",
        "croisière", "tourisme d'affaires",
    ],
    "Divertissement & Médias": [
        "jeux vidéo", "cinéma", "production audiovisuelle", "streaming", "musique",
        "médias", "télévision", "radio", "édition", "presse", "plateforme de contenu",
        "e-sport",
    ],
    "Éducation": [
        "université", "école", "edtech", "formation", "recherche", "centre de recherche",
        "formation en ligne", "bootcamp", "organisme de formation", "institut académique",
    ],
    "Secteur public & ONG": [
        "administration", "collectivité territoriale", "ONG", "association",
        "organisation internationale", "service public", "organisation gouvernementale",
        "institution publique", "chambre de commerce",
    ],
}


def _build_sector_tree_text() -> str:
    lines = []
    for domain, subs in SECTOR_TREE.items():
        lines.append(f"- {domain} : {', '.join(subs)}")
    return "\n".join(lines)


def _build_user_context(
    sectors: list[str] | None,
    categories: list[str] | None,
) -> str:
    parts = []
    if categories:
        parts.append(f"Domaines sélectionnés par le candidat : {', '.join(categories)}")
    if sectors:
        parts.append(f"Sous-secteurs sélectionnés par le candidat : {', '.join(sectors)}")
    if not parts:
        parts.append("Le candidat n'a sélectionné aucun domaine ni sous-secteur.")
    return "\n".join(parts)


# ── Prompt IA stratégique ─────────────────────────────────────────────────────

_SYSTEM_PROMPT = (
    "Tu es un conseiller expert en recherche d'emploi en France.\n"
    "Un candidat te demande de l'aide pour trouver des entreprises qui pourraient "
    "être intéressées par son profil.\n\n"

    "Tu connais parfaitement le marché de l'emploi français. Tu sais quels types "
    "d'entreprises recrutent pour chaque métier, comment elles se nomment, "
    "dans quels secteurs on les trouve.\n\n"

    "Le candidat va te donner son titre de poste et éventuellement les secteurs "
    "qui l'intéressent. Toi, tu dois lui dire EXACTEMENT ce qu'il devrait taper "
    "comme recherche sur 3 plateformes différentes pour trouver les bonnes entreprises.\n\n"

    "Réfléchis bien à la nature du poste :\n"
    "- Un serveur → c'est simple, on cherche des restaurants, brasseries, hôtels\n"
    "- Un juriste en tech → c'est plus complexe, il faut penser aux cabinets spécialisés, "
    "aux legaltech, aux départements juridiques de grosses boîtes tech\n"
    "- Un commercial B2B → ça dépend énormément du secteur choisi\n\n"

    "## PLATEFORME 1 : Apollo (base de données d'entreprises)\n\n"

    "### apollo_job_titles\n"
    "Ce paramètre cherche les entreprises qui ont des offres d'emploi actives.\n"
    "Dis au candidat comment son poste se dit en anglais. UNE seule traduction fidèle.\n\n"

    "### apollo_keywords\n"
    "Ce paramètre cherche les entreprises par leurs tags sectoriels (en anglais).\n"
    "Dis au candidat quels mots-clés taper pour trouver le bon type d'entreprises.\n"
    "Ça peut être des mots simples ou des expressions de 2-3 mots.\n"
    "Tout en anglais, en minuscules.\n"
    "Si le candidat a déjà choisi des sous-secteurs, traduis-les. "
    "Sinon, propose les plus pertinents pour son métier.\n\n"

    "## PLATEFORME 2 : Google Maps\n\n"

    "### google_maps_keywords\n"
    "Google Maps cherche des établissements physiques dans une ville.\n"
    "Dis au candidat ce qu'il devrait taper dans la barre de recherche Google Maps "
    "pour trouver des entreprises près de chez lui qui pourraient l'embaucher.\n"
    "C'est en FRANÇAIS.\n"
    "Sois précis et créatif : combine le type de structure avec la spécialité.\n"
    "Exemples :\n"
    "- Juriste en tech → 'cabinet avocat droit du numérique', 'legaltech', 'cabinet juridique startup'\n"
    "- Serveur → 'restaurant', 'brasserie', 'hôtel restaurant'\n"
    "- Dev web en fintech → 'agence web fintech', 'studio développement application bancaire'\n"
    "- Comptable → 'cabinet comptable', 'expert-comptable', 'cabinet audit financier'\n"
    "- Commercial B2B en SaaS → 'éditeur logiciel', 'entreprise SaaS', 'startup logiciel'\n"
    "N'utilise JAMAIS de termes vagues comme 'entreprise', 'société', 'bureau'.\n"
    "N'inclus JAMAIS d'écoles, administrations ou agences d'intérim.\n\n"

    "## FORMAT DE RÉPONSE\n"
    "Tu DOIS répondre UNIQUEMENT avec un objet JSON valide, sans texte avant ni après.\n"
    "Le JSON doit contenir exactement 3 clés :\n"
    "- \"apollo_job_titles\" : liste de strings (1 seul élément)\n"
    "- \"apollo_keywords\" : liste de strings (3 à 8 éléments)\n"
    "- \"google_maps_keywords\" : liste de strings (3 à 6 éléments)\n"
)

_USER_PROMPT = (
    'Le candidat cherche un poste de : "{secteur}"\n\n'
    "{user_context}\n\n"
    "Voici les sous-secteurs disponibles pour t'aider à choisir :\n{sector_tree}\n\n"
    "Que lui conseilles-tu de taper comme recherche sur chaque plateforme ?\n"
    "Réponds UNIQUEMENT avec le JSON."
)


# ── Fonction principale ──────────────────────────────────────────────────────

async def build_search_params(
    secteur: str,
    sectors: list[str] | None = None,
    categories: list[str] | None = None,
) -> dict:
    """
    Un seul appel IA stratégique qui renvoie tous les paramètres de recherche :
    - apollo_job_titles (EN)
    - apollo_keywords (EN)
    - google_maps_keywords (FR)
    """
    user_context = _build_user_context(sectors, categories)
    sector_tree_text = _build_sector_tree_text()
    prompt = _USER_PROMPT.format(
        secteur=secteur,
        user_context=user_context,
        sector_tree=sector_tree_text,
    )

    try:
        models = await get_models()
        logger.info(
            f"[SEARCH STRATEGY] model={models.MODEL_KEYWORDS}  "
            f"secteur='{secteur}'  sectors={sectors}  categories={categories}"
        )
        raw = await call_ai(
            model=models.MODEL_KEYWORDS,
            prompt=prompt,
            system_prompt=_SYSTEM_PROMPT,
            temperature=0,
        )
        data = json.loads(raw)
        result = {
            "apollo_job_titles": [
                t for t in data.get("apollo_job_titles", [])
                if isinstance(t, str) and t.strip()
            ],
            "apollo_keywords": [
                k for k in data.get("apollo_keywords", [])
                if isinstance(k, str) and k.strip()
            ],
            "google_maps_keywords": [
                k for k in data.get("google_maps_keywords", [])
                if isinstance(k, str) and k.strip()
            ],
        }
        if result["apollo_job_titles"]:
            logger.info(f"[SEARCH STRATEGY] apollo_job_titles: {result['apollo_job_titles']}")
            logger.info(f"[SEARCH STRATEGY] apollo_keywords: {result['apollo_keywords']}")
            logger.info(f"[SEARCH STRATEGY] google_maps_keywords: {result['google_maps_keywords']}")
            return result
    except Exception as e:
        logger.error(f"[SEARCH STRATEGY] Erreur: {e}")

    # Fallback minimal
    return {
        "apollo_job_titles": [secteur],
        "apollo_keywords": [],
        "google_maps_keywords": [secteur],
    }
