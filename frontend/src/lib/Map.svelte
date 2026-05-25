<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { dndzone } from 'svelte-dnd-action';

  // ── ArcGIS Maps SDK imports ───────────────────────────────────────────────
  import WebScene       from '@arcgis/core/WebScene';
  import SceneView      from '@arcgis/core/views/SceneView';
  import Basemap        from '@arcgis/core/Basemap';
  import TileLayer      from '@arcgis/core/layers/TileLayer';
  import GraphicsLayer  from '@arcgis/core/layers/GraphicsLayer';
  import FeatureLayer   from '@arcgis/core/layers/FeatureLayer';
  import GeoJSONLayer   from '@arcgis/core/layers/GeoJSONLayer';
  import Graphic        from '@arcgis/core/Graphic';
  import SimpleFillSymbol   from '@arcgis/core/symbols/SimpleFillSymbol';
  import SimpleLineSymbol   from '@arcgis/core/symbols/SimpleLineSymbol';
  import SimpleMarkerSymbol from '@arcgis/core/symbols/SimpleMarkerSymbol';
  import TextSymbol     from '@arcgis/core/symbols/TextSymbol';
  import Point          from '@arcgis/core/geometry/Point';
  import Polygon        from '@arcgis/core/geometry/Polygon';
  import Polyline       from '@arcgis/core/geometry/Polyline';
  import Color          from '@arcgis/core/Color';
  import * as geometryEngine from '@arcgis/core/geometry/geometryEngine';
  import * as reactiveUtils  from '@arcgis/core/core/reactiveUtils';
  import VectorTileLayer from '@arcgis/core/layers/VectorTileLayer';

  // ── Auth, Game State, Exercise State ──────────────────────────────────────
  import { auth, ROLE_LABELS, ROLE_COLOURS } from './auth';
  import { gameState } from './gameState';
  import { exerciseStore } from './exerciseStore';
  import type { Unit } from './gameState';
  import { computeViewshed } from './viewshed';
  import '@arcgis/core/assets/esri/themes/dark/main.css';

  let container: HTMLDivElement;
  let view: SceneView | null = null;
  let isReady = false;
  let isComputing = false;
  let hasViewshed = false;
  let errorMsg = '';

  let observerHeightM = 2;
  let maxRangeM = 5000;
  let obsTerrainElev = 0;
  let lastClickLon = 0;
  let lastClickLat = 0;

  $: role = $auth.role;

  let exconMode: string = 'viewshed';
  let placingError = '';
  
  let activeTeams: any[] = [];
  let allTeams: any[] = [];
  
  async function fetchActiveTeams() {
    try {
      const res = await fetch('http://localhost:8000/api/active_teams', {
        headers: { 'Authorization': `Bearer ${$auth.token}` }
      });
      const data = await res.json();
      const resTeams = await fetch('http://localhost:8000/api/teams', {
        headers: { 'Authorization': `Bearer ${$auth.token}` }
      });
      allTeams = await resTeams.json();
      activeTeams = allTeams.filter((t: any) => t.id === data.team_1_id || t.id === data.team_2_id);
    } catch(e) {}
  }

  let fofOrigin: Point | null = null;
  let trajOrigin: Point | null = null;
  let satelliteRAF: number | null = null;
  let satGraphic: Graphic | null = null;

  let drawingDistanceM = 0;
  let drawingAreaSqM = 0;
  let showRedrawConfirm: 'blue' | 'red' | null = null;

  let visiblePolygon: Polygon | null = null;

  let viewshedLayer: GraphicsLayer;
  let markerLayer:   GraphicsLayer;
  let unitsLayer:    GraphicsLayer;
  let boundaryLayer: GraphicsLayer;
  let worldBoundaryLayerSolid: GeoJSONLayer;
  let worldBoundaryLayerDash: GeoJSONLayer;
  let roadsLayer: VectorTileLayer;
  let customIntlBoundaryLayer: GraphicsLayer;
  // ── Toolbox & View State ────────────────────────────────────────────────
  let showToolbox = false;
  let showIntlBoundaries = false;
  let lightingMode: 'auto' | 'day' | 'night' = 'auto';

  function cycleLighting() {
    if (lightingMode === 'auto') lightingMode = 'day';
    else if (lightingMode === 'day') lightingMode = 'night';
    else lightingMode = 'auto';
    
    if (view && view.environment) {
      if (lightingMode === 'auto') {
        view.environment.lighting = { type: 'sun', date: new Date(), directShadowsEnabled: true } as any;
      } else if (lightingMode === 'day') {
        const d = new Date(); d.setHours(12, 0, 0, 0); // Noon
        view.environment.lighting = { type: 'sun', date: d, directShadowsEnabled: true } as any;
      } else {
        const d = new Date(); d.setHours(0, 0, 0, 0); // Midnight
        view.environment.lighting = { type: 'sun', date: d, directShadowsEnabled: false } as any;
      }
    }
  }
  
  let locGraphic: Graphic;
  let lacGraphic: Graphic;
  let showLoc = true;
  let showLac = true;
  let showRoads = false;

  let cursorLon = '0.000000';
  let cursorLat = '0.000000';
  let cameraAlt = 0;

  $: if (worldBoundaryLayerSolid && worldBoundaryLayerDash && customIntlBoundaryLayer) {
    worldBoundaryLayerSolid.visible = showIntlBoundaries;
    worldBoundaryLayerDash.visible = showIntlBoundaries;
    customIntlBoundaryLayer.visible = showIntlBoundaries;
  }
  
  $: if (locGraphic) locGraphic.visible = showLoc;
  $: if (lacGraphic) lacGraphic.visible = showLac;
  $: if (roadsLayer) roadsLayer.visible = showRoads;

  // ── Interactive Drawing State ─────────────────────────────────────────────
  let boundaryPoints: Point[] = [];
  let redoStack: Point[] = [];
  let showCancelConfirm = false;
  let showSegmentDistances = true;

  $: if (!exconMode.startsWith('draw-')) {
    showCancelConfirm = false;
  }
  const drawPinSymbol = new SimpleMarkerSymbol({
    style: 'circle',
    color: new Color([245, 197, 24, 0.9]),
    size: 10,
    outline: { color: new Color([255, 255, 255, 0.9]), width: 1.5 }
  });

  function getBoundaryFill(team: 'blue' | 'red') {
    return new SimpleFillSymbol({
      color: new Color(team === 'blue' ? [40, 120, 255, 0.2] : [220, 50, 50, 0.2]),
      outline: {
        color: new Color(team === 'blue' ? [40, 120, 255, 0.8] : [220, 50, 50, 0.8]),
        width: 2,
        style: 'dash'
      }
    });
  }
  
  function getBoundaryLine(team: 'blue' | 'red') {
    return new SimpleLineSymbol({
      color: new Color(team === 'blue' ? [40, 120, 255, 0.8] : [220, 50, 50, 0.8]),
      width: 2,
      style: 'solid'
    });
  }

  function redrawBoundaryProgress() {
    if (!boundaryLayer) return;
    boundaryLayer.removeAll();

    if (setupBoundaryBlue) {
      const poly = Polygon.fromJSON(setupBoundaryBlue);
      boundaryLayer.add(new Graphic({ geometry: poly, symbol: getBoundaryFill('blue') }));
    }
    if (setupBoundaryRed) {
      const poly = Polygon.fromJSON(setupBoundaryRed);
      boundaryLayer.add(new Graphic({ geometry: poly, symbol: getBoundaryFill('red') }));
    }

    if (boundaryPoints.length === 0) return;

    for (const pt of boundaryPoints) {
      boundaryLayer.add(new Graphic({ geometry: pt, symbol: drawPinSymbol }));
    }

    drawingDistanceM = 0;
    drawingAreaSqM = 0;

    const team = exconMode === 'draw-blue' ? 'blue' : 'red';

    if (boundaryPoints.length >= 2) {
      const paths = boundaryPoints.map(p => [p.longitude as number, p.latitude as number]);
      if (boundaryPoints.length > 2) {
        paths.push([boundaryPoints[0].longitude as number, boundaryPoints[0].latitude as number]);
      }
      const line = new Polyline({ paths: [paths], spatialReference: { wkid: 4326 } });
      boundaryLayer.add(new Graphic({ geometry: line, symbol: getBoundaryLine(team) }));
      drawingDistanceM = geometryEngine.geodesicLength(line, "meters");

      if (showSegmentDistances) {
        for (let i = 0; i < paths.length - 1; i++) {
           const p1 = new Point({ longitude: paths[i][0], latitude: paths[i][1], spatialReference: { wkid: 4326 } });
           const p2 = new Point({ longitude: paths[i+1][0], latitude: paths[i+1][1], spatialReference: { wkid: 4326 } });
           
           const segLine = new Polyline({ paths: [[ [p1.longitude!, p1.latitude!], [p2.longitude!, p2.latitude!] ]], spatialReference: { wkid: 4326 } });
           const distStr = (geometryEngine.geodesicLength(segLine, "meters") / 1000).toFixed(2) + " km";
           
           const midLon = (p1.longitude! + p2.longitude!) / 2;
           const midLat = (p1.latitude! + p2.latitude!) / 2;
           const midPt = new Point({ longitude: midLon, latitude: midLat, spatialReference: { wkid: 4326 } });
           
           const textSym = new TextSymbol({
              text: distStr,
              color: new Color([255, 255, 255, 0.9]),
              haloColor: new Color([0, 0, 0, 0.8]),
              haloSize: 1.5,
              font: { size: 10, weight: 'bold', family: 'Inter, sans-serif' },
              yoffset: 10
           });
           boundaryLayer.add(new Graphic({ geometry: midPt, symbol: textSym }));
        }
      }
    }
    
    if (boundaryPoints.length >= 3) {
      const rings = boundaryPoints.map(p => [p.longitude as number, p.latitude as number]);
      rings.push([boundaryPoints[0].longitude as number, boundaryPoints[0].latitude as number]);
      const poly = new Polygon({ rings: [rings], spatialReference: { wkid: 4326 } });
      boundaryLayer.add(new Graphic({ geometry: poly, symbol: getBoundaryFill(team) }));
      drawingAreaSqM = geometryEngine.geodesicArea(poly, "square-meters");
    }
  }

  // ── Drawing Toolbox Actions ─────────────────────────────────────────────
  function drawingUndo() {
    if (boundaryPoints.length > 0) {
      const p = boundaryPoints.pop();
      if (p) redoStack.push(p);
      boundaryPoints = [...boundaryPoints];
      redoStack = [...redoStack];
      redrawBoundaryProgress();
    }
  }

  function drawingRedo() {
    if (redoStack.length > 0) {
      const p = redoStack.pop();
      if (p) boundaryPoints.push(p);
      boundaryPoints = [...boundaryPoints];
      redoStack = [...redoStack];
      redrawBoundaryProgress();
    }
  }

  function drawingReset() {
    if (confirm('Are you sure you want to remove all points for this boundary?')) {
      boundaryPoints = [];
      redoStack = [];
      redrawBoundaryProgress();
    }
  }

  function drawingFinish() {
    if (boundaryPoints.length >= 3) {
      const team = exconMode === 'draw-blue' ? 'blue' : 'red';
      const rings = boundaryPoints.map(p => [p.longitude as number, p.latitude as number]);
      rings.push([boundaryPoints[0].longitude as number, boundaryPoints[0].latitude as number]);
      const poly = new Polygon({ rings: [rings], spatialReference: { wkid: 4326 } });
      
      if (team === 'blue') setupBoundaryBlue = poly.toJSON();
      else setupBoundaryRed = poly.toJSON();
      
      boundaryPoints = [];
      redoStack = [];
      exconMode = 'viewshed';
      redrawBoundaryProgress();
    } else {
      alert('Need at least 3 points to complete a boundary area.');
    }
  }

  function drawingCancel() {
    boundaryPoints = [];
    redoStack = [];
    redrawBoundaryProgress();
    exconMode = 'viewshed'; // Reverts cursor and closes toolbox
  }

  // ── EXCON Overlay Dialog State ─────────────────────────────────────────────
  let showExerciseDialog = false;
  $: if (showExerciseDialog) {
    fetchPlans();
  }
  let setupMode: 'select' | 'create' = 'select';
  
  let setupExName = '';
  let setupPlanName = '';
  let setupPlanDesc = '';
  
  let savedPlans: any[] = [];
  let isFetchingPlans = false;
  let showPlanManager = false;
  const flipDurationMs = 200;

  async function fetchPlans() {
    isFetchingPlans = true;
    try {
      const res = await fetch('http://localhost:8000/api/plans', {
        headers: { 'Authorization': `Bearer ${$auth.token}` }
      });
      if (res.ok) savedPlans = await res.json();
    } catch (e) {
      console.error(e);
    } finally {
      isFetchingPlans = false;
    }
  }

  async function savePlan() {
    if (!setupPlanName) return;
    if (savedPlans.length >= 5) {
      setupError = "Maximum 5 plans allowed.";
      return;
    }
    try {
      const res = await fetch('http://localhost:8000/api/plans', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${$auth.token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ name: setupPlanName, description: setupPlanDesc })
      });
      if (res.ok) {
        const newPlan = await res.json();
        savedPlans = [...savedPlans, newPlan];
        setupError = '';
      } else {
        const err = await res.json();
        setupError = err.detail;
      }
    } catch (e) {
      console.error(e);
    }
  }

  async function deletePlan(id: number) {
    try {
      await fetch(`http://localhost:8000/api/plans/${id}`, {
        method: 'DELETE',
        headers: { 'Authorization': `Bearer ${$auth.token}` }
      });
      savedPlans = savedPlans.filter(p => p.id !== id);
    } catch (e) {
      console.error(e);
    }
  }

  function handleDndConsider(e: CustomEvent<any>) {
    savedPlans = e.detail.items;
  }

  async function handleDndFinalize(e: CustomEvent<any>) {
    savedPlans = e.detail.items;
    try {
      await fetch('http://localhost:8000/api/plans/reorder', {
        method: 'PUT',
        headers: {
          'Authorization': `Bearer ${$auth.token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ plan_ids: savedPlans.map(p => p.id) })
      });
    } catch (err) {
      console.error(err);
    }
  }

  function selectPlan(plan: any) {
    setupPlanName = plan.name;
    setupPlanDesc = plan.description;
    setupExName = plan.name;
  }
  let setupOrbatFile: File | null = null;
  let setupOrbatData: any = null;
  let setupError = '';
  let setupRegionId = 'loc';

  let setupBoundaryBlue: any | null = null;
  let setupBoundaryRed: any | null = null;

  const REGIONS = [
    { id: 'loc', label: 'LOC (Line of Control)', lon: 74.5, lat: 34.5, z: 12_000, heading: 0, tilt: 70 },
    { id: 'lac', label: 'LAC (Line of Actual Control)', lon: 78.5, lat: 34.5, z: 12_000, heading: 0, tilt: 70 },
  ];

  function handleFileUpload(e: Event) {
    const target = e.target as HTMLInputElement;
    if (target.files && target.files[0]) {
      setupOrbatFile = target.files[0];
      isCheckingOrbat = true;
      setupOrbatData = null;
      setupError = '';
      
      const reader = new FileReader();
      reader.onload = (ev) => {
        setTimeout(() => {
          try {
            setupOrbatData = JSON.parse(ev.target?.result as string);
            isCheckingOrbat = false;
          } catch {
            setupError = 'INVALID JSON FILE';
            setupOrbatData = null;
            isCheckingOrbat = false;
          }
        }, 1200);
      };
      reader.readAsText(setupOrbatFile);
    }
  }

  function goHome() {
    if (view) {
      view.goTo({
        target: new Point({ longitude: 79.0, latitude: 22.0, z: 7000000, spatialReference: { wkid: 4326 } }),
        tilt: 0,
        heading: 0
      }, { duration: 2500 }).catch(console.error);
    }
  }

  let setupTeam1: number | null = null;
  let setupTeam2: number | null = null;
  let isCheckingOrbat = false;

  $: team1Name = allTeams.find(t => t.id === setupTeam1)?.name || 'Team 1';
  $: team2Name = allTeams.find(t => t.id === setupTeam2)?.name || 'Team 2';

  async function submitInitialise() {
    if (setupMode === 'create') {
      if (!setupTeam1 || !setupTeam2) { setupError = 'SELECT TWO ACTIVE TEAMS'; return; }
      if (!setupBoundaryBlue || !setupBoundaryRed) { setupError = 'PLEASE DRAW BOTH OPERATIONAL BOUNDARIES'; return; }
      
      if (setupPlanName && !savedPlans.find(p => p.name === setupPlanName)) {
        await savePlan();
      }

      try {
        await fetch('http://localhost:8000/api/active_teams', {
          method: 'POST',
          headers: { 
             'Content-Type': 'application/json',
             'Authorization': `Bearer ${$auth.token}` 
          },
          body: JSON.stringify({ team_1_id: setupTeam1, team_2_id: setupTeam2 })
        });
        await fetchActiveTeams();
      } catch (e) {
        setupError = 'FAILED TO SET ACTIVE TEAMS';
        return;
      }
      
      exerciseStore.setExercise({
        name: setupExName,
        boundaries: { blue: setupBoundaryBlue, red: setupBoundaryRed },
        orbat: setupOrbatData
      });
    } else {
      exerciseStore.setExercise({
        name: 'MOCK EXERCISE: OP MOUNTAIN PEAK',
        boundaries: { blue: null, red: null },
        orbat: null
      });
    }
    
    showExerciseDialog = false;
    goHome();
  }

  function clearViewshed() {
    viewshedLayer?.removeAll();
    markerLayer?.removeAll();
    visiblePolygon = null;
    hasViewshed = false;
    errorMsg = '';
    renderUnits($gameState.units);
  }

  const hiddenSymbol = new SimpleFillSymbol({
    color: new Color([210, 40, 40, 0.28]),
    outline: { color: new Color([200, 40, 40, 0.45]), width: 1 },
  });
  const visibleSymbol = new SimpleFillSymbol({
    color: new Color([40, 200, 100, 0.38]),
    outline: { color: new Color([40, 210, 90, 0.6]),  width: 1 },
  });
  const observerSymbol = new SimpleMarkerSymbol({
    color: new Color([255, 230, 0, 1]), size: 14,
    outline: { color: new Color([255, 255, 255, 1]), width: 2 },
  });
  const targetSymbol = new SimpleMarkerSymbol({
    style: 'cross',
    color: new Color([255, 50, 50, 1]), size: 16,
    outline: { color: new Color([255, 50, 50, 1]), width: 3 },
  });
  const fofVisibleSymbol = new SimpleFillSymbol({
    color: new Color([255, 160, 20, 0.5]),
    outline: { color: new Color([255, 200, 50, 0.8]), width: 1.5 },
  });
  const trajSafeSymbol = new SimpleLineSymbol({
    color: new Color([50, 255, 100, 0.9]), width: 3, style: 'solid'
  });
  const trajBlockedSymbol = new SimpleLineSymbol({
    color: new Color([255, 50, 50, 0.9]), width: 3, style: 'dash'
  });

  function unitSymbol(team_color: string) {
    return new SimpleMarkerSymbol({
      style: 'square',
      color: new Color(team_color || '#ffffff'),
      size: 16,
      outline: { color: new Color([255, 255, 255, 0.9]), width: 1.5 },
    });
  }
  function unitLabelSymbol(label: string, team_color: string) {
    return new TextSymbol({
      text: label || '■',
      color: new Color([255, 255, 255, 0.95]),
      haloColor: new Color(team_color || '#ffffff'),
      haloSize: 1.5,
      font: { size: 9, weight: 'bold', family: 'Inter, sans-serif' },
      yoffset: 12,
    });
  }

  function createWedgePolygon(center: Point, target: Point, radiusM: number, fovDeg: number = 60) {
     const cLat = center.latitude!;
     const cLon = center.longitude!;
     const tLat = target.latitude!;
     const tLon = target.longitude!;

     const dy = tLat - cLat;
     const dx = tLon - cLon;
     let azimuth = Math.atan2(dx, dy) * 180 / Math.PI; 
     
     const rings = [[cLon, cLat]];
     const startAz = azimuth - fovDeg/2;
     const endAz = azimuth + fovDeg/2;
     
     const R = 6378137;
     const lat1 = cLat * Math.PI / 180;
     const lon1 = cLon * Math.PI / 180;
     
     for (let a = startAz; a <= endAz; a += 5) {
        const brng = a * Math.PI / 180;
        const lat2 = Math.asin( Math.sin(lat1)*Math.cos(radiusM/R) + Math.cos(lat1)*Math.sin(radiusM/R)*Math.cos(brng) );
        const lon2 = lon1 + Math.atan2(Math.sin(brng)*Math.sin(radiusM/R)*Math.cos(lat1), Math.cos(radiusM/R)-Math.sin(lat1)*Math.sin(lat2));
        rings.push([lon2 * 180 / Math.PI, lat2 * 180 / Math.PI]);
     }
     const brng = endAz * Math.PI / 180;
     const lat2 = Math.asin( Math.sin(lat1)*Math.cos(radiusM/R) + Math.cos(lat1)*Math.sin(radiusM/R)*Math.cos(brng) );
     const lon2 = lon1 + Math.atan2(Math.sin(brng)*Math.sin(radiusM/R)*Math.cos(lat1), Math.cos(radiusM/R)-Math.sin(lat1)*Math.sin(lat2));
     rings.push([lon2 * 180 / Math.PI, lat2 * 180 / Math.PI]);
     
     rings.push([cLon, cLat]);
     return new Polygon({ rings: [rings], spatialReference: { wkid: 4326 } });
  }

  async function executeFieldOfFire(origin: Point, target: Point) {
      if (isComputing || !view) return;
      isComputing = true;
      errorMsg = '';
      try {
        const result = await computeViewshed(origin, view.map!.ground, { observerHeightM, maxRangeM: effectiveRangeM });
        const wedge = createWedgePolygon(origin, target, effectiveRangeM);
        const visibleWedge = geometryEngine.intersect(result.visible, wedge);
        if (visibleWedge) {
            if (Array.isArray(visibleWedge)) {
                visibleWedge.forEach(w => viewshedLayer.add(new Graphic({ geometry: w as any, symbol: fofVisibleSymbol })));
            } else {
                viewshedLayer.add(new Graphic({ geometry: visibleWedge as any, symbol: fofVisibleSymbol }));
            }
        }
      } catch (err: unknown) {
        errorMsg = err instanceof Error ? err.message : 'FoF error';
      } finally {
        isComputing = false;
      }
  }

  async function executeTrajectory(origin: Point, target: Point) {
      if (isComputing || !view) return;
      isComputing = true;
      errorMsg = '';
      
      const oLon = origin.longitude!;
      const oLat = origin.latitude!;
      const tLon = target.longitude!;
      const tLat = target.latitude!;

      const polyline = new Polyline({
          paths: [[[oLon, oLat], [tLon, tLat]]],
          spatialReference: { wkid: 4326 }
      });
      const dist = geometryEngine.geodesicLength(polyline, "meters");
      
      try {
          const p1Res = await view.map!.ground.queryElevation(origin);
          const p2Res = await view.map!.ground.queryElevation(target);
          const elev1 = p1Res.geometry.z!;
          const elev2 = p2Res.geometry.z!;
          
          const slopeRad = Math.atan2(elev2 - elev1, dist);
          const slopeDeg = slopeRad * 180 / Math.PI;

          const req = await fetch('http://localhost:8000/calculate_trajectory', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({
                  weapon_type: 'mortar_81mm',
                  elevation_m: elev1,
                  target_distance_m: dist,
                  slope_angle_deg: slopeDeg
              })
          });
          if (!req.ok) {
              const errData = await req.json();
              throw new Error(errData.detail || "Trajectory calc failed");
          }
          const data = await req.json();
          const arcPoints = data.arc;
          
          const pathsSafe = [];
          const pathsBlocked = [];
          let hitTerrain = false;
          
          const tLon = target.longitude!;
          const tLat = target.latitude!;
          const oLon = origin.longitude!;
          const oLat = origin.latitude!;

          const dx = tLon - oLon;
          const dy = tLat - oLat;
          
          const pts3d = [];
          for (const ap of arcPoints) {
              const ratio = ap.x_m / dist;
              const lon = oLon + dx * ratio;
              const lat = oLat + dy * ratio;
              pts3d.push(new Point({ longitude: lon, latitude: lat, z: ap.altitude_m, spatialReference: { wkid: 4326 } }));
          }
          
          const elevRes = await view.map!.ground.queryElevation(new Polyline({ paths: [pts3d.map(p => [p.longitude!, p.latitude!])], spatialReference: { wkid: 4326 } }));
          
          for (let i = 0; i < pts3d.length; i++) {
              const pt = pts3d[i];
              const pZ = pt.z!;
              const terrainZ = elevRes.geometry.paths[0][i][2];
              if (pZ < terrainZ && i > 5 && i < pts3d.length - 5) {
                  hitTerrain = true;
              }
              if (!hitTerrain) {
                  pathsSafe.push([pt.longitude!, pt.latitude!, pZ]);
              } else {
                  pathsBlocked.push([pt.longitude!, pt.latitude!, pZ]);
              }
          }
          
          if (pathsSafe.length > 0) {
              viewshedLayer.add(new Graphic({ geometry: new Polyline({ paths: [pathsSafe], spatialReference: { wkid: 4326 } }), symbol: trajSafeSymbol }));
          }
          if (pathsBlocked.length > 0) {
              viewshedLayer.add(new Graphic({ geometry: new Polyline({ paths: [pathsBlocked], spatialReference: { wkid: 4326 } }), symbol: trajBlockedSymbol }));
          }
      } catch (err: unknown) {
          errorMsg = err instanceof Error ? err.message : 'Traj error';
      } finally {
          isComputing = false;
      }
  }

  function toggleSatellite() {
      if (satelliteRAF) {
          cancelAnimationFrame(satelliteRAF);
          satelliteRAF = null;
          if (satGraphic) viewshedLayer.remove(satGraphic);
          satGraphic = null;
          return;
      }
      const satSymbol = new SimpleFillSymbol({
         color: new Color([255, 50, 150, 0.2]),
         outline: { color: new Color([255, 50, 150, 0.8]), width: 2 }
      });
      satGraphic = new Graphic({ symbol: satSymbol });
      viewshedLayer.add(satGraphic);
      
      let t = 0;
      function animate() {
          t += 0.005;
          const lon = 75.0 + t * 5;
          const lat = 34.0 + Math.sin(t*2) * 1;
          const wedge = createWedgePolygon(new Point({longitude:lon, latitude:lat, spatialReference: { wkid: 4326 }}), new Point({longitude:lon+1, latitude:lat, spatialReference: { wkid: 4326 }}), 15000, 360);
          if (satGraphic) satGraphic.geometry = wedge;
          
          if (t < 20) {
              satelliteRAF = requestAnimationFrame(animate);
          } else {
              toggleSatellite();
          }
      }
      animate();
  }

  function isUnitVisible(unit: Unit): boolean {
    if (role === 'excon' || role === 'syscon') return true;
    const ownTeam = $auth.team_name?.toLowerCase() === 'blue' ? 'blue' : 'red';
    if (unit.team.toLowerCase() === ownTeam) return true;
    if (!visiblePolygon) return false;
    const pt = new Point({ longitude: unit.lon, latitude: unit.lat, spatialReference: { wkid: 4326 } });
    try { return geometryEngine.contains(visiblePolygon, pt); } catch { return false; }
  }

  function renderUnits(units: Unit[]) {
    if (!unitsLayer) return;
    unitsLayer.removeAll();
    for (const unit of units) {
      if (!isUnitVisible(unit)) continue;
      const pt = new Point({ longitude: unit.lon, latitude: unit.lat, spatialReference: { wkid: 4326 } });
      unitsLayer.add(new Graphic({ geometry: pt, symbol: unitSymbol(unit.team_color) }));
      if (unit.label) unitsLayer.add(new Graphic({ geometry: pt, symbol: unitLabelSymbol(unit.label, unit.team_color) }));
    }
  }

  const unsubscribeGS = gameState.subscribe(state => {
    if (unitsLayer) renderUnits(state.units);
  });
  
  const unsubscribeES = exerciseStore.subscribe(state => {
    if (state) {
      setupBoundaryBlue = state.boundaries.blue;
      setupBoundaryRed = state.boundaries.red;
    }
    if (boundaryLayer) redrawBoundaryProgress();
  });

  onMount(async () => {
    fetchActiveTeams();
    if (role === 'excon' && !$exerciseStore) {
      // showExerciseDialog = true;
    }

    const scene = new WebScene({ basemap: 'satellite', ground: 'world-elevation' });

    viewshedLayer = new GraphicsLayer({ elevationInfo: { mode: 'on-the-ground' } });
    boundaryLayer = new GraphicsLayer({ elevationInfo: { mode: 'on-the-ground' } });
    markerLayer   = new GraphicsLayer({ elevationInfo: { mode: 'relative-to-ground', offset: 5 } });
    unitsLayer    = new GraphicsLayer({ elevationInfo: { mode: 'relative-to-ground', offset: 8 } });
    
    // Survey of India Official Administrative Boundaries (Country Outline) via DataMeet GeoJSON
    // Solid Red base
    worldBoundaryLayerSolid = new GeoJSONLayer({
      url: 'https://raw.githubusercontent.com/datameet/maps/master/Country/india-composite.geojson',
      visible: showIntlBoundaries,
      renderer: {
        type: 'simple',
        symbol: new SimpleLineSymbol({
          color: new Color([255, 0, 0, 1.0]), // Red
          width: 3,
          style: 'solid'
        })
      } as any
    });

    // Dashed Blue overlay to create red/blue dash effect
    worldBoundaryLayerDash = new GeoJSONLayer({
      url: 'https://raw.githubusercontent.com/datameet/maps/master/Country/india-composite.geojson',
      visible: showIntlBoundaries,
      renderer: {
        type: 'simple',
        symbol: new SimpleLineSymbol({
          color: new Color([0, 100, 255, 1.0]), // Blue
          width: 3,
          style: 'dash'
        })
      } as any
    });

    roadsLayer = new VectorTileLayer({
      url: "/roads-style.json",
      visible: showRoads
    });

    // Custom LOC and LAC lines (Purple Dotted)
    customIntlBoundaryLayer = new GraphicsLayer({
      visible: showIntlBoundaries,
      elevationInfo: { mode: 'on-the-ground' }
    });

    const customBoundarySymbol = new SimpleLineSymbol({
      color: new Color([180, 50, 255, 0.9]), // purple line
      width: 4,
      style: 'short-dash-dot' // Dotted/Dashed appearance
    });

    locGraphic = new Graphic({
      geometry: new Polyline({
        paths: [[[74.0, 33.0], [74.5, 34.5], [75.0, 34.8], [76.0, 35.0], [77.0, 35.1]]],
        spatialReference: { wkid: 4326 }
      }),
      symbol: customBoundarySymbol
    });

    lacGraphic = new Graphic({
      geometry: new Polyline({
        paths: [[[77.8, 35.5], [78.1, 35.2], [78.3, 34.8], [78.8, 33.7], [79.2, 33.1], [79.4, 32.7]]],
        spatialReference: { wkid: 4326 }
      }),
      symbol: customBoundarySymbol
    });

    customIntlBoundaryLayer.addMany([locGraphic, lacGraphic]);
    
    scene.addMany([viewshedLayer, worldBoundaryLayerSolid, worldBoundaryLayerDash, customIntlBoundaryLayer, boundaryLayer, markerLayer, unitsLayer, roadsLayer]);

    view = new SceneView({
      container,
      map: scene,
      camera: { position: { longitude: 86.925, latitude: 25.5, z: 250_000 }, tilt: 60, heading: 5 },
      environment: { lighting: { date: new Date(), directShadowsEnabled: true } },
      ui: { components: [] },
    });
    view.ui.remove("attribution");

    view.on('pointer-down', (event) => {
      if (event.button === 2 && (exconMode === 'draw-blue' || exconMode === 'draw-red')) {
        event.stopPropagation();
        drawingUndo();
      }
    });

    view.on('double-click', (event) => {
      if (exconMode === 'draw-blue' || exconMode === 'draw-red') {
        event.stopPropagation();
        drawingFinish();
      }
    });

    view.on('pointer-move', (event) => {
      if (!view) return;
      const mapPoint = view.toMap(event);
      if (mapPoint && mapPoint.longitude != null && mapPoint.latitude != null) {
        cursorLon = mapPoint.longitude.toFixed(6);
        cursorLat = mapPoint.latitude.toFixed(6);
      }
    });

    reactiveUtils.watch(
      () => view?.camera?.position?.z,
      (z) => {
        if (z !== undefined) cameraAlt = Math.round(z);
      }
    );

    await view.when();
    isReady = true;
    goHome();
    
    renderUnits($gameState.units);
    redrawBoundaryProgress();

    view.on('click', async (event) => {
      const pt = event.mapPoint;
      if (!pt || !view || !view.map || !view.map.ground) return;

      if (exconMode === 'draw-blue' || exconMode === 'draw-red') {
        boundaryPoints = [...boundaryPoints, pt];
        redoStack = [];
        redrawBoundaryProgress();
        return;
      }

      if (role === 'excon' && exconMode.startsWith('place-')) {
        const teamName = exconMode.split('place-')[1];
        const team = activeTeams.find(t => t.name === teamName);
        if (!team) return;
        placingError = '';
        try {
          await gameState.placeUnit(team.name, team.color, pt.longitude!, pt.latitude!);
        } catch (err) {
          placingError = err instanceof Error ? err.message : 'Failed to place unit';
        }
        return;
      }

      if (exconMode === 'fof') {
        if (!fofOrigin) {
           fofOrigin = pt;
           viewshedLayer.removeAll(); markerLayer.removeAll();
           markerLayer.add(new Graphic({ geometry: pt, symbol: observerSymbol }));
        } else {
           const target = pt;
           markerLayer.add(new Graphic({ geometry: pt, symbol: targetSymbol }));
           await executeFieldOfFire(fofOrigin, target);
           fofOrigin = null;
        }
        return;
      }

      if (exconMode === 'trajectory') {
        if (!trajOrigin) {
           trajOrigin = pt;
           viewshedLayer.removeAll(); markerLayer.removeAll();
           markerLayer.add(new Graphic({ geometry: pt, symbol: observerSymbol }));
        } else {
           const target = pt;
           markerLayer.add(new Graphic({ geometry: pt, symbol: targetSymbol }));
           await executeTrajectory(trajOrigin, target);
           trajOrigin = null;
        }
        return;
      }

      if (isComputing) return;

      errorMsg = '';
      hasViewshed = false;
      isComputing = true;
      viewshedLayer.removeAll();
      markerLayer.removeAll();

      lastClickLon = pt.longitude!;
      lastClickLat = pt.latitude!;
      markerLayer.add(new Graphic({ geometry: pt, symbol: observerSymbol }));

      try {
        const result = await computeViewshed(pt, view.map.ground, { observerHeightM, maxRangeM: effectiveRangeM });
        viewshedLayer.add(new Graphic({ geometry: result.fullRange, symbol: hiddenSymbol }));
        viewshedLayer.add(new Graphic({ geometry: result.visible,   symbol: visibleSymbol }));
        obsTerrainElev = result.observerTerrainElevation;
        visiblePolygon = result.visible;
        hasViewshed = true;
        renderUnits($gameState.units);
      } catch (err: unknown) {
        errorMsg = err instanceof Error ? err.message : 'Unknown error';
        markerLayer.removeAll();
        visiblePolygon = null;
      } finally {
        isComputing = false;
      }
    });
  });

  onDestroy(() => {
    unsubscribeGS();
    unsubscribeES();
    view?.destroy();
    view = null;
  });

  $: weatherMultiplier = $gameState.weather === 'Clear' ? 1.0 :
                         $gameState.weather === 'Rain' ? 0.7 :
                         $gameState.weather === 'Snow' ? 0.5 :
                         $gameState.weather === 'Fog' ? 0.3 : 1.0;

  $: effectiveRangeM = maxRangeM * weatherMultiplier;
  $: maxRangeKm = (effectiveRangeM / 1000).toFixed(1);

  $: if ($gameState.weather && hasViewshed && viewshedLayer && !isComputing) {
    if (lastClickLon && lastClickLat) {
      recomputeWeatherViewshed();
    }
  }

  async function recomputeWeatherViewshed() {
    if (!hasViewshed || isComputing || !view) return;
    isComputing = true;
    errorMsg = '';
    
    const pt = new Point({ longitude: lastClickLon, latitude: lastClickLat, spatialReference: { wkid: 4326 } });
    
    viewshedLayer.removeAll();
    try {
      const result = await computeViewshed(pt, view.map!.ground, { observerHeightM, maxRangeM: effectiveRangeM });
      viewshedLayer.add(new Graphic({ geometry: result.fullRange, symbol: hiddenSymbol }));
      viewshedLayer.add(new Graphic({ geometry: result.visible,   symbol: visibleSymbol }));
      obsTerrainElev = result.observerTerrainElevation;
      visiblePolygon = result.visible;
    } catch (err: unknown) {
      errorMsg = err instanceof Error ? err.message : 'Unknown error';
    } finally {
      isComputing = false;
    }
  }
  $: roleLabel  = role ? ROLE_LABELS[role]  : '';
  $: roleColour = role ? ROLE_COLOURS[role] : '#4d9fff';
  if ($auth.team_color) {
      roleColour = $auth.team_color;
  }
  if ($auth.team_name && role === 'player') {
      roleLabel = $auth.team_name.toUpperCase();
  }
  
  $: wsConnected = $gameState.connected;
</script>

<!-- ── Markup ─────────────────────────────────────────────────────────────── -->
<div class="map-wrapper" role="presentation" class:drawing-mode={exconMode.startsWith('draw-')} on:contextmenu={(e) => { if (exconMode.startsWith('draw-')) e.preventDefault(); }}>

  <!-- ArcGIS SceneView mount -->
  <div class="scene-container" bind:this={container}></div>

  <!-- ── HUD: Top header bar ────────────────────────────────────────────── -->
  <header class="hud-header">
    <div class="hud-logo">
      <svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#ddeeff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m8 3 4 8 5-5 5 15H2L8 3z"/></svg>
      <span class="logo-text">MOPT</span>
      
      {#if role === 'excon'}
        <div class="header-divider"></div>
        <button class="header-btn" class:active={showExerciseDialog} on:click={() => showExerciseDialog = !showExerciseDialog}>
          <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#f5c518" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="3 6 9 3 15 6 21 3 21 18 15 21 9 18 3 21"/></svg>
          EXERCISE
        </button>
      {/if}
    </div>

    {#if role}
      <div class="role-badge" style="--rc: {roleColour}">
        <span class="role-dot"></span>
        <span class="role-name">{roleLabel}</span>
        <button class="logout-btn" title="Log out" on:click={() => { auth.clearAuth(); gameState.disconnect(); exerciseStore.clear(); }}>
          <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" x2="9" y1="12" y2="12"/></svg>
        </button>
      </div>
    {/if}

    <div class="hud-status">
      <span class="ws-dot" class:ws-on={wsConnected} title={wsConnected ? 'WebSocket connected' : 'WebSocket offline'}></span>
      <span class="status-dot" class:ready={isReady}></span>
      <span class="status-label">{isReady ? '3D Terrain · ArcGIS' : 'Initialising…'}</span>
    </div>
  </header>

  <!-- ── EXCON EXERCISE DIALOG (Non-Blocking) ───────────────────────────── -->
  {#if showExerciseDialog && role === 'excon'}
   <div class="dialog-wrapper">
    <div class="dialog-panel" style="position: relative; top: 0; left: 0;">
      <header class="dialog-header">
        <div>
          <h2 class="dialog-title">EXERCISE INITIALISATION</h2>
          <p class="dialog-sub">Configure operational environment and ORBAT</p>
        </div>
        <button class="close-btn" aria-label="Close dialog" on:click={() => showExerciseDialog = false}>
          <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
        </button>
      </header>

      <div class="dialog-tabs">
        <button class="dialog-tab" class:active={setupMode === 'select'} on:click={() => {setupMode='select'; setupError='';}}>LOAD EXISTING</button>
        <button class="dialog-tab" class:active={setupMode === 'create'} on:click={() => {setupMode='create'; setupError='';}}>CREATE NEW</button>
      </div>

      <div class="dialog-body custom-scroll" style="max-height: 60vh; overflow-y: auto;">
        
        {#if setupMode === 'create'}
          <label class="setup-label" for="setupRegionId">OPERATIONAL REGION</label>
          <select id="setupRegionId" class="setup-input" bind:value={setupRegionId}>
            {#each REGIONS as region}
              <option value={region.id}>{region.label}</option>
            {/each}
          </select>

          <label class="setup-label" style="margin-top: 16px;" for="setupExName">EXERCISE DESIGNATION</label>
          <input id="setupExName" class="setup-input" type="text" placeholder="e.g. OP SNOW LEOPARD" bind:value={setupExName} />

          <label class="setup-label" style="margin-top: 16px;" for="setupPlanName">PLAN NAME</label>
          <input id="setupPlanName" class="setup-input" type="text" placeholder="e.g. Initial Deployment" bind:value={setupPlanName} />

          <label class="setup-label" style="margin-top: 16px;" for="setupPlanDesc">PLAN DESCRIPTION</label>
          <textarea id="setupPlanDesc" class="setup-input" rows="2" placeholder="Operational summary..." bind:value={setupPlanDesc}></textarea>

          <div style="display: flex; gap: 12px; margin-top: 16px;">
            <button class="setup-submit-btn" style="flex: 1;" on:click={savePlan}>SAVE PLAN</button>
            <button class="setup-submit-btn" style="background: rgba(255,255,255,0.1); border-color: transparent; color: #fff; width: auto; padding: 0 12px;" on:click={() => showPlanManager = !showPlanManager} title="Toggle Plan Manager">
              <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/></svg>
            </button>
          </div>

          <div style="display: flex; gap: 16px; margin-top: 16px;">
             <div style="flex: 1;">
                <label class="setup-label" for="setupTeam1">ACTIVE TEAM 1</label>
                <select id="setupTeam1" class="setup-input" bind:value={setupTeam1}>
                  <option value={null}>SELECT TEAM</option>
                  {#each allTeams.filter(t => t.id !== setupTeam2) as t}
                    <option value={t.id}>{t.name}</option>
                  {/each}
                </select>
             </div>
             <div style="flex: 1;">
                <label class="setup-label" for="setupTeam2">ACTIVE TEAM 2</label>
                <select id="setupTeam2" class="setup-input" bind:value={setupTeam2}>
                  <option value={null}>SELECT TEAM</option>
                  {#each allTeams.filter(t => t.id !== setupTeam1) as t}
                    <option value={t.id}>{t.name}</option>
                  {/each}
                </select>
             </div>
          </div>

          {#if setupTeam1 && setupTeam2}
            <label class="setup-label" style="margin-top: 16px;" for="setupFileInput">ORDER OF BATTLE (ORBAT) JSON</label>
            <div class="setup-file-box">
              <input id="setupFileInput" type="file" accept=".json" class="setup-file-input" on:change={handleFileUpload} />
              <div class="setup-file-display">
                {#if isCheckingOrbat}
                  <div class="spinner" style="width: 14px; height: 14px; border: 2px solid rgba(255,255,255,0.2); border-top-color: #fff; border-radius: 50%; animation: spin 1s linear infinite; display: inline-block; vertical-align: middle;"></div> Checking format...
                {:else if setupOrbatFile}
                  📄 {setupOrbatFile.name} {#if setupOrbatData}<span style="color: #22c55e; margin-left:6px;">✓</span>{/if}
                {:else}
                  CLICK TO BROWSE JSON
                {/if}
              </div>
            </div>
            
            <label class="setup-label" style="margin-top: 16px;">OPERATIONAL BOUNDARIES</label>
            <div class="dialog-draw-buttons">
              <button class="mode-btn draw-btn mode-blue" class:active={exconMode === 'draw-blue'} on:click={() => { 
                if (exconMode === 'draw-blue') { exconMode = 'viewshed'; drawingCancel(); }
                else if (setupBoundaryBlue) { showRedrawConfirm = 'blue'; } 
                else { exconMode = 'draw-blue'; boundaryPoints = []; redoStack = []; redrawBoundaryProgress(); } 
              }}>
                <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="margin-right: 4px; vertical-align: middle;"><path d="m12 19 7-7 3 3-7 7-3-3z"/><path d="m18 13-1.5-7.5L2 2l3.5 14.5L13 18l5-5z"/><path d="m2 2 7.586 7.586"/><circle cx="11" cy="11" r="2"/></svg>
                Draw {team1Name.toUpperCase()} Area
                {#if setupBoundaryBlue}<span class="check-mark">✓</span>{/if}
              </button>
              <button class="mode-btn draw-btn mode-red" class:active={exconMode === 'draw-red'} on:click={() => { 
                if (exconMode === 'draw-red') { exconMode = 'viewshed'; drawingCancel(); }
                else if (setupBoundaryRed) { showRedrawConfirm = 'red'; } 
                else { exconMode = 'draw-red'; boundaryPoints = []; redoStack = []; redrawBoundaryProgress(); } 
              }}>
                <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="margin-right: 4px; vertical-align: middle;"><path d="m12 19 7-7 3 3-7 7-3-3z"/><path d="m18 13-1.5-7.5L2 2l3.5 14.5L13 18l5-5z"/><path d="m2 2 7.586 7.586"/><circle cx="11" cy="11" r="2"/></svg>
                Draw {team2Name.toUpperCase()} Area
                {#if setupBoundaryRed}<span class="check-mark">✓</span>{/if}
              </button>
            </div>
            <span class="setup-hint" style="margin-top: 6px;">Click the map to add boundary points.</span>
          {/if}
          
        {:else}
          <label class="setup-label" for="setupSelectPlan">SAVED EXERCISES</label>
          <select id="setupSelectPlan" class="setup-input" on:change={(e) => {
             const val = e.target.value;
             if (val) {
                 const id = parseInt(val);
                 const p = savedPlans.find(plan => plan.id === id);
                 if (p) selectPlan(p);
             } else {
                 setupPlanName = ''; setupPlanDesc = ''; setupExName = '';
             }
          }}>
            <option value="">SELECT EXERCISE...</option>
            {#each savedPlans as plan}
              <option value={plan.id}>{plan.name}</option>
            {/each}
          </select>

          {#if setupPlanName}
            <div class="info-box" style="margin-top: 16px;">
              <strong style="color: #f5c518;">{setupPlanName}</strong>
              {#if setupPlanDesc}<p style="margin-top:4px; margin-bottom:0; font-size:12px; color: #a0c0e0;">{setupPlanDesc}</p>{/if}
            </div>
          {/if}

          <div class="info-box" style="margin-top: 16px;">
            <span class="info-dot"></span>
            Loading an existing exercise will restore the ORBAT and any previously placed units automatically.
          </div>
        {/if}

        {#if setupError}
          <div class="setup-error">
            <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
            {setupError}
          </div>
        {/if}

        {#if showRedrawConfirm}
          <div class="toast-overlay" style="position: absolute; background: rgba(0,0,0,0.7); display: flex; align-items: center; justify-content: center; z-index: 100;">
            <div class="toast-box">
              <div class="toast-icon">⚠️</div>
              <div class="toast-content">
                <strong>SUBMIT AREA AGAIN?</strong>
                <p>Do you want to redraw the {showRedrawConfirm.toUpperCase()} boundary? This will remove the set area.</p>
              </div>
              <div class="toast-actions">
                <button class="toast-btn toast-cancel" on:click={() => showRedrawConfirm = null}>NO, CANCEL</button>
                <button class="toast-btn toast-confirm-btn" on:click={() => { 
                  if (showRedrawConfirm === 'blue') setupBoundaryBlue = null;
                  if (showRedrawConfirm === 'red') setupBoundaryRed = null;
                  exconMode = ('draw-' + showRedrawConfirm);
                  showRedrawConfirm = null;
                  boundaryPoints = []; redoStack = []; redrawBoundaryProgress();
                }}>YES, REMOVE AREA</button>
              </div>
            </div>
          </div>
        {/if}

        <button class="setup-submit-btn" on:click={submitInitialise}>
          FINALISE ENVIRONMENT
        </button>
      </div>
    </div>
    
    {#if showPlanManager}
      <div class="plan-manager-panel">
        <h3 class="pm-title">PLAN MANAGER ({savedPlans.length}/5)</h3>
        {#if isFetchingPlans}
          <div style="padding: 16px; color: #a0c0e0; text-align: center; font-size: 12px;">Loading...</div>
        {:else}
          <section use:dndzone="{{items: savedPlans, flipDurationMs}}" on:consider="{handleDndConsider}" on:finalize="{handleDndFinalize}" class="pm-list">
            {#each savedPlans as plan (plan.id)}
              <div class="pm-card">
                <div class="pm-drag">≡</div>
                <div class="pm-info" on:click={() => { plan._expanded = !plan._expanded; savedPlans = savedPlans; }}>
                  <strong>{plan.name}</strong>
                  {#if plan._expanded && plan.description}
                    <div style="font-size: 11px; margin-top: 6px; color: #a0c0e0; font-weight: 400;">{plan.description}</div>
                  {/if}
                </div>
                <button class="pm-del" on:click={() => deletePlan(plan.id)} title="Delete Plan">&times;</button>
              </div>
            {/each}
          </section>
        {/if}
      </div>
    {/if}
   </div>
  {/if}

  <!-- ── FLOATING DRAWING TOOLBOX ────────────────────────────────────────── -->
  {#if exconMode.startsWith('draw-')}
    <div class="drawing-toolbox">
      <div class="toolbox-header">
        <span>DRAWING {exconMode === 'draw-blue' ? 'BLUE' : 'RED'} BOUNDARY</span>
        <button class="toolbox-close" on:click={() => showCancelConfirm = true} title="Cancel drawing">
          <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
        </button>
      </div>
      <div class="toolbox-stats" style="padding: 0 10px; font-size: 11px; color: #a0c0ff; display: flex; justify-content: space-between; margin-bottom: 6px;">
        <span>Dist: {(drawingDistanceM/1000).toFixed(2)} km</span>
        <span>Area: {(Math.abs(drawingAreaSqM)/1e6).toFixed(2)} km²</span>
      </div>
      <div style="padding: 0 10px; margin-bottom: 8px;">
        <label style="display:flex; align-items:center; gap:6px; font-size:10px; color:#a0c0ff; cursor:pointer;">
          <input type="checkbox" bind:checked={showSegmentDistances} on:change={redrawBoundaryProgress} style="accent-color: #5090ff; cursor:pointer;" />
          Show segment distances
        </label>
      </div>
      <div class="toolbox-actions">
        <button class="tool-btn" on:click={drawingUndo} disabled={boundaryPoints.length === 0} title="Undo last point">
          <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 7v6h6"/><path d="M21 17a9 9 0 0 0-9-9 9 9 0 0 0-6 2.3L3 13"/></svg>
          Reverse
        </button>
        <button class="tool-btn" on:click={drawingRedo} disabled={redoStack.length === 0} title="Redo undone point">
          <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 7v6h-6"/><path d="M3 17a9 9 0 0 1 9-9 9 9 0 0 1 6 2.3l3 2.7"/></svg>
          Fwd
        </button>
        <button class="tool-btn danger-btn" on:click={drawingReset} disabled={boundaryPoints.length === 0} title="Clear all points">
          <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18"/><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/></svg>
          Reset
        </button>
        <button class="tool-btn finish-btn" on:click={drawingFinish} disabled={boundaryPoints.length < 3} title="Finish shape">
          <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
          Finish
        </button>
      </div>
    </div>
    
    {#if showCancelConfirm}
      <div class="toast-overlay">
        <div class="toast-box">
          <div class="toast-icon">⚠️</div>
          <div class="toast-content">
            <strong>CANCEL DRAWING?</strong>
            <p>All unsaved boundary points will be removed from the map. This action cannot be undone.</p>
          </div>
          <div class="toast-actions">
            <button class="toast-btn toast-cancel" on:click={() => showCancelConfirm = false}>NO, RESUME</button>
            <button class="toast-btn toast-confirm-btn" on:click={() => { showCancelConfirm = false; drawingCancel(); }}>YES, CANCEL</button>
          </div>
        </div>
      </div>
    {/if}
  {/if}

  <!-- ── HUD: Main Map Action Toolbar Removed per Request ────────────────── -->

  <!-- ── ANALYSIS TOOLBOX (Right Side, Collapsible) ─────────────────────── -->
  <button class="toolbox-toggle" class:open={showToolbox} on:click={() => showToolbox = !showToolbox} aria-label="Toggle Analysis Toolbox">
    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
      <line x1="3" y1="12" x2="21" y2="12"></line>
      <line x1="3" y1="6" x2="21" y2="6"></line>
      <line x1="3" y1="18" x2="21" y2="18"></line>
    </svg>
  </button>

  <aside class="hud-panel toolbox-panel" class:hidden={!showToolbox} aria-label="Analysis Toolbox">
    <h2 class="panel-title">
      <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="margin-right:4px; vertical-align: middle;"><polygon points="12 2 2 7 12 12 22 7 12 2"/><polyline points="2 17 12 22 22 17"/><polyline points="2 12 12 17 22 12"/></svg>
      ANALYSIS TOOLBOX
    </h2>
    
    <div class="tb-buttons" style="margin-bottom: 16px; display: flex; gap: 8px;">
      <button class="tb-btn" style="flex: 1; justify-content: center;" on:click={goHome} title="Fly camera to overview">
        <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m3 9 9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/></svg>
        Home
      </button>
      <button class="tb-btn" style="flex: 1; justify-content: center;" on:click={cycleLighting} title="Toggle Day/Night Cycle">
        {#if lightingMode === 'auto'}
          <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="5"/><path d="M12 1v2"/><path d="M12 21v2"/><path d="M4.22 4.22l1.42 1.42"/><path d="M18.36 18.36l1.42 1.42"/><path d="M1 12h2"/><path d="M21 12h2"/><path d="M4.22 19.78l1.42-1.42"/><path d="M18.36 5.64l1.42-1.42"/></svg>
          Auto Time
        {:else if lightingMode === 'day'}
          <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="5"/><path d="M12 1v2"/><path d="M12 21v2"/><path d="M4.22 4.22l1.42 1.42"/><path d="M18.36 18.36l1.42 1.42"/><path d="M1 12h2"/><path d="M21 12h2"/><path d="M4.22 19.78l1.42-1.42"/><path d="M18.36 5.64l1.42-1.42"/></svg>
          Day
        {:else}
          <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>
          Night
        {/if}
      </button>
    </div>

    <h3 class="panel-subtitle">
      <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="margin-right:4px; vertical-align: middle;"><path d="M12 2a14.5 14.5 0 0 0 0 20 14.5 14.5 0 0 0 0-20"/><path d="M2 12h20"/></svg>
      Boundaries & Routing
    </h3>
    
    <div style="display: flex; flex-direction: column; gap: 12px;">
      <button class="tb-btn" class:active={showIntlBoundaries} on:click={() => showIntlBoundaries = !showIntlBoundaries} title="Toggle main borders">
        <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M2 12h20"/></svg>
        International Borders
      </button>

      {#if showIntlBoundaries}
        <div style="display: flex; flex-direction: column; gap: 8px; background: rgba(0,0,0,0.2); padding: 8px; border-radius: 4px; border: 1px solid rgba(255,255,255,0.05);">
          <label style="display: flex; align-items: center; gap: 8px; font-size: 11px; color: #a0c0e0; cursor: pointer; text-transform: uppercase;">
            <input type="checkbox" bind:checked={showLoc} />
            Highlight LOC (Line of Control)
          </label>
          <label style="display: flex; align-items: center; gap: 8px; font-size: 11px; color: #a0c0e0; cursor: pointer; text-transform: uppercase;">
            <input type="checkbox" bind:checked={showLac} />
            Highlight LAC (Line of Actual Control)
          </label>
          <div class="panel-divider" style="margin: 4px 0;"></div>
          <label style="display: flex; align-items: center; gap: 8px; font-size: 11px; color: #eebb44; font-weight: 600; cursor: pointer; text-transform: uppercase;">
            <input type="checkbox" bind:checked={showRoads} />
            Show Road Routes
          </label>
        </div>
      {/if}
    </div>
  </aside>

  <!-- ── Cursor Info Panel ────────────────────────────────────────── -->
  <div class="coords-container">
    <div class="coord-row"><span>LON</span> {cursorLon}°</div>
    <div class="coord-row"><span>LAT</span> {cursorLat}°</div>
    <div class="coord-row"><span>ALT</span> {cameraAlt.toLocaleString()} m</div>
  </div>

  <!-- ── Initial loading overlay ────────────────────────────────────────── -->
  {#if !isReady}
    <div class="loading-overlay">
      <div class="loading-spinner"></div>
      <p>Initialising 3D terrain…</p>
    </div>
  {/if}
</div>

<!-- ── Styles ─────────────────────────────────────────────────────────────── -->
<style>
  .map-wrapper { position: relative; width: 100vw; height: 100vh; overflow: hidden; font-family: 'Inter', sans-serif; background: #080c14; }
  .scene-container { position: absolute; inset: 0; }

  /* HUD Header */
  .hud-header { position: absolute; top: 0; left: 0; right: 0; z-index: 10; display: flex; align-items: center; justify-content: space-between; padding: 12px 20px; background: linear-gradient(180deg, rgba(6,10,22,0.95) 0%, rgba(6,10,22,0) 100%); pointer-events: none; }
  .hud-logo { display: flex; align-items: center; gap: 14px; pointer-events: auto; }
  .logo-text { font-size: 18px; font-weight: 700; letter-spacing: 3px; color: #ddeeff; text-transform: uppercase; }
  
  .header-divider { width: 1px; height: 24px; background: rgba(140,185,255,0.2); }
  .header-btn { display: flex; align-items: center; gap: 6px; background: rgba(20,35,70,0.6); border: 1px solid rgba(80,140,255,0.25); border-radius: 6px; padding: 6px 14px; color: #c0d8ff; font-family: inherit; font-size: 11px; font-weight: 700; letter-spacing: 1.5px; cursor: pointer; transition: 0.2s; }
  .header-btn:hover { background: rgba(40,80,160,0.5); border-color: rgba(80,170,255,0.5); }
  .header-btn.active { background: rgba(40,100,200,0.7); border-color: #5090ff; color: #fff; box-shadow: 0 0 12px rgba(80,144,255,0.4); }
  
  .role-badge { display: flex; align-items: center; gap: 8px; background: rgba(6,12,26,0.85); border: 1px solid var(--rc, #4d9fff)55; border-radius: 20px; padding: 5px 12px 5px 10px; pointer-events: auto; backdrop-filter: blur(10px); }
  .role-dot { width: 8px; height: 8px; border-radius: 50%; background: var(--rc, #4d9fff); box-shadow: 0 0 6px var(--rc, #4d9fff); animation: rolePulse 2s ease-in-out infinite; }
  @keyframes rolePulse { 0%,100%{opacity:1} 50%{opacity:0.5} }
  .role-name { font-size: 11px; font-weight: 700; letter-spacing: 2px; color: var(--rc, #4d9fff); text-transform: uppercase; }
  .logout-btn { background: none; border: none; color: rgba(160,190,255,0.45); cursor: pointer; padding: 0 4px; display: flex; align-items: center; transition: color 0.2s; }
  .logout-btn:hover { color: rgba(255,100,100,0.8); }

  .hud-status { display: flex; align-items: center; gap: 7px; pointer-events: auto; }
  .ws-dot { width: 6px; height: 6px; border-radius: 50%; background: rgba(150,60,60,0.7); }
  .ws-dot.ws-on { background: #22c55e; box-shadow: 0 0 6px #22c55e88; }
  .status-dot { width: 8px; height: 8px; border-radius: 50%; background: #f97316; }
  .status-dot.ready { background: #22c55e; box-shadow: 0 0 8px #22c55e88; }
  .status-label { font-size: 11px; letter-spacing: 1px; color: rgba(190,215,255,0.7); text-transform: uppercase; }

  /* Main Toolbar */
  .excon-toolbar { position: absolute; bottom: 36px; left: 50%; transform: translateX(-50%); z-index: 10; display: flex; align-items: center; gap: 8px; background: rgba(6,12,26,0.9); border: 1px solid rgba(80,140,255,0.3); border-radius: 8px; padding: 8px 14px; backdrop-filter: blur(14px); }
  .toolbar-label { font-size: 9px; letter-spacing: 2px; text-transform: uppercase; color: rgba(80,140,255,0.55); margin-right: 4px; }
  .mode-btn { cursor: pointer; font-family: inherit; font-size: 11px; font-weight: 600; letter-spacing: 0.8px; text-transform: uppercase; color: rgba(190,215,255,0.7); background: rgba(20,35,70,0.7); border: 1px solid rgba(80,130,255,0.25); border-radius: 5px; padding: 6px 12px; transition: 0.2s; display: flex; align-items: center; }
  .mode-btn.active { background: rgba(40,60,130,0.9); border-color: rgba(100,160,255,0.7); color: #c0d8ff; }
  .mode-btn.mode-blue.active { background: rgba(20,70,160,0.85); border-color: #4d9fff; color: #90c8ff; }
  .mode-btn.mode-red.active { background: rgba(130,20,20,0.85); border-color: #ff4d4d; color: #ffaaaa; }
  .mode-btn:hover:not(.active):not(:disabled) { background: rgba(30,50,100,0.8); border-color: rgba(80,140,255,0.4); }
  .mode-btn:disabled { opacity: 0.4; cursor: not-allowed; }
  .toolbar-divider { width: 1px; height: 20px; background: rgba(255,255,255,0.1); margin: 0 4px; }
  .toolbar-error { font-size: 11px; color: #ff6060; font-weight: 600; display: flex; align-items: center; margin-left: 8px; }

  /* Floating Drawing Toolbox */
  .drawing-toolbox { position: absolute; top: 100px; right: 280px; z-index: 15; background: rgba(10,16,28,0.95); border: 1px solid rgba(245,197,24,0.4); border-radius: 8px; box-shadow: 0 8px 24px rgba(0,0,0,0.8); backdrop-filter: blur(12px); overflow: hidden; animation: slideIn 0.2s ease; }
  .toolbox-header { display: flex; justify-content: space-between; align-items: center; background: rgba(245,197,24,0.15); padding: 8px 12px; font-size: 10px; font-weight: 800; color: #f5c518; letter-spacing: 1px; text-transform: uppercase; border-bottom: 1px solid rgba(245,197,24,0.2); }
  .toolbox-close { background: none; border: none; color: #f5c518; cursor: pointer; padding: 0; opacity: 0.7; transition: 0.2s; display: flex; }
  .toolbox-close:hover { opacity: 1; color: #ff6060; }
  .toolbox-actions { display: flex; gap: 4px; padding: 8px; }
  .tool-btn { background: rgba(0,0,0,0.4); border: 1px solid rgba(80,140,255,0.2); border-radius: 4px; color: #a0c0ff; font-family: inherit; font-size: 10px; font-weight: 600; padding: 6px 10px; display: flex; flex-direction: column; align-items: center; gap: 4px; cursor: pointer; transition: 0.2s; min-width: 56px; }
  .tool-btn:hover:not(:disabled) { background: rgba(40,80,160,0.4); border-color: #5090ff; color: #fff; }
  .tool-btn:disabled { opacity: 0.3; cursor: not-allowed; }
  .danger-btn:hover:not(:disabled) { background: rgba(160,40,40,0.4); border-color: #ff4d4d; color: #ffcccc; }
  .finish-btn { background: rgba(40,200,100,0.15); border-color: rgba(40,200,100,0.4); color: #80ffb0; }
  .finish-btn:hover:not(:disabled) { background: rgba(40,200,100,0.4); border-color: #40ff80; color: #fff; }

  /* Non-blocking Exercise Dialog */
  .dialog-wrapper { position: absolute; top: 70px; left: 20px; z-index: 20; display: flex; gap: 16px; animation: dialogPop 0.25s cubic-bezier(0.1, 0.9, 0.2, 1); pointer-events: auto; }
  .dialog-panel { width: 340px; background: rgba(10,16,28,0.95); border: 1px solid rgba(245,197,24,0.4); border-radius: 8px; box-shadow: 0 12px 48px rgba(0,0,0,0.8); overflow: hidden; pointer-events: auto; }
  .plan-manager-panel { width: 280px; background: rgba(10,16,28,0.95); border: 1px solid rgba(245,197,24,0.4); border-radius: 8px; box-shadow: 0 12px 48px rgba(0,0,0,0.8); overflow: hidden; display: flex; flex-direction: column; }
  .pm-title { background: rgba(245,197,24,0.1); color: #f5c518; padding: 12px; margin: 0; font-size: 12px; letter-spacing: 1px; border-bottom: 1px solid rgba(245,197,24,0.4); text-align: center; }
  .pm-list { flex: 1; overflow-y: auto; padding: 12px; display: flex; flex-direction: column; gap: 8px; min-height: 200px; }
  .pm-card { background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.1); border-radius: 4px; display: flex; align-items: center; padding: 8px; cursor: grab; }
  .pm-card:active { cursor: grabbing; }
  .pm-drag { padding: 0 8px; color: #f5c518; font-size: 18px; cursor: grab; }
  .pm-info { flex: 1; cursor: pointer; color: #fff; font-size: 13px; }
  .pm-del { background: none; border: none; color: #ff4d4d; font-size: 16px; cursor: pointer; padding: 0 8px; }
  .pm-del:hover { color: #ff0000; }
  @keyframes dialogPop { from { opacity: 0; transform: translate(-20px, 0) scale(0.95); } to { opacity: 1; transform: translate(0, 0) scale(1); } }
  
  .dialog-header { display: flex; justify-content: space-between; align-items: flex-start; padding: 16px; background: rgba(245,197,24,0.1); border-bottom: 1px solid rgba(245,197,24,0.2); }
  .dialog-title { margin: 0; font-size: 14px; font-weight: 800; color: #f5c518; letter-spacing: 2px; text-transform: uppercase; }
  .dialog-sub { margin: 4px 0 0; font-size: 10px; color: rgba(245,197,24,0.6); letter-spacing: 0.5px; text-transform: uppercase; }
  .close-btn { background: none; border: none; color: #f5c518; cursor: pointer; opacity: 0.6; padding: 0; display: flex; transition: opacity 0.2s; }
  .close-btn:hover { opacity: 1; }

  .dialog-tabs { display: flex; border-bottom: 1px solid rgba(80,140,255,0.2); }
  .dialog-tab { flex: 1; padding: 12px; background: rgba(0,0,0,0.3); border: none; color: rgba(180,210,255,0.5); font-size: 10px; font-weight: 700; letter-spacing: 1.5px; cursor: pointer; transition: 0.2s; }
  .dialog-tab:hover { background: rgba(40,80,160,0.2); color: rgba(180,210,255,0.8); }
  .dialog-tab.active { background: rgba(40,100,200,0.25); color: #c0d8ff; box-shadow: inset 0 -2px 0 #5090ff; }

  .dialog-body { padding: 20px; display: flex; flex-direction: column; }

  /* Custom Scrollbar for Dialog */
  .custom-scroll::-webkit-scrollbar { width: 6px; }
  .custom-scroll::-webkit-scrollbar-track { background: rgba(0,0,0,0.2); border-radius: 4px; }
  .custom-scroll::-webkit-scrollbar-thumb { background: rgba(245,197,24,0.3); border-radius: 4px; }
  .custom-scroll::-webkit-scrollbar-thumb:hover { background: rgba(245,197,24,0.6); }
  .setup-label { font-size: 9px; font-weight: 700; color: rgba(180,210,255,0.6); letter-spacing: 1px; margin-bottom: 6px; }
  .setup-input { width: 100%; background: rgba(0,0,0,0.4); border: 1px solid rgba(80,140,255,0.3); border-radius: 4px; padding: 10px; font-size: 12px; color: #ddeeff; font-family: inherit; outline: none; }
  .setup-input:focus { border-color: #5090ff; }
  
  .setup-file-box { position: relative; border: 1px dashed rgba(80,140,255,0.4); border-radius: 4px; background: rgba(20,40,80,0.2); height: 44px; display: flex; align-items: center; justify-content: center; transition: 0.2s; }
  .setup-file-box:hover { border-color: #5090ff; background: rgba(40,80,160,0.2); }
  .setup-file-input { position: absolute; inset: 0; opacity: 0; cursor: pointer; width: 100%; }
  .setup-file-display { font-size: 10px; font-weight: 600; color: #a0c0ff; pointer-events: none; letter-spacing: 1px; }
  
  .dialog-draw-buttons { display: flex; gap: 8px; }
  .dialog-draw-buttons .mode-btn { flex: 1; justify-content: center; }
  .check-mark { margin-left: 6px; color: #40ff80; font-weight: 800; }

  .setup-hint { font-size: 10px; color: rgba(150,185,240,0.5); }
  .setup-error { margin-top: 12px; font-size: 10px; color: #ff6060; font-weight: 600; display: flex; align-items: center; }
  
  .setup-submit-btn { margin-top: 20px; padding: 12px; background: #f5c518; color: #000; border: none; border-radius: 4px; font-size: 11px; font-weight: 800; letter-spacing: 2px; cursor: pointer; transition: 0.2s; }
  .setup-submit-btn:hover { background: #ffe050; transform: translateY(-1px); box-shadow: 0 4px 12px rgba(245,197,24,0.3); }

  .info-box { display: flex; align-items: center; gap: 12px; padding: 12px; background: rgba(40,100,200,0.15); border: 1px solid rgba(80,140,255,0.25); border-radius: 4px; font-size: 10px; color: #a0c0ff; line-height: 1.5; }
  .info-dot { flex-shrink: 0; width: 6px; height: 6px; border-radius: 50%; background: #5090ff; }

  /* ── Right Panel: Analysis Toolbox ── */
  .toolbox-toggle { position: absolute; top: 70px; right: 0; z-index: 9; background: rgba(6,12,26,0.88); border: 1px solid rgba(80,140,255,0.22); border-right: none; border-radius: 6px 0 0 6px; padding: 12px 6px; color: #c8deff; cursor: pointer; backdrop-filter: blur(14px); transition: 0.3s cubic-bezier(0.1, 0.9, 0.2, 1); display: flex; align-items: center; justify-content: center; }
  .toolbox-toggle:hover { background: rgba(20,40,80,0.9); }
  .toolbox-toggle.open { right: 260px; }

  .toolbox-panel { position: absolute; top: 70px; right: 20px; z-index: 10; width: 240px; background: rgba(6,12,26,0.88); border: 1px solid rgba(80,140,255,0.22); border-radius: 10px; padding: 16px; backdrop-filter: blur(14px); display: flex; flex-direction: column; gap: 10px; transition: 0.3s cubic-bezier(0.1, 0.9, 0.2, 1); }
  .toolbox-panel.hidden { transform: translateX(300px); opacity: 0; pointer-events: none; }

  .panel-title { display: flex; align-items: center; font-size: 13px; font-weight: 800; color: #c8deff; text-transform: uppercase; margin: 0; letter-spacing: 1px; }
  .panel-subtitle { display: flex; align-items: center; font-size: 11px; font-weight: 700; color: #a0c0ff; text-transform: uppercase; margin: 4px 0 2px; }
  .panel-divider { height: 1px; background: rgba(80,140,255,0.2); margin: 6px 0; }

  .tb-buttons { display: flex; gap: 8px; margin-top: 6px; }
  .tb-btn { flex: 1; display: flex; flex-direction: column; align-items: center; gap: 6px; background: rgba(0,0,0,0.3); border: 1px solid rgba(80,140,255,0.2); border-radius: 6px; color: #a0c0ff; font-family: inherit; font-size: 10px; font-weight: 600; padding: 8px; cursor: pointer; transition: 0.2s; }
  .tb-btn:hover { background: rgba(40,80,160,0.3); border-color: #5090ff; color: #fff; }
  .tb-btn.active { background: rgba(40,100,200,0.4); border-color: #5090ff; color: #fff; box-shadow: inset 0 0 8px rgba(80,144,255,0.2); }

  .panel-hint { font-size: 11px; line-height: 1.5; color: rgba(150,185,240,0.65); margin: 0; }
  .slider-label { display: flex; justify-content: space-between; font-size: 11px; color: rgba(160,195,255,0.75); margin-top: 4px; }
  .slider-value { color: #82c8ff; font-weight: 600; }
  .slider { -webkit-appearance: none; appearance: none; width: 100%; height: 4px; background: rgba(80,140,255,0.25); border-radius: 2px; }
  .slider::-webkit-slider-thumb { -webkit-appearance: none; appearance: none; width: 14px; height: 14px; border-radius: 50%; background: #5090ff; cursor: pointer; }
  
  .result-box { background: rgba(20,40,80,0.5); border: 1px solid rgba(80,140,255,0.18); border-radius: 6px; padding: 10px; display: flex; flex-direction: column; gap: 6px; }
  .result-row { display: flex; justify-content: space-between; }
  .result-label { font-size: 10px; color: rgba(140,180,240,0.6); }
  .result-value { font-size: 11px; color: #a0d0ff; font-weight: 600; }
  .error-box { background: rgba(180,30,30,0.25); border: 1px solid rgba(200,60,60,0.4); border-radius: 6px; padding: 8px; font-size: 11px; color: #ff9090; display: flex; align-items: center; }
  .clear-btn { padding: 8px; font-size: 11px; font-weight: 600; background: rgba(40,60,120,0.5); border: 1px solid rgba(80,130,255,0.3); border-radius: 6px; color: rgba(180,200,255,0.85); cursor: pointer; transition: 0.2s; }
  .clear-btn:hover:not(:disabled) { background: rgba(60,80,150,0.7); color: #fff; }

  /* Weather UI */
  .weather-controls { display: grid; grid-template-columns: 1fr 1fr; gap: 6px; margin-top: 6px; }
  .weather-btn { background: rgba(0,0,0,0.3); border: 1px solid rgba(80,140,255,0.2); border-radius: 6px; color: #a0c0ff; font-family: inherit; font-size: 10px; font-weight: 600; padding: 6px; cursor: pointer; transition: 0.2s; display: flex; align-items: center; justify-content: center; gap: 4px; }
  .weather-btn:hover { background: rgba(40,80,160,0.3); border-color: #5090ff; color: #fff; }
  .weather-btn.active { background: rgba(40,100,200,0.4); border-color: #5090ff; color: #fff; box-shadow: inset 0 0 8px rgba(80,144,255,0.2); }

  /* Overlays */
  .computing-overlay, .loading-overlay { position: absolute; inset: 0; z-index: 30; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 14px; background: rgba(4,8,20,0.65); backdrop-filter: blur(6px); color: rgba(180,210,255,0.85); }
  .loading-overlay { z-index: 20; background: rgba(6,10,20,0.85); text-transform: uppercase; letter-spacing: 1.5px; font-size: 13px; }
  .computing-spinner, .loading-spinner { width: 44px; height: 44px; border: 3px solid rgba(80,140,255,0.15); border-top-color: #5090ff; border-radius: 50%; animation: spin 0.85s linear infinite; }
  @keyframes spin { to { transform: rotate(360deg); } }

  /* Toast Confirm Dialog */
  .toast-overlay { position: fixed; inset: 0; z-index: 50; display: flex; align-items: center; justify-content: center; background: rgba(0,0,0,0.6); backdrop-filter: blur(3px); animation: dialogPop 0.2s ease; }
  .toast-box { background: rgba(15,20,35,0.98); border: 1px solid rgba(245,197,24,0.5); border-radius: 8px; padding: 18px; display: flex; flex-direction: column; gap: 12px; box-shadow: 0 10px 40px rgba(0,0,0,0.9); max-width: 320px; text-align: center; }
  .toast-icon { font-size: 24px; line-height: 1; margin-bottom: -4px; }
  .toast-content strong { color: #f5c518; font-size: 12px; letter-spacing: 1.5px; display: block; margin-bottom: 6px; }
  .toast-content p { color: #c0d8ff; font-size: 11px; margin: 0; line-height: 1.5; }
  .toast-actions { display: flex; gap: 10px; margin-top: 6px; }
  .toast-btn { flex: 1; padding: 10px; font-size: 10px; font-weight: 800; letter-spacing: 1px; cursor: pointer; border-radius: 4px; transition: 0.2s; border: none; }
  .toast-cancel { background: rgba(80,140,255,0.15); color: #a0c0ff; }
  .toast-cancel:hover { background: rgba(80,140,255,0.3); color: #fff; }
  .toast-confirm-btn { background: rgba(220,50,50,0.85); color: #fff; }
  .toast-confirm-btn:hover { background: #ff4040; box-shadow: 0 4px 12px rgba(220,50,50,0.5); }

  .coords-container { position: absolute; bottom: 0; right: 0; z-index: 10; display: flex; flex-direction: row; gap: 16px; background: rgba(6,12,26,0.85); border-top: 1px solid rgba(80,140,255,0.25); border-left: 1px solid rgba(80,140,255,0.25); border-top-left-radius: 8px; padding: 6px 12px; color: #a0c0e0; font-family: 'JetBrains Mono', monospace; font-size: 11px; font-weight: 500; letter-spacing: 0.5px; pointer-events: none; backdrop-filter: blur(8px); }
  .coord-row { display: flex; align-items: center; }
  .coord-row span { color: rgba(80,140,255,0.7); font-size: 9px; font-weight: 800; letter-spacing: 1px; margin-right: 6px; }

  :global(.drawing-mode .scene-container .esri-view-surface) { cursor: crosshair !important; }
  :global(.esri-attribution) {
    display: none !important;
  }
</style>
