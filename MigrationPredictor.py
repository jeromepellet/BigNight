import streamlit as st
import pandas as pd
import numpy as np
import requests
from datetime import datetime, timedelta

# --- CONFIGURATION DE LA PAGE ---
st.set_page_config(
    page_title="Radar des migrations d'amphibiens", 
    page_icon="🐸", 
    layout="wide"
)

# --- DONNÉES DES VILLES ---
CITY_DATA = {
    "Lausanne": (46.520, 6.634), "Genève": (46.202, 6.147), "Sion": (46.231, 7.359),
    "Neuchâtel": (47.000, 6.933), "Fribourg": (46.800, 7.150), "Berne": (46.948, 7.447),
    "Zurich": (47.374, 8.541), "Morges": (46.509, 6.498), "Yverdon": (46.779, 6.641),
    "Bulle": (46.615, 7.059), "Martigny": (46.103, 7.073), "Sierre": (46.292, 7.532)
}

# Traduction manuelle pour garantir le français sans dépendance système (locale)
DAYS_FR = {"Mon": "Lun", "Tue": "Mar", "Wed": "Mer", "Thu": "Jeu", "Fri": "Ven", "Sat": "Sam", "Sun": "Dim"}
MONTHS_FR = {
    "Jan": "Janv.", "Feb": "Févr.", "Mar": "Mars", "Apr": "Avril", "May": "Mai", "Jun": "Juin",
    "Jul": "Juil.", "Aug": "Août", "Sep": "Sept.", "Oct": "Oct.", "Nov": "Nov.", "Dec": "Déc."
}

def format_date_fr(dt):
    d_en = dt.strftime('%a')
    m_en = dt.strftime('%b')
    return f"{DAYS_FR.get(d_en, d_en)} {dt.day} {MONTHS_FR.get(m_en, m_en)}"

# --- LOGIQUE SCIENTIFIQUE ---

def get_moon_phase_data(date):
    ref_new_moon = datetime(2000, 1, 6, 18, 14)
    lunar_cycle = 29.530588861
    time_diff = (date - ref_new_moon).total_seconds() / 86400.0
    phase = (time_diff % lunar_cycle) / lunar_cycle
    illumination = (1 - np.cos(2 * np.pi * phase)) / 2
    
    if phase < 0.03 or phase > 0.97: emoji, name = "🌑", "Nouvelle lune"
    elif phase < 0.53 and phase > 0.47: emoji, name = "🌕", "Pleine lune"
    else: emoji = "🌙"; name = "Phase intermédiaire" # Simplifié pour la lisibilité
    
    dist_from_full = abs(phase - 0.5)
    f_lunar = 1.0 + 0.15 * np.cos(2 * np.pi * dist_from_full)
    return emoji, name, f_lunar

def calculate_migration_probability(temp_app, temps_72h, rain_24h, rain_2h, humidity, month, f_lunar):
    if temp_app < 2 or temp_app > 18: f_temp = 0.05
    else:
        normalized = (temp_app - 2) / (18 - 2)
        f_temp = min(1.0, max(0.05, ((normalized ** 2.5) * ((1 - normalized) ** 1.5)) / 0.35))
    
    f_stability = 0.1 if np.mean(temps_72h) < 4 else 0.5 if np.mean(temps_72h) < 6 else 1.0
    f_rain = 0.15 if rain_24h < 0.5 else min(1.0, (np.log1p(rain_24h) / 3.5) * (1.3 if rain_2h > 1.0 else 1.0))
    f_humidity = min(1.2, 0.6 + (humidity - 60) / 50) if humidity < 75 else min(1.2, 0.9 + (humidity - 75) / 100)
    
    seasonal_weights = {2: 0.60, 3: 1.00, 4: 0.85, 10: 0.35, 11: 0.15}
    f_season = seasonal_weights.get(month, 0.05)
    
    prob = (f_temp * 0.28 + f_stability * 0.24 + f_rain * 0.24 + f_humidity * 0.14 + f_season * 0.10)
    return int(min(100, max(0, prob * f_season * f_lunar * 100)))

