"""
services/trajectory.py
----------------------
Ballistic trajectory mathematics for MOPT.

Model: Point-mass projectile under constant gravity (no air resistance).
This is the standard "vacuum ballistics" model used for quick operational
estimates. Real-world corrections (drag, spin, Coriolis) would be added in
Phase 4.

Physics:
    x(t) = v₀ · cos(θ) · t
    y(t) = h₀ + v₀ · sin(θ) · t − ½ · g · t²

    where θ = launch angle above horizontal, v₀ = muzzle velocity, h₀ = 0 (rel.)

Slope correction:
    The target may sit higher (uphill) or lower (downhill) than the firing point.
    Height difference: Δh = R · tan(α)   where R = horizontal range, α = slope angle.
    We solve for the launch angle θ that achieves (x=R, y=Δh) simultaneously.

    Substituting T = R / (v₀·cos(θ)):
        Δh = R·tan(θ) − g·R²·sec²(θ) / (2·v₀²)

    Let t = tan(θ), sec²(θ) = 1 + t²:
        a·t² − R·t + c = 0
        where a = g·R² / (2·v₀²),  c = Δh + g·R² / (2·v₀²)

    Two real solutions ⇒ low-angle (direct fire) and high-angle (plunging fire).
    Negative discriminant ⇒ target is out of range.
"""

from math import sqrt, radians, degrees, cos, sin, tan, atan2, pi, isfinite
import numpy as np

# ── Constants ────────────────────────────────────────────────────────────────
G = 9.81  # gravitational acceleration (m/s²)
NUM_ARC_POINTS = 120  # resolution of the returned arc

# ── Weapon registry ───────────────────────────────────────────────────────────
WEAPON_PROFILES: dict[str, dict] = {
    "machine_gun_762": {
        "name": "Machine Gun (7.62 mm)",
        "muzzle_velocity": 855.0,   # m/s
        "fire_mode": "direct",      # low-angle solution preferred
        "max_range_m": 1_800.0,
        "min_range_m": 0.0,
        "description": "Standard infantry machine gun — direct fire, flat trajectory.",
    },
    "hmg_127": {
        "name": "Heavy Machine Gun (12.7 mm)",
        "muzzle_velocity": 900.0,
        "fire_mode": "direct",
        "max_range_m": 2_000.0,
        "min_range_m": 0.0,
        "description": "Heavy machine gun — direct fire, long-range suppression.",
    },
    "mortar_81mm": {
        "name": "Mortar (81 mm)",
        "muzzle_velocity": 290.0,   # charge 4 / maximum propellant
        "fire_mode": "indirect",    # high-angle (plunging) solution preferred
        "max_range_m": 5_650.0,
        "min_range_m": 100.0,
        "description": "Infantry mortar — indirect plunging fire, useful in dead ground.",
    },
    "mortar_120mm": {
        "name": "Mortar (120 mm)",
        "muzzle_velocity": 380.0,
        "fire_mode": "indirect",
        "max_range_m": 7_240.0,
        "min_range_m": 200.0,
        "description": "Heavy mortar — indirect fire, greater destructive effect.",
    },
    "artillery_105mm": {
        "name": "Artillery (105 mm)",
        "muzzle_velocity": 700.0,
        "fire_mode": "indirect",
        "max_range_m": 14_000.0,
        "min_range_m": 500.0,
        "description": "Light field artillery — indirect fire, high velocity.",
    },
}


def get_weapon_list() -> list[dict]:
    """Return available weapon profiles (for UI dropdowns)."""
    return [
        {"id": k, **{kk: vv for kk, vv in v.items()}}
        for k, v in WEAPON_PROFILES.items()
    ]


