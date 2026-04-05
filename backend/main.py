from fastapi import FastAPI, UploadFile, File, Form, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
import pandas as pd
import numpy as np
import folium
import branca.colormap as bcm
from branca.element import Template, MacroElement
import re
import math
import os
import uuid
import tempfile
import shutil

app = FastAPI(title="GPR Web Tool API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

TEMP_DIR = os.path.join(tempfile.gettempdir(), "gpr_web_tool")
os.makedirs(TEMP_DIR, exist_ok=True)

def haversine(lat1, lon1, lat2, lon2):
    R = 3958.8 # miles
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    return R * c * 5280

@app.get("/api/health")
def read_root():
    return {"status": "ok"}

@app.post("/preview")
async def preview_data(
    gpr_file: UploadFile = File(...)
):
    try:
        # Create a temporary file to read the data
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            shutil.copyfileobj(gpr_file.file, tmp)
            tmp_path = tmp.name

        # Read GPR outputs (sample only)
        df = pd.read_csv(tmp_path, sep=r'\s+', skiprows=5, header=None, names=range(12))
        os.remove(tmp_path)
        
        # Sort and take a dense sample for sparklines
        df = df.sort_values(by=1).dropna(subset=[1])
        
        # Downsample for preview speed (max 500 points)
        sample_size = min(len(df), 500)
        indices = np.linspace(0, len(df) - 1, sample_size, dtype=int)
        sample_df = df.iloc[indices]
        
        columns_preview = []
        # We check columns 2 through 11
        for col_idx in range(2, 12):
            series = sample_df[col_idx].fillna(0).tolist()
            # Basic validation: if all zeros or negative, we mark as likely empty
            is_empty = all(v <= 0 for v in series)
            
            columns_preview.append({
                "index": col_idx,
                "name": f"Layer {col_idx - 1}",
                "data": series,
                "is_empty": is_empty,
                "mean": float(sample_df[col_idx].mean()) if not is_empty else 0
            })
            
        return {
            "status": "success",
            "columns": columns_preview,
            "total_traces": len(df)
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.post("/analyze")
async def analyze_data(
    kml_file: UploadFile = File(...),
    gpr_file: UploadFile = File(...),
    antenna_offset: float = Form(0.0),
    title: str = Form("HMA Thickness"),
    thickness_column: int = Form(6)
):
    session_id = str(uuid.uuid4())
    session_dir = os.path.join(TEMP_DIR, session_id)
    os.makedirs(session_dir, exist_ok=True)
    
    kml_path = os.path.join(session_dir, kml_file.filename)
    gpr_path = os.path.join(session_dir, gpr_file.filename)
    
    with open(kml_path, "wb") as f:
        shutil.copyfileobj(kml_file.file, f)
    with open(gpr_path, "wb") as f:
        shutil.copyfileobj(gpr_file.file, f)
        
    try:
        # 1. Parse KML for physical route
        with open(kml_path, 'r', encoding='utf-8', errors='ignore') as f:
            kml_text = f.read()
            
        coords_match = re.search(r'<LineString>.*?<coordinates>(.*?)</coordinates>', kml_text, re.DOTALL)
        if not coords_match:
            return JSONResponse(status_code=400, content={"error": "Coordinates not found in KML"})
            
        coords_str = coords_match.group(1).strip()
        gps_points = []
        for line in coords_str.split('\n'):
            parts = line.strip().split(',')
            if len(parts) >= 2:
                gps_points.append((float(parts[1]), float(parts[0]))) # lat, lon
                
        # 2. Compute cumulative geographic distances
        kml_dist = [0.0]
        for i in range(1, len(gps_points)):
            dist = haversine(gps_points[i-1][0], gps_points[i-1][1], gps_points[i][0], gps_points[i][1])
            kml_dist.append(kml_dist[-1] + dist)
        kml_total_dist = kml_dist[-1]
        
        # 3. Read & Align GPR outputs
        df = pd.read_csv(gpr_path, sep=r'\s+', skiprows=5, header=None, names=range(12))
        df = df.sort_values(by=1).dropna(subset=[1])
        
        dmi_min = df[1].min()
        dmi_max = df[1].max()
        gpr_pct = (df[1] - dmi_min) / (dmi_max - dmi_min)
        target_dist = (gpr_pct * kml_total_dist) + antenna_offset
        
        lats = [p[0] for p in gps_points]
        lons = [p[1] for p in gps_points]
        
        df['Interp_Lat'] = np.interp(target_dist, kml_dist, lats)
        df['Interp_Lon'] = np.interp(target_dist, kml_dist, lons)
        
        plot_df = df.dropna(subset=[thickness_column]).copy()
        
        # 4. Interactive Map
        center_lat = np.mean([lats[0], lats[-1]])
        center_lon = np.mean([lons[0], lons[-1]])
        
        m = folium.Map(location=[center_lat, center_lon], zoom_start=15, control_scale=True, tiles='OpenStreetMap')
        folium.TileLayer(
            tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
            attr='Esri', name='Satellite View', overlay=False, control=True
        ).add_to(m)
        
        colormap = bcm.LinearColormap(colors=['red', 'crimson', 'blue', 'limegreen'], index=[2.0, 3.0, 4.0, 7.0], vmin=2.0, vmax=7.0)
        colormap.caption = f'{title} (Inches)'
        m.add_child(colormap)
        
        macro = MacroElement()
        macro._template = Template("""
        {% macro html(this, kwargs) %}
        <style>
          svg:not([class]) { background-color: rgba(255, 255, 255, 0.85) !important; border-radius: 8px !important; box-shadow: 2px 2px 6px rgba(0,0,0,0.3) !important; padding: 10px !important; margin-top: 10px !important; margin-left: 10px !important; z-index: 9999 !important; }
        </style>
        {% endmacro %}
        """)
        m.get_root().add_child(macro)
        
        feature_group = folium.FeatureGroup(name='HMA Thickness')
        sample_stride = max(1, len(plot_df) // 3000)
        
        for idx, row in plot_df.iloc[::sample_stride].iterrows():
            val = row[thickness_column]
            folium.CircleMarker(
                location=(row['Interp_Lat'], row['Interp_Lon']), radius=3.5, weight=0, fill=True,
                fill_color=colormap(val), fill_opacity=0.85,
                tooltip=f"<b>DMI Track:</b> {row[1]:.0f}<br><b>Thickness:</b> {val:.2f}"
            ).add_to(feature_group)
        feature_group.add_to(m)
        folium.LayerControl().add_to(m)
        
        map_path = os.path.join(session_dir, 'map.html')
        m.save(map_path)
        
        # 4.5 Calculate Statistics
        thickness_vals = plot_df[thickness_column].dropna()
        stats_mean = float(thickness_vals.mean())
        stats_std = float(thickness_vals.std())
        stats_min = float(thickness_vals.min())
        stats_max = float(thickness_vals.max())
        
        # 4.6 Excel Export
        excel_path = os.path.join(session_dir, 'analysis_results.xlsx')
        export_df = plot_df[[1, 'Interp_Lat', 'Interp_Lon', thickness_column]].copy()
        export_df.columns = ['DMI_Feet', 'Latitude', 'Longitude', 'Thickness_Inches']
        export_df.to_excel(excel_path, index=False)
        
        # 4.7 Prepare Frontend Plot Data (JSON)
        # Downsample profile for frontend performance (target ~2000 points)
        step = max(1, len(plot_df) // 2000)
        profile_json = []
        last_dmi = None
        for _, row in plot_df.iloc[::step].iterrows():
            curr_dmi = float(row[1])
            
            # If gap > 100ft, insert a null point to break the continuous line in ApexCharts
            if last_dmi is not None and (curr_dmi - last_dmi) > 100:
                profile_json.append({
                    "x": round(last_dmi + 1, 2),
                    "y": None,
                    "lat": float(row['Interp_Lat']),
                    "lon": float(row['Interp_Lon'])
                })
                
            profile_json.append({
                "x": round(curr_dmi, 2),
                "y": round(float(row[thickness_column]), 3),
                "lat": float(row['Interp_Lat']),
                "lon": float(row['Interp_Lon'])
            })
            last_dmi = curr_dmi
            
        # Prepare Distribution Data (Histogram Bins)
        counts, bin_edges = np.histogram(thickness_vals, bins=20)
        dist_json = []
        for i in range(len(counts)):
            dist_json.append({
                "x": round(float((bin_edges[i] + bin_edges[i+1]) / 2), 2),
                "y": int(counts[i])
            })
        
        return {
            "status": "success",
            "session_id": session_id,
            "map_url": f"/results/{session_id}/map.html",
            "excel_url": f"/results/{session_id}/analysis_results.xlsx",
            "chart_data": {
                "profile": profile_json,
                "distribution": dist_json
            },
            "data_summary": {
                "traces_parsed": len(plot_df),
                "total_distance_ft": kml_total_dist,
                "stats": {
                    "mean": round(stats_mean, 2),
                    "std": round(stats_std, 2),
                    "min": round(stats_min, 2),
                    "max": round(stats_max, 2)
                }
            }
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/results/{session_id}/{filename}")
def get_result(session_id: str, filename: str):
    file_path = os.path.join(TEMP_DIR, session_id, filename)
    if os.path.exists(file_path):
        return FileResponse(file_path)
    return JSONResponse(status_code=404, content={"error": "File not found"})

# Important: Mount static folders LAST otherwise it overrides the static API paths
FRONTEND_DEV_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "dist")
if os.path.isdir(FRONTEND_DEV_DIR):
    app.mount("/", StaticFiles(directory=FRONTEND_DEV_DIR, html=True), name="frontend")

if __name__ == "__main__":
    import uvicorn
    # run specifically on port 8000
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

