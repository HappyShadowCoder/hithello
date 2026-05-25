<script lang="ts">
  import { auth } from './lib/auth';
  import { gameState } from './lib/gameState';
  
  import LoginScreen from './lib/LoginScreen.svelte';
  import Map from './lib/Map.svelte';
  import SystemController from './lib/SystemController.svelte';
  
  import type { AuthState } from './lib/auth';

  function onLogin(event: CustomEvent<AuthState>) {
    if (event.detail.role !== 'syscon') {
      gameState.connect(event.detail);
    }
  }
</script>

{#if $auth.token === null}
  <LoginScreen on:login={onLogin} />
{:else if $auth.role === 'syscon'}
  <SystemController />
{:else}
  <Map />
{/if}

<style>
  :global(*, *::before, *::after) {
    box-sizing: border-box;
    margin: 0;
    padding: 0;
  }

  :global(html, body, #app) {
    width: 100%;
    height: 100%;
    overflow: hidden;
    background: #030608;
  }
</style>
