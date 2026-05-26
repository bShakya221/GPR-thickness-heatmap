# Nexus GPR Intelligence

An interactive, serverless-ready web application for analyzing Ground Penetrating Radar (GPR) pavement thickness telemetry against physical geolocational sequences.

This application accepts GPR traces (`.OUT`) mapped to High-Resolution GPS routes (`.KML`), interpolates them dynamically via the Haversine formula, and renders them instantly on interactive satellite topographies and analytical distribution maps.

## Architecture Structure
The application has been unified to run smoothly as a standalone Web Service bypassing rigorous corporate IT firewalls (100% ephemeral processing, zero persistent storage).

- **Frontend:** Vanilla JS powered by Vite, using the custom stylesheet in `frontend/src/style.css`.
- **Backend:** **Python/FastAPI** orchestrating Pandas, Folium, Branca, and Excel export logic to pipe visualizations straight back to the client.
- **Excel export:** `analysis_results.xlsx` includes the full interpolated data plus native Excel chart sheets for the longitudinal profile and thickness distribution.

## Operating Environments

### Local Development Usage
For the closest match to production, build the frontend and let FastAPI serve both the UI and API from one origin:

```bash
cd frontend
npm install
npm run build
```

```bash
cd backend
pip install -r requirements.txt
python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000`.

For Vite hot reload, run the backend separately and point the frontend at it:

```bash
cd backend
python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

```bash
cd frontend
$env:VITE_API_BASE="http://127.0.0.1:8000"
npm run dev
```

If Windows blocks port `8000`, choose another port for Uvicorn and use the same value in `VITE_API_BASE`.

### Production Usage (Google Cloud Run)
Deploy from the `gpr_web_tool` directory so Cloud Build only uploads the app, not the raw project data files in the parent folder.

```bash
gcloud run deploy gpr-thickness-map \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --memory 1Gi \
  --cpu 1 \
  --concurrency 2 \
  --max-instances 20 \
  --timeout 900
```

For the lowest fixed cost, leave minimum instances at the Cloud Run default of `0`. For lower cold-start lag during client use, set one warm instance:

```bash
gcloud run services update gpr-thickness-map \
  --region us-central1 \
  --min-instances 1
```

### Automatic GitHub Deploys
Commits pushed to `main` can deploy automatically through GitHub Actions. See `docs/cloud-run-cicd.md` for the one-time Google Cloud and GitHub setup.
