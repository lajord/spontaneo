import logging

from app.models.schemas import EnrichedContact
from app.apollo.schemas import ApolloEnrichedContact

logger = logging.getLogger(__name__)


def adapt_person_to_contact(
    apollo_person: dict,
    existing_contact: EnrichedContact | None = None,
) -> ApolloEnrichedContact:
    """Transforme la réponse Apollo /people/match en ApolloEnrichedContact.

    Si un contact existant est fourni, on fusionne :
    - Apollo est prioritaire pour : email (si verified), phone, linkedin_url
    - L'existant est prioritaire pour : role (plus contextualisé par Gemini)
    """
    person = apollo_person.get("person") or apollo_person

    # Extraction des données Apollo
    apollo_email = person.get("email")
    apollo_email_status = person.get("email_status", "")
    email_verified = apollo_email_status == "verified"

    phone = None
    phone_numbers = person.get("phone_numbers") or []
    if phone_numbers:
        phone = phone_numbers[0].get("sanitized_number") or phone_numbers[0].get("raw_number")

    linkedin_url = person.get("linkedin_url")
    apollo_id = person.get("id")

    # Déduction du genre depuis Apollo
    apollo_genre = None
    # Apollo ne fournit pas directement le genre, on garde celui de l'existant

    if existing_contact:
        # Fusion : Apollo enrichit, existant complète
        return ApolloEnrichedContact(
            type=existing_contact.type,
            nom=existing_contact.nom or person.get("last_name"),
            prenom=existing_contact.prenom or person.get("first_name"),
            role=existing_contact.role or person.get("title"),
            mail=(apollo_email if email_verified else None) or existing_contact.mail or apollo_email,
            genre=existing_contact.genre,
            email_verified=email_verified,
            phone=phone,
            linkedin_url=linkedin_url,
            apollo_id=apollo_id,
            ranking_score=None,
        )

    # Pas de contact existant, on crée depuis Apollo uniquement
    return ApolloEnrichedContact(
        type="specialise",
        nom=person.get("last_name"),
        prenom=person.get("first_name"),
        role=person.get("title"),
        mail=apollo_email,
        genre=apollo_genre,
        email_verified=email_verified,
        phone=phone,
        linkedin_url=linkedin_url,
        apollo_id=apollo_id,
        ranking_score=None,
    )


def adapt_organization(apollo_org: dict) -> dict:
    """Extrait les champs utiles de la réponse Apollo /organizations/enrich."""
    org = apollo_org.get("organization") or apollo_org

    return {
        "apollo_id": org.get("id"),
        "name": org.get("name"),
        "domain": org.get("primary_domain"),
        "website": org.get("website_url"),
        "industry": org.get("industry"),
        "estimated_employees": org.get("estimated_num_employees"),
        "annual_revenue": org.get("annual_revenue"),
        "annual_revenue_printed": org.get("annual_revenue_printed"),
        "total_funding": org.get("total_funding"),
        "latest_funding_stage": org.get("latest_funding_stage"),
        "founded_year": org.get("founded_year"),
        "city": org.get("city"),
        "country": org.get("country"),
        "short_description": org.get("short_description"),
        "linkedin_url": org.get("linkedin_url"),
        "logo_url": org.get("logo_url"),
        "technology_names": org.get("technology_names") or [],
        "keywords": org.get("keywords") or [],
    }
