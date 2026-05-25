"""
main.py — MOPT FastAPI Backend
================================
Serves the math-heavy geospatial and analytical endpoints for the
Mountain Operations Planning Tool.

Run locally:
    uvicorn main:app --reload --port 8000

Interactive API docs (Swagger):
    http://localhost:8000/docs

ReDoc:
    http://localhost:8000/redoc
"""

import json
import asyncio
from typing import Dict

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from models.trajectory import TrajectoryRequest, TrajectoryResponse
from models.coa import FAHPRequest, FAHPResponse, DIMENSION_LABELS, DEFAULT_PAIRWISE
from models.unit import Unit, PlaceUnitRequest, RemoveUnitRequest, SetWeatherRequest
from services.trajectory import compute_trajectory, get_weapon_list
from services.fahp import compute_fahp_weights, score_coas, sensitivity_analysis
from models.adjudicator import EngagementRequest, EngagementResponse
from services.adjudicator import Adjudicator
from routers import auth_router, syscon_router, plans_router
from services.auth import decode_access_token

adjudicator_svc = Adjudicator()

# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="MOPT Backend API",
    description=(
        "Mountain Operations Planning Tool — Backend Math Engine.\n\n"
        "Provides endpoints for ballistic trajectory computation, "
        "Fuzzy AHP Course of Action analysis, and real-time multi-role "
        "game-state synchronisation via WebSocket."
    ),
    version="0.3.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS — allow SvelteKit dev server ─────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1):\d+",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router.router)
app.include_router(syscon_router.router, prefix="/api")
app.include_router(plans_router.router)



# ── Phase 5: WebSocket connection manager ─────────────────────────────────────

class ConnectionManager:
    """
    Manages active WebSocket connections keyed by socket object.
    Records the role and username of each connected client.
    """

    def __init__(self) -> None:
        # socket → dict (role, username, team_id, team_color)
        self._connections: Dict[WebSocket, dict] = {}

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self._connections[ws] = {"role": "unknown", "username": "unknown"}

    def set_user_info(self, ws: WebSocket, info: dict) -> None:
        self._connections[ws] = info

    def disconnect(self, ws: WebSocket) -> None:
        self._connections.pop(ws, None)

    async def broadcast(self, message: dict) -> None:
        """Send a JSON message to every connected client."""
        payload = json.dumps(message)
        dead: list[WebSocket] = []
        for ws in list(self._connections.keys()):
            try:
                await ws.send_text(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)

    @property
    def connection_count(self) -> int:
        return len(self._connections)


manager = ConnectionManager()

# ── Phase 5: In-memory unit store ─────────────────────────────────────────────
# unit_id → Unit  (cleared on server restart; PostGIS persistence is Phase 6+)
units: Dict[str, Unit] = {}
global_weather: str = "Clear"


# ── Health check ──────────────────────────────────────────────────────────────
@app.get("/health", tags=["Utility"])
def health_check():
    """Confirm the API is running and return version info."""
    return {
        "status":      "ok",
        "version":     "0.3.0",
        "service":     "MOPT Backend",
        "connections": manager.connection_count,
        "units":       len(units),
    }


# ── Weapon list ───────────────────────────────────────────────────────────────
@app.get("/weapons", tags=["Trajectory"])
def list_weapons():
    """Return all registered weapon profiles for use in UI dropdowns."""
    return {"weapons": get_weapon_list()}


