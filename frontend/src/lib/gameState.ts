/**
 * gameState.ts — Real-time game state store + WebSocket client
 * =============================================================
 * Maintains the shared operational picture (all placed units) and
 * the local viewshed polygon used for Fog of War filtering.
 *
 * WebSocket message protocol (server → client):
 *   { type: "state_snapshot", units: Unit[] }   — sent on join
 *   { type: "unit_placed",    unit: Unit }       — new unit broadcast
 *   { type: "unit_removed",   id: string }       — unit removed broadcast
 *   { type: "pong" }                             — keep-alive reply
 *
 * Client → server:
 *   { type: "join", role: "excon"|"blue"|"red" } — identify on connect
 *   { type: "ping" }                              — keep-alive
 */

import { writable, get } from 'svelte/store';
import type { Role } from './auth';

// ── Types ─────────────────────────────────────────────────────────────────────

export type Weather = 'Clear' | 'Rain' | 'Snow' | 'Fog';

export interface Unit {
  id:    string;
  team:  string;
  team_color: string;
  lon:   number;
  lat:   number;
  label: string;
}

export interface GameState {
  units:     Unit[];
  connected: boolean;
  role:      Role | null;
  weather:   Weather;
}

// ── Store ─────────────────────────────────────────────────────────────────────

function createGameStateStore() {
  const { subscribe, update, set } = writable<GameState>({
    units:     [],
    connected: false,
    role:      null,
    weather:   'Clear',
  });

  let socket: WebSocket | null = null;
  let pingInterval: ReturnType<typeof setInterval> | null = null;

  /** Add or update a unit in the store. */
  function upsertUnit(unit: Unit) {
    update(s => {
      const existing = s.units.findIndex(u => u.id === unit.id);
      if (existing >= 0) {
        const next = [...s.units];
        next[existing] = unit;
        return { ...s, units: next };
      }
      return { ...s, units: [...s.units, unit] };
    });
  }

  /** Remove a unit from the store by ID. */
  function removeUnit(id: string) {
    update(s => ({ ...s, units: s.units.filter(u => u.id !== id) }));
  }

  return {
    subscribe,

    /**
     * Open a WebSocket connection to the backend and identify with the given role.
     * Idempotent — calling while already connected is a no-op.
     */
    connect(authState: any): void {
      if (socket && socket.readyState === WebSocket.OPEN) return;

      const WS_URL = 'ws://localhost:8000/ws';
      socket = new WebSocket(WS_URL);

      socket.addEventListener('open', () => {
        update(s => ({ ...s, connected: true, role: authState.role }));
        socket!.send(JSON.stringify({ type: 'join', token: authState.token }));

        // Keep-alive ping every 25 seconds
        pingInterval = setInterval(() => {
          if (socket?.readyState === WebSocket.OPEN) {
            socket.send(JSON.stringify({ type: 'ping' }));
          }
        }, 25_000);
      });

      socket.addEventListener('message', (event: MessageEvent) => {
        let msg: any;
        try { msg = JSON.parse(event.data as string); }
        catch { return; }

        switch (msg.type) {
          case 'state_snapshot':
            update(s => ({ ...s, units: msg.units as Unit[], weather: msg.weather as Weather }));
            break;
          case 'unit_placed':
            upsertUnit(msg.unit as Unit);
            break;
          case 'unit_removed':
            removeUnit(msg.id as string);
            break;
          case 'weather_changed':
            update(s => ({ ...s, weather: msg.weather as Weather }));
            break;
          case 'pong':
          case 'error':
          default:
            break;
        }
      });

      socket.addEventListener('close', () => {
        update(s => ({ ...s, connected: false }));
        if (pingInterval) { clearInterval(pingInterval); pingInterval = null; }
        socket = null;
      });

      socket.addEventListener('error', () => {
        console.warn('[MOPT] WebSocket error — server may not be running');
      });
    },

    /** Close the WebSocket connection cleanly. */
    disconnect(): void {
      if (pingInterval) { clearInterval(pingInterval); pingInterval = null; }
      socket?.close();
      socket = null;
      set({ units: [], connected: false, role: null, weather: 'Clear' });
    },

    /**
     * Place a unit via REST POST /place_unit.
     * The server will broadcast the new unit to all WebSocket clients.
     */
    async placeUnit(team: string, team_color: string, lon: number, lat: number, label = ''): Promise<void> {
      const resp = await fetch('http://localhost:8000/place_unit', {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({ team, team_color, lon, lat, label }),
      });
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}));
        throw new Error(err.detail ?? 'Failed to place unit');
      }
    },

    /**
     * Remove a unit via REST POST /remove_unit.
     * The server will broadcast the removal to all WebSocket clients.
     */
    async removeUnitById(id: string): Promise<void> {
      const resp = await fetch('http://localhost:8000/remove_unit', {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({ id }),
      });
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}));
        throw new Error(err.detail ?? 'Failed to remove unit');
      }
    },

    /** Change the global weather state via REST POST /set_weather (EXCON only) */
    async setWeather(weather: Weather): Promise<void> {
      const resp = await fetch('http://localhost:8000/set_weather', {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({ weather }),
      });
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}));
        throw new Error(err.detail ?? 'Failed to set weather');
      }
    },

    /** Read the current state synchronously. */
    getState(): GameState {
      return get({ subscribe });
    },
  };
}

export const gameState = createGameStateStore();
