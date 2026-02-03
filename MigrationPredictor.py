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

# --- DONNÉES DES VILLES ---
CITY_DATA = {
    "Lausanne": (46.520, 6.634), "Genève": (46.202, 6.147), "Sion": (46.231, 7.359),
    "Neuchâtel": (47.000, 6.933), "Fribourg": (46.800, 7.150), "Berne": (46.948, 7.447),
    "Morges": (46.509, 6.498), "Yverdon": (46.779, 6.641), "Bulle": (46.615, 7.059)
}

DAYS_FR = {"Mon": "Lun", "Tue": "Mar", "Wed": "Mer", "Thu": "Jeu", "Fri": "Ven", "Sat": "Sam", "Sun": "Dim"}

# --- LOGIQUE SCIENTIFIQUE ---

def get_moon_data(date_obj):
    """Calcule l'illumination lunaire. Effet POSITIF selon Grant et al. (2009)."""
    ref_new_moon = datetime(2025, 2, 28)
    diff = (date_obj - ref_new_moon).total_seconds() / (24 * 3600)
    phase = (diff % 29.53) / 29.53
    illumination = (1 - np.cos(2 * np.pi * phase)) / 2
    
    if phase < 0.06 or phase > 0.94: emoji, name = "🌑", "Nouvelle lune"
    elif phase < 0.5: emoji, name = "🌓", "Premier quartier"
    elif phase < 0.56: emoji, name = "🌕", "Pleine lune"
    else: emoji, name = "🌗", "Dernier quartier"
    
    # Correction Grant 2009 : La lumière synchronise les arrivées (Bonus max +15%)
    f_lune = 1.0 + (illumination * 0.15)
    return illumination, emoji, name, f_lune

def beta_like_temperature_response(temp):
    if temp < 2 or temp > 18: return 0.05
    normalized = (temp - 2) / (18 - 2)
    response = (normalized ** (3.5 - 1)) * ((1 - normalized) ** (2.5 - 1))
    return min(1.0, max(0.05, response / 0.32))

def calculate_migration_probability(temp, temps_72h, rain_24h, rain_2h, hum, month, f_lune):
    f_temp = beta_like_temperature_response(temp)
    f_stab = 0.1 if np.mean(temps_72h) < 4 else 0.5 if np.mean(temps_72h) < 6 else 1.0
    f_rain = min(1.0, (np.log1p(rain_24h) / 3.5) * (1.3 if rain_2h > 1.0 else 1.0))
    f_hum = min(1.2, 0.6 + (hum - 60) / 50) if hum < 75 else min(1.2, 0.9 + (hum - 75) / 100)
    
    weights = {2: 0.60, 3: 1.00, 4: 0.85, 10: 0.35}
    f_season = weights.get(month, 0.05)
    
    prob = (f_temp * 0.30 + f_stab * 0.20 + f_rain * 0.25 + f_hum * 0.15 + f_season * 0.10)
    return int(min(100, max(0, prob * f_season * f_lune * 100)))

# --- INTERFACE ---
st.title("🐸 Radar scientifique des migrations")
st.caption("Modèle Bufo bufo & Rana temporaria | Calibré Grant (2009) & karch")

if 'selected_city' not in st.session_state: st.session_state['selected_city'] = "Lausanne"

col1, col2 = st.columns([2, 1])
with col1:
    ville = st.selectbox("📍 Localité :", list(CITY_DATA.keys()), index=list(CITY_DATA.keys()).index(st.session_state['selected_city']))
    LAT, LON = CITY_DATA[ville]
with col2:
    st.write("")
    if st.button("🛰️ Géolocalisation"):
        loc = get_geolocation()
        if loc:
            st.info("Position détectée. Recherche de la ville la plus proche...")