# ── Trajectory endpoint ───────────────────────────────────────────────────────
@app.post("/calculate_trajectory", response_model=TrajectoryResponse, tags=["Trajectory"])
def calculate_trajectory(req: TrajectoryRequest):
    """
    Compute the parabolic ballistic arc for a given weapon, firing position,
    and target geometry.

    **Physics model**: Point-mass projectile, constant gravity (9.81 m/s²),
    no air resistance. Slope correction via height-difference Δh = R·tan(α).

    The launch angle is solved analytically from the quadratic:

        (g·R² / 2v₀²) · tan²(θ) − R · tan(θ) + (Δh + g·R² / 2v₀²) = 0

    - **Direct fire** weapons (MG, HMG) use the **low-angle** solution.
    - **Indirect fire** weapons (mortars, artillery) use the **high-angle**
      (plunging) solution.
    """
    try:
        result = compute_trajectory(
            weapon_type=req.weapon_type,
            elevation_m=req.elevation_m,
            target_distance_m=req.target_distance_m,
            slope_angle_deg=req.slope_angle_deg,
            launch_angle_deg=req.launch_angle_deg,
        )
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Internal error: {exc}") from exc


# ── FAHP / COA endpoint ───────────────────────────────────────────────────────
@app.post("/coa_fahp", response_model=FAHPResponse, tags=["COA Analysis"])
def coa_fahp(req: FAHPRequest):
    """
    Compare ≥ 2 Courses of Action using the **Fuzzy Analytic Hierarchy Process
    (FAHP)** across 8 military dimensions:

    1. Tactical Advantage  2. Logistic Feasibility  3. Force Protection
    4. Speed of Action     5. Terrain Exploitation  6. Deception Potential
    7. Flexibility         8. Risk Level

    **Method**: Chang (1996) extent analysis on Triangular Fuzzy Numbers (TFNs).

    If `pairwise_matrix` is omitted, equal weights are assumed (all TFNs = (1,1,1)).

    **Sensitivity analysis**: 200 Monte Carlo weight-perturbation trials are
    run to report whether the top-ranked COA is stable under uncertainty.
    """
    try:
        n = 8
        raw_matrix = req.pairwise_matrix or DEFAULT_PAIRWISE

        if len(raw_matrix) != n or any(len(row) != n for row in raw_matrix):
            raise ValueError(
                f"pairwise_matrix must be {n}×{n}. "
                f"Got {len(raw_matrix)}×{len(raw_matrix[0]) if raw_matrix else '?'}."
            )

        # ── 1. Compute FAHP weights ─────────────────────────────────────────
        weights, synthetic_extents = compute_fahp_weights(raw_matrix, n)

        # ── 2. Build dimension weight objects ───────────────────────────────
        dimensions = [
            {
                "dimension": label,
                "weight":    round(w, 6),
                "fuzzy_synthetic_extent": list(se),
            }
            for label, w, se in zip(DIMENSION_LABELS, weights, synthetic_extents)
        ]

        # ── 3. Score and rank COAs ──────────────────────────────────────────
        coa_dicts = [c.model_dump() for c in req.coa_list]
        rankings  = score_coas(coa_dicts, weights, DIMENSION_LABELS)

        recommended = rankings[0]["name"] if rankings else "N/A"

        # ── 4. Sensitivity analysis ─────────────────────────────────────────
        sensitivity = sensitivity_analysis(
            coa_list=coa_dicts,
            base_weights=weights,
            dimension_labels=DIMENSION_LABELS,
        )

        return {
            "dimensions":     dimensions,
            "rankings":       rankings,
            "recommended_coa": recommended,
            "sensitivity":    sensitivity,
        }

    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Internal error: {exc}") from exc


# ── Phase 6: Combat Adjudication ──────────────────────────────────────────────
@app.post("/adjudicate_engagement", response_model=EngagementResponse, tags=["Combat Adjudication"])
def adjudicate_engagement(req: EngagementRequest):
    """
    Resolve a combat engagement between two units.
    Calculates casualties and morale drops based on:
    - Numerical strength
    - Weapon Lethality Index (WLI)
    - Terrain multipliers
    - Weather penalties
    """
    try:
        result = adjudicator_svc.resolve_engagement(
            attacker=req.attacker.model_dump(),
            defender=req.defender.model_dump(),
            environment=req.environment.model_dump()
        )
        return result
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Internal error: {exc}") from exc


