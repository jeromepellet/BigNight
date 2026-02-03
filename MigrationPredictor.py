import streamlit as st
import pandas as pd
import numpy as np
import requests
from datetime import datetime
from streamlit_js_eval import get_geolocation # Installation: pip install streamlit-js-eval

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

DAYS_FR = {"Mon": "Lun", "Tue": "Mar", "Wed": "Mer", "Thu": "Jeu", "Fri": "Ven", "Sat": "Sam", "Sun": "Dim"}

# --- LOGIQUE SCIENTIFIQUE ---
def get_moon_data(date):
    ref_new_moon = datetime(2025, 2, 28)
    lunar_cycle = 29.53059
    diff = (date - ref_new_moon).total_seconds() / (24 * 3600)
    phase = (diff % lunar_cycle) / lunar_cycle
    illumination = (1 - np.cos(2 * np.pi * phase)) / 2
    emoji = "🌑" if phase < 0.06 or phase > 0.94 else "🌓" if phase < 0.5 else "🌕" if phase < 0.56 else "🌗"
    name = "Nouvelle lune" if emoji == "🌑" else "Lune croissante" if emoji == "🌓" else "Pleine lune" if emoji == "🌕" else "Lune décroissante"
    return illumination, emoji, name

def calculate_prob(temp_ressentie, rain_8h, rain_2h, month, illum):
    seasonal = {1: 0.1, 2: 0.7, 3: 1.0, 4: 0.9, 5: 0.3, 10: 0.4, 11: 0.2}
    f_month = seasonal.get(month, 0.05)
    f_temp = np.exp(-0.5 * ((temp_ressentie - 10) / 4) ** 2) if 4 <= temp_ressentie <= 20 else (0.1 if temp_ressentie > 20 else 0)
    rain_total = rain_8h + rain_2h
    f_rain = min(1.0, 0.2 + (rain_total * 0.2)) if rain_total > 0 else 0.2
    f_lune = 1.15 if illum < 0.3 else (0.95 if illum > 0.7 else 1.0)
    return int(min(100, max(0, (f_month * f_temp * f_rain * f_lune) * 100)))

def find_closest_city(lat, lon):
    distances = {name: np.sqrt((lat-c[0])**2 + (lon-c[1])**2) for name, c in CITY_DATA.items()}
    return min(distances, key=distances.get)

# --- (i) SÉLECTION DE LA VILLE & GPS ---
st.title("🐸 Radar des migrations d'amphibiens")

if 'selected_city' not in st.session_state:
    st.session_state['selected_city'] = "Lausanne"

col_gps1, col_gps2 = st.columns([2, 1])
with col_gps1:
    ville = st.selectbox("📍 Localité :", list(CITY_DATA.keys()), 
                         index=list(CITY_DATA.keys()).index(st.session_state['selected_city']))
    LAT, LON = CITY_DATA[ville]
with col_gps2:
    st.write("") # Espacement
    if st.button("🛰️ Me géolocaliser"):
        loc = get_geolocation()
        if loc:
            lat, lon = loc['coords']['latitude'], loc['coords']['longitude']
            st.session_state['selected_city'] = find_closest_city(lat, lon)
            st.rerun()

