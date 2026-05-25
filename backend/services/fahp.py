"""
services/fahp.py
-----------------
Fuzzy Analytic Hierarchy Process (FAHP) for Course of Action (COA) comparison.

Method: Chang (1996) Extent Analysis on Triangular Fuzzy Numbers (TFNs)
Reference: Chang, D.-Y. (1996). Applications of the extent analysis method
           on fuzzy AHP. European Journal of Operational Research, 95(3), 649-655.

8 Military Dimensions (from MOPT project brief):
    1. Tactical Advantage
    2. Logistic Feasibility
    3. Force Protection
    4. Speed of Action
    5. Terrain Exploitation
    6. Deception Potential
    7. Flexibility
    8. Risk Level

Triangular Fuzzy Number (TFN) Notation:
    M = (l, m, u)  where l = lower bound, m = modal value, u = upper bound
    Represents linguistic uncertainty in pairwise comparisons.

Saaty Fuzzy Scale:
    Importance          TFN
    ─────────────────────────
    Equal               (1, 1, 1)
    Moderate            (2, 3, 4)
    Strong              (4, 5, 6)
    Very Strong         (6, 7, 8)
    Extreme             (8, 9, 10)
    Reciprocal of M     (1/u, 1/m, 1/l)

Algorithm Steps:
    1. Build n×n fuzzy pairwise comparison matrix
    2. Compute fuzzy synthetic extent values: S_i = Σⱼ M_ij ⊗ (Σᵢ Σⱼ M_ij)⁻¹
    3. Compute degree of possibility: V(S_i ≥ S_k) for all k ≠ i
    4. Priority weight for criterion i: d(A_i) = min_k V(S_i ≥ S_k)
    5. Normalize weights: W = d / Σd
    6. Weighted COA score: score(COA_i) = Σⱼ w_j × coa_score_ij
    7. Sensitivity analysis: perturb weights and check ranking stability
"""

import random
import numpy as np
from typing import Optional

# ── TFN arithmetic ─────────────────────────────────────────────────────────────

TFN = tuple[float, float, float]  # (lower, modal, upper)


def tfn_add(a: TFN, b: TFN) -> TFN:
    """Element-wise addition of two TFNs: (l₁+l₂, m₁+m₂, u₁+u₂)."""
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def tfn_sum(tfns: list[TFN]) -> TFN:
    """Sum a list of TFNs."""
    result: TFN = (0.0, 0.0, 0.0)
    for t in tfns:
        result = tfn_add(result, t)
    return result


def tfn_reciprocal(a: TFN) -> TFN:
    """
    Reciprocal of TFN (l, m, u)⁻¹ = (1/u, 1/m, 1/l).
    Guards against division by zero.
    """
    l, m, u = a
    if abs(l) < 1e-12 or abs(m) < 1e-12 or abs(u) < 1e-12:
        raise ValueError(f"Cannot invert TFN with zero component: {a}")
    return (1.0 / u, 1.0 / m, 1.0 / l)


def tfn_multiply_element(a: TFN, b: TFN) -> TFN:
    """Element-wise (fuzzy) multiplication: (l₁·l₂, m₁·m₂, u₁·u₂)."""
    return (a[0] * b[0], a[1] * b[1], a[2] * b[2])


def tfn_defuzzify(a: TFN) -> float:
    """
    Centre of gravity (centroid) defuzzification for a TFN:
    crisp = (l + m + u) / 3
    """
    return (a[0] + a[1] + a[2]) / 3.0


# ── Degree of possibility ────────────────────────────────────────────────────

def degree_of_possibility(s1: TFN, s2: TFN) -> float:
    """
    V(S₁ ≥ S₂): Degree of possibility that fuzzy number S₁ is at least as
    large as S₂, using Chang's intersection-height formula.

    Cases:
      m₁ ≥ m₂  →  V = 1.0   (S₁ clearly dominates)
      u₁ ≤ l₂  →  V = 0.0   (S₁ is entirely below S₂)
      Otherwise →  V = (l₂ − u₁) / ((m₁ − u₁) − (m₂ − l₂))
    """
    l1, m1, u1 = s1
    l2, m2, u2 = s2

    if m1 >= m2:
        return 1.0
    if u1 <= l2:
        return 0.0

    denom = (m1 - u1) - (m2 - l2)
    if abs(denom) < 1e-12:
        return 0.0  # degenerate case

    return max(0.0, min(1.0, (l2 - u1) / denom))


# ── Core FAHP ────────────────────────────────────────────────────────────────

def _build_full_matrix(upper_triangle: list[list[list[float]]], n: int) -> list[list[TFN]]:
    """
    Fill in the lower triangle of the pairwise comparison matrix using
    fuzzy reciprocals (lower triangle[i][j] = reciprocal(upper[j][i])).
    Diagonal is always (1, 1, 1).
    """
    matrix: list[list[TFN]] = [[(1.0, 1.0, 1.0)] * n for _ in range(n)]
    for i in range(n):
        for j in range(n):
            if i == j:
                matrix[i][j] = (1.0, 1.0, 1.0)
            elif j > i:
                raw = upper_triangle[i][j]
                tfn: TFN = (float(raw[0]), float(raw[1]), float(raw[2]))
                matrix[i][j] = tfn
                matrix[j][i] = tfn_reciprocal(tfn)
    return matrix


