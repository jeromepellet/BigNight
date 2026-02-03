import streamlit as st
import pandas as pd
import numpy as np
import requests
from datetime import datetime

# --- TENTATIVE D'IMPORT DE PGEOCODE ---
try:
    import pgeocode
    nomi = pgeocode.Nominatim('ch')
except ImportError:
    st.error("La bibliothèque 'pgeocode' est manquante. Installez-la avec : pip install pgeocode")
    st.stop()

# --- CONFIGURATION ---
st.set_page_config(page_title="Radar Batraciens MétéoSuisse", page_icon="🐸", layout="wide")

st.title("🐸 Radar de Migration (MétéoSuisse + Phases Lunaires)")

# --- FONCTIONS LUNAIRES ---
def get_moon_data(date):
    """Calcule l'illumination et renvoie l'emoji correspondant."""
    ref_new_moon = datetime(2025, 2, 28)
    lunar_cycle = 29.53059
    diff = (date - ref_new_moon).total_seconds() / (24 * 3600)
    phase = (diff % lunar_cycle) / lunar_cycle
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

# --- STATIONS & MÉTÉO ---
STATIONS_METEO = {
    "Lausanne-Pully": (46.5119, 6.6672, "PUY"),
    "Genève-Cointrin": (46.2330, 6.1090, "GVE"),
    "Sion": (46.2187, 7.3303, "SIO"),
    "Neuchâtel": (46.9907, 6.9356, "NEU"),
    "Fribourg-Posieux": (46.7718, 7.1038, "FRE"),
    "Payerne": (46.8115, 6.9423, "PAY"),
    "Aigle": (46.3193, 6.9248, "AIG"),
    "Chaux-de-Fonds": (47.0837, 6.7925, "CDF")
}

@st.cache_data(ttl=600)
def fetch_meteoswiss_live():
    url = "https://data.geo.admin.ch/ch.meteoschweiz.messwerte-aktuell/ch.meteoschweiz.messwerte-aktuell_en.csv"
    try:
        # On force le séparateur ';' et on ignore les erreurs de lignes mal formées
        df = pd.read_csv(url, sep=';', on_bad_lines='skip')
        return df
    except Exception as e:
        st.error(f"Erreur de connexion aux données MétéoSuisse : {e}")
        return None

# --- INTERFACE ---
npa_input = st.sidebar.text_input("Votre Code Postal (NPA) :", "1010")

try:
    info_npa = nomi.query_postal_code(npa_input)
    if pd.isna(info_npa.latitude):
        LAT, LON, VILLE = 46.516, 6.632, "Lausanne"
    else:
        LAT, LON, VILLE = info_npa.latitude, info_npa.longitude, info_npa.place_name
except:
    LAT, LON, VILLE = 46.516, 6.632, "Lausanne (Défaut)"

# Trouver station la plus proche
dist_min = float('inf')
station_id = "PUY"
for nom, (slat, slon, sid) in STATIONS_METEO.items():
    d = np.sqrt((LAT - slat)**2 + (LON - slon)**2)
    if d < dist_min:
        dist_min = d
        station_id = sid

st.sidebar.success(f"📍 Localisation : {VILLE}")
st.sidebar.info(f"Station : {station_id}")

# --- CALCUL ET AFFICHAGE ---
df_live = fetch_meteoswiss_live()

if df_live is not None:
    data_station = df_live[df_live['Station/Location'] == station_id]

    if not data_station.empty:
        row = data_station.iloc[0]
        try:
            # Conversion sécurisée en float
            temp = float(row['tre200s0'])
            pluie = float(row['rre150z0'])
            humi = float(row['ure200s0'])
            
            illum, moon_emoji = get_moon_data(datetime.now())
            boost_lune = 1.0 + (illum * 0.2)
            
            f_temp = 0.1 + ((temp - 4) / 4) * 0.9 if 4 <= temp <= 8 else (1.0 if temp > 8 else 0.05)
            f_pluie = 1.0 if pluie > 0 else (0.8 if humi > 85 else 0.2)
            f_mois = {1:0.1, 2:0.6, 3:1.0, 4:1.0, 5:0.5}.get(datetime.now().month, 0.0)
            
            prob = int(min(100, (f_temp * f_pluie * f_mois * boost_lune) * 100))

            # --- TABLEAU DE SYNTHÈSE ---
            st.subheader(f"📍 État actuel à {VILLE}")
            
            recap_df = pd.DataFrame({
                "Paramètre": ["Température", "Précipitations", "Humidité", "Lune"],
                "Valeur": [f"{temp} °C", f"{pluie} mm", f"{humi} %", f"{moon_emoji} ({int(illum*100)}%)"]
            })
            st.table(recap_df)

            st.divider()
            
            # Rendu Grenouilles
            num_frogs = max(1, min(5, (prob // 20) + 1))
            st.markdown(f"<h1 style='text-align: center;'>{' 🐸 ' * num_frogs}</h1>", unsafe_allow_html=True)
            st.metric("Indice de migration", f"{prob} %")
            st.progress(prob / 100)

        except (ValueError, TypeError):
            st.warning(f"Données incomplètes pour la station {station_id}. Les capteurs sont peut-être en maintenance.")
    else:
        st.error(f"La station {station_id} ne répond pas.")
else:
    st.error("Impossible de charger le flux MétéoSuisse.")
