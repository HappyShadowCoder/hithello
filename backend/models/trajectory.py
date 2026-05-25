"""Pydantic request/response models for the trajectory endpoint."""
from typing import Optional
from pydantic import BaseModel, Field


class TrajectoryRequest(BaseModel):
    """Ballistic trajectory calculation parameters."""

    weapon_type: str = Field(
        ...,
        description=(
            "Weapon identifier. Supported: "
            "'machine_gun_762', 'hmg_127', 'mortar_81mm', 'mortar_120mm', 'artillery_105mm'"
        ),
        examples=["mortar_81mm"],
    )
    elevation_m: float = Field(
        ...,
        description="Elevation of the firing position above sea level (metres ASL).",
        examples=[3500.0],
    )
    target_distance_m: float = Field(
        ...,
        gt=0,
        description="Horizontal distance from firing position to target (metres).",
        examples=[2000.0],
    )
    slope_angle_deg: float = Field(
        default=0.0,
        ge=-60,
        le=60,
        description=(
            "Terrain slope angle in degrees. "
            "Positive = uphill to target, negative = downhill."
        ),
        examples=[15.0],
    )
    launch_angle_deg: Optional[float] = Field(
        default=None,
        ge=0,
        lt=90,
        description=(
            "Override the computed launch angle (degrees above horizontal). "
            "If omitted the optimal angle is solved automatically."
        ),
    )


class ArcPoint(BaseModel):
    """Single point along the ballistic arc."""

    time_s: float = Field(..., description="Elapsed time from launch (seconds).")
    x_m: float = Field(..., description="Horizontal distance from firing position (metres).")
    altitude_m: float = Field(..., description="Altitude above sea level (metres ASL).")


class TrajectoryMeta(BaseModel):
    """Summary metadata for the computed trajectory."""

    weapon_name: str
    launch_angle_deg: float
    time_of_flight_s: float
    max_height_agl_m: float          # metres above the firing point
    max_altitude_asl_m: float        # metres ASL
    target_height_diff_m: float      # Δh due to slope (+ = uphill)
    impact_velocity_ms: float
    impact_angle_deg: float          # degrees below horizontal at impact
    effective_range_m: float
    in_range: bool


class TrajectoryResponse(BaseModel):
    """Full trajectory response."""

    arc: list[ArcPoint]
    metadata: TrajectoryMeta
