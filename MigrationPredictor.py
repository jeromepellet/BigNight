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
    url = "https://data.geo.admin.ch/ch.meteoschweiz.messwerte-aktuell/ch.meteoschweiz.messwerte-aktuell_en.csv"
    # User-Agent pour éviter d'être bloqué par le pare-feu de la Confédération
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    try:
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code == 200:
            # Décodage explicite en UTF-8
            df = pd.read_csv(io.StringIO(response.content.decode('utf-8')), sep=';')
            return df, False  # Données réelles
    except Exception as e:
        print(f"Erreur de connexion : {e}")
    
    # En cas d'échec, on génère des données de secours (Dummy Data)
    dummy_data = pd.DataFrame({
        'Station/Location': list(STATIONS.values()),
        'tre200s0': [8.2, 9.5, 7.0, 6.8, 7.5, 8.0, 9.2, 4.5, 7.8, 10.2],  # Temp
        'rre150z0': [0.2, 0.0, 0.5, 0.0, 0.1, 0.0, 0.3, 0.8, 0.0, 0.0],  # Pluie
        'ure200s0': [88, 72, 90, 75, 85, 80, 89, 92, 78, 82]             # Humidité
    })
    return dummy_data, True  # Données simulées

# --- INTERFACE ---
st.title("🐸 Radar de Migration des Batraciens")
st.markdown("Ce radar analyse les conditions météo en temps réel pour prédire les pics de migration (printemps/automne).")

with st.sidebar:
    st.header("📍 Localisation")
    nom_ville = st.selectbox("Sélectionnez votre région :", list(STATIONS.keys()))
    id_station = STATIONS[nom_ville]
    st.info(f"Station Météo : **{id_station}**")

# Chargement
df, is_dummy = fetch_meteo_data()

if is_dummy:
    st.warning("⚠️ MétéoSuisse est injoignable. Affichage de données simulées pour démonstration.")

# Filtrage
data_station = df[df['Station/Location'] == id_station]

if not data_station.empty:
    try:
        # Extraction des paramètres
        temp = float(data_station['tre200s0'].iloc[0])
        pluie = float(data_station['rre150z0'].iloc[0])
        humi = float(data_station['ure200s0'].iloc[0])

        # Calcul du score de probabilité
        score = 0
        # 1. Température (idéal 7-12°C)
        if 5 <= temp <= 14: score += 40
        elif 3 <= temp < 5 or 14 < temp <= 18: score += 15
        
        # 2. Précipitations / Humidité
        if pluie > 0: score += 40
        elif humi > 85: score += 30
        elif humi > 70: score += 15
        
        # 3. Facteur saisonnier (Mars-Avril = Bonus)
        mois_actuel = datetime.now().month
        if mois_actuel in [3, 4]: score += 20

        score = min(100, score)

        # Affichage des métriques
        st.divider()
        col1, col2, col3 = st.columns(3)
        col1.metric("🌡️ Température", f"{temp} °C")
        col2.metric("🌧️ Précipitations", f"{pluie} mm")
        col3.metric("💧 Humidité", f"{humi} %")

        # Résultat Visuel
        st.divider()
        st.subheader("Estimation de l'activité")
        
        if score > 75:
            st.error(f"🚨 **PROBABILITÉ TRÈS ÉLEVÉE ({score}%)**")
            st.markdown("**Conseil :** Migration massive en cours. Évitez les routes forestières et roulez prudemment près des points d'eau.")
        elif score > 40:
            st.warning(f"⚠️ **PROBABILITÉ MODÉRÉE ({score}%)**")
            st.markdown("**Conseil :** Conditions favorables. Quelques déplacements nocturnes attendus.")
        else:
            st.success(f"💤 **PROBABILITÉ FAIBLE ({score}%)**")
            st.markdown("**Conseil :** Conditions peu favorables à la migration (trop sec ou trop froid).")
        
        st.progress(score / 100)

    except Exception as e:
        st.error(f"Erreur lors du traitement des données de la station : {e}")
else:
    st.error("Aucune donnée disponible pour cette station dans le flux actuel.")

st.divider()
st.caption(f"Source : MétéoSuisse | Dernière mise à jour : {datetime.now().strftime('%d.%m.%Y à %H:%M')}")