# --- INTERFACE ---
st.title("🐸 Radar des migrations d'amphibiens")
st.caption("Modèle V5 | Température Ressentie | Synchronisation Lunaire Grant (2009)")

ville = st.selectbox("📍 Choisir une localité :", list(CITY_DATA.keys()))
LAT, LON = CITY_DATA[ville]

# --- DONNÉES ---
@st.cache_data(ttl=3600)
def get_weather_data(lat, lon):
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat, "longitude": lon,
        "hourly": "temperature_2m,apparent_temperature,precipitation,relative_humidity_2m",
        "timezone": "Europe/Berlin", "past_days": 7, "forecast_days": 8
    }
    return requests.get(url, params=params).json()

try:
    weather = get_weather_data(LAT, LON)
    df = pd.DataFrame(weather['hourly'])
    df['time'] = pd.to_datetime(df['time'])
    results = []
    now_dt = datetime.now().date()

    for i in range(len(df)):
        # On calcule les probabilités pour chaque soir à 20h
        if df.iloc[i]['time'].hour == 20:
            if i < 72: continue
            row = df.iloc[i]
            m_emoji, m_name, f_lunar = get_moon_phase_data(row['time'])
            
            prob = calculate_migration_probability(
                row['apparent_temperature'], df.iloc[i-72:i]['temperature_2m'].values,
                df.iloc[i-24:i]['precipitation'].sum(), df.iloc[i-2:i]['precipitation'].sum(),
                row['relative_humidity_2m'], row['time'].month, f_lunar
            )
            
            results.append({
                "Date": format_date_fr(row['time']),
                "dt_obj": row['time'].date(), 
                "T° Ressentie": f"{round(row['apparent_temperature'], 1)}°C",
                "Pluie 24h": f"{round(df.iloc[i-24:i]['precipitation'].sum(), 1)} mm",
                "Lune": m_emoji, 
                "Probabilité": f"{prob}%",
                "Activité": "🐸" * (prob // 20 + 1) if prob > 15 else "❌"
            })

    res_df = pd.DataFrame(results)

    # --- DASHBOARD ---
    today = res_df[res_df['dt_obj'] == now_dt]
    if not today.empty:
        score = int(today.iloc[0]['Probabilité'].replace('%',''))
        color = "red" if score > 70 else "orange" if score > 40 else "green"
        
        st.markdown(f"""
        <div style="padding:20px; border-radius:10px; border-left: 10px solid {color}; background:rgba(0,0,0,0.05); margin-bottom:25px;">
            <h2 style="margin:0;">Ce soir : {today.iloc[0]['Probabilité']} — {today.iloc[0]['Activité']}</h2>
            <p style="font-size:1.1em; margin-top:10px;">Conditions basées sur la météo de 20h00 à {ville}.</p>
        </div>""", unsafe_allow_html=True)

    # --- AFFICHAGE DES TABLEAUX (7 JOURS CHACUN) ---
    st.divider()
    col_tab1, col_tab2 = st.columns(2)
    
    with col_tab1:
        st.subheader("📅 Prévisions (7 jours)")
        # Aujourd'hui + les 6 prochains jours
        future_df = res_df[res_df['dt_obj'] >= now_dt].head(7)
        st.table(future_df.drop(columns=['dt_obj']).set_index('Date'))
    
    with col_tab2:
        st.subheader("📜 Historique (7 jours)")
        # Les 7 jours précédant aujourd'hui
        past_df = res_df[res_df['dt_obj'] < now_dt].tail(7).iloc[::-1]
        st.table(past_df.drop(columns=['dt_obj']).set_index('Date'))

except Exception as e:
    st.error(f"Erreur technique : {e}")

st.caption(f"© n+p wildlife ecology | Version 5.0 | {datetime.now().strftime('%d.%m.%Y')}")
