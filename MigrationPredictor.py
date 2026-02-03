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
WEIGHT_TEMP_APP    = 0.25  
WEIGHT_STABILITY   = 0.20  
WEIGHT_RAIN_8H     = 0.20  
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

def calculate_migration_probability(temp_app, temps_72h, rain_8h, rain_2h, humidity, month, f_lunar):
    temp_app = 0 if pd.isna(temp_app) else temp_app
    
    # 1. CALCUL DE LA BASE (Pondération classique)
    if temp_app < 2 or temp_app > 20: 
        f_temp = 0.05
    else:
        normalized = (temp_app - 2) / (18 - 2)
        f_temp = min(1.0, max(0.05, ((normalized ** 2.5) * ((1 - normalized) ** 1.5)) / 0.35))
    
    temps_72h = temps_72h[~np.isnan(temps_72h)]
    mean_temp = np.mean(temps_72h) if len(temps_72h) > 0 else 0
    f_stability = 0.1 if mean_temp < 4 else 0.5 if mean_temp < 6 else 1.0
    
    f_rain = 0.10 if rain_8h < 0.2 else min(1.0, (np.log1p(rain_8h * 2) / 3.5))
    f_humidity = min(1.0, (humidity / 90) ** 2) # Courbe exponentielle pour l'humidité
    
    seasonal_weights = {2: 0.50, 3: 1.00, 4: 0.85, 10: 0.30}
    f_season = seasonal_weights.get(month, 0.05)
    
    # SCORE INITIAL
    prob = (f_temp * WEIGHT_TEMP_APP + f_stability * WEIGHT_STABILITY + 
            f_rain * WEIGHT_RAIN_8H + f_humidity * WEIGHT_HUMIDITY + f_season * WEIGHT_SEASON)
    
    score = prob * f_season * f_lunar * 100

    # 2. APPLICATION DES FACTEURS LIMITANTS (Coupe-circuits)
    # Si T° < 5°C : La probabilité chute de 70% (Léthargie)
    if temp_app < 5.0:
        score *= 0.3
        
    # Si pas de pluie ( < 0.3mm) ET humidité < 80% : Migration bloquée
    if rain_8h < 0.3 and humidity < 80:
        score *= 0.2
        
    return int(min(100, max(0, score)))

def get_activity_icon(prob):
    if prob < 20: return "❌"
    elif prob < 40: return "🐸"
    elif prob < 60: return "🐸🐸"
    elif prob < 80: return "🐸🐸🐸"
    elif prob < 95: return "🐸🐸🐸🐸"
    else: return "🐸🐸🐸🐸🐸"

def get_migration_label(prob):
    """Retourne une interprétation textuelle du score."""
    if prob < 20: return "Migration peu probable"
    elif prob < 40: return "Migration faible attendue"
    elif prob < 60: return "Migration modérée"
    elif prob < 80: return "Forte migration attendue"
    elif prob < 95: return "Migration massive imminente"
    else: return "Pic de migration critique"

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
                "Pluie 8h": f"{round(rain_8h, 1)}mm",
                "Lune": m_emoji, 
                "Probab.": f"{prob}%",
                "Activité": get_activity_icon(prob),
                "Label": get_migration_label(prob)
            })

    res_df = pd.DataFrame(results)

    # --- DASHBOARD & ALERTES ---
    today = res_df[res_df['dt_obj'] == now_dt]
    if not today.empty:
        score = int(today.iloc[0]['Probab.'].replace('%',''))
        label = today.iloc[0]['Label']
        icon = today.iloc[0]['Activité']
        color = "red" if score > 70 else "orange" if score > 40 else "green"
        
        st.markdown(f"""
        <div style="padding:25px; border-radius:15px; border-left: 12px solid {color}; background:rgba(0,0,0,0.05); margin-bottom:20px;">
            <h4 style="margin:0; text-transform:uppercase; font-size:0.9em; opacity:0.7;">Statut actuel ({ville})</h4>
            <h2 style="margin:0; color:{color};">{label} — {icon}</h2>
            <p style="margin-top:10px; font-size:1.1em;">Probabilité estimée : <b>{score}%</b> à 20h00</p>
        </div>""", unsafe_allow_html=True)

        if score >= 80:
            st.error("🚨 **ALERTE MIGRATION MASSIVE** : Conditions optimales. Haute vigilance requise sur les routes !")
            st.balloons()
        elif score >= 50:
            st.warning("⚠️ **ACTIVITÉ MODÉRÉE** : Les sorties sont probables dès la tombée de la nuit.")

    # --- AFFICHAGE ---
    st.subheader("📅 Prévisions (7 jours)")
    st.table(res_df[res_df['dt_obj'] >= now_dt].head(7).drop(columns=['dt_obj', 'Label']).set_index('Date'))

    st.subheader("📜 Historique (7 jours)")
    st.table(res_df[res_df['dt_obj'] < now_dt].tail(7).iloc[::-1].drop(columns=['dt_obj', 'Label']).set_index('Date'))

except Exception as e:
    st.error(f"Erreur technique : {e}")

# --- SECTIONS INFO ---
st.divider()
tab1, tab2 = st.tabs(["💡 Guide de terrain", "⚗️ Méthodologie"])

with tab1:
    st.markdown("""
    ### Guide d'interprétation
    - **Migration peu probable** (<20%) : Trop sec ou trop froid. Repos nocturne.
    - **Migration faible/modérée** (20-60%) : Quelques individus (mâles surtout) peuvent sortir.
    - **Forte migration / Massive** (>60%) : Déplacement massif des populations vers les sites de reproduction.
    - **Pic de migration** (>95%) : Phénomène exceptionnel déclenché par des conditions météo parfaites (douceur et pluie après une période de froid).
    """)

with tab2:
    st.markdown("""
    ### Paramétrage du modèle
    Ce radar analyse le stimulus biologique via 5 piliers :
    1. **Chaleur cumulée** (Stabilité 72h) : Le sol doit être dégelé.
    2. **Stimulus hydrique** (Pluie 8h) : Pluie tombée entre 12h et 20h.
    3. **Hygrométrie** : Une humidité >75% réduit le risque de dessiccation.
    4. **Orientation Lunaire** : Influence sur le rythme d'activité nocturne.
    5. **Fenêtre de reproduction** : Calibrage saisonnier (Mars est le mois pivot en Suisse).
    """)

st.caption(f"© n+p wildlife ecology | Données : MétéoSuisse | {datetime.now().strftime('%d.%m.%Y à %H:%M')}")
