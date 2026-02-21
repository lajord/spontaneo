from fastapi import APIRouter
from app.models.schemas import GenerationRequest, GenerationResponse
from app.services.ai_service import AIService

router = APIRouter()
ai_service = AIService()


@router.post("/cover-letter", response_model=GenerationResponse)
async def generate_cover_letter(request: GenerationRequest):
    """Génère une lettre de motivation personnalisée."""
    result = await ai_service.generate_cover_letter(
        job_title=request.job_title,
        company_name=request.company_name,
        company_sector=request.company_sector,
        user_profile=request.user_profile,
    )
    return GenerationResponse(content=result, type="cover_letter")
