# SmartNav AI — Local Setup, Android Mobile Testing & Deployment Guide

## 1. Local Development Setup

### Prerequisites
- Node.js 20+ and npm
- Python 3.11+
- Docker (optional, for PostgreSQL + PostGIS) or a managed PostgreSQL/PostGIS database (e.g., Supabase)

### Step 1: Start PostgreSQL + PostGIS (Optional via Docker)
```bash
cd smartnav-ai
docker compose up -d postgres
```
If you want to run locally without Docker or PostgreSQL during quick evaluation, leave `DATABASE_URL` unset (it defaults to local SQLite `smartnav.db`).

### Step 2: Configure Environment Variables
Copy `.env.example` to `.env` in `smartnav-ai/`:
```bash
cp .env.example .env
```
Update `SECRET_KEY` and `DATABASE_URL` as needed.

### Step 3: Start the Backend (FastAPI)
```bash
cd smartnav-ai/backend
python -m venv .venv
# Windows PowerShell:
.\.venv\Scripts\Activate.ps1
# macOS/Linux:
# source .venv/bin/activate

pip install -r requirements.txt
# Run Alembic migrations when using PostgreSQL/PostGIS:
# alembic upgrade head
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
Swagger API documentation is available at `http://localhost:8000/docs`.

### Step 4: Start the Frontend (React + Vite)
```bash
cd smartnav-ai/frontend
npm install
npm run dev
```
Open `http://localhost:5173`.

---

## 2. Testing Real Mobile GPS Using an Android Phone & Laptop

Modern mobile browsers (Chrome on Android, Safari on iOS) **block `navigator.geolocation` on non-HTTPS origins** (except `localhost`). When accessing your laptop's dev server from an Android phone over Wi-Fi (e.g., `https://192.168.x.x:5173`), you **must** use HTTPS.

### Option A: Built-in Vite HTTPS Mode (Same Wi-Fi Network)
1. Ensure your laptop and Android phone are on the same Wi-Fi network.
2. Start the backend on `0.0.0.0:8000`:
   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```
3. Start Vite with HTTPS enabled (`@vitejs/plugin-basic-ssl` is preconfigured in `vite.config.js` and proxies `/api` to `127.0.0.1:8000`, avoiding mixed-content blocks):
   - **Windows PowerShell**:
     ```powershell
     $env:HTTPS="true"; npm run dev
     ```
   - **macOS/Linux**:
     ```bash
     HTTPS=true npm run dev
     ```
4. Find your laptop's LAN IP (`ipconfig` on Windows or `ifconfig` on macOS/Linux), e.g. `192.168.1.42`.
5. On your Android phone, open Chrome and navigate to `https://192.168.1.42:5173`.
6. Accept the local self-signed development certificate warning ("Advanced -> Proceed").
7. Tap **Live GPS** or **Current Location** and grant Chrome permission to access **Precise Location**.
8. Walk or drive outdoors to observe real latitude/longitude, accuracy radius (meters), speed (km/h), heading arrow, and automatic route recalculation.

### Option B: HTTPS Tunnel (Recommended for Trusted SSL)
Use Cloudflare Tunnel (`cloudflared tunnel --url http://localhost:5173`) or ngrok (`ngrok http 5173`) to get a valid public `https://` URL that works immediately on Android without certificate prompts.

### Foreground vs. Background Browser Tracking Limitations
- **Supported**: SmartNav AI supports continuous **foreground browser GPS tracking** while the browser tab is active and the screen stays awake.
- **Limitation**: Mobile web browsers (Android Chrome, iOS Safari) suspend or throttle JavaScript timers and `navigator.geolocation.watchPosition()` callbacks when the user switches apps, minimizes the browser, or locks the phone screen. True background GPS navigation while the screen is off requires a native Android/iOS app (using Android Foreground Services) or a wrapper such as Capacitor/React Native. Keep the screen awake in foreground mode during trips.

---

## 3. Production Deployment (Vercel + Render + Supabase)

1. **Database (Supabase PostgreSQL + PostGIS)**:
   - Create a Supabase project.
   - Enable the `postgis` extension in Supabase SQL Editor: `CREATE EXTENSION IF NOT EXISTS postgis;`
   - Copy the Postgres connection string (`postgresql+psycopg://postgres:<PASSWORD>@db.<PROJECT>.supabase.co:5432/postgres`).

2. **Backend (Render)**:
   - Connect the repository using `render.yaml` (`rootDir: smartnav-ai/backend`).
   - Set `DATABASE_URL` to your Supabase connection string and `CORS_ORIGINS` to your Vercel HTTPS domain (`https://your-app.vercel.app`).
   - Render runs `alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT`.

3. **Frontend (Vercel)**:
   - Set Root Directory to `smartnav-ai/frontend`.
   - Add environment variable `VITE_API_BASE_URL=https://your-render-backend.onrender.com/api`.
   - Deploy (`vercel.json` handles SPA routing and `Permissions-Policy: geolocation=(self)` over HTTPS).
