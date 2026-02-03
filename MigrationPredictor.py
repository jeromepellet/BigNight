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

# --- DONNÉES DES VILLES (COORDONNÉES SUISSES) ---
CITY_DATA = {
    "Lausanne": (46.520, 6.634), "Genève": (46.202, 6.147), "Sion": (46.231, 7.359),
    "Neuchâtel": (47.000, 6.933), "Fribourg": (46.800, 7.150), "Berne": (46.948, 7.447),
    "Zurich": (47.374, 8.541), "Bâle": (47.555, 7.591), "Lugano": (46.004, 8.951),
    "La Chaux-de-Fonds": (47.112, 6.838), "Yverdon": (46.779, 6.641), "Bulle": (46.615, 7.059),
    "Martigny": (46.103, 7.073), "Sierre": (46.292, 7.532), "Morges": (46.509, 6.498)
}

DAYS_FR = {
    "Mon": "Lun", "Tue": "Mar", "Wed": "Mer", "Thu": "Jeu", 
    "Fri": "Ven", "Sat": "Sam", "Sun": "Dim"
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

def calculate_prob(temp_ressentie, rain_8h, rain_2h, month, illum):
    # Facteur saisonnier (Phénologie)
    seasonal = {1: 0.1, 2: 0.7, 3: 1.0, 4: 0.9, 5: 0.3, 10: 0.4, 11: 0.2}
    f_month = seasonal.get(month, 0.05)
    
    # Courbe de Gauss basée sur la température RESSENTIE (plus réaliste face au vent/bise)
    # L'optimum reste 10°C, mais le vent réduit drastiquement le score
    f_temp = np.exp(-0.5 * ((temp_ressentie - 10) / 4) ** 2) if 4 <= temp_ressentie <= 20 else (0.1 if temp_ressentie > 20 else 0)
    
    # Influence de la pluie
    rain_total = rain_8h + rain_2h
    f_rain = min(1.0, 0.2 + (rain_total * 0.2)) if rain_total > 0 else 0.2
    
    # Influence de la luminosité lunaire
    f_lune = 1.15 if illum < 0.3 else (0.95 if illum > 0.7 else 1.0)
    
    return int(min(100, max(0, (f_month * f_temp * f_rain * f_lune) * 100)))

# --- INTERFACE UTILISATEUR ---
st.title("🐸 Radar des migrations d'amphibiens")

st.markdown("""
### 💡 Comment ça marche ?
Cet outil analyse les conditions environnementales critiques pour les amphibiens en croisant les données de **MétéoSuisse** :
* **Température Ressentie** : Le facteur clé. Contrairement à la température de l'air, elle inclut l'effet du **vent (Bise)**. Un vent sec bloque la migration par risque de dessiccation.
* **Humidité cumulative** : L'algorithme scanne les pluies cumulées **8h avant** la tombée de la nuit pour évaluer la saturation du sol.
* **Luminosité & Cycle** : Intègre les phases de la lune et la période biologique (février-avril).

📡 *Les données sont actualisées toutes les heures pour la station la plus proche de la localité choisie.*
""")
st.divider()

col_sel1, col_sel2 = st.columns([1, 2])
with col_sel1:
    ville = st.selectbox("📍 Sélectionner une localité :", list(CITY_DATA.keys()))
    LAT, LON = CITY_DATA[ville]

@st.cache_data(ttl=3600)
def get_weather_data(lat, lon):
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat, "longitude": lon,
        "hourly": "temperature_2m,apparent_temperature,precipitation,relative_humidity_2m",
        "timezone": "Europe/Berlin", "past_days": 14, "forecast_days": 8,
        "models": "best_match"
    }
    return requests.get(url, params=params).json()

