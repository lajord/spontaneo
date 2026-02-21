from pydantic import BaseModel
from typing import Optional


class UserProfile(BaseModel):
    """Profil utilisateur pour la génération."""

    first_name: str
    last_name: str
    job_title: str
    bio: Optional[str] = None
    skills: list[str] = []


class GenerationRequest(BaseModel):
    """Requête de génération de candidature."""

    job_title: str
    company_name: str
    company_sector: Optional[str] = None
    user_profile: Optional[UserProfile] = None


class GenerationResponse(BaseModel):
    """Réponse de génération."""

    content: str
    type: str  # "cover_letter", "email", etc.
