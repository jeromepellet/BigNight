import streamlit as st
import pandas as pd
import numpy as np
import requests
import plotly.express as px
from datetime import datetime, timedelta

# --- CONFIGURATION ---
st.set_page_config(page_title="Radar Migration Amphibiens", page_icon="🐸", layout="centered")

# --- PARAMÈTRES DU MODÈLE (Ajustés pour être plus stricts) ---
SATURATION_THRESHOLD = 0.5  
W_SEASON = 0.15       # Réduit pour ne pas gonfler artificiellement le score
W_TEMP_8H = 0.30      
W_FEEL_2H = 0.25      
W_RAIN_8H = 0.15      
W_RAIN_CURR = 0.15    

CITY_DATA = {
    "Lausanne": (46.520, 6.634), "Genève": (46.202, 6.147), "Sion": (46.231, 7.359),
    "Neuchâtel": (47.000, 6.933), "Fribourg": (46.800, 7.150), "Berne": (46.948, 7.447),
    "Zurich": (47.374, 8.541), "Morges": (46.509, 6.498), "Yverdon": (46.779, 6.641)
}

def calculate_migration_probability(temp_8h_avg, feel_2h, rain_8h_total, rain_curr, month):
    # 1. Température : Très stricte en dessous de 4°C
    if feel_2h < 4.0:
        f_feel_2h = (feel_2h / 4.0) ** 2 if feel_2h > 0 else 0
    else:
        f_feel_2h = min(1.0, (feel_2h - 4) / 8 + 0.5) # Plafonne vers 12°C

    f_temp_8h = min(1.0, max(0, (temp_8h_avg - 2) / 10))
    
    # 2. Pluie Cumulée (Besoin d'un sol humide)
    f_rain_8h = min(1.0, rain_8h_total / 3.0)
    
    # 3. Pluie Actuelle (Saturation Drizzle)
    if rain_curr < 0.05:
        f_rain_curr = 0.0  # Pas de pluie = 0 pour ce facteur
    elif rain_curr <= SATURATION_THRESHOLD:
        f_rain_curr = 1.0
    else:
        f_rain_curr = max(0.2, 1.0 - (rain_curr - SATURATION_THRESHOLD) / 1.5)
    
    # 4. Saison
    seasonal_map = {2: 0.5, 3: 1.0, 4: 0.9, 10: 0.4}
    f_season = seasonal_map.get(month, 0.05)
    
    # Calcul Initial
    score = (f_season * W_SEASON + f_temp_8h * W_TEMP_8H + 
             f_feel_2h * W_FEEL_2H + f_rain_8h * W_RAIN_8H + 
             f_rain_curr * W_RAIN_CURR) * 100

    # --- LE FREIN (CRITICAL PENALTIES) ---
    # Si pas de pluie DU TOUT (actuelle et passée), la probabilité chute massivement
    if rain_curr < 0.1 and rain_8h_total < 0.1:
        score *= 0.1 
    
    # Si froid intense
    if feel_2h < 3.0:
        score *= 0.05

    return int(min(100, max(0, score)))

# --- LOGIQUE API ET UI ---
st.title("🐸 Radar de Migration")
st.caption("Modèle strict : Pénalise fortement le froid et l'absence de pluie.")

ville = st.selectbox("📍 Station :", list(CITY_DATA.keys()))
LAT, LON = CITY_DATA[ville]

@st.cache_data(ttl=3600)
def get_weather_data(lat, lon):
    url = "https://api.open-meteo.com/v1/forecast"
    params = {"latitude": lat, "longitude": lon, "hourly": "temperature_2m,apparent_temperature,precipitation", "timezone": "Europe/Berlin", "forecast_days": 8}
    return requests.get(url, params=params).json()

try:
    data = get_weather_data(LAT, LON)
    df = pd.DataFrame(data['hourly'])
    df['time'] = pd.to_datetime(df['time'])
    
    daily_summary = []
    tonight_curve_data = []
    now_dt = datetime.now().date()

    for d in sorted(df['time'].dt.date.unique()):
        start_night = datetime.combine(d, datetime.min.time()) + timedelta(hours=20)
        end_night = start_night + timedelta(hours=10)
        night_df = df[(df['time'] >= start_night) & (df['time'] <= end_night)].copy()
        
        if night_df.empty: continue

        hourly_results = []
        for idx, row in night_df.iterrows():
            i = int(idx)
            p = calculate_migration_probability(
                df.iloc[max(0, i-8):i]['temperature_2m'].mean(),
                df.iloc[max(0, i-2)]['apparent_temperature'],
                df.iloc[max(0, i-8):i]['precipitation'].sum(),
                row['precipitation'],
                row['time'].month
            )
            hourly_results.append({"time": row['time'], "p": p})
            if d == now_dt:
                tonight_curve_data.append({"Heure": row['time'], "Probabilité": p})

        best = max(hourly_results, key=lambda x: x['p'])
        
        daily_summary.append({
            "Date": d.strftime("%d %b"),
            "dt_obj": d,
            "Heure Opt.": best['time'].strftime("%H:00"),
            "T° ressentie": f"{round(night_df['apparent_temperature'].mean(), 1)}°C",
            "Pluie": f"{round(night_df['precipitation'].sum(), 1)}mm",
            "Score": best['p']
        })

    # --- DASHBOARD ---
    tonight = next((item for item in daily_summary if item["dt_obj"] == now_dt), None)
    if tonight:
        st.subheader(f"Prévisions pour cette nuit à {ville}")
        col1, col2 = st.columns([1, 2])
        col1.metric("Pic Probabilité", f"{tonight['Score']}%")
        col1.write(f"🕒 **Heure idéale : {tonight['Heure Opt.']}**")
        
        if tonight_curve_data:
            c_df = pd.DataFrame(tonight_curve_data)
            fig = px.area(c_df, x="Heure", y="Probabilité", range_y=[0, 100])
            fig.update_traces(line_color='#27AE60')
            fig.update_layout(height=250, margin=dict(l=0,r=0,b=0,t=0))
            st.plotly_chart(fig, use_container_width=True)

    st.subheader("📅 Prochaines nuits")
    res_df = pd.DataFrame(daily_summary).drop(columns=['dt_obj'])
    st.dataframe(res_df, use_container_width=True)

except Exception as e:
    st.error(f"Erreur : {e}")