# ── Phase 5: Place unit (EXCON REST trigger) ──────────────────────────────────
@app.post("/place_unit", tags=["Game State"])
async def place_unit(req: PlaceUnitRequest):
    """
    Place a tactical unit on the map and broadcast it to all WebSocket clients.
    """
    unit = Unit(team=req.team, team_color=req.team_color, lon=req.lon, lat=req.lat, label=req.label)
    units[unit.id] = unit
    await manager.broadcast({
        "type": "unit_placed",
        "unit": unit.model_dump(),
    })
    return {"status": "placed", "unit": unit.model_dump()}


# ── Phase 5: Remove unit (EXCON REST trigger) ─────────────────────────────────
@app.post("/remove_unit", tags=["Game State"])
async def remove_unit(req: RemoveUnitRequest):
    """Remove a unit by ID and broadcast the removal to all clients."""
    if req.id not in units:
        raise HTTPException(status_code=404, detail=f"Unit '{req.id}' not found.")
    del units[req.id]
    await manager.broadcast({
        "type": "unit_removed",
        "id":   req.id,
    })
    return {"status": "removed", "id": req.id}


# ── Phase 7: Set Global Weather (EXCON REST trigger) ──────────────────────────
@app.post("/set_weather", tags=["Game State"])
async def set_weather(req: SetWeatherRequest):
    global global_weather
    if req.weather not in ["Clear", "Rain", "Snow", "Fog"]:
        raise HTTPException(status_code=400, detail="Invalid weather state")
    
    global_weather = req.weather
    await manager.broadcast({
        "type": "weather_changed",
        "weather": global_weather,
    })
    return {"status": "success", "weather": global_weather}


# ── Phase 5: List current units ───────────────────────────────────────────────
@app.get("/units", tags=["Game State"])
def list_units():
    """Return all currently placed units (used for state snapshot on reconnect)."""
    return {"units": [u.model_dump() for u in units.values()]}


# ── Phase 5: WebSocket endpoint ───────────────────────────────────────────────
@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    """
    WebSocket endpoint for real-time game state synchronisation.

    **Protocol**:
    - Client connects and immediately sends: `{ "type": "join", "role": "excon"|"blue"|"red" }`
    - Server responds with a state snapshot: `{ "type": "state_snapshot", "units": [...] }`
    - Server broadcasts `unit_placed` / `unit_removed` events to all connected clients
    - Client may send `{ "type": "ping" }` for keep-alive; server replies `{ "type": "pong" }`
    """
    await manager.connect(ws)
    try:
        while True:
            raw = await ws.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await ws.send_text(json.dumps({"type": "error", "detail": "Invalid JSON"}))
                continue

            msg_type = msg.get("type")

            if msg_type == "join":
                token = msg.get("token")
                if not token:
                    await ws.send_text(json.dumps({
                        "type":   "error",
                        "detail": "Missing token.",
                    }))
                    continue
                
                payload = decode_access_token(token)
                if not payload:
                    await ws.send_text(json.dumps({
                        "type":   "error",
                        "detail": "Invalid token.",
                    }))
                    continue
                    
                role = payload.get("role", "unknown")
                username = payload.get("sub", "unknown")
                
                # We optionally could load the team details from DB here
                # but to avoid DB calls in WS loop, we can just rely on the token info
                # or frontend can pass team info in the join message.
                # Let's just trust the token for role.
                manager.set_user_info(ws, {"role": role, "username": username})
                
                # Send current state snapshot to the newly joined client
                await ws.send_text(json.dumps({
                    "type":    "state_snapshot",
                    "role":    role,
                    "weather": global_weather,
                    "units":   [u.model_dump() for u in units.values()],
                }))

            elif msg_type == "ping":
                await ws.send_text(json.dumps({"type": "pong"}))

            else:
                await ws.send_text(json.dumps({
                    "type":   "error",
                    "detail": f"Unknown message type '{msg_type}'.",
                }))

    except WebSocketDisconnect:
        manager.disconnect(ws)
