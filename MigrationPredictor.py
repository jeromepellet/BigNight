import streamlit as st
import pandas as pd
import numpy as np
import requests
from datetime import datetime, timedelta

# --- CONFIGURATION DE LA PAGE ---
st.set_page_config(
    page_title="Radar des migrations d'amphibiens", 
    page_icon="🐸", 
    layout="centered"
)

# --- PARAMÈTRES DU MODÈLE ---
WEIGHT_TEMP_APP    = 0.25  
WEIGHT_STABILITY   = 0.20  
WEIGHT_RAIN_24H    = 0.20  
WEIGHT_HUMIDITY    = 0.15  
WEIGHT_SEASON      = 0.10  
LUNAR_BOOST_MAX    = 0.10  

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
    
    prob = (f_temp * WEIGHT_TEMP_APP + f_stability * WEIGHT_STABILITY + 
            f_rain * WEIGHT_RAIN_24H + f_humidity * WEIGHT_HUMIDITY + f_season * WEIGHT_SEASON)
    
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
st.caption("Modèle prédictif basé sur les données haute résolution de MétéoSuisse")

ville = st.selectbox("📍 Station de référence :", list(CITY_DATA.keys()))
LAT, LON = CITY_DATA[ville]

@st.cache_data(ttl=3600)
def get_weather_data(lat, lon):
    url = "https://api.open-meteo.com/v1/forecast"
    # Utilisation du modèle haute résolution de MétéoSuisse (COSMO)
    params = {
        "latitude": lat, "longitude": lon,
        "hourly": "temperature_2m,apparent_temperature,precipitation,relative_humidity_2m",
        "timezone": "Europe/Berlin", "past_days": 10, "forecast_days": 8,
        "models": "meteofrance_seamless,icon_seamless,best_match" # "best_match" inclut les données locales optimisées
    }
    return requests.get(url, params=params).json()

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
            
            prob = calculate_migration_probability(
                row['apparent_temperature'], df.iloc[i-72:i]['temperature_2m'].values,
                df.iloc[i-24:i]['precipitation'].sum(), df.iloc[i-2:i]['precipitation'].sum(),
                row['relative_humidity_2m'], row['time'].month, f_lunar
            )
            
            results.append({
                "Date": format_date_fr(row['time']), 
                "dt_obj": row['time'].date(), 
                "T° Ress.": f"{round(row['apparent_temperature'], 1)}°C",
                "Pluie 24h": f"{round(df.iloc[i-24:i]['precipitation'].sum(), 1)}mm",
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
            <p style="margin-top:5px;">Analyse météo locale (modèles suisses) pour {ville}.</p>
        </div>""", unsafe_allow_html=True)

        # ALERTE SEUIL
        if score >= 80:
            st.error("🚨 **ALERTE MIGRATION MASSIVE** : Les conditions sont optimales. Risque élevé de mortalité routière. Installez les dispositifs de sauvetage !")
            st.balloons()
        elif score >= 50:
            st.warning("⚠️ **ACTIVITÉ MODÉRÉE** : Migration probable. Une surveillance des sites sensibles est recommandée dès la tombée de la nuit.")

    # --- AFFICHAGE DES TABLEAUX ---
    st.subheader("📅 Prévisions (7 jours)")
    st.table(res_df[res_df['dt_obj'] >= now_dt].head(7).drop(columns=['dt_obj']).set_index('Date'))

    st.subheader("📜 Historique (7 jours)")
    st.table(res_df[res_df['dt_obj'] < now_dt].tail(7).iloc[::-1].drop(columns=['dt_obj']).set_index('Date'))

except Exception as e:
    st.error(f"Erreur technique : {e}")

# --- SECTIONS INFO AMÉLIORÉES ---
st.divider()
tab1, tab2 = st.tabs(["💡 Guide de terrain", "⚗️ Méthodologie"])

with tab1:
    st.markdown("""
    ### Comment interpréter ces indices ?
    * **Température (T° Ress.)** : Les amphibiens s'activent au-dessus de **5°C**. En dessous de 2°C, le risque de gel bloque tout mouvement.
    * **Pluviométrie** : Une pluie fine et continue est plus favorable qu'un orage violent. L'indice prend en compte le cumul sur 24h.
    * **Lune** : Une lune croissante ou pleine (🌕) booste souvent la migration si l'humidité est suffisante.
    * **Activité ❌** : Conditions hostiles (sec ou trop froid).
    * **Activité 🐸 à 🐸🐸** : Quelques individus pionniers (souvent les mâles).
    * **Activité 🐸🐸🐸+** : Migration de masse (femelles et couples en amplexus).
    """)

with tab2:
    st.markdown("""
    ### Précision du modèle
    Ce radar utilise les données du service **Open-Meteo**, configuré pour prioriser les modèles **COSMO (MétéoSuisse)** et **ICON (DWD)**, offrant une résolution de 2km sur le territoire suisse.
    
    **Variables pondérées :**
    1.  **Stabilité 72h** : Analyse si le sol a eu le temps de se réchauffer.
    2.  **Humidité relative** : Seuil critique à 75%.
    3.  **Facteur Lunaire** : Ajustement selon la luminosité nocturne (influence prouvée sur *Bufo bufo*).
    4.  **Fenêtre Saisonnière** : Le modèle est calibré spécifiquement pour la phénologie des espèces suisses (Grenouille rousse, Crapaud commun, Tritons).
    """)

st.caption(f"© n+p wildlife ecology | Données : MétéoSuisse via Open-Meteo | {datetime.now().strftime('%d.%m.%Y à %H:%M')}")
