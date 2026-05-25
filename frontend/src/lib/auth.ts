import { writable, get } from 'svelte/store';

export type Role = 'syscon' | 'excon' | 'player';

export interface AuthState {
  token: string | null;
  role: Role | null;
  team_id: number | null;
  team_color: string | null;
  team_name: string | null;
}

const SESSION_KEY = 'mopt_auth';

function createAuthStore() {
  const storedStr = sessionStorage.getItem(SESSION_KEY);
  let stored: AuthState = {
    token: null,
    role: null,
    team_id: null,
    team_color: null,
    team_name: null,
  };
  
  if (storedStr) {
    try {
      stored = JSON.parse(storedStr);
    } catch (e) {
      console.error("Failed to parse auth state");
    }
  }

  const { subscribe, set } = writable<AuthState>(stored);

  return {
    subscribe,

    setAuth(state: AuthState): void {
      sessionStorage.setItem(SESSION_KEY, JSON.stringify(state));
      set(state);
    },

    clearAuth(): void {
      sessionStorage.removeItem(SESSION_KEY);
      set({
        token: null,
        role: null,
        team_id: null,
        team_color: null,
        team_name: null,
      });
    },

    getAuth(): AuthState {
      return get({ subscribe });
    },
  };
}

export const auth = createAuthStore();

export const ROLE_LABELS: Record<Role, string> = {
  syscon: 'SYSTEM CONTROLLER',
  excon:  'EXCON',
  player: 'PLAYER',
};

export const ROLE_COLOURS: Record<Role, string> = {
  syscon: '#aaaaaa',  // grey
  excon:  '#f5c518',  // gold
  player: '#ffffff',  // dynamically overridden by team color
};
