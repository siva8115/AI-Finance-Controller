from pydantic import BaseModel
from typing import Generic, TypeVar, Optional, List

T = TypeVar('T')


class HealthCheckResponse(BaseModel):
    status: str
    project_name: str
    version: str = "1.0.0"
    database_connected: bool


class APIResponse(BaseModel, Generic[T]):
    success: bool
    message: str
    data: Optional[T] = None
    errors: Optional[List[str]] = None
