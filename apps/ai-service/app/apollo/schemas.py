from pydantic import BaseModel
from typing import Optional

from app.models.schemas import EnrichedContact


class RankedContact(BaseModel):
    """Contact enrichi avec un score de pertinence attribué par Gemini."""
    contact: EnrichedContact
    score: int  # 0-100
    reason: str


class ApolloEnrichedContact(EnrichedContact):
    """Extension d'EnrichedContact avec les données Apollo.io."""
    email_verified: bool = False
    phone: Optional[str] = None
    linkedin_url: Optional[str] = None
    apollo_id: Optional[str] = None
    ranking_score: Optional[int] = None
