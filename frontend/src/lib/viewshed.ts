/**
 * viewshed.ts
 * -----------
 * Client-side viewshed computation using the ArcGIS Maps SDK Ground.queryElevation API.
 *
 * Algorithm: "Maximum Elevation Angle" (horizon method)
 *   For each radial ray cast from the observer:
 *     - Sample terrain elevation at regular intervals along the ray
 *     - Track the running maximum elevation angle seen so far
 *     - A sample is VISIBLE if its elevation angle >= the running maximum
 *     - A sample is HIDDEN if the terrain angle drops below that maximum
 *       (meaning a ridge in between blocks line-of-sight)
 *
 * Why NOT Turf.js?
 *   Turf.js is a 2D spatial library — it has no concept of terrain height or
 *   line-of-sight occlusion. A proper viewshed must query real terrain
 *   elevations, which ArcGIS Ground.queryElevation() provides natively.
 *
 * Why NOT a GIS server?
 *   This runs entirely in the browser via batch queryElevation calls on the
 *   ArcGIS World Elevation service, requiring no backend infrastructure.
 */

import type Ground from '@arcgis/core/Ground';
import Point from '@arcgis/core/geometry/Point';
import Polygon from '@arcgis/core/geometry/Polygon';
import Multipoint from '@arcgis/core/geometry/Multipoint';

// ── Constants ────────────────────────────────────────────────────────────────
const EARTH_RADIUS_M = 6_371_000;

// ── Public types ─────────────────────────────────────────────────────────────

export interface ViewshedOptions {
  /** Height of the observer above the terrain surface in metres. Default: 2 */
  observerHeightM?: number;
  /** Maximum analysis range in metres. Default: 5000 */
  maxRangeM?: number;
  /** Number of radial rays to cast (angular resolution). Default: 72 (= 5° per ray) */
  rayCount?: number;
  /** Number of terrain samples per ray (range resolution). Default: 50 */
  samplesPerRay?: number;
}

export interface ViewshedResult {
  /** Polygon representing terrain visible from the observer — render GREEN */
  visible: Polygon;
  /**
   * Polygon covering the full analysis range circle.
   * Render this RED beneath the visible polygon:
   *   full-range (red) + visible fan (green) = clear visual separation.
   */
  fullRange: Polygon;
  /** Raw terrain elevation at the observer point (metres ASL) */
  observerTerrainElevation: number;
}

// ── Geometry helpers ─────────────────────────────────────────────────────────

/**
 * Compute the [longitude, latitude] of a point that is `distanceM` metres
 * away from (lat, lon) at `bearingDeg` degrees (0 = north, clockwise).
 * Uses the spherical-earth haversine formula.
 */
function destinationPoint(
  lat: number,
  lon: number,
  bearingDeg: number,
  distanceM: number,
): [number, number] {
  const φ1 = (lat * Math.PI) / 180;
  const λ1 = (lon * Math.PI) / 180;
  const θ  = (bearingDeg * Math.PI) / 180;
  const δ  = distanceM / EARTH_RADIUS_M;

  const φ2 = Math.asin(
    Math.sin(φ1) * Math.cos(δ) +
    Math.cos(φ1) * Math.sin(δ) * Math.cos(θ),
  );
  const λ2 =
    λ1 +
    Math.atan2(
      Math.sin(θ) * Math.sin(δ) * Math.cos(φ1),
      Math.cos(δ) - Math.sin(φ1) * Math.sin(φ2),
    );

  return [(λ2 * 180) / Math.PI, (φ2 * 180) / Math.PI];
}

/**
 * Build a regular polygon ring approximating a circle of `radiusM` metres
 * around (lat, lon).  Used for the full-range background polygon.
 */
function circleRing(lat: number, lon: number, radiusM: number, steps = 360): number[][] {
  const ring: number[][] = [];
  for (let i = 0; i <= steps; i++) {
    const [dLon, dLat] = destinationPoint(lat, lon, (i / steps) * 360, radiusM);
    ring.push([dLon, dLat]);
  }
  return ring;
}

// ── Main export ──────────────────────────────────────────────────────────────

/**
 * Compute a viewshed for a given observer point on the ArcGIS terrain.
 *
 * @param observer   - ArcGIS Point (must have latitude/longitude in WGS84)
 * @param ground     - The SceneView's `view.map.ground` object
 * @param opts       - Tunable parameters (see ViewshedOptions)
 * @returns          - Visible polygon, full-range polygon, observer elevation
 */