def compute_fahp_weights(
    pairwise_raw: list[list[list[float]]],
    n: int = 8,
) -> tuple[list[float], list[TFN]]:
    """
    Apply Chang's extent analysis to derive crisp priority weights from an
    n×n fuzzy pairwise comparison matrix.

    Returns:
        weights          — list of n normalised crisp weights (sum = 1.0)
        synthetic_extents — list of n TFNs (one per criterion)
    """
    matrix = _build_full_matrix(pairwise_raw, n)

    # ── Step 2: Row sums and total sum ────────────────────────────────────────
    row_sums: list[TFN] = []
    for i in range(n):
        row_sums.append(tfn_sum(matrix[i]))

    total: TFN = tfn_sum(row_sums)
    total_recip: TFN = tfn_reciprocal(total)

    # ── Step 3: Fuzzy synthetic extent values S_i ─────────────────────────────
    # S_i = row_sum_i ⊗ total_recip  (element-wise multiplication)
    S: list[TFN] = [tfn_multiply_element(rs, total_recip) for rs in row_sums]

    # ── Step 4: Degree of possibility d(A_i) ─────────────────────────────────
    # d(A_i) = min_{k ≠ i} V(S_i ≥ S_k)
    d: list[float] = []
    for i in range(n):
        min_deg = float("inf")
        for k in range(n):
            if k != i:
                deg = degree_of_possibility(S[i], S[k])
                min_deg = min(min_deg, deg)
        d.append(max(0.0, min_deg if min_deg != float("inf") else 0.0))

    # ── Step 5: Normalise ─────────────────────────────────────────────────────
    total_d = sum(d)
    if total_d < 1e-12:
        # All criteria indistinguishable → equal weights
        weights = [1.0 / n] * n
    else:
        weights = [di / total_d for di in d]

    return weights, S


# ── COA scoring ───────────────────────────────────────────────────────────────

def score_coas(
    coa_list: list[dict],
    weights: list[float],
    dimension_labels: list[str],
) -> list[dict]:
    """
    Compute weighted scores for each COA and return ranked results.

    Args:
        coa_list         — list of dicts with 'name' and 'scores' keys
        weights          — list of dimension weights (sum = 1)
        dimension_labels — list of dimension names

    Returns a list of dicts sorted by weighted_score descending, with rank.
    """
    results = []
    for coa in coa_list:
        scores = coa["scores"]
        weighted_total = sum(w * s for w, s in zip(weights, scores))
        contributions  = {
            dim: round(w * s, 4)
            for dim, w, s in zip(dimension_labels, weights, scores)
        }
        results.append(
            {
                "name":                   coa["name"],
                "weighted_score":         round(weighted_total, 6),
                "dimension_contributions": contributions,
            }
        )

    results.sort(key=lambda x: x["weighted_score"], reverse=True)
    for rank, r in enumerate(results, start=1):
        r["rank"] = rank

    return results


# ── Sensitivity analysis ──────────────────────────────────────────────────────

def sensitivity_analysis(
    coa_list: list[dict],
    base_weights: list[float],
    dimension_labels: list[str],
    n_perturbations: int = 200,
    noise_sigma: float = 0.05,
    seed: int = 42,
) -> dict:
    """
    Perturb the FAHP weights with Gaussian noise and count how often the
    top-ranked COA changes. This tells commanders how sensitive the
    recommendation is to the pairwise comparison judgements.

    A recommendation is 'stable' if the top COA never changes across all
    perturbation scenarios.

    Args:
        base_weights    — crisp FAHP weights (n,)
        noise_sigma     — std deviation of Gaussian perturbation
        n_perturbations — number of Monte Carlo trials

    Returns a dict with stability statistics.
    """
    rng = random.Random(seed)
    n = len(base_weights)
    base_ranked = score_coas(coa_list, base_weights, dimension_labels)
    base_top    = base_ranked[0]["name"] if base_ranked else None
    rank_changes = 0

    for _ in range(n_perturbations):
        # Gaussian noise on weights, then re-normalise
        perturbed = [
            max(1e-6, w + rng.gauss(0.0, noise_sigma))
            for w in base_weights
        ]
        total = sum(perturbed)
        perturbed = [p / total for p in perturbed]

        ranked = score_coas(coa_list, perturbed, dimension_labels)
        if ranked and ranked[0]["name"] != base_top:
            rank_changes += 1

    return {
        "is_stable":                 rank_changes == 0,
        "n_perturbations_run":       n_perturbations,
        "n_rank_changes":            rank_changes,
        "recommended_coa_consistent": rank_changes == 0,
    }
