from fastapi import APIRouter
from app.api.v1.endpoints import data, reconciliation, evaluation, ai, review, resolution, audit

api_router = APIRouter()
api_router.include_router(data.router)
api_router.include_router(reconciliation.router)
api_router.include_router(evaluation.router)
api_router.include_router(ai.router)
api_router.include_router(review.router)
api_router.include_router(resolution.router)
api_router.include_router(audit.router)
