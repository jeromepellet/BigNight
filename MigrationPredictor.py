import streamlit as st
import pandas as pd
import numpy as np
import requests
from datetime import datetime

# Configuration de la page
st.set_page_config(page_title="Radar Batraciens Suisse", layout="wide", page_icon="🐸")

# --- PARAMÈTRES LUNAIRES ---
# Référence : Nouvelle lune le 28 février 2025 (pour caler le cycle de 29.5 jours)
REF_NOUVELLE_LUNE = datetime(2025, 2, 28)
CYCLE_LUNAIRE = 29.53059

# --- STATIONS MÉTÉOSUISSE ---
STATIONS = {
    "Aigle": "AIG", "Altdorf": "ALT", "Avenches": "AVE", "Bale-Binningen": "BAS", 
    "Bulle": "BUL", "Berne": "BER", "Bienne": "BIE", "Château-d'Oex": "CHX",
    "Chaux-de-Fonds (La)": "CDF", "Coire": "CHU", "Crans-Montana": "MON", 
    "Delémont": "DEL", "Fribourg / Posieux": "FRE", "Genève / Cointrin": "GVE", 
    "Gstaad": "GST", "Interlaken": "INT", "Lausanne / Pully": "PUY", 
    "Montreux": "MOT", "Neuchâtel": "NEU", "Nyon": "NYO", "Payerne": "PAY", 
    "Sion": "SIO", "St-Gall": "STG", "Vevey": "VEV", "Visp (Viège)": "VIS", 
    "Yverdon-les-Bains": "YVE", "Zermatt": "ZER" # (Liste abrégée ici pour le code, mais extensible)
}

# --- FONCTIONS ---
def calculer_illumination_lune(date):
    """Calcule le pourcentage d'illumination de la lune (0 à 1)"""
    diff = (date - REF_NOUVELLE_LUNE).total_seconds() / (24 * 3600)
    phase = (diff % CYCLE_LUNAIRE) / CYCLE_LUNAIRE
    return (1 - np.cos(2 * np.pi * phase)) / 2

def get_linear_score(valeur, min_val, max_val):
    if valeur <= min_val: return 0.1
    if valeur >= max_val: return 1.0
    return 0.1 + ((valeur - min_val) / (max_val - min_val)) * 0.9

@st.cache_data(ttl=600)
def charger_donnees_meteoswiss():
    url = "https://data.geo.admin.ch/ch.meteoschweiz.messwerte-aktuell/ch.meteoschweiz.messwerte-aktuell_en.csv"
    try:
        return pd.read_csv(url, sep=';')
    except:
        return None

# --- INTERFACE ---
st.title("🐸 Radar de Migration Batraciens (Météo + Lune)")
st.sidebar.header("Paramètres")
ville_choisie = st.sidebar.selectbox("Station MétéoSuisse :", sorted(list(STATIONS.keys())))
code_station = STATIONS[ville_choisie]

df_brut = charger_donnees_meteoswiss()

if df_brut is not None:
    try:
        data = df_brut[df_brut['Station/Location'] == code_station].iloc[0]
        t = float(data['tre200s0']) # Température
        p = float(data['rre150z0']) # Pluie
        h = float(data['ure200s0']) # Humidité
        
        # 1. Calcul Lune
        maintenant = datetime.now()
        illumination = calculer_illumination_lune(maintenant)
        boost_lunaire = 1.0 + (illumination * 0.25) # Jusqu'à 25% de bonus si pleine lune
        
        # 2. Algorithme de migration
        f_mois = {1:0.1, 2:0.5, 3:1.0, 4:1.0, 5:0.4}.get(maintenant.month, 0.0)
        f_temp = get_linear_score(t, 4, 8)
        f_hum = 1.0 if p > 0 else get_linear_score(h, 70, 95)
        
        # 3. Probabilité Finale (Météo * Boost Lune)
        prob = int((f_mois * f_temp * f_hum * boost_lunaire) * 100)
        prob = min(100, prob)

        # Affichage
        st.subheader(f"Station : {ville_choisie}")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Température", f"{t} °C")
        c2.metric("Pluie", f"{p} mm")
        c3.metric("Humidité", f"{h} %")
        c4.metric("Lune", f"{int(illumination*100)} %")
        
        st.divider()

        # Système de Grenouilles
        num_frogs = max(1, min(5, (prob // 20) + 1))
        frog_display = " ".join(["🐸" for _ in range(num_frogs)])
        
        st.markdown(f"<h1 style='text-align: center; font-size: 80px;'>{frog_display}</h1>", unsafe_allow_html=True)
        
        # Message de statut
        if prob > 80: st.error(f"### 🚨 MIGRATION MASSIVE ({prob}%)")
        elif prob > 50: st.warning(f"### ⚠️ MIGRATION FORTE ({prob}%)")
        else: st.success(f"### ✅ ACTIVITÉ FAIBLE ({prob}%)")

        st.caption(f"Données MétéoSuisse du {data['Date']} | Cycle lunaire inclus.")

    except Exception as e:
        st.error(f"Erreur de lecture : {e}")