try:
    data = get_weather_data(LAT, LON)
    df = pd.DataFrame(data['hourly'])
    df['time'] = pd.to_datetime(df['time'])
    
    results = []
    TARGET_HOUR = 20 
    now_dt = datetime.now().date()
    
    for i in range(len(df)):
        if df.iloc[i]['time'].hour == TARGET_HOUR:
            if i < 8: continue
            row = df.iloc[i]
            
            t_air = row['temperature_2m']
            t_ressentie = row['apparent_temperature']
            r8 = df.iloc[i-8:i]['precipitation'].sum()
            r2 = df.iloc[i-2:i]['precipitation'].sum()
            h = row['relative_humidity_2m']
            m = row['time'].month
            illum, m_emoji, m_name = get_moon_data(row['time'])
            
            # Utilisation de la température RESSENTIE pour la probabilité
            p = calculate_prob(t_ressentie, r8, r2, m, illum)
            
            if p <= 20: activity = "❌"
            else: activity = "🐸" * min(5, max(1, p // 20))

            diff_jours = (row['time'].date() - now_dt).days
            if diff_jours <= 0: fiab = "100%"
            elif diff_jours <= 2: fiab = "90%"
            elif diff_jours <= 4: fiab = "70%"
            else: fiab = "50%"

            date_en = row['time'].strftime('%a %d %b')
            for en, fr in DAYS_FR.items(): date_en = date_en.replace(en, fr)

            results.append({
                "Date": date_en,
                "dt_obj": row['time'].date(),
                "Air (°C)": round(t_air, 1),
                "Ressenti (°C)": round(t_ressentie, 1),
                "Pluie 8h (mm)": round(r8, 1),
                "Humidité (%)": int(h),
                "Lune": m_emoji,
                "Probabilité": f"{p}%",
                "Fiabilité": fiab,
                "Activité": activity
            })

    res_df = pd.DataFrame(results)
    
    # --- DASHBOARD PRINCIPAL ---
    today_res = res_df[res_df['dt_obj'] == now_dt]
    if not today_res.empty:
        prob_str = today_res.iloc[0]['Probabilité']
        score = int(prob_str.replace('%',''))
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("🌡️ Temp. Ressentie", f"{today_res.iloc[0]['Ressenti (°C)']}°C", f"Air: {today_res.iloc[0]['Air (°C)']}°C")
        c2.metric("🌧️ Pluie (8h)", f"{today_res.iloc[0]['Pluie 8h (mm)']} mm")
        c3.metric("💧 Humidité", f"{today_res.iloc[0]['Humidité (%)']}%")
        _, m_emoji, m_name = get_moon_data(datetime.now())
        c4.metric(f"{m_emoji} Lune", m_name)

        color = "red" if score > 70 else "orange" if score > 40 else "green"
        st.markdown(f"""
        <div style="background-color:rgba(0,0,0,0.05); padding:20px; border-radius:10px; border-left: 10px solid {color}; margin-top:10px;">
            <h1 style="margin:0; color:{color};">{prob_str} {today_res.iloc[0]['Activité']}</h1>
            <p style="font-size:1.1em;"><b>Expertise Herpétologique :</b> {"Migration massive probable. Conditions optimales." if score > 70 else "Activité modérée, restez vigilants sur les routes." if score > 20 else "Conditions défavorables (froid, vent sec ou hors saison)."}</p>
        </div>
        """, unsafe_allow_html=True)

    # --- TABLES DES DONNÉES ---
    st.divider()
    col_tab1, col_tab2 = st.columns(2)
    
    with col_tab1:
        st.subheader("📅 Prévisions (7 jours)")
        future = res_df[res_df['dt_obj'] >= now_dt].drop(columns=['dt_obj'])
        st.dataframe(future.set_index('Date'), use_container_width=True)

    with col_tab2:
        st.subheader("📜 Historique (14 jours)")
        past = res_df[res_df['dt_obj'] < now_dt].drop(columns=['dt_obj', 'Fiabilité']).iloc[::-1]
        st.dataframe(past.set_index('Date'), use_container_width=True)

except Exception as e:
    st.error(f"Erreur lors de la récupération des données : {e}")

st.divider()
st.caption(f"© n+p wildlife ecology | Source : MétéoSuisse (Modèles haute résolution) | Actualisé le {datetime.now().strftime('%d.%m.%Y à %H:%M')}")
