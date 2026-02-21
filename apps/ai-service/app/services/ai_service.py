from typing import Optional
from app.models.schemas import UserProfile


class AIService:
    """Service de génération IA pour les candidatures spontanées."""

    async def generate_cover_letter(
        self,
        job_title: str,
        company_name: str,
        company_sector: Optional[str] = None,
        user_profile: Optional[UserProfile] = None,
    ) -> str:
        """
        Génère une lettre de motivation personnalisée.

        TODO: Intégrer l'appel OpenAI / LLM ici.
        """
        # Placeholder — sera remplacé par un vrai appel LLM
        return (
            f"Madame, Monsieur,\n\n"
            f"Je me permets de vous adresser ma candidature spontanée "
            f"pour le poste de {job_title} au sein de {company_name}.\n\n"
            f"[Contenu généré par IA — à implémenter]\n\n"
            f"Cordialement"
        )
