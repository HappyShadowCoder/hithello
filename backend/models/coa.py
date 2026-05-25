"""Pydantic request/response models for the FAHP / COA comparison endpoint."""
from typing import Optional
from pydantic import BaseModel, Field

# ── 8 Military dimensions (from MOPT project brief) ─────────────────────────
DIMENSION_LABELS = [
    "Tactical Advantage",
    "Logistic Feasibility",
    "Force Protection",
    "Speed of Action",
    "Terrain Exploitation",
    "Deception Potential",
    "Flexibility",
    "Risk Level",
]

# Default equal-weight pairwise comparison matrix (all TFNs = (1,1,1))
DEFAULT_PAIRWISE = [
    [[1.0, 1.0, 1.0] for _ in range(8)] for _ in range(8)
]


class COAInput(BaseModel):
    """Scores for a single Course of Action across all 8 dimensions."""

    name: str = Field(..., description="COA identifier (e.g. 'COA Alpha').")
    scores: list[float] = Field(
        ...,
        min_length=8,
        max_length=8,
        description=(
            "Score for each of the 8 military dimensions, in this order: "
            + ", ".join(DIMENSION_LABELS)
            + ". Values must be in [0, 10]."
        ),
        examples=[[8, 6, 7, 9, 5, 4, 7, 3]],
    )


class FAHPRequest(BaseModel):
    """
    FAHP COA comparison request.

    Pairwise comparison matrix uses Triangular Fuzzy Numbers (TFNs).
    Each cell is a list [l, m, u] where l ≤ m ≤ u.

    Saaty fuzzy scale:
      Equal importance     → [1, 1, 1]
      Moderate             → [2, 3, 4]
      Strong               → [4, 5, 6]
      Very strong          → [6, 7, 8]
      Extreme              → [8, 9, 10]
    Reciprocals are applied automatically for the lower triangle.
    If omitted, equal weights (all [1,1,1]) are assumed.
    """

    coa_list: list[COAInput] = Field(
        ...,
        min_length=2,
        description="List of COAs to compare (minimum 2).",
    )
    pairwise_matrix: Optional[list[list[list[float]]]] = Field(
        default=None,
        description=(
            "8×8 matrix of TFNs representing pairwise importance of the 8 dimensions. "
            "Only the upper triangle is used; lower triangle is derived from reciprocals."
        ),
    )


class DimensionWeight(BaseModel):
    """FAHP-derived weight for one dimension."""

    dimension: str
    weight: float
    fuzzy_synthetic_extent: list[float]  # (l, m, u) of the synthetic extent value


class COARanking(BaseModel):
    """Ranked result for one COA."""

    rank: int
    name: str
    weighted_score: float
    dimension_contributions: dict[str, float]  # dimension → contribution to total score


class SensitivityResult(BaseModel):
    """Result of weight-perturbation sensitivity analysis."""

    is_stable: bool
    n_perturbations_run: int
    n_rank_changes: int
    recommended_coa_consistent: bool


class FAHPResponse(BaseModel):
    """Full FAHP COA comparison response."""

    dimensions: list[DimensionWeight]
    rankings: list[COARanking]
    recommended_coa: str
    sensitivity: SensitivityResult
