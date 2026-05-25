"""
models/unit.py — Unit data models for Phase 5
==============================================
Defines the data structures for map units (Blue/Red team forces)
used in WebSocket broadcasts and the /place_unit REST endpoint.
"""

from typing import Literal
from pydantic import BaseModel, Field
import uuid


class Unit(BaseModel):
    """A single tactical unit placed on the map."""
    id:   str   = Field(default_factory=lambda: str(uuid.uuid4()))
    team: str
    team_color: str = "#ffffff"
    lon:  float = Field(description="WGS84 longitude")
    lat:  float = Field(description="WGS84 latitude")
    label: str  = Field(default="", description="Optional unit label, e.g. 'Alpha-1'")


class PlaceUnitRequest(BaseModel):
    """Request body for POST /place_unit (EXCON only)."""
    team:  str
    team_color: str = "#ffffff"
    lon:   float
    lat:   float
    label: str = ""


class RemoveUnitRequest(BaseModel):
    """Request body for POST /remove_unit (EXCON only)."""
    id: str


class SetWeatherRequest(BaseModel):
    """Request body for POST /set_weather (EXCON only)."""
    weather: Literal["Clear", "Rain", "Snow", "Fog"]