# --- RÉCUPÉRATION MÉTÉO ---
@st.cache_data(ttl=3600)
def get_weather_data(lat, lon):
    url = "https://api.open-meteo.com/v1/forecast"
    params = {"latitude": lat, "longitude": lon, "hourly": "temperature_2m,precipitation,relative_humidity_2m", "timezone": "Europe/Berlin", "past_days": 7, "forecast_days": 7}
    return requests.get(url, params=params).json()

try:
    data = get_weather_data(LAT, LON)
    df = pd.DataFrame(data['hourly'])
    df['time'] = pd.to_datetime(df['time'])
    results = []
    now_dt = datetime.now().date()

    for i in range(len(df)):
        if df.iloc[i]['time'].hour == 20:
            if i < 72: continue
            row = df.iloc[i]
            _, m_emoji, _, f_lune = get_moon_data(row['time'])
            
            prob = calculate_migration_probability(
                row['temperature_2m'], df.iloc[i-72:i]['temperature_2m'].values,
                df.iloc[i-24:i]['precipitation'].sum(), df.iloc[i-2:i]['precipitation'].sum(),
                row['relative_humidity_2m'], row['time'].month, f_lune
            )
            
            date_fr = row['time'].strftime('%a %d %b')
            for en, fr in DAYS_FR.items(): date_fr = date_fr.replace(en, fr)
            
            results.append({
                "Date": date_fr, "dt_obj": row['time'].date(), "T°C": round(row['temperature_2m'], 1),
                "Pluie 24h": round(df.iloc[i-24:i]['precipitation'].sum(), 1), "Lune": m_emoji,
                "Probabilité": f"{prob}%", "Activité": "🐸" * (prob // 20 + 1) if prob > 10 else "❌"
            })

    res_df = pd.DataFrame(results)

    # --- DASHBOARD DU JOUR ---
    today = res_df[res_df['dt_obj'] == now_dt]
    if not today.empty:
        score = int(today.iloc[0]['Probabilité'].replace('%',''))
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("🌡️ Température", f"{today.iloc[0]['T°C']}°C")
        c2.metric("🌧️ Pluie (24h)", f"{today.iloc[0]['Pluie 24h']} mm")
        c3.metric("💧 Humidité", f"{data['hourly']['relative_humidity_2m'][0]}%")
        _, m_emoji, m_name, _ = get_moon_data(datetime.now())
        c4.metric(f"{m_emoji} Lune", m_name)

        color = "red" if score > 70 else "orange" if score > 40 else "green"
        st.markdown(f"""<div style="padding:20px; border-radius:10px; border-left: 10px solid {color}; background:rgba(0,0,0,0.05);">
            <h1 style="color:{color};">{today.iloc[0]['Probabilité']} — {today.iloc[0]['Activité']}</h1>
            <p>{"<b>Alerte migration massive</b>" if score > 70 else "<b>Mouvements localisés</b>" if score > 40 else "<b>Activité faible</b>"}</p></div>""", unsafe_allow_html=True)

    # --- AFFICHAGE ---
    st.divider()
    col_tab1, col_tab2 = st.columns(2)
    with col_tab1:
        st.subheader("📅 Prévisions (7j)")
        st.dataframe(res_df[res_df['dt_obj'] >= now_dt].drop(columns=['dt_obj']).set_index('Date'), use_container_width=True)
    with col_tab2:
        st.subheader("📜 Historique (7j)")
        st.dataframe(res_df[res_df['dt_obj'] < now_dt].drop(columns=['dt_obj']).iloc[::-1].set_index('Date'), use_container_width=True)

except Exception as e:
    st.error(f"Erreur technique : {e}")

# --- MÉTHODOLOGIE ---
with st.expander("🔬 Science du modèle"):
    st.markdown("""
    **Modulateur Lunaire (Grant et al., 2009)** : Contrairement aux idées reçues, l'illumination lunaire 
    favorise la synchronisation des arrivées sur les sites de ponte. Un bonus de probabilité est 
    appliqué lors de la pleine lune pour refléter ce comportement social.
    """)
st.caption(f"© n+p wildlife ecology | {datetime.now().strftime('%d.%m.%Y')}")
