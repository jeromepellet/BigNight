import streamlit as st
import pandas as pd
import numpy as np
import requests
from datetime import datetime
from streamlit_js_eval import get_geolocation

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
    "Zurich": (47.374, 8.541), "Morges": (46.509, 6.498), "Yverdon": (46.779, 6.641),
    "Bulle": (46.615, 7.059), "Martigny": (46.103, 7.073), "Sierre": (46.292, 7.532)
}

DAYS_FR = {"Mon": "Lun", "Tue": "Mar", "Wed": "Mer", "Thu": "Jeu", "Fri": "Ven", "Sat": "Sam", "Sun": "Dim"}

# --- CALCUL PRÉCIS DE LA PHASE LUNAIRE (Meeus 1991) ---
def get_moon_phase_data(date):
    ref_new_moon = datetime(2000, 1, 6, 18, 14)
    lunar_cycle = 29.530588861
    time_diff = (date - ref_new_moon).total_seconds() / 86400.0
    phase = (time_diff % lunar_cycle) / lunar_cycle
    illumination = (1 - np.cos(2 * np.pi * phase)) / 2
    
    if phase < 0.03 or phase > 0.97: emoji, name = "🌑", "Nouvelle lune"
    elif phase < 0.22: emoji, name = "🌒", "Premier croissant"
    elif phase < 0.28: emoji, name = "🌓", "Premier quartier"
    elif phase < 0.47: emoji, name = "🌔", "Lune gibbeuse"
    elif phase < 0.53: emoji, name = "🌕", "Pleine lune"
    elif phase < 0.72: emoji, name = "🌖", "Lune gibbeuse"
    elif phase < 0.78: emoji, name = "🌗", "Dernier quartier"
    else: emoji, name = "🌘", "Dernier croissant"
    
    # Modulateur Lunaire (Grant et al. 2009) : Sync positive à la pleine lune
    # Facteur entre 0.85 et 1.15
    dist_from_full = abs(phase - 0.5)
    f_lunar = 1.0 + 0.15 * np.cos(2 * np.pi * dist_from_full)
    
    return illumination, emoji, name, phase, f_lunar

# --- LOGIQUE SCIENTIFIQUE AMÉLIORÉE (V4) ---

def calculate_migration_probability(temp_app, temps_72h, rain_24h, rain_2h, humidity, month, f_lunar):
    """
    Modèle intégrant la Température Ressentie (Apparent Temperature)
    pour tenir compte de l'effet coupe-circuit du vent sec (Bise).
    """
    # 1. Réponse thermique (Température ressentie)
    if temp_app < 2 or temp_app > 18:
        f_temp = 0.05
    else:
        normalized = (temp_app - 2) / (18 - 2)
        f_temp = ((normalized ** 2.5) * ((1 - normalized) ** 1.5)) / 0.35
        f_temp = min(1.0, max(0.05, f_temp))
    
    # 2. Stabilité thermique 72h
    mean_72h = np.mean(temps_72h)
    f_stability = 0.1 if mean_72h < 4 else 0.5 if mean_72h < 6 else 1.0
    
    # 3. Précipitations
    f_rain = 0.15 if rain_24h < 0.5 else min(1.0, (np.log1p(rain_24h) / 3.5) * (1.3 if rain_2h > 1.0 else 1.0))
    
    # 4. Humidité
    f_humidity = min(1.2, 0.6 + (humidity - 60) / 50) if humidity < 75 else min(1.2, 0.9 + (humidity - 75) / 100)
    
    # 5. Phénologie Suisse (karch)
    seasonal_weights = {2: 0.60, 3: 1.00, 4: 0.85, 10: 0.35, 11: 0.15}
    f_season = seasonal_weights.get(month, 0.05)
    
    # Calcul final
    prob = (f_temp * 0.28 + f_stability * 0.24 + f_rain * 0.24 + f_humidity * 0.14 + f_season * 0.10)
    return int(min(100, max(0, prob * f_season * f_lunar * 100)))

# --- INTERFACE ---
st.title("🐸 Radar scientifique des migrations")
st.caption("Modèle V4 | Intègre Température Ressentie (Vent) & Cycle Lunaire (Grant 2009)")

if 'selected_city' not in st.session_state:
    st.session_state['selected_city'] = "Lausanne"

c_gps1, c_gps2 = st.columns([2, 1])
with c_gps1:
    ville = st.selectbox("📍 Localité :", list(CITY_DATA.keys()), index=list(CITY_DATA.keys()).index(st.session_state['selected_city']))
    LAT, LON = CITY_DATA[ville]
with c_gps2:
    st.write("")
    if st.button("🛰️ Me géolocaliser"):
        loc = get_geolocation()
        if loc: st.info("Position détectée. Recherche de la station la plus proche...")

