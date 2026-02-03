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

# --- DONNÉES DES VILLES (Top 100 Suisse) ---
CITY_DATA = {
    "Zurich": (47.374, 8.541), "Genève": (46.202, 6.147), "Bâle": (47.555, 7.591),
    "Lausanne": (46.520, 6.634), "Berne": (46.948, 7.447), "Winterthour": (47.499, 8.729),
    "Lucerne": (47.050, 8.300), "St-Gall": (47.424, 9.371), "Lugano": (46.004, 8.951),
    "Bienne": (47.133, 7.250), "Bellinzone": (46.195, 9.030), "Thoune": (46.767, 7.633),
    "La Chaux-de-Fonds": (47.112, 6.838), "Fribourg": (46.800, 7.150), "Sion": (46.231, 7.359),
    "Neuchâtel": (47.000, 6.933), "Yverdon-les-Bains": (46.779, 6.641), "Montreux": (46.431, 6.913),
    "Bulle": (46.615, 7.059), "Martigny": (46.103, 7.073), "Sierre": (46.292, 7.532),
    "Morges": (46.509, 6.498), "Nyon": (46.383, 6.233), "Vevey": (46.467, 6.850)
}

# --- LOGIQUE SCIENTIFIQUE ---

def get_moon_data(date):
    """Calcule l'illumination lunaire simplifiée."""
    ref_new_moon = datetime(2025, 2, 28)
    lunar_cycle = 29.53059
    diff = (date - ref_new_moon).total_seconds() / (24 * 3600)
    phase = (diff % lunar_cycle) / lunar_cycle
    illumination = (1 - np.cos(2 * np.pi * phase)) / 2
    
    if phase < 0.06 or phase > 0.94: emoji, name = "🌑", "Nouvelle lune"
    elif phase < 0.19: emoji, name = "🌒", "Premier croissant"
    elif phase < 0.31: emoji, name = "🌓", "Premier quartier"
    elif phase < 0.44: emoji, name = "🌔", "Lune gibbeuse"
    elif phase < 0.56: emoji, name = "🌕", "Pleine lune"
    elif phase < 0.69: emoji, name = "🌖", "Lune décroissante"
    elif phase < 0.81: emoji, name = "🌗", "Dernier quartier"
    else: emoji, name = "🌘", "Dernier croissant"
    
    return illumination, emoji, name

def calculate_prob(temp, rain_8h, rain_2h, month, illum):
    # Facteur Mois
    seasonal = {1: 0.1, 2: 0.7, 3: 1.0, 4: 0.9, 5: 0.3, 10: 0.4, 11: 0.2}
    f_month = seasonal.get(month, 0.05)
    
    # Facteur Température (Optimale 8-12°C)
    if temp < 4: f_temp = 0.1
    elif temp > 20: f_temp = 0.3
    else: f_temp = np.exp(-0.5 * ((temp - 10) / 4) ** 2)
    
    # Facteur Pluie
    rain_total = rain_8h + rain_2h
    f_rain = min(1.0, 0.2 + (rain_total * 0.2)) if rain_total > 0 else 0.2
    
    # Facteur Lune (Nuits sombres favorisées)
    f_lune = 1.15 if illum < 0.3 else (0.95 if illum > 0.7 else 1.0)
    
    prob = (f_month * f_temp * f_rain * f_lune) * 100
    return int(min(100, max(0, prob)))

# --- INTERFACE ---
st.title("🐸 Radar de Migration des Batraciens")
st.markdown("*Prévisions combinées : Météo temps-réel, Cycles Lunaires et Phénologie*")

# Sélection de la ville
with st.sidebar:
    st.header("📍 Localisation")
    ville = st.selectbox("Choisir une ville :", list(CITY_DATA.keys()))
    LAT, LON = CITY_DATA[ville]
    TARGET_HOUR = st.slider("Heure d'observation (soir) :", 17, 23, 20)
    st.divider()
    st.info("Cet outil prédit l'activité du Crapaud commun et de la Grenouille rousse lors de la 'fenêtre du crépuscule'.")

