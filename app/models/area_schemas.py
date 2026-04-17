"""
Schemas Pydantic para áreas geográficas e atribuições de usuários.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class AreaCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    description: Optional[str] = Field(None, max_length=512)
    bbox: List[float] = Field(..., min_length=4, max_length=4, description="[min_lon, min_lat, max_lon, max_lat]")
    coordinates: Optional[List[List[float]]] = Field(None, description="GeoJSON polygon [[lon, lat], ...]")
    area_hectares: Optional[float] = Field(None, ge=0)


class AreaUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=128)
    description: Optional[str] = Field(None, max_length=512)
    bbox: Optional[List[float]] = Field(None, min_length=4, max_length=4)
    coordinates: Optional[List[List[float]]] = None
    area_hectares: Optional[float] = Field(None, ge=0)


class AreaResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    bbox: List[float]
    coordinates: Optional[List[List[float]]]
    area_hectares: Optional[float]
    created_by: str
    created_at: datetime
    updated_at: datetime
    assigned_users: List[str] = []


class AssignUserRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=64)


class UserListResponse(BaseModel):
    username: str
    is_admin: bool
