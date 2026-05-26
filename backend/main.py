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

def recommend_thickness_column(columns, default_column=6):
    usable = [col for col in columns if not col["is_empty"]]
    if not usable:
        return None

    plausible = [
        col for col in usable
        if col["positive_ratio"] >= 0.15 and 1.0 <= col["positive_mean"] <= 12.0
    ]
    for col in plausible:
        if col["index"] == default_column:
            return default_column
    candidates = plausible or usable
    return min(candidates, key=lambda col: (abs(col["positive_mean"] - 4.0), col["index"]))["index"]

def write_excel_report(excel_path, export_df, distribution_df, stats, total_distance_ft, title):
    profile_df = export_df[["DMI_Feet", "Thickness_Inches"]].copy()
    summary_rows = [
        ("Analysis", title),
        ("Traces Processed", len(export_df)),
        ("Total Distance (ft)", total_distance_ft),
        ("Average Thickness (in)", stats["mean"]),
        ("Std Deviation (in)", stats["std"]),
        ("Minimum Thickness (in)", stats["min"]),
        ("Maximum Thickness (in)", stats["max"]),
    ]

    with pd.ExcelWriter(excel_path, engine="xlsxwriter") as writer:
        pd.DataFrame(summary_rows, columns=["Metric", "Value"]).to_excel(writer, index=False, sheet_name="Summary")
        export_df.to_excel(writer, index=False, sheet_name="Interpolated Data")
        profile_df.to_excel(writer, index=False, sheet_name="Longitudinal Plot")
        distribution_df.to_excel(writer, index=False, sheet_name="Thickness Distribution")

        wb = writer.book
        header_fmt = wb.add_format({"bold": True, "font_color": "white", "bg_color": "#004F71", "align": "center"})
        integer_fmt = wb.add_format({"num_format": "#,##0"})
        decimal_fmt = wb.add_format({"num_format": "0.00"})
        chart_title_fmt = {"name": "Arial", "size": 11}
        sheets = writer.sheets

        for sheet_name, df in [
            ("Summary", pd.DataFrame(summary_rows, columns=["Metric", "Value"])),
            ("Interpolated Data", export_df),
            ("Longitudinal Plot", profile_df),
            ("Thickness Distribution", distribution_df),
        ]:
            ws = sheets[sheet_name]
            ws.freeze_panes(1, 0)
            ws.set_row(0, None, header_fmt)
            for col_idx, col_name in enumerate(df.columns):
                max_len = max([len(str(col_name))] + [len(str(value)) for value in df[col_name].head(200)])
                ws.set_column(col_idx, col_idx, min(max(max_len + 2, 12), 24))

        data_ws = sheets["Interpolated Data"]
        data_ws.add_table(0, 0, len(export_df), len(export_df.columns) - 1, {
            "name": "InterpolatedData",
            "style": "Table Style Medium 2",
            "columns": [{"header": col} for col in export_df.columns],
        })
        data_ws.set_column("A:A", 14, integer_fmt)
        data_ws.set_column("B:D", 16, decimal_fmt)

        profile_ws = sheets["Longitudinal Plot"]
        profile_ws.add_table(0, 0, len(profile_df), len(profile_df.columns) - 1, {
            "name": "LongitudinalData",
            "style": "Table Style Medium 2",
            "columns": [{"header": col} for col in profile_df.columns],
        })
        profile_ws.set_column("A:A", 14, integer_fmt)
        profile_ws.set_column("B:B", 16, decimal_fmt)
        profile_chart = wb.add_chart({"type": "scatter", "subtype": "straight"})
        profile_chart.add_series({
            "name": "Thickness",
            "categories": ["Longitudinal Plot", 1, 0, len(profile_df), 0],
            "values": ["Longitudinal Plot", 1, 1, len(profile_df), 1],
            "line": {"color": "#CC0000", "width": 1.25},
            "marker": {"type": "none"},
        })
        profile_chart.set_title({"name": "Longitudinal Distribution", "name_font": chart_title_fmt})
        profile_chart.set_x_axis({
            "name": "DMI (ft)",
            "num_format": "#,##0",
            "major_gridlines": {"visible": True, "line": {"color": "#D9D9D9"}},
        })
        profile_chart.set_y_axis({
            "name": "Thickness (in.)",
            "num_format": "0.0",
            "major_gridlines": {"visible": True, "line": {"color": "#D9D9D9"}},
        })
        profile_chart.set_legend({"none": True})
        profile_chart.set_size({"width": 980, "height": 460})
        profile_ws.insert_chart("D2", profile_chart)

        dist_ws = sheets["Thickness Distribution"]
        dist_ws.add_table(0, 0, len(distribution_df), len(distribution_df.columns) - 1, {
            "name": "ThicknessDistribution",
            "style": "Table Style Medium 2",
            "columns": [{"header": col} for col in distribution_df.columns],
        })
        dist_ws.set_column("A:A", 16)
        dist_ws.set_column("B:D", 16, decimal_fmt)
        dist_ws.set_column("E:E", 12, integer_fmt)
        dist_chart = wb.add_chart({"type": "column"})
        dist_chart.add_series({
            "name": "Trace Count",
            "categories": ["Thickness Distribution", 1, 0, len(distribution_df), 0],
            "values": ["Thickness Distribution", 1, 4, len(distribution_df), 4],
            "fill": {"color": "#004F71"},
            "border": {"color": "#004F71"},
        })
        dist_chart.set_title({"name": "Thickness Distribution", "name_font": chart_title_fmt})
        dist_chart.set_x_axis({"name": "Thickness Bin (in.)"})
        dist_chart.set_y_axis({
            "name": "Trace Count",
            "num_format": "#,##0",
            "major_gridlines": {"visible": True, "line": {"color": "#D9D9D9"}},
        })
        dist_chart.set_legend({"none": True})
        dist_chart.set_size({"width": 980, "height": 460})
        dist_ws.insert_chart("G2", dist_chart)

        summary_ws = writer.sheets["Summary"]
        summary_ws.write("A10", "Workbook Contents", wb.add_format({"bold": True}))
        summary_ws.write("A11", "Interpolated Data")
        summary_ws.write("B11", "Full DMI, latitude, longitude, and thickness export.")
        summary_ws.write("A12", "Longitudinal Plot")
        summary_ws.write("B12", "Native Excel scatter plot with a line.")
        summary_ws.write("A13", "Thickness Distribution")
        summary_ws.write("B13", "Native Excel histogram-style column chart.")

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
            full_series = pd.to_numeric(df[col_idx], errors="coerce")
            valid = full_series.dropna()
            positive = valid[valid > 0]
            sample_series = pd.to_numeric(sample_df[col_idx], errors="coerce").fillna(0)
            is_empty = valid.empty or positive.empty
            
            columns_preview.append({
                "index": col_idx,
                "name": f"Layer {col_idx - 1}",
                "data": sample_series.tolist(),
                "is_empty": is_empty,
                "mean": float(valid.mean()) if not valid.empty else 0,
                "positive_mean": float(positive.mean()) if not positive.empty else 0,
                "positive_ratio": float(len(positive) / len(df)) if len(df) else 0
            })
            
        return {
            "status": "success",
            "columns": columns_preview,
            "recommended_column": recommend_thickness_column(columns_preview),
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
        if thickness_column not in df.columns:
            return JSONResponse(status_code=400, content={"error": f"Thickness column {thickness_column} is not present in the GPR file"})
        
        dmi_min = df[1].min()
        dmi_max = df[1].max()
        if dmi_max == dmi_min:
            return JSONResponse(status_code=400, content={"error": "GPR DMI range is zero; cannot align traces to the KML path"})

        gpr_pct = (df[1] - dmi_min) / (dmi_max - dmi_min)
        target_dist = (gpr_pct * kml_total_dist) + antenna_offset
        
        lats = [p[0] for p in gps_points]
        lons = [p[1] for p in gps_points]
        
        df['Interp_Lat'] = np.interp(target_dist, kml_dist, lats)
        df['Interp_Lon'] = np.interp(target_dist, kml_dist, lons)
        
        df[thickness_column] = pd.to_numeric(df[thickness_column], errors="coerce")
        plot_df = df.dropna(subset=[thickness_column]).copy()
        if plot_df.empty:
            return JSONResponse(status_code=400, content={"error": f"Selected layer {thickness_column} has no numeric thickness data. Choose another layer from the preview."})
        
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
        stats_std = float(thickness_vals.std(ddof=0))
        stats_min = float(thickness_vals.min())
        stats_max = float(thickness_vals.max())
        stats = {
            "mean": stats_mean,
            "std": stats_std,
            "min": stats_min,
            "max": stats_max
        }

        # Prepare Distribution Data (Histogram Bins)
        counts, bin_edges = np.histogram(thickness_vals, bins=20)
        distribution_rows = []
        for i in range(len(counts)):
            bin_start = round(float(bin_edges[i]), 2)
            bin_end = round(float(bin_edges[i+1]), 2)
            distribution_rows.append({
                "Thickness_Bin_Inches": f"{bin_start:.2f}-{bin_end:.2f}",
                "Bin_Center_Inches": round(float((bin_edges[i] + bin_edges[i+1]) / 2), 2),
                "Bin_Start_Inches": bin_start,
                "Bin_End_Inches": bin_end,
                "Count": int(counts[i])
            })
        distribution_df = pd.DataFrame(distribution_rows)

        # 4.6 Excel Export
        excel_path = os.path.join(session_dir, 'analysis_results.xlsx')
        export_df = plot_df[[1, 'Interp_Lat', 'Interp_Lon', thickness_column]].copy()
        export_df.columns = ['DMI_Feet', 'Latitude', 'Longitude', 'Thickness_Inches']
        write_excel_report(excel_path, export_df, distribution_df, stats, kml_total_dist, title)
        
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
            
        dist_json = [
            {"x": row["Bin_Center_Inches"], "y": row["Count"]}
            for row in distribution_rows
        ]
        
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
