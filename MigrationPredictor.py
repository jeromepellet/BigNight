import streamlit as st
import pandas as pd
import numpy as np
import requests
import plotly.express as px  # Added for the graph
from datetime import datetime, timedelta

# --- CONFIGURATION ---
st.set_page_config(page_title="Radar Migration Amphibiens", page_icon="🐸", layout="wide")

# --- ALGORITHM CONSTANTS ---
SATURATION_THRESHOLD = 0.5  # Rain in mm/h where it becomes "too much"
W_SEASON = 0.20
W_TEMP_8H = 0.25
W_FEEL_2H = 0.25
W_RAIN_8H = 0.15
W_RAIN_CURR = 0.15

CITY_DATA = {
    "Lausanne": (46.520, 6.634), "Genève": (46.202, 6.147), "Sion": (46.231, 7.359),
    "Neuchâtel": (47.000, 6.933), "Fribourg": (46.800, 7.150), "Berne": (46.948, 7.447),
    "Zurich": (47.374, 8.541), "Morges": (46.509, 6.498), "Yverdon": (46.779, 6.641)
}

def calculate_migration_probability(temp_8h_avg, feel_2h, rain_8h_total, rain_curr, month):
    # 1. Temperature (Standard Logistic)
    f_temp_8h = min(1.0, max(0, (temp_8h_avg - 2) / 10)) 
    f_feel_2h = min(1.0, max(0, (feel_2h - 2) / 10))
    
    # 2. Rainfall 8h (Cumulative)
    f_rain_8h = min(1.0, rain_8h_total / 5.0)
    
    # 3. CURRENT RAIN SATURATION LOGIC
    # Peaks at 0.3-0.5mm, drops significantly if > 1.0mm
    if rain_curr <= 0.1:
        f_rain_curr = 0.2  # Too dry
    elif rain_curr <= SATURATION_THRESHOLD:
        f_rain_curr = 1.0  # Perfect drizzle
    else:
        # Penalty for heavy rain: decreases as rain increases
        f_rain_curr = max(0.1, 1.0 - (rain_curr - SATURATION_THRESHOLD) / 3.0)
    
    # 4. Season
    seasonal_map = {2: 0.6, 3: 1.0, 4: 0.9, 5: 0.4, 9: 0.3, 10: 0.5}
    f_season = seasonal_map.get(month, 0.1)
    
    score = (f_season * W_SEASON + f_temp_8h * W_TEMP_8H + 
             f_feel_2h * W_FEEL_2H + f_rain_8h * W_RAIN_8H + 
             f_rain_curr * W_RAIN_CURR) * 100

    # Kill switches
    if feel_2h < 2: score = 0
    if rain_8h_total < 0.1 and rain_curr < 0.1: score *= 0.2
    
    return int(min(100, score))

# --- APP LOGIC ---
st.title("🐸 Radar de Migration : Saturation Drizzle Mode")
ville = st.selectbox("📍 Choisir une station :", list(CITY_DATA.keys()))
LAT, LON = CITY_DATA[ville]

try:
    # Fetch Data
    url = f"https://api.open-meteo.com/v1/forecast?latitude={LAT}&longitude={LON}&hourly=temperature_2m,apparent_temperature,precipitation&timezone=Europe/Berlin"
    data = requests.get(url).json()
    df = pd.DataFrame(data['hourly'])
    df['time'] = pd.to_datetime(df['time'])
    
    # Process Tonight's Curve
    now = datetime.now()
    start_tonight = datetime.combine(now.date(), datetime.min.time()) + timedelta(hours=20)
    end_tonight = start_tonight + timedelta(hours=10)
    
    night_mask = (df['time'] >= start_tonight) & (df['time'] <= end_tonight)
    tonight_df = df[night_mask].copy()

    if not tonight_df.empty:
        results = []
        for idx, row in tonight_df.iterrows():
            i = int(idx)
            p = calculate_migration_probability(
                df.iloc[max(0, i-8):i]['temperature_2m'].mean(),
                df.iloc[max(0, i-2)]['apparent_temperature'],
                df.iloc[max(0, i-8):i]['precipitation'].sum(),
                row['precipitation'],
                row['time'].month
            )
            results.append({"Heure": row['time'], "Probabilité": p})
        
        curve_df = pd.DataFrame(results)
        best_row = curve_df.loc[curve_df['Probabilité'].idxmax()]

        # --- DISPLAY DASHBOARD ---
        col1, col2 = st.columns([1, 2])
        
        with col1:
            st.metric("Pic de Probabilité", f"{best_row['Probabilité']}%")
            st.success(f"🕒 Heure Optimale : {best_row['Heure'].strftime('%H:00')}")
            st.write(f"Note: Le modèle pénalise désormais les pluies fortes (> {SATURATION_THRESHOLD}mm/h).")

        with col2:
            fig = px.line(curve_df, x="Heure", y="Probabilité", title="Évolution de la probabilité durant la nuit")
            fig.update_traces(line_color='#2ECC71', mode='lines+markers')
            st.plotly_chart(fig, use_container_width=True)

except Exception as e:
    st.error(f"Erreur : {e}")
