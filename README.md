# Nexus GPR Intelligence

An interactive, serverless-ready web application for analyzing Ground Penetrating Radar (GPR) pavement thickness telemetry against physical geolocational sequences.

This application accepts GPR traces (`.OUT`) mapped to High-Resolution GPS routes (`.KML`), interpolates them dynamically via the Haversine formula, and renders them instantly on interactive satellite topographies and analytical distribution maps.

## Architecture Structure
The application has been unified to run smoothly as a standalone Web Service bypassing rigorous corporate IT firewalls (100% ephemeral processing, zero persistent storage).

- **Frontend:** Vanilla JS powered by Vite, utilizing **Tailwind CSS v3** for a dynamic glassmorphic interface.
- **Backend:** **Python/FastAPI** orchestrating Pandas, Folium, and Matplotlib logic to pipe visualizations straight back to the client.

## Operating Environments

### Local Development Usage
To test updates locally:
1. Initialize the UI builder:
```bash
cd frontend
npm install
npm run dev
```

2. Spin up the API in a different terminal:
```bash
cd backend
pip install -r requirements.txt
python main.py
```

### Production Usage (Render / Cloud Deployment)
This repository is pre-configured to deploy dynamically as a centralized Web Service.

**Build Pipeline:** The root `build.sh` will seamlessly transpile the Tailwind static assets into `frontend/dist/` and establish the python environment automatically.

**Engine Commands:** Fast API automatically intercepts routing dynamically. Use standard Uvicorn commands.
```bash
./build.sh
cd backend && uvicorn main:app --host 0.0.0.0 --port $PORT
```
