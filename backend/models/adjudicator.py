from pydantic import BaseModel
from typing import Literal

class UnitCombatStats(BaseModel):
    numerical_strength: int
    wli: float

class EnvironmentStats(BaseModel):
    terrain_multiplier: float
    weather_penalty: float

class EngagementRequest(BaseModel):
    attacker: UnitCombatStats
    defender: UnitCombatStats
    environment: EnvironmentStats

class EngagementResponse(BaseModel):
    attacker_casualties: int
    defender_casualties: int
    defender_morale_state: Literal["Holding", "Pinned", "Retreating", "Routed"]
    attacker_morale_state: Literal["Holding", "Pinned", "Retreating", "Routed"]
    ammo_depleted: bool