# --- RÉCUPÉRATION DES DONNÉES ---
@st.cache_data(ttl=3600)
def get_forecast(lat, lon):
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat, "longitude": lon,
        "hourly": "temperature_2m,precipitation,relative_humidity_2m",
        "timezone": "Europe/Berlin", "past_days": 2, "forecast_days": 7
    }
    r = requests.get(url, params=params)
    return r.json()

try:
    data = get_forecast(LAT, LON)
    df = pd.DataFrame(data['hourly'])
    df['time'] = pd.to_datetime(df['time'])
    
    # Calcul des probabilités pour chaque jour à l'heure cible
    results = []
    for i in range(len(df)):
        if df.iloc[i]['time'].hour == TARGET_HOUR:
            if i < 8: continue
            
            row = df.iloc[i]
            t = row['temperature_2m']
            r8 = df.iloc[i-8:i]['precipitation'].sum()
            r2 = df.iloc[i-2:i]['precipitation'].sum()
            h = row['relative_humidity_2m']
            m = row['time'].month
            illum, m_emoji, m_name = get_moon_data(row['time'])
            
            p = calculate_prob(t, r8, r2, m, illum)
            
            results.append({
                "Date": row['time'],
                "Temp": t,
                "Pluie_8h": r8,
                "Humidité": h,
                "Lune": m_emoji,
                "Prob": p
            })

    res_df = pd.DataFrame(results)
    now = datetime.now()
    today_res = res_df[res_df['Date'].dt.date == now.date()]

    # --- DASHBOARD DU SOIR (BILAN) ---
    if not today_res.empty:
        st.subheader(f"📊 Bilan pour ce soir à {ville} ({TARGET_HOUR}h)")
        score = today_res.iloc[0]['Prob']
        
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("🌡️ Température", f"{today_res.iloc[0]['Temp']}°C")
        c2.metric("🌧️ Pluie (8h)", f"{today_res.iloc[0]['Pluie_8h']:.1f} mm")
        c3.metric("💧 Humidité", f"{today_res.iloc[0]['Humidité']}%")
        illum_val, m_emoji, m_name = get_moon_data(now)
        c4.metric(f"{m_emoji} Lune", m_name)

        # Indicateur visuel
        frogs = "🐸" * (max(1, score // 20))
        color = "red" if score > 70 else "orange" if score > 40 else "green"
        
        st.markdown(f"""
        <div style="background-color:rgba(0,0,0,0.05); padding:20px; border-radius:10px; border-left: 10px solid {color};">
            <h1 style="margin:0; color:{color};">{score}% - {frogs}</h1>
            <p style="font-size:1.2em;">{"🚨 <b>ALERTE MIGRATION MAJEURE</b> : Prudence maximale sur les routes !" if score > 70 else 
               "⚠️ <b>ACTIVITÉ MODÉRÉE</b> : Quelques déplacements attendus." if score > 40 else 
               "💤 <b>ACTIVITÉ FAIBLE</b> : Conditions peu favorables."}</p>
        </div>
        """, unsafe_allow_html=True)

    # --- TABLEAU DE SYNTHÈSE 7 JOURS ---
    st.divider()
    st.subheader("📅 Prévisions sur 7 jours")
    
    future_df = res_df[res_df['Date'].dt.date >= now.date()].copy()
    future_df['Date'] = future_df['Date'].dt.strftime('%A %d %b')
    
    # Formatage pour affichage
    view_df = future_df.rename(columns={
        "Temp": "Temp (°C)", 
        "Pluie_8h": "Pluie 8h (mm)", 
        "Prob": "Probabilité (%)"
    })
    
    st.table(view_df.set_index('Date'))

except Exception as e:
    st.error(f"Erreur lors de la récupération des données : {e}")

st.caption(f"© n+p wildlife ecology | Données : Open-Meteo & Modèles Phénologiques | Actualisé à {datetime.now().strftime('%H:%M')}")
