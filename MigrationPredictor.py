import streamlit as st
import pandas as pd
import requests
import io
from datetime import datetime

# --- CONFIGURATION PAGE ---
st.set_page_config(
    page_title="Radar Batraciens Suisse",
    page_icon="🐸",
    layout="wide"
)

# --- CONSTANTES ---
STATIONS = {
    "Lausanne (Pully)": "PUY",
    "Genève (Cointrin)": "GVE",
    "Sion": "SIO",
    "Neuchâtel": "NEU",
    "Fribourg (Posieux)": "FRE",
    "Payerne": "PAY",
    "Aigle": "AIG",
    "La Chaux-de-Fonds": "CDF",
    "Berne": "BER",
    "Lugano": "LUG"
}

# --- RÉCUPÉRATION DES DONNÉES ---
@st.cache_data(ttl=600)
def fetch_meteo_data():
    # URL directe des mesures automatiques actuelles de MétéoSuisse
    url = "https://data.geo.admin.ch/ch.meteoschweiz.messwerte-aktuell/ch.meteoschweiz.messwerte-aktuell_en.csv"
    
    # Simulation d'un navigateur réel pour contourner les blocages pare-feu
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/csv'
    }
    
    try:
        # Tentative de connexion avec un délai généreux
        response = requests.get(url, headers=headers, timeout=20)
        
        if response.status_code == 200:
            # On vérifie que le contenu n'est pas vide
            if len(response.content) > 100:
                df = pd.read_csv(io.StringIO(response.content.decode('utf-8')), sep=';')
                return df, "LIVE"
            else:
                return None, "EMPTY_FILE"
        else:
            return None, f"HTTP_{response.status_code}"
            
    except Exception as e:
        return None, f"ERROR_{str(e)}"

# --- INTERFACE ---
st.title("🐸 Radar de Migration des Batraciens")
st.markdown("Analyse en temps réel des conditions de migration pour la Suisse.")

with st.sidebar:
    st.header("📍 Localisation")
    nom_ville = st.selectbox("Sélectionnez votre région :", list(STATIONS.keys()))
    id_station = STATIONS[nom_ville]
    st.info(f"Station Météo : **{id_station}**")

# Récupération
df, status = fetch_meteo_data()

# Gestion du mode "Secours" si MétéoSuisse bloque
if status != "LIVE":
    st.warning(f"⚠️ Connexion MétéoSuisse indisponible ({status}). Utilisation des données de secours.")
    # Données simulées cohérentes avec la saison actuelle
    df = pd.DataFrame({
        'Station/Location': list(STATIONS.values()),
        'tre200s0': [8.2, 9.5, 7.0, 6.8, 7.5, 8.0, 9.2, 4.5, 7.8, 10.2],  # Temp
        'rre150z0': [0.2, 0.0, 0.5, 0.0, 0.1, 0.0, 0.3, 0.8, 0.0, 0.0],  # Pluie
        'ure200s0': [88, 72, 90, 75, 85, 80, 89, 92, 78, 82]             # Humidité
    })

# --- AFFICHAGE ---
data_station = df[df['Station/Location'] == id_station]

if not data_station.empty:
    try:
        # tre200s0 = Température (°C), rre150z0 = Précipitations (mm), ure200s0 = Humidité (%)
        temp = float(data_station['tre200s0'].iloc[0])
        pluie = float(data_station['rre150z0'].iloc[0])
        humi = float(data_station['ure200s0'].iloc[0])

        # Logique de calcul du score (0-100)
        score = 0
        if 6 <= temp <= 13: score += 40
        if pluie > 0.1: score += 40
        elif humi > 85: score += 30
        
        # Bonus saisonnier (février à avril)
        if datetime.now().month in [2, 3, 4]: score += 20
        score = min(100, score)

        # Dashboard
        st.divider()
        c1, c2, c3 = st.columns(3)
        c1.metric("🌡️ Température", f"{temp} °C")
        c2.metric("🌧️ Pluie (10 min)", f"{pluie} mm")
        c3.metric("💧 Humidité", f"{humi} %")

        st.divider()
        
        # Indicateur de probabilité
        couleur = "red" if score > 75 else "orange" if score > 40 else "green"
        st.markdown(f"<h1 style='text-align:center; color:{couleur};'>Probabilité : {score}%</h1>", unsafe_allow_html=True)
        st.progress(score / 100)
        
        if score > 75:
            st.error("🚨 **ALERTE MIGRATION** : Conditions idéales. Attention sur les routes !")
        elif score > 40:
            st.warning("⚠️ **ACTIVITÉ MODÉRÉE** : Quelques déplacements probables cette nuit.")
        else:
            st.success("😴 **ACTIVITÉ FAIBLE** : Les conditions ne sont pas réunies pour une migration.")

    except Exception as e:
        st.error(f"Erreur technique : {e}")

st.divider()
st.caption(f"Dernière tentative de mise à jour : {datetime.now().strftime('%H:%M:%S')}")
