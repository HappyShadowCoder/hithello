<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import { auth } from './auth';
  import type { AuthState } from './auth';

  const dispatch = createEventDispatcher<{ login: AuthState }>();

  let username = '';
  let password = '';
  let errorMsg = '';
  let isFading = false;
  let isSysconMode = false;
  let isLoading = false;

  async function submitLogin() {
    if (!username || !password) {
      errorMsg = 'PLEASE ENTER CREDENTIALS';
      return;
    }
    
    errorMsg = '';
    isLoading = true;
    
    try {
      const formData = new URLSearchParams();
      formData.append('username', username);
      formData.append('password', password);

      const res = await fetch('http://localhost:8000/login', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: formData.toString()
      });

      if (!res.ok) {
        errorMsg = 'AUTHORISATION FAILED';
        isLoading = false;
        return;
      }

      const data = await res.json();
      
      if (isSysconMode && data.role !== 'syscon') {
         errorMsg = 'INSUFFICIENT CLEARANCE FOR SYSCON';
         isLoading = false;
         return;
      }

      isFading = true;
      const authState: AuthState = {
        token: data.access_token,
        role: data.role,
        team_id: data.team_id,
        team_color: data.team_color,
        team_name: data.team_name
      };

      setTimeout(() => {
        auth.setAuth(authState);
        dispatch('login', authState);
      }, 500);

    } catch (e) {
      errorMsg = 'NETWORK ERROR';
      isLoading = false;
    }
  }

  function handleKeydown(e: KeyboardEvent) {
    if (e.key === 'Enter') submitLogin();
  }
</script>

