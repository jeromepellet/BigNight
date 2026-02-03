import streamlit as st
import requests
import pandas as pd
import numpy as np
from datetime import datetime

# --- CONFIGURATION ---
st.set_page_config(page_title="Toad Predictor", page_icon="🐸")

def get_moon(date):
    ref = datetime(2025, 2, 28)
    diff = (date - ref).total_seconds() / (24 * 3600)
    phase = (diff % 29.53) / 29.53
    illum = (1 - np.cos(2 * np.pi * phase)) / 2
    emojis = ["🌑","🌒","🌓","🌔","🌕","🌖","🌗","🌘"]
    idx = int((phase * 8) + 0.5) % 8
    return emojis[idx], illum

st.title("🐸 Toad Migration Predictor")

# --- SIDEBAR ---
villes = {"Lausanne": (46.51, 6.63), "Geneva": (46.20, 6.14), "Sion": (46.22, 7.35)}
choix = st.sidebar.selectbox("City", list(villes.keys()))
lat, lon = villes[choix]

# --- DATA ---
url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&hourly=temperature_2m,precipitation,relative_humidity_2m&timezone=Europe/Berlin"

try:
    data = requests.get(url).json()
    df = pd.DataFrame(data['hourly'])
    df['time'] = pd.to_datetime(df['time'])
    
    results = []
    # Filter for evening hours (19:00)
    subset = df[df['time'].dt.hour == 19].tail(7)
    
    for _, row in subset.iterrows():
        dt = row['time'].to_pydatetime()
        m_emoji, illum = get_moon(dt)
        
        # Simple Logic
        t = row['temperature_2m']
        p = row['precipitation']
        h = row['relative_humidity_2m']
        
        # Score calculation
        f_t = 1.0 if t > 8 else (0.1 if t < 4 else 0.5)
        f_p = 1.0 if p > 0 else (0.6 if h > 85 else 0.2)
        prob = int(f_t * f_p * (1 + (illum * 0.2)) * 100)
        
        results.append({
            "Day": dt.strftime('%a %d'),
            "Temp": f"{t}°C",
            "Rain": f"{p}mm",
            "Moon": m_emoji,
            "Prob": f"{prob}% {'🐸' * (prob//25) if prob > 20 else '❌'}"
        })
    
    st.table(pd.DataFrame(results).set_index("Day"))

except Exception as e:
    st.error(f"Waiting for data... ({e})")
