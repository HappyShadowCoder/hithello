const fs = require('fs');
const file = '/Users/swastiek/Desktop/MOPT/frontend/src/lib/Map.svelte';
let content = fs.readFileSync(file, 'utf8');

// 1. Types and Variables
content = content.replace(
  `type ExconMode = 'viewshed' | 'place-blue' | 'place-red' | 'draw-blue' | 'draw-red';
  let exconMode: ExconMode = 'viewshed';`,
  `type ExconMode = 'viewshed' | 'fof' | 'trajectory' | 'satellite' | 'place-blue' | 'place-red' | 'draw-blue' | 'draw-red';
  let exconMode: ExconMode = 'viewshed';

  let fofOrigin: Point | null = null;
  let trajOrigin: Point | null = null;
  let satelliteRAF: number | null = null;
  let satGraphic: Graphic | null = null;

  let drawingDistanceM = 0;
  let drawingAreaSqM = 0;
  let showRedrawConfirm: 'blue' | 'red' | null = null;`
);

// 2. Symbols
content = content.replace(
  `  const observerSymbol = new SimpleMarkerSymbol({
    color: new Color([255, 230, 0, 1]), size: 14,
    outline: { color: new Color([255, 255, 255, 1]), width: 2 },
  });`,
  `  const observerSymbol = new SimpleMarkerSymbol({
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
  });`
);

// 3. redrawBoundaryProgress calculations
content = content.replace(
  `    if (boundaryPoints.length >= 2) {
      const paths = boundaryPoints.map(p => [p.longitude as number, p.latitude as number]);
      if (boundaryPoints.length > 2) {
        paths.push([boundaryPoints[0].longitude as number, boundaryPoints[0].latitude as number]);
      }
      const line = new Polyline({ paths: [paths], spatialReference: { wkid: 4326 } });
      boundaryLayer.add(new Graphic({ geometry: line, symbol: getBoundaryLine(team) }));
    }`,
  `    drawingDistanceM = 0;
    drawingAreaSqM = 0;

    if (boundaryPoints.length >= 2) {
      const paths = boundaryPoints.map(p => [p.longitude as number, p.latitude as number]);
      if (boundaryPoints.length > 2) {
        paths.push([boundaryPoints[0].longitude as number, boundaryPoints[0].latitude as number]);
      }
      const line = new Polyline({ paths: [paths], spatialReference: { wkid: 4326 } });
      boundaryLayer.add(new Graphic({ geometry: line, symbol: getBoundaryLine(team) }));
      drawingDistanceM = geometryEngine.geodesicLength(line, "meters");
    }`
);
content = content.replace(
  `    if (boundaryPoints.length >= 3) {
      const rings = boundaryPoints.map(p => [p.longitude as number, p.latitude as number]);
      rings.push([boundaryPoints[0].longitude as number, boundaryPoints[0].latitude as number]);
      const poly = new Polygon({ rings: [rings], spatialReference: { wkid: 4326 } });
      boundaryLayer.add(new Graphic({ geometry: poly, symbol: getBoundaryFill(team) }));
    }`,
  `    if (boundaryPoints.length >= 3) {
      const rings = boundaryPoints.map(p => [p.longitude as number, p.latitude as number]);
      rings.push([boundaryPoints[0].longitude as number, boundaryPoints[0].latitude as number]);
      const poly = new Polygon({ rings: [rings], spatialReference: { wkid: 4326 } });
      boundaryLayer.add(new Graphic({ geometry: poly, symbol: getBoundaryFill(team) }));
      drawingAreaSqM = geometryEngine.geodesicArea(poly, "square-meters");
    }`
);

// 4. Click Handler for Map
content = content.replace(
  `      if (role === 'excon' && exconMode !== 'viewshed') {
        const team = exconMode === 'place-blue' ? 'blue' : 'red';
        placingError = '';
        try {
          await gameState.placeUnit(team, pt.longitude!, pt.latitude!);
        } catch (err) {
          placingError = err instanceof Error ? err.message : 'Failed to place unit';
        }
        return;
      }`,
  `      if (role === 'excon' && exconMode.startsWith('place-')) {
        const team = exconMode === 'place-blue' ? 'blue' : 'red';
        placingError = '';
        try {
          await gameState.placeUnit(team, pt.longitude!, pt.latitude!);
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
      }`
);

