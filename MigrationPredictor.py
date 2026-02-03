import streamlit as st
import pandas as pd
import numpy as np
import requests
from datetime import datetime

# --- CONFIGURATION DE LA PAGE ---
st.set_page_config(
    page_title="Radar des migrations d'amphibiens", 
    page_icon="🐸", 
    layout="centered"
)

# --- PARAMÈTRES DU MODÈLE ---
WEIGHT_TEMP_APP    = 0.30  
WEIGHT_STABILITY   = 0.10  
WEIGHT_RAIN_8H     = 0.30 
WEIGHT_HUMIDITY    = 0.20  
WEIGHT_SEASON      = 0.05  
LUNAR_BOOST_MAX    = 0.05  

CITY_DATA = {
    "Lausanne": (46.520, 6.634), "Genève": (46.202, 6.147), "Sion": (46.231, 7.359),
    "Neuchâtel": (47.000, 6.933), "Fribourg": (46.800, 7.150), "Berne": (46.948, 7.447),
    "Zurich": (47.374, 8.541), "Morges": (46.509, 6.498), "Yverdon": (46.779, 6.641),
    "Bulle": (46.615, 7.059), "Martigny": (46.103, 7.073), "Sierre": (46.292, 7.532)
}

DAYS_FR = {"Mon": "Lun", "Tue": "Mar", "Wed": "Mer", "Thu": "Jeu", "Fri": "Ven", "Sat": "Sam", "Sun": "Dim"}
MONTHS_FR = {"Jan": "Janv.", "Feb": "Févr.", "Mar": "Mars", "Apr": "Avril", "May": "Mai", "Jun": "Juin",
             "Jul": "Juil.", "Aug": "Août", "Sep": "Sept.", "Oct": "Oct.", "Nov": "Nov.", "Dec": "Déc."}

def format_date_fr(dt):
    return f"{DAYS_FR.get(dt.strftime('%a'), dt.strftime('%a'))} {dt.day} {MONTHS_FR.get(dt.strftime('%b'), dt.strftime('%b'))}"

# --- LOGIQUE SCIENTIFIQUE ---

def get_moon_phase_data(date):
    ref_new_moon = datetime(2000, 1, 6, 18, 14)
    lunar_cycle = 29.530588861
    time_diff = (date - ref_new_moon).total_seconds() / 86400.0
    phase = (time_diff % lunar_cycle) / lunar_cycle
    
    if phase < 0.0625 or phase > 0.9375: emoji = "🌑"
    elif phase <= 0.1875: emoji = "🌒"
    elif phase <= 0.3125: emoji = "🌓"
    elif phase <= 0.4375: emoji = "🌔"
    elif phase <= 0.5625: emoji = "🌕"
    elif phase <= 0.6875: emoji = "🌖"
    elif phase <= 0.8125: emoji = "🌗"
    else: emoji = "🌘"
    
    dist_from_full = abs(phase - 0.5)
    f_lunar = 1.0 + LUNAR_BOOST_MAX * np.cos(2 * np.pi * dist_from_full)
    return emoji, f_lunar

def calculate_migration_probability(temp_app, temps_72h, rain_8h, rain_2h, humidity, month, f_lunar):
    temp_app = 0 if pd.isna(temp_app) else temp_app
    
    if temp_app < 2 or temp_app > 18: f_temp = 0.05
    else:
        normalized = (temp_app - 2) / (18 - 2)
        f_temp = min(1.0, max(0.05, ((normalized ** 2.5) * ((1 - normalized) ** 1.5)) / 0.35))
    
    temps_72h = temps_72h[~np.isnan(temps_72h)]
    mean_temp = np.mean(temps_72h) if len(temps_72h) > 0 else 0
    
    f_stability = 0.1 if mean_temp < 4 else 0.5 if mean_temp < 6 else 1.0
    
    # Sensibilité accrue pour la pluie sur 8h (seuil abaissé car fenêtre plus courte)
    f_rain = 0.15 if rain_8h < 0.3 else min(1.0, (np.log1p(rain_8h * 2) / 3.5) * (1.3 if rain_2h > 0.8 else 1.0))
    
    f_humidity = min(1.2, 0.6 + (humidity - 60) / 50) if humidity < 75 else min(1.2, 0.9 + (humidity - 75) / 100)
    
    seasonal_weights = {2: 0.60, 3: 1.00, 4: 0.85, 10: 0.35, 11: 0.15}
    f_season = seasonal_weights.get(month, 0.05)
    
    prob = (f_temp * WEIGHT_TEMP_APP + f_stability * WEIGHT_STABILITY + 
            f_rain * WEIGHT_RAIN_8H + f_humidity * WEIGHT_HUMIDITY + f_season * WEIGHT_SEASON)
    
    return int(min(100, max(0, prob * f_season * f_lunar * 100)))

def get_activity_icon(prob):
    if prob < 20: return "❌"
    elif prob < 40: return "🐸"
    elif prob < 60: return "🐸🐸"
    elif prob < 80: return "🐸🐸🐸"
    elif prob < 95: return "🐸🐸🐸🐸"
    else: return "🐸🐸🐸🐸🐸"

