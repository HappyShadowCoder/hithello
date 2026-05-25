<script lang="ts">
  import { onMount } from 'svelte';
  import { auth } from './auth';

  let teams: any[] = [];
  let users: any[] = [];
  
  // Forms
  let newTeamName = '';
  let newTeamColor = '#ffffff';
  
  let newUsername = '';
  let newUserPassword = '';
  let newUserRole = 'player';
  let newUserTeam = '';

  let errorMsg = '';
  let successMsg = '';

  const token = $auth.token;

  async function fetchTeams() {
    const res = await fetch('http://localhost:8000/api/teams', {
      headers: { 'Authorization': `Bearer ${token}` }
    });
    if (res.ok) {
      teams = await res.json();
    }
  }

  async function fetchUsers() {
    const res = await fetch('http://localhost:8000/api/users', {
      headers: { 'Authorization': `Bearer ${token}` }
    });
    if (res.ok) {
      users = await res.json();
    }
  }

  onMount(() => {
    fetchTeams();
    fetchUsers();
  });

  async function createTeam() {
    errorMsg = ''; successMsg = '';
    if (!newTeamName) return;
    
    const res = await fetch('http://localhost:8000/api/teams', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      },
      body: JSON.stringify({ name: newTeamName, color: newTeamColor })
    });

    if (res.ok) {
      successMsg = 'TEAM CREATED';
      newTeamName = '';
      fetchTeams();
    } else {
      const data = await res.json();
      errorMsg = data.detail || 'ERROR CREATING TEAM';
    }
  }

  async function createUser() {
    errorMsg = ''; successMsg = '';
    if (!newUsername || !newUserPassword) return;
    
    const payload: any = {
      username: newUsername,
      password: newUserPassword,
      role: newUserRole
    };
    if (newUserRole === 'player') {
      if (!newUserTeam) {
         errorMsg = 'SELECT A TEAM FOR PLAYER';
         return;
      }
      payload.team_id = parseInt(newUserTeam);
    }

    const res = await fetch('http://localhost:8000/api/users', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      },
      body: JSON.stringify(payload)
    });

    if (res.ok) {
      successMsg = 'USER CREATED';
      newUsername = '';
      newUserPassword = '';
      fetchUsers();
    } else {
      const data = await res.json();
      errorMsg = data.detail || 'ERROR CREATING USER';
    }
  }

  function logout() {
    auth.clearAuth();
  }
</script>

