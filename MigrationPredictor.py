import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime

# Configuration de la page
st.set_page_config(page_title="Migration Batraciens Suisse", layout="wide", page_icon="🐸")

st.title("🐸 Prévision de Migration des Batraciens (Réseau SwissMetNet)")
st.markdown("Analyse en temps réel basée sur les stations officielles de **MétéoSuisse**.")

# --- DICTIONNAIRE ÉTENDU DES STATIONS (EXTRAIT DES ~100 PRINCIPALES) ---
STATIONS = {
    "Aigle": "AIG", "Altdorf": "ALT", "Altstätten": "ALT", "Andermatt": "ANT", "Appenzell": "APP",
    "Avenches": "AVE", "Bale-Binningen": "BAS", "Bad Ragaz": "RAG", "Bulle": "BUL", "Berne": "BER",
    "Bevieux": "BEV", "Bienne": "BIE", "Bourg-St-Pierre": "BOP", "Buchillon": "BUC", "Château-d'Oex": "CHX",
    "Chaux-de-Fonds (La)": "CDF", "Coire": "CHU", "Col du Grand St-Bernard": "GSB", "Corgémont": "COR",
    "Crans-Montana": "MON", "Davos": "DAV", "Delémont": "DEL", "Ebnat-Kappel": "EBK", "Echallens": "ECH",
    "Evolène": "EVO", "Fahy": "FAH", "Fribourg / Posieux": "FRE", "Genève / Cointrin": "GVE", "Glaris": "GLA",
    "Grimsel Hospiz": "GRI", "Grono": "GRO", "Gstaad": "GST", "Gütsch": "GUE", "Interlaken": "INT",
    "Jungfraujoch": "JUN", "Kloten (Zurich)": "KLO", "La Brévine": "LBR", "La Dôle": "DOL", "L'Auberson": "AUB",
    "Lausanne / Pully": "PUY", "Le Moléson": "MOL", "Les Attelas": "ATT", "Les Diablerets": "DIA",
    "Locarno / Monti": "OTL", "Lugano": "LUG", "Lucerne": "LUZ", "Magadino / Cadenazzo": "MAG", "Marsens": "MAR",
    "Mathod": "MAT", "Meiringen": "MEI", "Mervelier": "MER", "Montreux": "MOT", "Moutier": "MOU",
    "Muree (La)": "MUR", "Muri": "MUR", "Nax": "NAX", "Neuchâtel": "NEU", "Nyon": "NYO",
    "Oberägeri": "OBA", "Oron": "ORO", "Payerne": "PAY", "Pilocourt": "PIL", "Plaffeien": "PLA",
    "Pontresina": "PON", "Praz-de-Fort": "PDF", "Rances": "RAN", "Rapperswil": "RAP", "Reconvilier": "REC",
    "Rolle": "ROL", "Romont": "ROM", "Säntis": "SAE", "Samedan": "SAM", "Sarnen": "SAR",
    "Schaffhouse": "SHA", "Scuol": "SCU", "Semsales": "SEM", "Sion": "SIO", "St-Gall": "STG",
    "St-Moritz": "STM", "St-Prex": "SPX", "Ste-Croix": "STC", "Stans": "STA", "Taverne": "TAV",
    "Thun": "THU", "Titlis": "TIT", "Triolet": "TRI", "Troistorrents": "TRO", "Vaduz": "VAD",
    "Val de Bagnes": "VAB", "Val de Travers": "VTR", "Vevey": "VEV", "Visp (Viège)": "VIS", "Wädenswil": "WAE",
    "Weissfluhjoch": "WFJ", "Würenlingen": "WUE", "Yverdon-les-Bains": "YVE", "Zermatt": "ZER", "Zoug": "ZOU"
}

# --- FONCTIONS ---
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
ville_choisie = st.sidebar.selectbox("Sélectionnez votre station locale :", sorted(list(STATIONS.keys())))
code_station = STATIONS[ville_choisie]

df_brut = charger_donnees_meteoswiss()

if df_brut is not None:
    try:
        data = df_brut[df_brut['Station/Location'] == code_station].iloc[0]
        
        # tre200s0 = Temp air, rre150z0 = Précip, ure200s0 = Humidité
        t = float(data['tre200s0'])
        p = float(data['rre150z0'])
        h = float(data['ure200s0'])
        
        # Algorithme de migration
        f_mois = {1:0.1, 2:0.5, 3:1.0, 4:1.0, 5:0.4}.get(datetime.now().month, 0.0)
        f_temp = get_linear_score(t, 4, 8)
        f_hum = 1.0 if p > 0 else get_linear_score(h, 70, 95)
        
        prob = int((f_mois * f_temp * f_hum) * 100)
        
        # Affichage
        st.subheader(f"Données de la station : {ville_choisie}")
        c1, c2, c3 = st.columns(3)
        c1.metric("Température", f"{t} °C")
        c2.metric("Pluie (10 min)", f"{p} mm")
        c3.metric("Humidité", f"{h} %")
        
        st.divider()
        st.write(f"### Indice de probabilité : **{prob}%**")
        st.progress(prob / 100)
        
        if prob > 70:
            st.error("🚨 **Conditions Critiques** : Sortez les dispositifs de sauvetage !")
        elif prob > 40:
            st.warning("⚠️ **Vigilance** : Migration active observée.")
        else:
            st.success("✅ **Calme** : Peu de risques pour le moment.")
            
    except:
        st.error("Données temporairement indisponibles pour cette station.")
else:
    st.error("Connexion au serveur MétéoSuisse impossible.")
