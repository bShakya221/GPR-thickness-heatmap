from fastapi import FastAPI, UploadFile, File, Form, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
import pandas as pd
import numpy as np
import folium
import branca.colormap as bcm
import matplotlib
matplotlib.use('Agg') # important for server contexts to avoid threading issues
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
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

@app.post("/analyze")
async def analyze_data(
    kml_file: UploadFile = File(...),
    gpr_file: UploadFile = File(...),
    thickness_column: int = Form(6),
    antenna_offset: float = Form(0.0),
    title: str = Form("HMA Thickness")
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
        
        # 5. Chart rendering
        plot_df_chart = df[[1, thickness_column]].sort_values(by=1)
        gap_mask = plot_df_chart[1].diff() > 100
        if gap_mask.any():
            gap_indices = plot_df_chart.index[gap_mask]
            nan_rows = pd.DataFrame(index=gap_indices - 0.5, columns=plot_df_chart.columns)
            plot_df_chart = pd.concat([plot_df_chart, nan_rows]).sort_index()
            plot_df_chart = plot_df_chart.sort_values(by=1)
            
        # Using a default font to avoid 'Verdana' missing on different OS
        fig, ax = plt.subplots(figsize=(10, 4.89), facecolor='#e6e6e6')
        ax.set_facecolor('#e6e6e6')
        if not plot_df_chart.empty:
            ax.plot(plot_df_chart[1], plot_df_chart[thickness_column], '-', linewidth=1.5, alpha=0.9, color='forestgreen', label='HMA Thickness', zorder=2)
            
        for spine in ax.spines.values():
            spine.set_visible(True)
            spine.set_color('#333333')
            spine.set_linewidth(1.2)
            
        ax.tick_params(direction='in', length=5, width=1.0, colors='#111111', pad=8, labelsize=9)
        ax.set_title(f'{title} Profile', fontsize=14, fontweight='bold', color='#111111', pad=15)
        
        def format_ft_to_mi_ft(x, pos):
            mi = int(x // 5280)
            ft = int(x % 5280)
            return f'{mi} mi {ft} ft' if mi > 0 else f'{ft} ft'
            
        ax.xaxis.set_major_formatter(ticker.FuncFormatter(format_ft_to_mi_ft))
        plt.xticks(rotation=45)
        ax.set_xlabel('DMI (Miles and Feet)', fontsize=11, fontweight='bold', color='#333333', labelpad=10)
        ax.set_ylabel('Thickness (inches)', fontsize=11, fontweight='bold', color='#333333', labelpad=10)
        ax.set_ylim(1, 8)
        ax.legend(loc='upper right', fontsize=10, frameon=True, facecolor='white', edgecolor='#333333')
        ax.grid(True, linestyle='--', color='#cccccc', alpha=0.8, zorder=0)
        plt.tight_layout()
        
        chart_path = os.path.join(session_dir, 'chart.png')
        plt.savefig(chart_path, dpi=300)
        plt.close(fig)
        
        return {
            "status": "success",
            "session_id": session_id,
            "map_url": f"/results/{session_id}/map.html",
            "chart_url": f"/results/{session_id}/chart.png",
            "data_summary": {
                "traces_parsed": len(plot_df),
                "total_distance_ft": kml_total_dist
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

@app.post("/preview")
async def preview_columns(gpr_file: UploadFile = File(...)):
    try:
        # Read limited rows for performance
        df = pd.read_csv(gpr_file.file, sep=r'\s+', skiprows=5, header=None, nrows=2000, names=range(12))
        df = df.sort_values(by=1).dropna(subset=[1])
        
        previews = {}
        # We start from column 2 (Value 1) up to 11
        for col_idx in range(2, 12):
            if col_idx in df.columns:
                # Get a sample of ~100 points
                series = df[col_idx].dropna()
                if not series.empty:
                    sample_indices = np.linspace(0, len(series) - 1, 100, dtype=int)
                    previews[col_idx] = series.iloc[sample_indices].tolist()
        
        return {"columns": previews}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

# Important: Mount static folders LAST otherwise it overrides the static API paths
FRONTEND_DEV_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "dist")
if os.path.isdir(FRONTEND_DEV_DIR):
    app.mount("/", StaticFiles(directory=FRONTEND_DEV_DIR, html=True), name="frontend")

if __name__ == "__main__":
    import uvicorn
    # run specifically on port 8000
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