# --- INTERFACE ---
st.title("🐸 Radar des migrations d'amphibiens en Suisse")
st.caption("Modèle prédictif basé sur les données haute résolution de MétéoSuisse (COSMO)")

ville = st.selectbox("📍 Station de référence :", list(CITY_DATA.keys()))
LAT, LON = CITY_DATA[ville]

@st.cache_data(ttl=3600)
def get_weather_data(lat, lon):
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat, "longitude": lon,
        "hourly": "temperature_2m,apparent_temperature,precipitation,relative_humidity_2m",
        "timezone": "Europe/Berlin", "past_days": 10, "forecast_days": 8,
        "models": "best_match"
    }
    resp = requests.get(url, params=params).json()
    if 'hourly' in resp and 'apparent_temperature' not in resp['hourly']:
        resp['hourly']['apparent_temperature'] = resp['hourly']['temperature_2m']
    return resp

try:
    weather = get_weather_data(LAT, LON)
    df = pd.DataFrame(weather['hourly'])
    df['time'] = pd.to_datetime(df['time'])
    results = []
    now_dt = datetime.now().date()

    for i in range(len(df)):
        if df.iloc[i]['time'].hour == 20:
            if i < 72: continue
            row = df.iloc[i]
            m_emoji, f_lunar = get_moon_phase_data(row['time'])
            
            t_app = row.get('apparent_temperature', row['temperature_2m'])
            # Calcul de la pluie sur les 8 dernières heures (i-8 jusqu'à i)
            rain_8h = df.iloc[i-8:i]['precipitation'].sum()
            rain_2h = df.iloc[i-2:i]['precipitation'].sum()
            
            prob = calculate_migration_probability(
                t_app, df.iloc[i-72:i]['temperature_2m'].values,
                rain_8h, rain_2h,
                row['relative_humidity_2m'], row['time'].month, f_lunar
            )
            
            results.append({
                "Date": format_date_fr(row['time']), 
                "dt_obj": row['time'].date(), 
                "T° Ress.": f"{round(t_app, 1)}°C",
                "Pluie 8h": f"{round(rain_8h, 1)}mm", # Libellé mis à jour
                "Lune": m_emoji, 
                "Probab.": f"{prob}%",
                "Activité": get_activity_icon(prob)
            })

    res_df = pd.DataFrame(results)

    # --- DASHBOARD & ALERTES ---
    today = res_df[res_df['dt_obj'] == now_dt]
    if not today.empty:
        score = int(today.iloc[0]['Probab.'].replace('%',''))
        color = "red" if score > 70 else "orange" if score > 40 else "green"
        
        st.markdown(f"""
        <div style="padding:20px; border-radius:10px; border-left: 10px solid {color}; background:rgba(0,0,0,0.05); margin-bottom:20px;">
            <h2 style="margin:0; color:{color};">Ce soir : {today.iloc[0]['Probab.']} — {today.iloc[0]['Activité']}</h2>
            <p style="margin-top:5px;">Analyse locale pour <b>{ville}</b> (Pluie cumulée dès 12h00 pour le rapport de 20h00).</p>
        </div>""", unsafe_allow_html=True)

        if score >= 80:
            st.error("🚨 **ALERTE MIGRATION MASSIVE** : Conditions idéales. Sortez les gilets et les seaux !")
            st.balloons()
        elif score >= 50:
            st.warning("⚠️ **ACTIVITÉ MODÉRÉE** : Migration probable.")

    # --- AFFICHAGE ---
    st.subheader("📅 Prévisions (7 jours)")
    st.table(res_df[res_df['dt_obj'] >= now_dt].head(7).drop(columns=['dt_obj']).set_index('Date'))

    st.subheader("📜 Historique (7 jours)")
    st.table(res_df[res_df['dt_obj'] < now_dt].tail(7).iloc[::-1].drop(columns=['dt_obj']).set_index('Date'))

except Exception as e:
    st.error(f"Erreur technique : {e}")

# --- SECTIONS INFO ---
st.divider()
tab1, tab2 = st.tabs(["💡 Guide de terrain", "⚗️ Méthodologie"])

with tab1:
    st.markdown("""
    ### Guide d'interprétation
    * **Pluie 8h** : Mesure les précipitations tombées entre midi et 20h. C'est le déclencheur principal de la sortie nocturne.
    * **T° Ress.** : Température prévue à 20h. Cruciale pour le métabolisme.
    * **Indices 🐸** : Plus il y a de grenouilles, plus la probabilité de croiser des femelles et des amplexus (couples) est forte.
    """)

with tab2:
    st.markdown("""
    ### Paramétrage du modèle
    * **Fenêtre de pluie** : Réduite à 8h pour capturer l'immédiateté du stimulus hydrique.
    * **Modèle MétéoSuisse** : Utilisation du modèle COSMO via Open-Meteo pour une précision topographique optimale.
    * **Facteurs** : Température (25%), Stabilité 72h (20%), Pluie 8h (20%), Humidité (15%), Saison (10%), Lune (10%).
    """)

st.caption(f"© n+p wildlife ecology | Données : MétéoSuisse | {datetime.now().strftime('%d.%m.%Y à %H:%M')}")
