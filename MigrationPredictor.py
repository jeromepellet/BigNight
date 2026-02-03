import streamlit as st
import pandas as pd
import requests
from datetime import datetime

# Configuration minimale
st.set_page_config(page_title="Radar Batraciens", layout="wide")

# Liste simplifiée des stations
STATIONS = {
    "Lausanne": "PUY",
    "Genève": "GVE",
    "Sion": "SIO",
    "Neuchâtel": "NEU",
    "Fribourg": "FRE",
    "La Chaux-de-Fonds": "CDF"
}

st.title("🐸 Radar Batraciens Suisse")

# Sidebar
ville = st.sidebar.selectbox("Choisir une ville", list(STATIONS.keys()))
station_id = STATIONS[ville]

# Récupération des données avec Time-out pour éviter de bloquer le serveur
@st.cache_data(ttl=600)
def get_data():
    url = "https://data.geo.admin.ch/ch.meteoschweiz.messwerte-aktuell/ch.meteoschweiz.messwerte-aktuell_en.csv"
    try:
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            import io
            return pd.read_csv(io.StringIO(r.text), sep=';')
    except:
        return None
    return None

data = get_data()

if data is not None:
    line = data[data['Station/Location'] == station_id]
    if not line.empty:
        # Extraction sécurisée
        try:
            temp = float(line['tre200s0'].iloc[0])
            pluie = float(line['rre150z0'].iloc[0])
            humi = float(line['ure200s0'].iloc[0])
            
            # Calcul score
            score = 0
            if 5 < temp < 15: score += 40
            if pluie > 0: score += 40
            elif humi > 80: score += 20
            
            # Affichage
            c1, c2, c3 = st.columns(3)
            c1.metric("Température", f"{temp} °C")
            c2.metric("Pluie", f"{pluie} mm")
            c3.metric("Humidité", f"{humi} %")
            
            st.write(f"### Probabilité de migration : {score}%")
            st.progress(score/100)
        except:
            st.error("Données de la station incomplètes.")
    else:
        st.warning("Station non trouvée dans le flux MétéoSuisse.")
else:
    st.error("Impossible de contacter MétéoSuisse.")
