import streamlit as st
import requests
import pandas as pd
import numpy as np
from datetime import datetime

# --- CONFIGURATION & INTERFACE ---
st.set_page_config(page_title="Toad Predictor Pro", page_icon="🐸", layout="wide")

st.title("🐸 Prédicteur de Migration Batraciens")

st.write("""
**Version Alpha Stable** : Cette version utilise les coordonnées directes pour garantir une compatibilité totale.
Le calcul est basé sur le produit de 6 facteurs (Mois, Pluie 8h/2h, Température 8h/2h et Cycle Lunaire).
""")
st.divider()

# --- INTERFACE LATÉRALE ---
st.sidebar.header("📍 Localisation & Horaire")

villes = {
    "Lausanne": {"lat": 46.516, "lon": 6.632},
    "Genève": {"lat": 46.204, "lon": 6.143},
    "Zurich": {"lat": 47.376, "lon": 8.541},
    "Berne": {"lat": 46.948, "lon": 7.447},
    "Bâle": {"lat": 47.559, "lon": 7.588},
    "Lugano": {"lat": 46.003, "lon": 8.951},
    "Sion": {"lat": 46.229, "lon": 7.359},
    "Neuchâtel": {"lat": 46.990, "lon": 6.929},
    "Yverdon": {"lat": 46.778, "lon": 6.641}
}

ville_choisie = st.sidebar.selectbox("Choisissez une ville :", list(villes.keys()))
LAT = villes[ville_choisie]["lat"]
LON = villes[ville_choisie]["lon"]

HEURE_CIBLE = st.sidebar.slider("Heure de passage (24h) :", 16, 22, 19)

# --- FONCTIONS DE CALCUL ---
def get_linear_score(value, min_val, max_val):
    if value <= min_val: return 0.1
    if value >= max_val: return 1.0
    return 0.1 + ((value - min_val) / (max_val - min_val)) * 0.9

def get_moon_info(date):
    # Référence : Nouvelle lune le 28 février 2025
    ref_new_moon = datetime(2025, 2, 28)
    diff = (date - ref_new_moon).total_seconds() / (24 * 3600)
    phase = (diff % 29.53) / 29.53
    illumination = (1 - np.cos(2 * np.pi * phase)) / 2
    
    if phase < 0.06 or phase > 0.94: emoji = "🌑" 
    elif phase < 0.19: emoji = "🌒"
    elif phase < 0.31: emoji = "🌓" 
    elif phase < 0.44: emoji = "🌔"
    elif phase < 0.56: emoji = "🌕" 
    elif phase < 0.69: emoji = "🌖"
    elif phase < 0.81: emoji = "🌗" 
    else: emoji = "🌘"
    return illumination, emoji

def get_frog_emoji(prob):
    if prob >= 80: return "🐸🐸🐸🐸"
    if prob >= 50: return "🐸🐸🐸"
    if prob >= 20: return "🐸🐸"
    if prob > 0: return "🐸"
    return "❌"

# --- RÉCUPÉRATION DES DONNÉES ---
url = "https://api.open-meteo.com/v1/forecast"
params = {
    "latitude": LAT, "longitude": LON,
    "hourly": "temperature_2m,precipitation,apparent_temperature",
    "timezone": "Europe/Berlin",
    "past_days": 7,
    "forecast_days": 7
}

try:
    response = requests.get(url, params=params)
    data = response.json()

    if 'hourly' in data:
        df = pd.DataFrame(data['hourly'])
        df['time'] = pd.to_datetime(df['time'])
        maintenant = datetime.now()

        all_results = []
        for i in range(len(df)):
            if df.iloc[i]['time'].hour == HEURE_CIBLE:
                idx = i
                if idx < 8: continue 
                
                row = df.iloc[idx]
                
                # 1. Mois
                f_month = {1:0.1, 2:0.5, 3:1.0, 4:1.0, 5:0.4}.get(row['time'].month, 0.0)
                
                # 2. Pluie
                rain_8h = df.iloc[idx-8 : idx]['precipitation'].sum()
                f_rain8 = 1.0 if rain_8h >= 10 else (0.1 if rain_8h == 0 else 0.1 + (rain_8h/10)*0.9)
                
                # 3. Température
                temp_8h = df.iloc[idx-8 : idx]['temperature_2m'].mean()
                f_temp8 = get_linear_score(temp_8h, 4, 8)
                
                # 4. Lune
                illum, moon_emoji = get_moon_info(row['time'].to_pydatetime())
                f_moon = 1.0 + (illum * 0.2)
                
                # Probabilité
                prob = int(min(100, (f_month * f_rain8 * f_temp8 * f_moon) * 100))
                
                all_results.append({
                    "Date": row['time'],
                    "Pluie 8h": f"{rain_8h:.1f}mm",
                    "Temp 8h": f"{temp_8h:.1f}°C",
                    "Lune": f"{moon_emoji}",
                    "Prob": prob,
                    "Résumé": f"{prob}% {get_frog_emoji(prob)}"
                })

        full_df = pd.DataFrame(all_results)
        future_df = full_df[full_df['Date'].dt.date >= maintenant.date()].copy()
        future_df['Date_Fr'] = future_df['Date'].dt.strftime('%d %b (%a)')

        st.subheader(f"🔮 Prévisions : {ville_choisie}")
        st.table(future_df.drop(columns=['Prob', 'Date']).rename(columns={'Date_Fr': 'Date'}))
        
        st.markdown("<p style='text-align: center; color: grey; margin-top: 50px;'>© n+p wildlife ecology</p>", unsafe_allow_html=True)
    else:
        st.error("Erreur API Météo.")
except Exception as e:
    st.error(f"Erreur technique : {e}")