def _solve_launch_angle(v0: float, R: float, delta_h: float, mode: str) -> float:
    """
    Solve for the launch angle θ (radians) that sends a projectile with
    muzzle velocity v0 to horizontal range R with height difference delta_h.

    mode: 'direct'   → low-angle solution (flatter, faster)
          'indirect' → high-angle solution (plunging / lofted arc)

    Raises ValueError if the target is beyond the weapon's kinematic range.
    """
    if R <= 0:
        raise ValueError("Target distance must be positive.")

    # Quadratic coefficients in tan(θ)
    a = G * R ** 2 / (2 * v0 ** 2)
    b = -R
    c = delta_h + G * R ** 2 / (2 * v0 ** 2)

    discriminant = b ** 2 - 4 * a * c

    if discriminant < 0:
        # Kinematically impossible — target is out of range
        raise ValueError(
            f"Target at {R:.0f} m (Δh = {delta_h:+.0f} m) is out of kinematic range "
            f"for v₀ = {v0:.0f} m/s. Max flat-ground range ≈ {v0**2/G:.0f} m."
        )

    sqrt_disc = sqrt(discriminant)
    tan_low  = (-b - sqrt_disc) / (2 * a)   # low-angle (direct fire)
    tan_high = (-b + sqrt_disc) / (2 * a)   # high-angle (plunging / indirect)

    # Guard against extreme angles that are physically unrealisable
    if mode == "direct":
        theta = atan2(tan_low, 1)
    else:
        theta = atan2(tan_high, 1)

    if not isfinite(theta):
        raise ValueError("Could not determine a valid launch angle for the given parameters.")

    return theta


def compute_trajectory(
    weapon_type: str,
    elevation_m: float,
    target_distance_m: float,
    slope_angle_deg: float = 0.0,
    launch_angle_deg: float | None = None,
) -> dict:
    """
    Compute a ballistic trajectory.

    Args:
        weapon_type        — key from WEAPON_PROFILES
        elevation_m        — firing position altitude (m ASL)
        target_distance_m  — horizontal distance to target (m)
        slope_angle_deg    — terrain slope (+ve = uphill, -ve = downhill)
        launch_angle_deg   — override angle (deg); computed if None

    Returns a dict with keys 'arc' (list of ArcPoint dicts) and 'metadata'.
    """
    profile = WEAPON_PROFILES.get(weapon_type)
    if not profile:
        raise ValueError(
            f"Unknown weapon type '{weapon_type}'. "
            f"Valid options: {list(WEAPON_PROFILES.keys())}"
        )

    v0    = profile["muzzle_velocity"]
    R     = target_distance_m
    alpha = radians(slope_angle_deg)

    # Height difference between firing point and target due to slope
    delta_h = R * tan(alpha)

    # ── Determine launch angle ────────────────────────────────────────────────
    if launch_angle_deg is not None:
        theta = radians(launch_angle_deg)
    else:
        theta = _solve_launch_angle(v0, R, delta_h, profile["fire_mode"])

    # ── Kinematic quantities ──────────────────────────────────────────────────
    vx = v0 * cos(theta)
    vy = v0 * sin(theta)

    # Time of flight: when x(t) = R
    t_flight = R / vx

    # ── Generate arc ──────────────────────────────────────────────────────────
    times = np.linspace(0.0, t_flight, NUM_ARC_POINTS)
    x_vals = vx * times
    y_rel  = vy * times - 0.5 * G * times ** 2   # metres above firing point
    alt_asl = elevation_m + y_rel                 # absolute altitude

    arc = [
        {
            "time_s":      float(t),
            "x_m":         float(x),
            "altitude_m":  float(a),
        }
        for t, x, a in zip(times, x_vals, alt_asl)
    ]

    # ── Peak altitude ─────────────────────────────────────────────────────────
    # dy/dt = vy − g·t = 0  →  t_apex = vy / g
    t_apex           = vy / G
    max_height_agl_m = float(vy * t_apex - 0.5 * G * t_apex ** 2) if t_apex > 0 else 0.0

    # ── Impact velocity & angle ───────────────────────────────────────────────
    impact_vy        = vy - G * t_flight
    impact_speed     = float(sqrt(vx ** 2 + impact_vy ** 2))
    impact_angle_deg = float(degrees(atan2(abs(impact_vy), vx)))

    # ── In-range check (operational, not kinematic) ───────────────────────────
    in_range = (
        profile["min_range_m"] <= R <= profile["max_range_m"]
    )

    return {
        "arc": arc,
        "metadata": {
            "weapon_name":          profile["name"],
            "launch_angle_deg":     float(degrees(theta)),
            "time_of_flight_s":     float(t_flight),
            "max_height_agl_m":     max_height_agl_m,
            "max_altitude_asl_m":   float(elevation_m + max_height_agl_m),
            "target_height_diff_m": float(delta_h),
            "impact_velocity_ms":   impact_speed,
            "impact_angle_deg":     impact_angle_deg,
            "effective_range_m":    float(R),
            "in_range":             in_range,
        },
    }
