from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from backend.database.session import get_db
from backend.database.repositories import ModelRunRepository
from backend.schemas.models import ModelInfoResponse
from backend.models.model_run import ModelType

router = APIRouter(prefix="/models", tags=["models"])


@router.get("", response_model=list[ModelInfoResponse])
async def list_models(db: AsyncSession = Depends(get_db)):
    repo = ModelRunRepository(db)
    
    models = []
    for model_type in ModelType:
        latest = await repo.get_latest(model_type)
        if latest:
            models.append(ModelInfoResponse(
                model_name=latest.model_name.value,
                model_version=latest.model_version,
                metrics=latest.get_metrics(),
                trained_at=latest.trained_at,
            ))
    return models