# --- DONNÉES ---
@st.cache_data(ttl=3600)
def get_weather_data(lat, lon):
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat, "longitude": lon,
        "hourly": "temperature_2m,apparent_temperature,precipitation,relative_humidity_2m",
        "timezone": "Europe/Berlin", "past_days": 7, "forecast_days": 7
    }
    return requests.get(url, params=params).json()

try:
    weather = get_weather_data(LAT, LON)
    df = pd.DataFrame(weather['hourly'])
    df['time'] = pd.to_datetime(df['time'])
    results = []
    now_dt = datetime.now().date()

    for i in range(len(df)):
        if df.iloc[i]['time'].hour == 20: # On analyse le pic de début de nuit
            if i < 72: continue
            row = df.iloc[i]
            _, m_emoji, m_name, _, f_lunar = get_moon_phase_data(row['time'])
            
            prob = calculate_migration_probability(
                row['apparent_temperature'], df.iloc[i-72:i]['temperature_2m'].values,
                df.iloc[i-24:i]['precipitation'].sum(), df.iloc[i-2:i]['precipitation'].sum(),
                row['relative_humidity_2m'], row['time'].month, f_lunar
            )
            
            date_fr = row['time'].strftime('%a %d %b')
            for en, fr in DAYS_FR.items(): date_fr = date_fr.replace(en, fr)
            
            results.append({
                "Date": date_fr, "dt_obj": row['time'].date(), 
                "T° Ressentie": round(row['apparent_temperature'], 1),
                "Pluie 24h (mm)": round(df.iloc[i-24:i]['precipitation'].sum(), 1),
                "Lune": m_emoji, "Probabilité": f"{prob}%",
                "Activité": "🐸" * (prob // 20 + 1) if prob > 15 else "❌"
            })

    res_df = pd.DataFrame(results)

    # --- DASHBOARD ---
    today = res_df[res_df['dt_obj'] == now_dt]
    if not today.empty:
        score = int(today.iloc[0]['Probabilité'].replace('%',''))
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("🌡️ T° Ressentie", f"{today.iloc[0]['T° Ressentie']}°C")
        c2.metric("🌧️ Pluie (24h)", f"{today.iloc[0]['Pluie 24h (mm)']} mm")
        c3.metric("💧 Humidité", f"{df.iloc[0]['relative_humidity_2m']}%")
        _, m_emoji, m_name, _, _ = get_moon_phase_data(datetime.now())
        c4.metric(f"{m_emoji} Lune", m_name)

        color = "red" if score > 70 else "orange" if score > 40 else "green"
        st.markdown(f"""
        <div style="padding:20px; border-radius:10px; border-left: 10px solid {color}; background:rgba(0,0,0,0.05); margin-bottom:25px;">
            <h1 style="color:{color}; margin:0;">{today.iloc[0]['Probabilité']} — {today.iloc[0]['Activité']}</h1>
            <p style="font-size:1.1em; margin-top:10px;">{"<b>Alerte migration massive</b> : Sortie prioritaire recommandée." if score > 70 else "<b>Activité modérée</b> : Surveillance conseillée." if score > 40 else "<b>Calme</b> : Conditions peu favorables."}</p>
        </div>""", unsafe_allow_html=True)

    # --- AFFICHAGE ---
    st.divider()
    col_tab1, col_tab2 = st.columns(2)
    with col_tab1:
        st.subheader("📅 Prévisions (7 jours)")
        st.dataframe(res_df[res_df['dt_obj'] >= now_dt].drop(columns=['dt_obj']).set_index('Date'), use_container_width=True)
    with col_tab2:
        st.subheader("📜 Historique (7 jours)")
        st.dataframe(res_df[res_df['dt_obj'] < now_dt].drop(columns=['dt_obj']).iloc[::-1].set_index('Date'), use_container_width=True)

except Exception as e:
    st.error(f"Erreur technique : {e}")

# --- MÉTHODOLOGIE ---
with st.expander("🔬 Méthodologie Scientifique"):
    st.markdown("""
    ### Un modèle unifié pour le terrain
    Ce radar utilise la **Température Ressentie** (Apparent Temperature) pour intégrer l'effet du vent et du refroidissement par évaporation sur la peau des amphibiens. 
    
    **Facteurs clés :**
    - **Température Ressentie** : Capture l'effet bloquant de la Bise (vent froid/sec).
    - **Cycle Lunaire** : Synchronisation positive lors de la pleine lune (Grant et al. 2009).
    - **Stabilité 72h** : Prise en compte de l'inertie thermique du sol.
    
    **Référence :** *Grant, R. A., et al. (2009). The lunar cycle: a cue for amphibian reproductive phenology? Animal Behaviour.*
    """)
st.caption(f"© n+p wildlife ecology | Version 4.0 | {datetime.now().strftime('%d.%m.%Y')}")
