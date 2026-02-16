"""
Common API schemas.
"""

from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    detail: str
    code: str | None = None


class SuccessResponse(BaseModel):
    message: str
    data: dict | None = None


class PaginationParams(BaseModel):
    page: int = Field(default=1, ge=1)
    per_page: int = Field(default=20, ge=1, le=100)

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.per_page


class PaginatedResponse(BaseModel):
    items: list
    total: int
    page: int
    per_page: int
    pages: int
