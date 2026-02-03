import streamlit as st
import requests
import pandas as pd
import numpy as np
from datetime import datetime
import pgeocode  # Bibliothèque pour les codes postaux mondiaux

# --- CONFIGURATION & INTERFACE ---
st.set_page_config(page_title="Prédicteur de Crapauds Pro", page_icon="🐸", layout="wide")

st.title("🐸 Prédiction de Migration des Batraciens (Suisse)")

# --- INITIALISATION GÉO-NPA ---
nomi = pgeocode.Nominatim('ch') # Base de données suisse

# --- STATIONS MÉTÉOSUISSE (Points de référence) ---
STATIONS_SUISSE = {
    "Lausanne-Pully": (46.512, 6.667), "Genève-Cointrin": (46.233, 6.109),
    "Neuchâtel": (46.990, 6.929), "Sion": (46.219, 7.330),
    "Fribourg-Posieux": (46.771, 7.104), "Payerne": (46.811, 6.942),
    "Yverdon-les-Bains": (46.778, 6.641), "Aigle": (46.319, 6.924),
    "Echallens": (46.641, 6.634), "Morges": (46.510, 6.498),
    "Nyon": (46.383, 6.239), "Berne-Belp": (46.914, 7.502),
    "Bâle-Binningen": (47.541, 7.583), "Zurich-Fluntern": (47.378, 8.565),
    "Lugano": (46.003, 8.951), "Chaux-de-Fonds": (47.101, 6.826)
}

# --- FONCTIONS ---
def calculer_distance(lat1, lon1, lat2, lon2):
    return np.sqrt((lat1 - lat2)**2 + (lon1 - lon2)**2)

def trouver_station_proche(lat, lon):
    plus_proche = "Lausanne-Pully"
    dist_min = float('inf')
    for nom, coords in STATIONS_SUISSE.items():
        d = calculer_distance(lat, lon, coords[0], coords[1])
        if d < dist_min:
            dist_min = d
            plus_proche = nom
    return plus_proche

def calculer_facteur_lune(date):
    ref_nouvelle_lune = datetime(2025, 2, 28)
    cycle_lunaire = 29.53059
    diff = (date - ref_nouvelle_lune).total_seconds() / (24 * 3600)
    phase = (diff % cycle_lunaire) / cycle_lunaire
    illumination = (1 - np.cos(2 * np.pi * phase)) / 2
    return 1.0 + (illumination * 0.2)

def get_frog_emoji(prob):
    if prob >= 80: return "🐸🐸🐸🐸"
    if prob >= 50: return "🐸🐸"
    if prob >= 20: return "🐸"
    return "❌"

# --- INTERFACE LATÉRALE ---
st.sidebar.header("📍 Localisation")
npa_input = st.sidebar.text_input("Entrez le NPA suisse (ex: 1000, 1260, 1950) :", "1000")

# Récupération des données GPS du NPA
info_npa = nomi.query_postal_code(npa_input)

if pd.isna(info_npa.latitude):
    st.sidebar.error("NPA non trouvé en Suisse. Utilisation de Lausanne par défaut.")
    LAT, LON, NOM_LOC = 46.516, 6.632, "Lausanne"
else:
    LAT, LON = info_npa.latitude, info_npa.longitude
    NOM_LOC = f"{info_npa.place_name} ({npa_input})"
    st.sidebar.success(f"Localisé : {NOM_LOC}")

station_proche = trouver_station_proche(LAT, LON)
st.sidebar.info(f"Station météo de référence : **{station_proche}**")

HEURE_CIBLE = st.sidebar.slider("Heure du relevé :", 16, 22, 19)

# --- RÉCUPÉRATION & CALCULS ---
url = "https://api.open-meteo.com/v1/forecast"
params = {
    "latitude": LAT, "longitude": LON,
    "hourly": "temperature_2m,precipitation,apparent_temperature",
    "timezone": "Europe/Berlin", "past_days": 7, "forecast_days": 7
}

try:
    response = requests.get(url, params=params)
    data = response.json()

    if 'hourly' in data:
        df = pd.DataFrame(data['hourly'])
        df['time'] = pd.to_datetime(df['time'])
        all_results = []

        for i in range(len(df)):
            if df.iloc[i]['time'].hour == HEURE_CIBLE:
                idx = i
                if idx < 8: continue
                
                row = df.iloc[idx]
                dt_obj = row['time'].to_pydatetime()
                
                # Algorithme Alpha
                f_mois = {1:0.1, 2:0.5, 3:1.0, 4:1.0, 5:0.4}.get(dt_obj.month, 0.0)
                r8 = df.iloc[idx-8:idx]['precipitation'].sum()
                f_r8 = 1.0 if r8 >= 10 else (0.1 if r8 == 0 else 0.1 + (r8/10)*0.9)
                t8 = df.iloc[idx-8:idx]['temperature_2m'].mean()
                f_t8 = 0.1 + ((t8 - 4) / 4) * 0.9 if 4 <= t8 <= 8 else (1.0 if t8 > 8 else 0.1)
                
                f_moon = calculer_facteur_lune(dt_obj)
                
                prob = int(min(100, (f_mois * f_r8 * f_t8 * f_moon) * 100))
                
                all_results.append({
                    "Date_DT": row['time'],
                    "Pluie (8h)": f"{r8:.1f}mm",
                    "Temp (8h)": f"{t8:.1f}°C",
                    "Lune": f"+{int((f_moon-1)*100)}%",
                    "Score": prob,
                    "Verdict": f"{prob}% {get_frog_emoji(prob)}"
                })

        full_df = pd.DataFrame(all_results)
        future_df = full_df[full_df['Date_DT'].dt.date >= datetime.now().date()].copy()
        future_df['Date'] = future_df['Date_DT'].dt.strftime('%d %b (%a)')

        st.subheader(f"🔮 Prévisions pour {NOM_LOC}")
        st.table(future_df.drop(columns=['Score', 'Date_DT']).set_index('Date'))
        
    st.markdown("<p style='text-align: center; color: grey;'>© n+p wildlife ecology | Données Open-Meteo & pgeocode</p>", unsafe_allow_html=True)
except Exception as e:
    st.error(f"Erreur de connexion : {e}")
