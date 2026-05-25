/**
 * exerciseStore.ts — Active Exercise State
 * =========================================
 * Holds the current exercise configuration (name, boundaries, ORBAT)
 * set up by EXCON.
 */

import { writable } from 'svelte/store';

export interface Boundaries {
  blue: any | null; // ArcGIS Polygon JSON
  red:  any | null; // ArcGIS Polygon JSON
}

export interface Exercise {
  name:       string;
  boundaries: Boundaries;
  orbat:      any | null; // Parsed JSON
}

function createExerciseStore() {
  const { subscribe, set, update } = writable<Exercise | null>(null);

  return {
    subscribe,
    
    /** Set the active exercise state */
    setExercise(ex: Exercise) {
      set(ex);
    },

    /** Update just the boundaries */
    setBoundary(team: 'blue' | 'red', polygonJSON: any) {
      update(ex => {
        if (!ex) return ex;
        return {
          ...ex,
          boundaries: {
            ...ex.boundaries,
            [team]: polygonJSON
          }
        };
      });
    },
    
    /** Clear the active exercise (e.g. on logout) */
    clear() {
      set(null);
    }
  };
}

export const exerciseStore = createExerciseStore();
