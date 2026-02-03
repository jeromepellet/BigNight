import streamlit as st
import pandas as pd
import numpy as np
import requests
from datetime import datetime

# --- CONFIGURATION PAGE ---
st.set_page_config(page_title="Radar Batraciens", page_icon="🐸", layout="wide")

# --- DONNÉES FIXES (Remplace pgeocode) ---
# Format: "Nom Ville": (Latitude, Longitude, ID_Station_MeteoSuisse)
VILLES_SUISSES = {
    "Lausanne": (46.516, 6.632, "PUY"),
    "Genève": (46.204, 6.143, "GVE"),
    "Sion": (46.229, 7.359, "SIO"),
    "Neuchâtel": (46.991, 6.931, "NEU"),
    "Fribourg": (46.806, 7.161, "FRE"),
    "Payerne": (46.820, 6.937, "PAY"),
    "Aigle": (46.315, 6.965, "AIG"),
    "La Chaux-de-Fonds": (47.103, 6.832, "CDF"),
    "Berne": (46.948, 7.447, "BER"),
    "Lugano": (46.003, 8.951, "LUG")
}

# --- RÉCUPÉRATION MÉTÉO ---
@st.cache_data(ttl=600)
def fetch_meteo_live():
    url = "https://data.geo.admin.ch/ch.meteoschweiz.messwerte-aktuell/ch.meteoschweiz.messwerte-aktuell_en.csv"
    try:
        df = pd.read_csv(url, sep=';')
        return df
    except Exception as e:
        st.error(f"Erreur de connexion MétéoSuisse : {e}")
        return None

# --- INTERFACE ---
st.title("🐸 Radar de Migration des Batraciens")
st.markdown("Prévisions basées sur les données en temps réel de MétéoSuisse.")

with st.sidebar:
    st.header("📍 Localisation")
    choix_ville = st.selectbox("Sélectionnez votre ville :", list(VILLES_SUISSES.keys()))
    lat, lon, station_id = VILLES_SUISSES[choix_ville]
    st.info(f"Station MétéoSuisse : **{station_id}**")

# Récupération des données
df_meteo = fetch_meteo_live()

if df_meteo is not None:
    # On cherche la ligne correspondant à la station
    data_station = df_meteo[df_meteo['Station/Location'] == station_id]
    
    if not data_station.empty:
        # tre200s0 = Température, rre150z0 = Précipitations, ure200s0 = Humidité
        try:
            temp = float(data_station['tre200s0'].iloc[0])
            pluie = float(data_station['rre150z0'].iloc[0])
            humi = float(data_station['ure200s0'].iloc[0])
            
            # Calcul du score de migration simplifié
            score = 0
            if 5 <= temp <= 13: score += 40
            if pluie > 0: score += 40
            elif humi > 80: score += 30
            
            # Affichage
            col1, col2, col3 = st.columns(3)
            col1.metric("🌡️ Température", f"{temp} °C")
            col2.metric("🌧️ Pluie (10 min)", f"{pluie} mm")
            col3.metric("💧 Humidité", f"{humi} %")
            
            st.divider()
            
            # Résultat
            st.subheader("Probabilité de migration")
            couleur = "red" if score > 70 else "orange" if score > 30 else "green"
            st.markdown(f"<h1 style='text-align:center; color:{couleur};'>{score}%</h1>", unsafe_allow_html=True)
            st.progress(score / 100)
            
            if score > 70:
                st.error("🚨 **Conditions optimales !** Migration massive probable ce soir.")
            elif score > 30:
                st.warning("⚠️ **Activité possible.** Quelques déplacements à prévoir.")
            else:
                st.success("💤 **Calme.** Trop sec ou trop froid pour une migration majeure.")
                
        except Exception as e:
            st.warning("Certaines données météo sont manquantes pour cette station.")
    else:
        st.error("La station sélectionnée ne répond pas.")

st.divider()
st.caption(f"Dernière mise à jour : {datetime.now().strftime('%H:%M:%S')}")