// 5. Add Advanced Phase 8 functions
const funcs = \`
  function createWedgePolygon(center: Point, target: Point, radiusM: number, fovDeg: number = 60) {
     const dy = target.latitude - center.latitude;
     const dx = target.longitude - center.longitude;
     let azimuth = Math.atan2(dx, dy) * 180 / Math.PI; 
     
     const rings = [[center.longitude, center.latitude]];
     const startAz = azimuth - fovDeg/2;
     const endAz = azimuth + fovDeg/2;
     
     const R = 6378137;
     const lat1 = center.latitude * Math.PI / 180;
     const lon1 = center.longitude * Math.PI / 180;
     
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
     
     rings.push([center.longitude, center.latitude]);
     return new Polygon({ rings: [rings], spatialReference: { wkid: 4326 } });
  }

  async function executeFieldOfFire(origin: Point, target: Point) {
      if (isComputing || !view) return;
      isComputing = true;
      errorMsg = '';
      try {
        const result = await computeViewshed(origin, view.map.ground, { observerHeightM, maxRangeM: effectiveRangeM });
        const wedge = createWedgePolygon(origin, target, effectiveRangeM);
        const visibleWedge = geometryEngine.intersect(result.visible, wedge);
        if (visibleWedge) {
            viewshedLayer.add(new Graphic({ geometry: visibleWedge, symbol: fofVisibleSymbol }));
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
      
      const polyline = new Polyline({
          paths: [[[origin.longitude, origin.latitude], [target.longitude, target.latitude]]],
          spatialReference: { wkid: 4326 }
      });
      const dist = geometryEngine.geodesicLength(polyline, "meters");
      
      try {
          const p1Res = await view.map.ground.queryElevation(origin);
          const p2Res = await view.map.ground.queryElevation(target);
          const elev1 = p1Res.geometry.z;
          const elev2 = p2Res.geometry.z;
          
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
             const e = await req.json();
             throw new Error(e.detail || "Trajectory calc failed");
          }
          const data = await req.json();
          const arcPoints = data.arc;
          
          const pathsSafe = [];
          const pathsBlocked = [];
          let hitTerrain = false;
          
          const dx = target.longitude - origin.longitude;
          const dy = target.latitude - origin.latitude;
          
          const pts3d = [];
          for (const ap of arcPoints) {
              const ratio = ap.x_m / dist;
              const lon = origin.longitude + dx * ratio;
              const lat = origin.latitude + dy * ratio;
              pts3d.push(new Point({ longitude: lon, latitude: lat, z: ap.altitude_m, spatialReference: { wkid: 4326 } }));
          }
          
          const elevRes = await view.map.ground.queryElevation(new Polyline({ paths: [pts3d.map(p => [p.longitude, p.latitude])], spatialReference: { wkid: 4326 } }));
          
          for (let i = 0; i < pts3d.length; i++) {
              const pt = pts3d[i];
              const terrainZ = elevRes.geometry.paths[0][i][2];
              if (pt.z < terrainZ && i > 5 && i < pts3d.length - 5) {
                  hitTerrain = true;
              }
              if (!hitTerrain) {
                  pathsSafe.push([pt.longitude, pt.latitude, pt.z]);
              } else {
                  pathsBlocked.push([pt.longitude, pt.latitude, pt.z]);
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
\`;

content = content.replace(
  \`  // ── HUD: Main Map Action Toolbar ──────────────────────────────────────\`,
  funcs + \`\n  // ── HUD: Main Map Action Toolbar ──────────────────────────────────────\`
);
\`

// 6. Setup Boundary Draw UI logic
content = content.replace(
  \`<button class="mode-btn draw-btn mode-blue" class:active={exconMode === 'draw-blue'} on:click={() => { exconMode = 'draw-blue'; boundaryPoints = []; redoStack = []; redrawBoundaryProgress(); }}>\`,
  \`<button class="mode-btn draw-btn mode-blue" class:active={exconMode === 'draw-blue'} on:click={() => { 
    if (setupBoundaryBlue) { showRedrawConfirm = 'blue'; } else { exconMode = 'draw-blue'; boundaryPoints = []; redoStack = []; redrawBoundaryProgress(); } 
  }}>\`
);

content = content.replace(
  \`<button class="mode-btn draw-btn mode-red" class:active={exconMode === 'draw-red'} on:click={() => { exconMode = 'draw-red'; boundaryPoints = []; redoStack = []; redrawBoundaryProgress(); }}>\`,
  \`<button class="mode-btn draw-btn mode-red" class:active={exconMode === 'draw-red'} on:click={() => { 
    if (setupBoundaryRed) { showRedrawConfirm = 'red'; } else { exconMode = 'draw-red'; boundaryPoints = []; redoStack = []; redrawBoundaryProgress(); } 
  }}>\`
);

// Add the redraw confirm toast
content = content.replace(
  \`        {:else}
          <div class="info-box" style="margin-top: 16px;">\`,
  \`        {:else}
          <div class="info-box" style="margin-top: 16px;">\`
);

// Wait, better to place it at the end of dialog body
content = content.replace(
  \`        <button class="setup-submit-btn" on:click={submitInitialise}>
          FINALISE ENVIRONMENT
        </button>\`,
  \`        {#if showRedrawConfirm}
          <div class="toast-overlay" style="position: absolute;">
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
                  exconMode = 'draw-' + showRedrawConfirm as ExconMode;
                  showRedrawConfirm = null;
                  boundaryPoints = []; redoStack = []; redrawBoundaryProgress();
                }}>YES, REMOVE AREA</button>
              </div>
            </div>
          </div>
        {/if}

        <button class="setup-submit-btn" on:click={submitInitialise}>
          FINALISE ENVIRONMENT
        </button>\`
);

// 7. Add advanced features to EXCON toolbar
content = content.replace(
  \`      <button class="mode-btn" class:active={exconMode === 'viewshed'} on:click={() => { exconMode = 'viewshed'; placingError = ''; }}>
        <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="margin-right:4px; vertical-align: middle;"><path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/></svg>
        Viewshed
      </button>\`,
  \`      <button class="mode-btn" class:active={exconMode === 'viewshed'} on:click={() => { exconMode = 'viewshed'; placingError = ''; viewshedLayer.removeAll(); markerLayer.removeAll(); }}>
        Viewshed
      </button>
      <button class="mode-btn" class:active={exconMode === 'fof'} on:click={() => { exconMode = 'fof'; fofOrigin = null; placingError = ''; viewshedLayer.removeAll(); markerLayer.removeAll(); }}>
        Field of Fire
      </button>
      <button class="mode-btn" class:active={exconMode === 'trajectory'} on:click={() => { exconMode = 'trajectory'; trajOrigin = null; placingError = ''; viewshedLayer.removeAll(); markerLayer.removeAll(); }}>
        Trajectory
      </button>
      <button class="mode-btn" class:active={exconMode === 'satellite'} on:click={() => { exconMode = 'satellite'; toggleSatellite(); placingError = ''; }}>
        Satellite
      </button>\`
);

// 8. Add distance and area to drawing toolbox
content = content.replace(
  \`      <div class="toolbox-header">
        <span>DRAWING {exconMode === 'draw-blue' ? 'BLUE' : 'RED'} BOUNDARY</span>
      </div>\`,
  \`      <div class="toolbox-header">
        <span>DRAWING {exconMode === 'draw-blue' ? 'BLUE' : 'RED'} BOUNDARY</span>
      </div>
      <div class="toolbox-stats" style="padding: 0 10px; font-size: 11px; color: #a0c0ff; display: flex; justify-content: space-between; margin-bottom: 6px;">
        <span>Dist: {(drawingDistanceM/1000).toFixed(2)} km</span>
        <span>Area: {(drawingAreaSqM/1e6).toFixed(2)} km²</span>
      </div>\`
);

fs.writeFileSync(file, content);
console.log("Patched Map.svelte successfully!");
