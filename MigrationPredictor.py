import streamlit as st
import requests
import pandas as pd
import numpy as np
from datetime import datetime

# --- CONFIGURATION ---
st.set_page_config(page_title="Toad Predictor Pro", page_icon="🐸", layout="wide")

st.title("🐸 Prédicteur de Migration Batraciens")
st.markdown("Version **Alpha Stable** | © n+p wildlife ecology")

# --- FONCTIONS ---
def get_moon_info(date):
    """Calcule l'illumination et renvoie l'emoji."""
    # Référence : Nouvelle lune le 28 février 2025
    ref_new_moon = datetime(2025, 2, 28)
    diff = (date - ref_new_moon).total_seconds() / (24 * 3600)
    phase = (diff % 29.53) / 29.53
    illum = (1 - np.cos(2 * np.pi * phase)) / 2
    
    if phase < 0.06 or phase > 0.94: emoji = "🌑" 
    elif phase < 0.19: emoji = "🌒"
    elif phase < 0.31: emoji = "🌓" 
    elif phase < 0.44: emoji = "🌔"
    elif phase < 0.56: emoji = "🌕" 
    elif phase < 0.69: emoji = "🌖"
    elif phase < 0.81: emoji = "🌗" 
    else: emoji = "🌘"
    return illum, emoji

def get_frog_emoji(prob):
    if prob >= 80: return "🐸🐸🐸🐸"
    if prob >= 50: return "🐸🐸"
    if prob >= 20: return "🐸"
    return "❌"

# --- SIDEBAR ---
st.sidebar.header("📍 Secteur d'étude")
villes = {
    "Lausanne": (46.516, 6.632), "Genève": (46.204, 6.143),
    "Neuchâtel": (46.990, 6.929), "Fribourg": (46.806, 7.161),
    "Sion": (46.233, 7.356), "Yverdon": (46.778, 6.641),
    "Berne": (46.948, 7.447), "Bâle": (47.559, 7.588),
    "Zurich": (47.376, 8.541), "Lugano": (46.003, 8.951)
}
nom_ville = st.sidebar.selectbox("Ville de référence :", list(villes.keys()))
lat, lon = villes[nom_ville]

heure_recherche = st.sidebar.slider("Heure du relevé :", 17, 23, 19)

# --- DATA ---
url = "https://api.open-meteo.com/v1/forecast"
params = {
    "latitude": lat, "longitude": lon,
    "hourly": "temperature_2m,precipitation,relative_humidity_2m",
    "timezone": "Europe/Berlin", "past_days": 7, "forecast_days": 7
}

try:
    data = requests.get(url, params=params).json()
    df = pd.DataFrame(data['hourly'])
    df['time'] = pd.to_datetime(df['time'])
    
    results = []
    for i in range(len(df)):
        if df.iloc[i]['time'].hour == heure_recherche:
            row = df.iloc[i]
            dt = row['time'].to_pydatetime()
            
            # Algorithme de calcul
            f_m = {1:0.1, 2:0.6, 3:1.0, 4:1.0, 5:0.5}.get(dt.month, 0.0)
            t = row['temperature_2m']
            f_t = 0.1 + ((t-4)/4)*0.9 if 4<=t<=8 else (1.0 if t>8 else 0.05)
            p = row['precipitation']
            h = row['relative_humidity_2m']
            f_p = 1.0 if p > 0 else (0.7 if h > 85 else 0.2)
            illum, m_emoji = get_moon_info(dt)
            
            prob = int(min(100, (f_m * f_t * f_p * (1+(illum*0.2))) * 100))
            
            results.append({
                "Date": dt.strftime('%d %b (%a)'),
                "Temp": f"{t}°C",
                "Lune": f"{m_emoji}",
                "Probabilité": f"{prob}% {get_frog_emoji(prob)}"
            })

    # Affichage
    st.subheader(f"Prévisions pour {nom_ville}")
    st.table(pd.DataFrame(results).set_index("Date"))

except Exception as e:
    st.error("Connexion météo impossible. Vérifiez votre accès internet.")