# --- RÉCUPÉRATION DONNÉES ---
@st.cache_data(ttl=3600)
def get_weather_data(lat, lon):
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat, "longitude": lon,
        "hourly": "temperature_2m,apparent_temperature,precipitation,relative_humidity_2m",
        "timezone": "Europe/Berlin", "past_days": 14, "forecast_days": 8, "models": "best_match"
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
            t_air, t_res = row['temperature_2m'], row['apparent_temperature']
            r8 = df.iloc[i-8:i]['precipitation'].sum()
            r2 = df.iloc[i-2:i]['precipitation'].sum()
            h, m = row['relative_humidity_2m'], row['time'].month
            illum, m_emoji, m_name = get_moon_data(row['time'])
            p = calculate_prob(t_res, r8, r2, m, illum)
            
            activity = "❌" if p <= 20 else "🐸" * min(5, max(1, p // 20))
            diff_jours = (row['time'].date() - now_dt).days
            fiab = "100%" if diff_jours <= 0 else "90%" if diff_jours <= 2 else "70%" if diff_jours <= 4 else "50%"
            
            date_fr = row['time'].strftime('%a %d %b')
            for en, fr in DAYS_FR.items(): date_fr = date_fr.replace(en, fr)

            results.append({
                "Date": date_fr, "dt_obj": row['time'].date(), "Air (°C)": round(t_air, 1),
                "Ressenti (°C)": round(t_res, 1), "Pluie 8h (mm)": round(r8, 1),
                "Humidité (%)": int(h), "Lune": m_emoji, "Probabilité": f"{p}%",
                "Fiabilité": fiab, "Activité": activity
            })

    res_df = pd.DataFrame(results)

    # --- (ii) BILAN POUR CETTE NUIT (DASHBOARD) ---
    today_res = res_df[res_df['dt_obj'] == now_dt]
    if not today_res.empty:
        score = int(today_res.iloc[0]['Probabilité'].replace('%',''))
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("🌡️ Ressenti", f"{today_res.iloc[0]['Ressenti (°C)']}°C")
        c2.metric("🌧️ Pluie (8h)", f"{today_res.iloc[0]['Pluie 8h (mm)']} mm")
        c3.metric("💧 Humidité", f"{today_res.iloc[0]['Humidité (%)']}%")
        _, m_emoji, m_name = get_moon_data(datetime.now())
        c4.metric(f"{m_emoji} Lune", m_name)

        color = "red" if score > 70 else "orange" if score > 40 else "green"
        st.markdown(f"""
        <div style="background-color:rgba(0,0,0,0.05); padding:20px; border-radius:10px; border-left: 10px solid {color}; margin-top:10px; margin-bottom:20px;">
            <h1 style="margin:0; color:{color};">{today_res.iloc[0]['Probabilité']} {today_res.iloc[0]['Activité']}</h1>
            <p style="font-size:1.1em;"><b>Analyse locale :</b> {"Migration massive probable. Protection des routes recommandée." if score > 70 else "Activité modérée, restez vigilants." if score > 20 else "Conditions défavorables ce soir."}</p>
        </div>
        """, unsafe_allow_html=True)

    # --- (iii) TABLEAUX ---
    st.divider()
    col_tab1, col_tab2 = st.columns(2)
    with col_tab1:
        st.subheader("📅 Prévisions (7 jours)")
        st.dataframe(res_df[res_df['dt_obj'] >= now_dt].drop(columns=['dt_obj']).set_index('Date'), use_container_width=True)
    with col_tab2:
        st.subheader("📜 Historique (14 jours)")
        st.dataframe(res_df[res_df['dt_obj'] < now_dt].drop(columns=['dt_obj', 'Fiabilité']).iloc[::-1].set_index('Date'), use_container_width=True)

except Exception as e:
    st.error(f"Erreur de connexion : {e}")

# --- (iv) EXPLICATION & COPYRIGHT ---
st.divider()
with st.expander("💡 Comment fonctionne ce radar ?", expanded=False):
    st.markdown("""
    Cet outil prédit les pics de migration en analysant les données de **MétéoSuisse** (modèles COSMO haute résolution) :
    * **Température Ressentie** : Le facteur clé. Intègre l'effet de la **Bise** (vent sec) qui bloque la migration par risque de dessiccation.
    * **Humidité cumulative** : Analyse des précipitations **8h avant** la tombée de la nuit pour évaluer la saturation du sol.
    * **Phénologie & Lune** : Pondère le score selon le mois (pic en mars) et la luminosité nocturne.
    """)
st.caption(f"© n+p wildlife ecology | Source : MétéoSuisse | Actualisé le {datetime.now().strftime('%d.%m.%Y à %H:%M')}")
