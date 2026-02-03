import streamlit as st
import pandas as pd
import numpy as np
import requests
from datetime import datetime, timedelta

# --- CONFIGURATION ---
st.set_page_config(
    page_title="Radar Batraciens Pro", 
    page_icon="🐸", 
    layout="wide"
)

# --- DONNÉES DES VILLES ---
CITY_DATA = {
    "Lausanne": (46.520, 6.634), "Genève": (46.202, 6.147), "Sion": (46.231, 7.359),
    "Neuchâtel": (47.000, 6.933), "Fribourg": (46.800, 7.150), "Berne": (46.948, 7.447),
    "Zurich": (47.374, 8.541), "Bâle": (47.555, 7.591), "Lugano": (46.004, 8.951),
    "La Chaux-de-Fonds": (47.112, 6.838), "Yverdon": (46.779, 6.641), "Bulle": (46.615, 7.059),
    "Martigny": (46.103, 7.073), "Sierre": (46.292, 7.532), "Morges": (46.509, 6.498)
}

# --- LOGIQUE SCIENTIFIQUE ---
def get_moon_data(date):
    ref_new_moon = datetime(2025, 2, 28)
    lunar_cycle = 29.53059
    diff = (date - ref_new_moon).total_seconds() / (24 * 3600)
    phase = (diff % lunar_cycle) / lunar_cycle
    illumination = (1 - np.cos(2 * np.pi * phase)) / 2
    if phase < 0.06 or phase > 0.94: emoji, name = "🌑", "Nouvelle lune"
    elif phase < 0.5: emoji, name = "🌓", "Lune croissante"
    elif phase < 0.56: emoji, name = "🌕", "Pleine lune"
    else: emoji, name = "🌗", "Lune décroissante"
    return illumination, emoji, name

def calculate_prob(temp, rain_8h, rain_2h, month, illum):
    seasonal = {1: 0.1, 2: 0.7, 3: 1.0, 4: 0.9, 5: 0.3, 10: 0.4, 11: 0.2}
    f_month = seasonal.get(month, 0.05)
    f_temp = np.exp(-0.5 * ((temp - 10) / 4) ** 2) if 4 <= temp <= 20 else 0.1
    rain_total = rain_8h + rain_2h
    f_rain = min(1.0, 0.2 + (rain_total * 0.2)) if rain_total > 0 else 0.2
    f_lune = 1.15 if illum < 0.3 else (0.95 if illum > 0.7 else 1.0)
    return int(min(100, max(0, (f_month * f_temp * f_rain * f_lune) * 100)))

# --- INTERFACE HAUT DE PAGE ---
st.title("🐸 Radar de Migration des Batraciens")

# Choix de la ville en haut au lieu de la sidebar
col_v1, col_v2 = st.columns([1, 2])
with col_v1:
    ville = st.selectbox("📍 Sélectionner une localité :", list(CITY_DATA.keys()))
    LAT, LON = CITY_DATA[ville]

# --- RÉCUPÉRATION DES DONNÉES ---
@st.cache_data(ttl=3600)
def get_weather_data(lat, lon):
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat, "longitude": lon,
        "hourly": "temperature_2m,precipitation,relative_humidity_2m",
        "timezone": "Europe/Berlin", "past_days": 14, "forecast_days": 8
    }
    return requests.get(url, params=params).json()

try:
    data = get_weather_data(LAT, LON)
    df = pd.DataFrame(data['hourly'])
    df['time'] = pd.to_datetime(df['time'])
    
    results = []
    TARGET_HOUR = 20 # Fixé à 20h pour le bilan nocturne
    
    for i in range(len(df)):
        if df.iloc[i]['time'].hour == TARGET_HOUR:
            if i < 8: continue
            row = df.iloc[i]
            t, r8, r2, h, m = row['temperature_2m'], df.iloc[i-8:i]['precipitation'].sum(), df.iloc[i-2:i]['precipitation'].sum(), row['relative_humidity_2m'], row['time'].month
            illum, m_emoji, m_name = get_moon_data(row['time'])
            p = calculate_prob(t, r8, r2, m, illum)
            
            # Système de grenouilles (1 pour 20%)
            nb_frogs = max(1, p // 20) if p > 5 else 0
            results.append({
                "Date": row['time'],
                "Temp (°C)": round(t, 1),
                "Pluie 8h (mm)": round(r8, 1),
                "Humidité (%)": int(h),
                "Lune": m_emoji,
                "Probabilité": p,
                "Activité": "🐸" * nb_frogs if nb_frogs > 0 else "❌"
            })

    res_df = pd.DataFrame(results)
    now_dt = datetime.now().date()
    
    # --- DASHBOARD DU SOIR ---
    today_res = res_df[res_df['Date'].dt.date == now_dt]
    if not today_res.empty:
        score = today_res.iloc[0]['Probabilité']
        st.divider()
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("🌡️ Température", f"{today_res.iloc[0]['Temp (°C)']}°C")
        c2.metric("🌧️ Pluie (8h)", f"{today_res.iloc[0]['Pluie 8h (mm)']} mm")
        c3.metric("💧 Humidité", f"{today_res.iloc[0]['Humidité (%)']}%")
        illum_val, m_emoji, m_name = get_moon_data(datetime.now())
        c4.metric(f"{m_emoji} Lune", m_name)

        color = "red" if score > 70 else "orange" if score > 40 else "green"
        st.markdown(f"""<div style="background-color:rgba(0,0,0,0.05); padding:20px; border-radius:10px; border-left: 10px solid {color}; margin-top:10px;">
            <h1 style="margin:0; color:{color};">{score}% {today_res.iloc[0]['Activité']}</h1>
            <p style="font-size:1.1em;"><b>Conseil :</b> {"Migration massive prévue. Redoublez de prudence !" if score > 70 else "Conditions favorables pour quelques sorties." if score > 40 else "Calme plat attendu ce soir."}</p>
        </div>""", unsafe_allow_html=True)

    # --- TABLES PREVISIONS ET HISTORIQUE ---
    st.divider()
    col_tab1, col_tab2 = st.columns(2)
    
    with col_tab1:
        st.subheader("📅 Prévisions (7 jours)")
        future = res_df[res_df['Date'].dt.date >= now_dt].copy()
        future['Date'] = future['Date'].dt.strftime('%a %d %b')
        st.dataframe(future.set_index('Date'), use_container_width=True)

    with col_tab2:
        st.subheader("📜 Historique (14 jours)")
        past = res_df[res_df['Date'].dt.date < now_dt].copy().sort_values('Date', ascending=False)
        past['Date'] = past['Date'].dt.strftime('%a %d %b')
        st.dataframe(past.set_index('Date'), use_container_width=True)

except Exception as e:
    st.error(f"Erreur technique : {e}")

st.divider()
st.caption(f"© n+p wildlife ecology | Données actualisées le {datetime.now().strftime('%d.%m.%Y à %H:%M')}")
