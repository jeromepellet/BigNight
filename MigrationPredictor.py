import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime

# Configuration
st.set_page_config(page_title="Suivi Migration - MeteoSuisse", layout="wide")

st.title("🐸 Prévision de Migration (Source: MeteoSuisse)")
st.info("Données issues de la station officielle de Lausanne-Pully (PUY)")

# --- FONCTIONS ---
def calculer_lune(date):
    # Nouvelle lune de référence: 28 fév 2025
    ref_nouvelle_lune = datetime(2025, 2, 28)
    cycle = 29.53059
    diff = (date - ref_nouvelle_lune).total_seconds() / (24 * 3600)
    phase = (diff % cycle) / cycle
    return (1 - np.cos(2 * np.pi * phase)) / 2

@st.cache_data(ttl=3600)
def charger_donnees_meteoswiss():
    # URL des données en direct de MeteoSuisse (dernières 48h)
    url = "https://data.geo.admin.ch/ch.meteoschweiz.messwerte-aktuell/ch.meteoschweiz.messwerte-aktuell_en.csv"
    df_raw = pd.read_csv(url, sep=';')
    
    # Filtrer pour la station de Pully (Lausanne)
    df_puy = df_raw[df_raw['Station/Location'] == 'PUY'].copy()
    return df_puy

# --- LOGIQUE ---
try:
    # 1. Récupération des données réelles
    data_puy = charger_donnees_meteoswiss()
    
    # Extraire les valeurs clés (Température et Précipitations)
    # Les noms de colonnes peuvent varier selon le format MeteoSuisse actuel
    temp_actuelle = float(data_puy['tre200s0'].values[0]) # Température de l'air 2m
    pluie_10min = float(data_puy['rre150z0'].values[0])   # Précipitations
    
    # 2. Calcul du Score de Migration
    illumination = calculer_lune(datetime.now())
    
    # Facteur Température (Seuil critique 4°C)
    f_temp = min(1.0, max(0.1, (temp_actuelle - 4) / 6)) if temp_actuelle > 4 else 0.0
    
    # Facteur Pluie (Basé sur les dernières mesures)
    f_pluie = 1.0 if pluie_10min > 0 else 0.1
    
    # Score Final avec Boost Lunaire (20%)
    score_final = (f_temp * f_pluie * (1.0 + (illumination * 0.2))) * 100
    score_final = min(100, score_final)

    # --- AFFICHAGE INTERFACE ---
    col1, col2, col3 = st.columns(3)
    col1.metric("Température (Pully)", f"{temp_actuelle} °C")
    col2.metric("Pluie (Dernière mesure)", f"{pluie_10min} mm")
    col3.metric("Illumination Lunaire", f"{round(illumination*100)} %")

    st.divider()

    # Jauge de probabilité
    st.write(f"### Probabilité actuelle de mouvement : **{round(score_final)}%**")
    st.progress(score_final / 100)

    if score_final > 75:
        st.error("🔥 **ALERTE MIGRATION MASSIVE** : Conditions optimales réunies !")
    elif score_final > 40:
        st.warning("🚶 **MIGRATION MODÉRÉE** : Quelques individus actifs prévus.")
    else:
        st.success("💤 **CALME** : Trop froid ou trop sec pour un mouvement important.")

except Exception as e:
    st.error(f"Impossible de lire les données directes de MeteoSuisse : {e}")
    st.write("Vérifiez la connexion ou le format du fichier CSV de Geo.admin.ch")
