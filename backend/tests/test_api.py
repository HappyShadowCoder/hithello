"""
tests/test_api.py
------------------
Functional tests for the MOPT backend endpoints.
Run after starting the server with: uvicorn main:app --reload

Usage:
    python tests/test_api.py
"""

import json
import sys
import urllib.request
import urllib.error

BASE_URL = "http://localhost:8000"


def post(path: str, payload: dict) -> dict:
    data    = json.dumps(payload).encode()
    request = urllib.request.Request(
        f"{BASE_URL}{path}",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=10) as resp:
        return json.loads(resp.read())


def get(path: str) -> dict:
    with urllib.request.urlopen(f"{BASE_URL}{path}", timeout=10) as resp:
        return json.loads(resp.read())


def section(title: str) -> None:
    print(f"\n{'─' * 60}")
    print(f"  {title}")
    print(f"{'─' * 60}")


def run_tests() -> None:
    passed = 0
    failed = 0

    # ── 1. Health check ───────────────────────────────────────────────────────
    section("TEST 1 — Health Check")
    try:
        r = get("/health")
        assert r["status"] == "ok", f"Expected 'ok', got {r['status']}"
        print(f"  ✅ PASS  →  {r}")
        passed += 1
    except Exception as e:
        print(f"  ❌ FAIL  →  {e}")
        failed += 1

    # ── 2. Weapon list ────────────────────────────────────────────────────────
    section("TEST 2 — GET /weapons")
    try:
        r = get("/weapons")
        assert len(r["weapons"]) >= 5, "Expected at least 5 weapon types"
        print(f"  ✅ PASS  →  {len(r['weapons'])} weapons returned")
        for w in r["weapons"]:
            print(f"     • {w['id']:20s}  v₀={w['muzzle_velocity']} m/s  "
                  f"range={w['max_range_m']/1000:.1f} km")
        passed += 1
    except Exception as e:
        print(f"  ❌ FAIL  →  {e}")
        failed += 1

    # ── 3. Mortar trajectory — uphill target ──────────────────────────────────
    section("TEST 3 — /calculate_trajectory  (81mm mortar, uphill 15°, 2000 m)")
    payload = {
        "weapon_type":       "mortar_81mm",
        "elevation_m":       3500.0,
        "target_distance_m": 2000.0,
        "slope_angle_deg":   15.0,
    }
    try:
        r = post("/calculate_trajectory", payload)
        meta = r["metadata"]
        assert len(r["arc"]) == 120, f"Expected 120 arc points, got {len(r['arc'])}"
        assert meta["launch_angle_deg"] > 45, "Mortar should use high-angle solution"
        assert meta["in_range"] is True, "2000m should be in range for 81mm"
        print(f"  ✅ PASS")
        print(f"     Launch angle:     {meta['launch_angle_deg']:.1f}°")
        print(f"     Time of flight:   {meta['time_of_flight_s']:.2f} s")
        print(f"     Max height AGL:   {meta['max_height_agl_m']:.0f} m")
        print(f"     Max altitude ASL: {meta['max_altitude_asl_m']:.0f} m")
        print(f"     Impact speed:     {meta['impact_velocity_ms']:.0f} m/s")
        print(f"     Impact angle:     {meta['impact_angle_deg']:.1f}°")
        print(f"     In-range:         {meta['in_range']}")
        passed += 1
    except Exception as e:
        print(f"  ❌ FAIL  →  {e}")
        failed += 1

    # ── 4. Machine gun — flat terrain ─────────────────────────────────────────
    section("TEST 4 — /calculate_trajectory  (7.62mm MG, flat, 800 m)")
    payload = {
        "weapon_type":       "machine_gun_762",
        "elevation_m":       1200.0,
        "target_distance_m": 800.0,
        "slope_angle_deg":   0.0,
    }
    try:
        r = post("/calculate_trajectory", payload)
        meta = r["metadata"]
        assert meta["launch_angle_deg"] < 45, "MG should use low-angle solution"
        assert meta["in_range"] is True
        print(f"  ✅ PASS")
        print(f"     Launch angle:  {meta['launch_angle_deg']:.3f}°")
        print(f"     Time of flight: {meta['time_of_flight_s']:.3f} s")
        print(f"     Max height AGL: {meta['max_height_agl_m']:.1f} m")
        passed += 1
    except Exception as e:
        print(f"  ❌ FAIL  →  {e}")
        failed += 1

    # ── 5. Out-of-range error ─────────────────────────────────────────────────
    section("TEST 5 — /calculate_trajectory  (mortar, 20 km — out of range error)")
    payload = {
        "weapon_type":       "mortar_81mm",
        "elevation_m":       3500.0,
        "target_distance_m": 20_000.0,
        "slope_angle_deg":   0.0,
    }
    try:
        r = post("/calculate_trajectory", payload)
        print(f"  ❌ FAIL  →  Expected 400 error but got: {r}")
        failed += 1
    except urllib.error.HTTPError as e:
        if e.code == 400:
            body = json.loads(e.read())
            print(f"  ✅ PASS  →  Correctly returned HTTP 400: {body['detail'][:80]}")
            passed += 1
        else:
            print(f"  ❌ FAIL  →  Unexpected HTTP {e.code}")
            failed += 1
    except Exception as e:
        print(f"  ❌ FAIL  →  {e}")
        failed += 1

    # ── 6. FAHP — equal weights ────────────────────────────────────────────────
    section("TEST 6 — /coa_fahp  (equal weights, 2 COAs)")
    payload = {
        "coa_list": [
            {"name": "COA Alpha", "scores": [8, 6, 7, 9, 5, 4, 7, 3]},
            {"name": "COA Bravo", "scores": [6, 8, 5, 7, 8, 6, 5, 5]},
        ]
        # pairwise_matrix omitted → equal weights
    }
    try:
        r = post("/coa_fahp", payload)
        assert len(r["rankings"]) == 2
        assert r["rankings"][0]["rank"] == 1
        top = r["rankings"][0]
        print(f"  ✅ PASS")
        print(f"     Recommended COA: {r['recommended_coa']}")
        for row in r["rankings"]:
            print(f"     Rank {row['rank']}: {row['name']:15s}  "
                  f"score={row['weighted_score']:.4f}")
        print(f"     Stable ranking:  {r['sensitivity']['is_stable']}")
        passed += 1
    except Exception as e:
        print(f"  ❌ FAIL  →  {e}")
        failed += 1

    # ── 7. FAHP — custom pairwise weights ─────────────────────────────────────
    section("TEST 7 — /coa_fahp  (custom weights: Tactical Advantage strongly preferred)")
    # Dimension 0 (Tactical Advantage) is strongly preferred over all others
    matrix = [[[1, 1, 1]] * 8 for _ in range(8)]
    for j in range(1, 8):
        matrix[0][j] = [4, 5, 6]   # Tactical Advantage >> others
        matrix[j][0] = [1/6, 1/5, 1/4]  # reciprocal

    payload = {
        "coa_list": [
            {"name": "COA Alpha", "scores": [9, 5, 6, 7, 4, 3, 6, 2]},  # high tactical
            {"name": "COA Bravo", "scores": [4, 9, 8, 6, 9, 8, 7, 7]},  # high logistics
            {"name": "COA Charlie", "scores": [7, 7, 7, 7, 7, 7, 7, 4]},
        ],
        "pairwise_matrix": matrix,
    }
    try:
        r = post("/coa_fahp", payload)
        assert len(r["rankings"]) == 3
        print(f"  ✅ PASS")
        print(f"     Recommended COA: {r['recommended_coa']}")
        for row in r["rankings"]:
            print(f"     Rank {row['rank']}: {row['name']:15s}  "
                  f"score={row['weighted_score']:.4f}")
        print(f"     Dimension weights (top 3):")
        for d in sorted(r["dimensions"], key=lambda x: -x["weight"])[:3]:
            print(f"       {d['dimension']:25s}  w={d['weight']:.4f}")
        print(f"     Stable ranking:  {r['sensitivity']['is_stable']}")
        passed += 1
    except Exception as e:
        print(f"  ❌ FAIL  →  {e}")
        failed += 1

    # ── Summary ────────────────────────────────────────────────────────────────
    print(f"\n{'═' * 60}")
    print(f"  RESULTS:  {passed} passed  |  {failed} failed")
    print(f"{'═' * 60}\n")

    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    run_tests()