<div class="login-screen" class:fading={isFading}>

  <!-- Animated background grid -->
  <div class="bg-grid" aria-hidden="true"></div>
  <div class="bg-radial" aria-hidden="true"></div>
  <div class="scanlines" aria-hidden="true"></div>

  <!-- Header -->
  <header class="login-header">
    <div class="header-line top-line"></div>
    <div class="header-content">
      <span class="header-icon">⛰</span>
      <div class="header-titles">
        <h1 class="header-title">MOPT</h1>
        <p class="header-sub">Mountain Operations Planning Tool</p>
      </div>
      <div class="header-classify">
        <span class="classify-badge">EXERCISE USE ONLY</span>
      </div>
    </div>
    <div class="header-line bottom-line"></div>
  </header>

  <!-- Login Form -->
  <div class="login-container" class:syscon={isSysconMode}>
    <div class="login-card">
       <span class="corner tl" aria-hidden="true"></span>
       <span class="corner tr" aria-hidden="true"></span>
       <span class="corner bl" aria-hidden="true"></span>
       <span class="corner br" aria-hidden="true"></span>
       
       <h2 class="form-title">{isSysconMode ? 'SYSCON PORTAL' : 'OPERATIONAL LOGIN'}</h2>
       <p class="form-sub">{isSysconMode ? 'SYSTEM CONTROLLER ACCESS' : 'ENTER CREDENTIALS'}</p>
       
       <div class="auth-area">
          <input 
            type="text" 
            class="input-field" 
            placeholder="USERNAME" 
            bind:value={username} 
            on:keydown={handleKeydown}
          />
          <input 
            type="password" 
            class="input-field" 
            placeholder="PASSWORD" 
            bind:value={password} 
            on:keydown={handleKeydown}
          />
          <button 
            class="auth-btn" 
            on:click={submitLogin}
            disabled={isLoading}
          >
            {isLoading ? 'AUTHENTICATING...' : 'AUTHENTICATE'}
          </button>
          {#if errorMsg}
            <div class="auth-error">{errorMsg}</div>
          {/if}
       </div>
    </div>
  </div>
  
  {#if !isSysconMode}
    <button class="syscon-toggle" on:click={() => { isSysconMode = true; errorMsg = ''; }}>
       [ ACCESS SYSTEM CONTROLLER ]
    </button>
  {:else}
    <button class="syscon-toggle" on:click={() => { isSysconMode = false; errorMsg = ''; }}>
       [ RETURN TO OPERATIONAL LOGIN ]
    </button>
  {/if}

  <!-- Footer -->
  <footer class="login-footer">
    <span class="footer-text">UNCLASSIFIED // FOR EXERCISE USE ONLY // NOT FOR OPERATIONAL USE</span>
  </footer>

</div>

<style>
  .login-screen {
    position: fixed; inset: 0; display: flex; flex-direction: column;
    align-items: center; justify-content: center; gap: 32px;
    background: #030608; font-family: 'Inter', system-ui, sans-serif;
    overflow: hidden; transition: opacity 0.5s ease; z-index: 100;
  }
  .login-screen.fading { opacity: 0; pointer-events: none; }

  .bg-grid {
    position: absolute; inset: 0;
    background-image: linear-gradient(rgba(40,100,200,0.06) 1px, transparent 1px),
                      linear-gradient(90deg, rgba(40,100,200,0.06) 1px, transparent 1px);
    background-size: 48px 48px; animation: gridDrift 20s linear infinite;
  }
  @keyframes gridDrift { 0% { background-position: 0 0; } 100% { background-position: 48px 48px; } }
  .bg-radial { position: absolute; inset: 0; background: radial-gradient(ellipse 70% 60% at 50% 50%, rgba(20,50,120,0.35) 0%, transparent 70%); pointer-events: none; }
  .scanlines { position: absolute; inset: 0; pointer-events: none; background: repeating-linear-gradient(0deg, transparent, transparent 2px, rgba(0,0,0,0.06) 2px, rgba(0,0,0,0.06) 4px); }

  .login-header { position: relative; width: 100%; max-width: 960px; padding: 0 24px; }
  .header-line { height: 1px; background: linear-gradient(90deg, transparent 0%, rgba(80,140,255,0.5) 30%, rgba(80,140,255,0.5) 70%, transparent 100%); }
  .top-line { margin-bottom: 16px; } .bottom-line { margin-top: 16px; }
  .header-content { display: flex; align-items: center; gap: 18px; }
  .header-icon { font-size: 32px; color: #ddeeff; }
  .header-titles { flex: 1; }
  .header-title { margin: 0; font-size: 28px; font-weight: 800; letter-spacing: 8px; color: #ddeeff; text-transform: uppercase; line-height: 1; }
  .header-sub { margin: 4px 0 0; font-size: 11px; letter-spacing: 3px; color: rgba(140,185,255,0.55); text-transform: uppercase; }
  .classify-badge { font-size: 10px; font-weight: 700; letter-spacing: 2px; color: rgba(255,220,80,0.8); border: 1px solid rgba(255,220,80,0.3); border-radius: 3px; padding: 4px 10px; text-transform: uppercase; white-space: nowrap; }

  .login-container { margin-top: 20px; transition: all 0.3s; --accent: #4d9fff; }
  .login-container.syscon { --accent: #ff4d4d; }

  .login-card {
    position: relative; padding: 40px; background: rgba(6,12,26,0.85);
    border: 1px solid rgba(80,140,255,0.18); border-radius: 12px;
    text-align: center; backdrop-filter: blur(16px);
    box-shadow: 0 8px 40px var(--accent)25, 0 0 80px var(--accent)10;
    width: 320px;
  }

  .corner { position: absolute; width: 16px; height: 16px; border-color: var(--accent); border-style: solid; opacity: 0.8; }
  .tl { top: 8px; left: 8px; border-width: 2px 0 0 2px; }
  .tr { top: 8px; right: 8px; border-width: 2px 2px 0 0; }
  .bl { bottom: 8px; left: 8px; border-width: 0 0 2px 2px; }
  .br { bottom: 8px; right: 8px; border-width: 0 2px 2px 0; }

  .form-title { margin: 0; font-size: 18px; font-weight: 800; letter-spacing: 4px; color: var(--accent); }
  .form-sub { margin: 8px 0 24px; font-size: 10px; letter-spacing: 2px; color: rgba(160,190,240,0.5); }

  .auth-area { display: flex; flex-direction: column; gap: 12px; }
  .input-field {
    background: rgba(0,0,0,0.4); border: 1px solid var(--accent); border-radius: 4px;
    padding: 10px; font-size: 12px; letter-spacing: 1px; color: var(--accent);
    outline: none; text-align: center; font-family: inherit;
  }
  .input-field::placeholder { color: var(--accent); opacity: 0.5; letter-spacing: 2px; font-size: 10px; }
  .auth-btn {
    background: var(--accent); color: #000; border: none; border-radius: 4px;
    padding: 10px; font-size: 11px; font-weight: 800; letter-spacing: 2px;
    cursor: pointer; transition: opacity 0.2s;
  }
  .auth-btn:hover { opacity: 0.8; }
  
  .auth-error { font-size: 9px; color: #ff4d4d; letter-spacing: 1px; font-weight: 700; animation: shake 0.3s; }
  @keyframes shake { 0%, 100% { transform: translateX(0); } 25% { transform: translateX(-4px); } 75% { transform: translateX(4px); } }

  .syscon-toggle {
    background: transparent; border: none; color: rgba(140,185,255,0.5);
    font-size: 10px; letter-spacing: 2px; cursor: pointer; transition: color 0.2s;
    font-family: inherit; z-index: 10;
  }
  .syscon-toggle:hover { color: #fff; }

  .login-footer { position: absolute; bottom: 16px; left: 0; right: 0; text-align: center; z-index: 10; }
  .footer-text { font-size: 9px; letter-spacing: 1.5px; color: rgba(100,130,180,0.35); text-transform: uppercase; }
</style>
