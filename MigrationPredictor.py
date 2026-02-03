import streamlit as st
import pandas as pd
import numpy as np
import requests
import os
from datetime import datetime
from math import radians, cos, sin, asin, sqrt

# --- CONFIGURATION ENVIRONNEMENT ---
# Indispensable pour le déploiement Cloud : définit un dossier accessible en écriture
import os
# On crée le dossier s'il n'existe pas
if not os.path.exists('/tmp/pgeocode_data'):
    os.makedirs('/tmp/pgeocode_data')
os.environ['PGEOCODE_DATA_DIR'] = '/tmp/pgeocode_data'

import pgeocode

# --- CONFIGURATION PAGE ---
st.set_page_config(
    page_title="Radar Batraciens Pro", 
    page_icon="🐸", 
    layout="wide"
)

# --- CONSTANTES ---
# Dictionnaire des stations : Nom -> (Lat, Lon, ID MétéoSuisse)
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

# --- LOGIQUE DE GÉOLOCALISATION ---
@st.cache_resource
def get_geocoder():
    """Initialise le moteur de recherche de codes postaux."""
    return pgeocode.Nominatim('ch')

def haversine(lat1, lon1, lat2, lon2):
    """Calcule la distance en km entre deux points (formule de Haversine)."""
    R = 6371  # Rayon de la Terre en km
    dLat = radians(lat2 - lat1)
    dLon = radians(lon2 - lon1)
    lat1, lat2 = radians(lat1), radians(lat2)
    a = sin(dLat/2)**2 + cos(lat1)*cos(lat2)*sin(dLon/2)**2
    c = 2*asin(sqrt(a))
    return R * c

def find_nearest_station(user_lat, user_lon):
    """Associe les coordonnées de l'utilisateur à la station la plus proche."""
    best_station = None
    min_dist = float('inf')
    
    for name, (s_lat, s_lon, s_id) in STATIONS_METEO.items():
        d = haversine(user_lat, user_lon, s_lat, s_lon)
        if d < min_dist:
            min_dist = d
            best_station = {"id": s_id, "name": name, "dist": d}
    return best_station

# --- RÉCUPÉRATION MÉTÉO ---
@st.cache_data(ttl=600)
def fetch_meteoswiss_data():
    """Récupère les données live de MétéoSuisse."""
    url = "https://data.geo.admin.ch/ch.meteoschweiz.messwerte-aktuell/ch.meteoschweiz.messwerte-aktuell_en.csv"
    try:
        df = pd.read_csv(url, sep=';')
        return df
    except Exception as e:
        st.error(f"Erreur de connexion MétéoSuisse: {e}")
        return None

# --- CALCUL PROBABILITÉ (Modèle simplifié) ---
def get_migration_score(temp, rain, humidity):
    score = 0
    # Température optimale entre 7 et 12 degrés
    if 5 <= temp <= 15: score += 40
    # Pluie ou forte humidité
    if rain > 0: score += 40
    elif humidity > 80: score += 30
    # Saison (Mars/Avril)
    month = datetime.now().month
    if month in [3, 4]: score += 20
    return min(100, score)

# --- INTERFACE UTILISATEUR ---
def main():
    st.title("🐸 Radar Batraciens Suisse")
    st.markdown("---")

    with st.sidebar:
        st.header("📍 Localisation")
        npa = st.text_input("Entrez votre NPA (ex: 1000, 1200)", value="1000")
        
        nomi = get_geocoder()
        location_data = nomi.query_postal_code(npa)
        
        if pd.isna(location_data.latitude):
            st.error("NPA non trouvé.")
            st.stop()
        
        st.success(f"Ville détectée : **{location_data.place_name}**")
        
        # Trouver la station la plus proche
        station = find_nearest_station(location_data.latitude, location_data.longitude)
        st.info(f"Station la plus proche : **{station['name']}** ({station['dist']:.1f} km)")

    # Récupération des données météo
    df_meteo = fetch_meteoswiss_data()
    
    if df_meteo is not None:
        # Filtrage pour la station sélectionnée
        row = df_meteo[df_meteo['Station/Location'] == station['id']]
        
        if not row.empty:
            # Extraction des valeurs (MétéoSuisse : tre200s0=temp, rre150z0=précip, ure200s0=hum)
            temp = float(row['tre200s0'].values[0])
            rain = float(row['rre150z0'].values[0])
            hum = float(row['ure200s0'].values[0])
            
            # Calcul du score
            prob = get_migration_score(temp, rain, hum)
            
            # Affichage des métriques
            col1, col2, col3 = st.columns(3)
            col1.metric("🌡️ Température", f"{temp} °C")
            col2.metric("🌧️ Pluie (10 min)", f"{rain} mm")
            col3.metric("💧 Humidité", f"{hum} %")
            
            st.markdown("---")
            
            # Affichage de la probabilité
            st.subheader("Estimation du risque de migration")
            color = "green" if prob < 30 else "orange" if prob < 70 else "red"
            st.markdown(f"<h1 style='color:{color}; text-align:center;'>{prob}%</h1>", unsafe_allow_html=True)
            st.progress(prob / 100)
            
            if prob > 70:
                st.warning("⚠️ **ALERTE :** Risque de migration massif. Soyez vigilants sur les routes près des zones humides !")
            else:
                st.info("Conditions calmes pour le moment.")
        else:
            st.warning(f"La station {station['id']} ne transmet pas de données actuellement.")

if __name__ == "__main__":
    main()
