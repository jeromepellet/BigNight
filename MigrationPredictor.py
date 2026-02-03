import streamlit as st
import requests
import pandas as pd
import numpy as np
from datetime import datetime

# --- CONFIGURATION ---
st.set_page_config(page_title="Toad Predictor Pro", page_icon="🐸", layout="wide")

st.title("🐸 Swiss Toad Migration Predictor")
st.markdown("Automated model for *Bufo bufo* | Version 2.1 (Stable)")

# --- FONCTION LUNE ---
def get_moon_info(date):
    # Référence: Nouvelle lune le 28 fév 2025
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

# --- SIDEBAR ---
st.sidebar.header("Settings")
villes = {
    "Lausanne": (46.516, 6.632), "Geneva": (46.204, 6.143),
    "Zurich": (47.376, 8.541), "Bern": (46.948, 7.447),
    "Sion": (46.229, 7.359), "Neuchâtel": (46.990, 6.929)
}
choix = st.sidebar.selectbox("City:", list(villes.keys()))
lat, lon = villes[choix]
h_cible = st.sidebar.slider("Hour:", 17, 22, 19)

# --- CALCULS ---
url = "https://api.open-meteo.com/v1/forecast"
params = {
    "latitude": lat, "longitude": lon,
    "hourly": "temperature_2m,precipitation,relative_humidity_2m",
    "timezone": "Europe/Berlin", "past_days": 3, "forecast_days": 7
}

try:
    data = requests.get(url, params=params).json()
    df = pd.DataFrame(data['hourly'])
    df['time'] = pd.to_datetime(df['time'])
    
    res = []
    for i in range(len(df)):
        if df.iloc[i]['time'].hour == h_cible:
            row = df.iloc[i]
            dt = row['time'].to_pydatetime()
            
            # Algorithme
            f_m = {1:0.1, 2:0.5, 3:1.0, 4:1.0, 5:0.4}.get(dt.month, 0.0)
            t = row['temperature_2m']
            f_t = 0.1 + ((t-4)/4)*0.9 if 4<=t<=8 else (1.0 if t>8 else 0.05)
            p = row['precipitation']
            h = row['relative_humidity_2m']
            f_p = 1.0 if p > 0 else (0.7 if h > 85 else 0.2)
            illum, m_emoji = get_moon_info(dt)
            
            prob = int(min(100, (f_m * f_t * f_p * (1+(illum*0.2))) * 100))
            
            res.append({
                "Date": dt.strftime('%a %d %b'),
                "Temp": f"{t}°C",
                "Rain": f"{p}mm",
                "Moon": f"{m_emoji}",
                "Migration": f"{prob}% {'🐸'*(max(1,prob//20)) if prob>10 else '❌'}"
            })

    st.table(pd.DataFrame(res).set_index("Date"))
    
except Exception as e:
    st.error(f"Error: {e}")

st.caption("© n+p wildlife ecology")