export async function computeViewshed(
  observer: Point,
  ground: Ground,
  opts: ViewshedOptions = {},
): Promise<ViewshedResult> {
  const {
    observerHeightM  = 2,
    maxRangeM        = 5_000,
    rayCount         = 72,
    samplesPerRay    = 50,
  } = opts;

  const stepM = maxRangeM / samplesPerRay;
  const lat   = observer.latitude!;
  const lon   = observer.longitude!;

  // ── Step 1: Query observer terrain elevation ─────────────────────────────
  const obsResult      = await ground.queryElevation(observer);
  const obsTerrainElev = (obsResult.geometry as Point).z ?? 0;
  const obsEyeElev     = obsTerrainElev + observerHeightM; // eye-level elevation

  // ── Step 2: Generate all sample points (rayCount × samplesPerRay) ────────
  // Laid out as: ray-0 samples, ray-1 samples, …, ray-N samples
  const sampleCoords: number[][] = [];

  for (let r = 0; r < rayCount; r++) {
    const bearing = (r / rayCount) * 360;
    for (let s = 1; s <= samplesPerRay; s++) {
      const [sLon, sLat] = destinationPoint(lat, lon, bearing, stepM * s);
      sampleCoords.push([sLon, sLat]);
    }
  }

  // ── Step 3: Batch elevation query (single network round-trip) ────────────
  const multiPt = new Multipoint({
    points: sampleCoords,
    spatialReference: { wkid: 4326 },
  });

  const elevResult   = await ground.queryElevation(multiPt);
  const elevatedMPt  = elevResult.geometry as Multipoint;

  // ── Step 4: Determine visibility per ray (horizon-angle algorithm) ────────
  //
  // For each sample along a ray (near → far):
  //   elevAngle = atan2(sampleElev - obsEyeElev, horizontalDistance)
  //
  //   If elevAngle >= maxElevAngle: VISIBLE → update max, record sample
  //   Otherwise:                   HIDDEN  (ridge in front blocks sight)
  //
  // `lastVisibleStep[r]` = the furthest VISIBLE sample index (1-based)
  const lastVisibleStep = new Array<number>(rayCount).fill(1);

  for (let r = 0; r < rayCount; r++) {
    let maxElevAngle = -Math.PI / 2; // start at -90° (looking down)

    for (let s = 0; s < samplesPerRay; s++) {
      const idx        = r * samplesPerRay + s;
      const pt         = elevatedMPt.points[idx];
      const sampleElev = (pt[2] ?? 0);
      const dist       = stepM * (s + 1);

      const elevAngle  = Math.atan2(sampleElev - obsEyeElev, dist);

      if (elevAngle >= maxElevAngle) {
        maxElevAngle         = elevAngle;
        lastVisibleStep[r]   = s + 1; // extend visible boundary for this ray
      }
    }
  }

  // ── Step 5: Build the visible polygon ────────────────────────────────────
  //
  // A "fan" polygon: observer at centre, each ray's tip at its last visible
  // sample distance.  Adjacent rays share edges → no gaps.
  const visibleRing: number[][] = [[lon, lat]]; // start at observer

  for (let r = 0; r <= rayCount; r++) {
    const ri      = r % rayCount;
    const bearing = (ri / rayCount) * 360;
    const visDist = stepM * lastVisibleStep[ri];
    const [vLon, vLat] = destinationPoint(lat, lon, bearing, visDist);
    visibleRing.push([vLon, vLat]);
  }

  visibleRing.push([lon, lat]); // close ring back to observer

  const visiblePolygon = new Polygon({
    rings: [visibleRing],
    spatialReference: { wkid: 4326 },
  });

  // ── Step 6: Build full-range circle polygon ───────────────────────────────
  //
  // This is the red "analysis area" disc.  Rendering order:
  //   1. Draw fullRange (RED)  → everything is assumed hidden
  //   2. Draw visible   (GREEN) → overdraws the actually-visible portion
  //
  // Net result: red = hidden, green = visible — exactly as required.
  const fullRangePolygon = new Polygon({
    rings: [circleRing(lat, lon, maxRangeM)],
    spatialReference: { wkid: 4326 },
  });

  return {
    visible: visiblePolygon,
    fullRange: fullRangePolygon,
    observerTerrainElevation: obsTerrainElev,
  };
}
