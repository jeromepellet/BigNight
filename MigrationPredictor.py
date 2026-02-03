import streamlit as st
import pandas as pd
import numpy as np
import requests
from datetime import datetime, timedelta

# --- CONFIGURATION ---
st.set_page_config(page_title="Radar Amphibiens Nocturne", page_icon="🐸")

CITY_DATA = {
    "Lausanne": (46.520, 6.634), "Genève": (46.202, 6.147), "Sion": (46.231, 7.359),
    "Neuchâtel": (47.000, 6.933), "Fribourg": (46.800, 7.150), "Berne": (46.948, 7.447),
    "Zurich": (47.374, 8.541), "Morges": (46.509, 6.498), "Yverdon": (46.779, 6.641)
}

# --- LOGIQUE DE CALCUL AMÉLIORÉE (AVEC COUPE-CIRCUITS) ---
def calculate_migration_probability(t_app, temps_72h, rain_8h, humidity, month, f_lunar):
    # Base de calcul
    normalized_t = (t_app - 2) / 16
    f_temp = min(1.0, max(0.05, ((normalized_t**2.5) * ((1-normalized_t)**1.5)) / 0.35)) if 2 < t_app < 20 else 0.05
    
    f_stab = 0.1 if np.mean(temps_72h) < 4 else 1.0
    f_rain = min(1.0, np.log1p(rain_8h * 2) / 3.5) if rain_8h > 0.2 else 0.1
    f_hum = (humidity / 90)**2
    
    seasonal_weights = {2: 0.5, 3: 1.0, 4: 0.8, 10: 0.3}
    f_seas = seasonal_weights.get(month, 0.05)
    
    # Score initial pondéré
    score = (f_temp * 0.3 + f_stab * 0.2 + f_rain * 0.25 + f_hum * 0.15 + f_seas * 0.1) * f_seas * f_lunar * 100
    
    # COUPE-CIRCUITS (Loi du minimum)
    if t_app < 5.0: score *= 0.3  # Malus froid
    if rain_8h < 0.3 and humidity < 80: score *= 0.2 # Malus sécheresse
    
    return int(min(100, max(0, score)))

# --- INTERFACE ---
st.title("🐸 Radar des migrations (Analyse Nocturne)")
ville = st.selectbox("📍 Station :", list(CITY_DATA.keys()))
lat, lon = CITY_DATA[ville]

@st.cache_data(ttl=3600)
def get_weather_data(lat, lon):
    url = "https://api.open-meteo.com/v1/forecast"
    params = {"latitude": lat, "longitude": lon, "hourly": "temperature_2m,apparent_temperature,precipitation,relative_humidity_2m",
              "timezone": "Europe/Berlin", "past_days": 7, "forecast_days": 8, "models": "best_match"}
    return requests.get(url, params=params).json()

try:
    data = get_weather_data(lat, lon)
    df = pd.DataFrame(data['hourly'])
    df['time'] = pd.to_datetime(df['time'])
    
    # Correction apparent_temp
    if 'apparent_temperature' not in df.columns: df['apparent_temperature'] = df['temperature_2m']

    night_results = []
    # On groupe par jour pour analyser chaque nuit (18h à 02h le lendemain)
    unique_days = sorted(df['time'].dt.date.unique())

    for day in unique_days:
        # Sélection de la plage nocturne : 18h ce jour-là -> 02h le lendemain
        start_night = datetime.combine(day, datetime.min.time()) + timedelta(hours=18)
        end_night = start_night + timedelta(hours=8)
        
        mask = (df['time'] >= start_night) & (df['time'] <= end_night)
        night_df = df[mask]
        
        if len(night_df) < 5: continue # Ignore si données incomplètes
        
        # Calcul du pic de probabilité sur la nuit
        probs_night = []
        for idx, row in night_df.iterrows():
            idx_int = int(idx)
            # Facteurs lunaires et saisonniers simplifiés pour l'exemple
            ref_moon = datetime(2000, 1, 6, 18, 14)
            lunar_cycle = 29.53
            phase = (((row['time'] - ref_moon).total_seconds() / 86400) % lunar_cycle) / lunar_cycle
            f_lunar = 1.0 + 0.1 * np.cos(2 * np.pi * abs(phase - 0.5))
            
            p = calculate_migration_probability(
                row['apparent_temperature'], 
                df.iloc[idx_int-72:idx_int]['temperature_2m'].values,
                df.iloc[idx_int-8:idx_int]['precipitation'].sum(),
                row['relative_humidity_2m'],
                row['time'].month,
                f_lunar
            )
            probs_night.append(p)
        
        max_prob = max(probs_night)
        avg_temp = night_df['apparent_temperature'].mean()
        total_rain = night_df['precipitation'].sum()
        
        night_results.append({
            "Nuit du": day.strftime("%d %b"),
            "Pic Prob.": f"{max_prob}%",
            "T° Moy. Nuit": f"{round(avg_temp, 1)}°C",
            "Pluie Nuit": f"{round(total_rain, 1)}mm",
            "score": max_prob
        })

    res_df = pd.DataFrame(night_results)
    
    # Dashboard principal (Aujourd'hui)
    today_score = night_results[-8]['score'] # Indexation simplifiée
    color = "red" if today_score > 70 else "orange" if today_score > 40 else "green"
    st.metric("Probabilité maximale cette nuit", f"{today_score}%", delta_color="normal")
    
    st.subheader("📅 Prévisions nocturnes (18h - 02h)")
    st.table(res_df.drop(columns=['score']).tail(8))

except Exception as e:
    st.error(f"Erreur : {e}")
