# MOPT (Mountain Operations Planning Tool)

## Setup Instructions

### Backend Setup
1. Navigate to the backend directory:
   ```bash
   cd backend
   ```
2. Create and activate a virtual environment:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Set up the environment variables (e.g., copy `.env.example` to `.env` if applicable).
5. Initialize the database if needed:
   ```bash
   python init_db.py
   ```

### Frontend Setup
1. Navigate to the frontend directory:
   ```bash
   cd frontend
   ```
2. Install dependencies:
   ```bash
   npm install
   ```

## Running the Code

### 1. Run the Backend (Python FastAPI)

The backend handles trajectory math, FAHP calculations, and the WebSocket server for real-time multiplayer updates.

Open a terminal and run the following commands:

```bash
# Navigate to the backend folder
cd backend

# Activate the virtual environment
source .venv/bin/activate

# Start the server (runs on port 8000)
uvicorn main:app --reload --port 8000
```

*Note: The server is ready when you see "Application startup complete." in the output.*

### 2. Run the Frontend (SvelteKit)

The frontend is a web app using the ArcGIS Maps SDK for 3D terrain and viewshed analysis.

Open a **new, separate** terminal window and run:

```bash
# Navigate to the frontend folder
cd frontend

# Start the development server (runs on port 5173)
npm run dev
```

### 3. Open the Application

1. Open your web browser and go to: [http://localhost:5173](http://localhost:5173)
2. You should see the Premium Military Login Screen.

---

## Testing Phase 5: Multiplayer & Fog of War

To see the real-time WebSocket synchronization and Fog of War filtering in action:

1. Open **three separate browser tabs**, all pointing to `http://localhost:5173`.
2. **Tab 1:** Select **EXCON**. 
   - Use the top toolbar to switch from "👁 Viewshed" to "■ Blue Unit" or "■ Red Unit". 
   - Click anywhere on the map to place units. They will appear instantly.
3. **Tab 2:** Select **BLUE TEAM**. 
   - You will see the units placed by EXCON in real-time. 
   - **Fog of War:** You will *always* see Blue units, but you will only see Red units if they fall inside a Viewshed that you have computed (by clicking on the map).
4. **Tab 3:** Select **RED TEAM**. 
   - Similar to Blue Team, you will *always* see Red units, but Blue units are hidden unless they fall within your calculated Viewshed.