<div class="syscon-layout">
  <header class="syscon-header">
    <h1>SYSCON DASHBOARD</h1>
    <button class="logout-btn" on:click={logout}>LOGOUT</button>
  </header>

  <div class="syscon-content">
    <!-- Messages -->
    {#if errorMsg}
      <div class="msg error">{errorMsg}</div>
    {/if}
    {#if successMsg}
      <div class="msg success">{successMsg}</div>
    {/if}

    <div class="panels">
      <!-- Teams Panel -->
      <div class="panel">
        <h2>TEAMS</h2>
        <div class="list">
          {#each teams as team}
            <div class="list-item">
               <span class="color-dot" style="background: {team.color}"></span>
               {team.name} (ID: {team.id})
            </div>
          {/each}
        </div>
        
        <h3>ADD NEW TEAM</h3>
        <div class="form">
          <input type="text" placeholder="TEAM NAME" bind:value={newTeamName} />
          <div class="color-picker">
             <span>COLOR:</span>
             <input type="color" bind:value={newTeamColor} />
          </div>
          <button on:click={createTeam}>CREATE TEAM</button>
        </div>
      </div>

      <!-- Users Panel -->
      <div class="panel">
        <h2>USERS</h2>
        <div class="list">
          {#each users as user}
            <div class="list-item">
               {user.username} - [{user.role.toUpperCase()}] 
               {#if user.team_id}
                 (Team ID: {user.team_id})
               {/if}
            </div>
          {/each}
        </div>

        <h3>ADD NEW USER</h3>
        <div class="form">
          <input type="text" placeholder="USERNAME" bind:value={newUsername} />
          <input type="password" placeholder="PASSWORD" bind:value={newUserPassword} />
          <select bind:value={newUserRole}>
             <option value="player">PLAYER</option>
             <option value="excon">EXCON</option>
             <option value="syscon">SYSCON</option>
          </select>
          {#if newUserRole === 'player'}
            <select bind:value={newUserTeam}>
               <option value="">SELECT TEAM</option>
               {#each teams as team}
                 <option value={team.id}>{team.name}</option>
               {/each}
            </select>
          {/if}
          <button on:click={createUser}>CREATE USER</button>
        </div>
      </div>
    </div>
  </div>
</div>

<style>
  .syscon-layout {
    width: 100%;
    height: 100%;
    background: #030608;
    color: #ddeeff;
    font-family: 'Inter', system-ui, sans-serif;
    display: flex;
    flex-direction: column;
    overflow-y: auto;
  }
  
  .syscon-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 20px 40px;
    background: rgba(20, 30, 40, 0.5);
    border-bottom: 1px solid rgba(80,140,255,0.2);
  }
  .syscon-header h1 {
    margin: 0;
    font-size: 20px;
    letter-spacing: 4px;
  }
  .logout-btn {
    background: transparent;
    color: #ff4d4d;
    border: 1px solid #ff4d4d;
    padding: 8px 16px;
    cursor: pointer;
    border-radius: 4px;
    letter-spacing: 2px;
  }
  .logout-btn:hover { background: rgba(255, 77, 77, 0.1); }

  .syscon-content {
    padding: 40px;
    flex: 1;
  }
  
  .msg { padding: 12px; border-radius: 4px; margin-bottom: 20px; text-align: center; font-weight: bold; letter-spacing: 2px; }
  .msg.error { background: rgba(255, 77, 77, 0.2); color: #ff4d4d; border: 1px solid #ff4d4d; }
  .msg.success { background: rgba(77, 255, 77, 0.2); color: #4dff4d; border: 1px solid #4dff4d; }

  .panels {
    display: flex;
    gap: 40px;
  }
  .panel {
    flex: 1;
    background: rgba(10, 20, 30, 0.6);
    border: 1px solid rgba(80,140,255,0.2);
    border-radius: 8px;
    padding: 24px;
  }
  
  .panel h2 { margin: 0 0 16px 0; font-size: 16px; letter-spacing: 3px; color: #4d9fff; border-bottom: 1px solid rgba(80,140,255,0.2); padding-bottom: 8px; }
  .panel h3 { margin: 24px 0 12px 0; font-size: 12px; letter-spacing: 2px; color: rgba(221, 238, 255, 0.7); }

  .list {
    max-height: 200px;
    overflow-y: auto;
    background: rgba(0, 0, 0, 0.3);
    border-radius: 4px;
    padding: 12px;
    margin-bottom: 20px;
  }
  .list-item {
    display: flex;
    align-items: center;
    padding: 8px 0;
    border-bottom: 1px solid rgba(255,255,255,0.05);
    font-size: 12px;
    letter-spacing: 1px;
  }
  .color-dot {
    width: 12px; height: 12px; border-radius: 50%; margin-right: 12px; border: 1px solid rgba(255,255,255,0.3);
  }

  .form {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }
  .form input[type="text"], .form input[type="password"], .form select {
    background: rgba(0, 0, 0, 0.5);
    border: 1px solid rgba(80,140,255,0.3);
    color: #fff;
    padding: 10px;
    border-radius: 4px;
    font-family: inherit;
    font-size: 12px;
    letter-spacing: 1px;
  }
  
  .color-picker {
    display: flex; align-items: center; gap: 12px; font-size: 12px; letter-spacing: 1px;
  }
  .color-picker input[type="color"] {
    background: transparent; border: none; cursor: pointer; height: 32px; width: 48px;
  }

  .form button {
    background: #4d9fff;
    color: #000;
    border: none;
    padding: 12px;
    font-weight: bold;
    letter-spacing: 2px;
    border-radius: 4px;
    cursor: pointer;
  }
  .form button:hover { opacity: 0.8; }
</style>
