import streamlit as st
import pandas as pd
import numpy as np
import requests
from datetime import datetime
import pgeocode

# --- CONFIGURATION ---
st.set_page_config(page_title="Radar Batraciens Suisse", page_icon="🐸", layout="wide")

# Utilisation du cache pour pgeocode (évite de télécharger la base de données à chaque clic)
@st.cache_resource
def get_geocoder():
    return pgeocode.Nominatim('ch')

nomi = get_geocoder()

st.title("🐸 Radar de Migration (MétéoSuisse Live)")

# --- FONCTIONS ---
def get_moon_emoji(date):
    ref_new_moon = datetime(2025, 2, 28)
    lunar_cycle = 29.53059
    diff = (date - ref_new_moon).total_seconds() / (24 * 3600)
    phase = (diff % lunar_cycle) / lunar_cycle
    illumination = (1 - np.cos(2 * np.pi * phase)) / 2
    
    if phase < 0.06 or phase > 0.94: return "🌑", illumination
    elif phase < 0.19: return "🌒", illumination
    elif phase < 0.31: return "🌓", illumination
    elif phase < 0.44: return "🌔", illumination
    elif phase < 0.56: return "🌕", illumination
    elif phase < 0.69: return "🌖", illumination
    elif phase < 0.81: return "🌗", illumination
    else: return "🌘", illumination

@st.cache_data(ttl=600)
def fetch_meteoswiss():
    url = "https://data.geo.admin.ch/ch.meteoschweiz.messwerte-aktuell/ch.meteoschweiz.messwerte-aktuell_en.csv"
    return pd.read_csv(url, sep=';', on_bad_lines='skip')

# --- STATIONS ---
STATIONS = {
    "Lausanne": (46.51, 6.66, "PUY"), "Genève": (46.23, 6.10, "GVE"),
    "Sion": (46.21, 7.33, "SIO"), "Neuchâtel": (46.99, 6.93, "NEU"),
    "Fribourg": (46.77, 7.10, "FRE"), "Payerne": (46.81, 6.94, "PAY"),
    "Aigle": (46.31, 6.92, "AIG"), "La Chaux-de-Fonds": (47.08, 6.79, "CDF"),
    "Bâle": (47.54, 7.58, "BAS"), "Zurich": (47.37, 8.56, "SMA")
}

# --- LOGIQUE NPA ---
npa = st.sidebar.text_input("Code Postal (NPA) :", "1000")
res = nomi.query_postal_code(npa)

if not pd.isna(res.latitude):
    u_lat, u_lon, u_ville = res.latitude, res.longitude, res.place_name
else:
    u_lat, u_lon, u_ville = 46.51, 6.63, "Lausanne (Défaut)"

# Trouver station la plus proche
sid = "PUY"
d_min = 999
for n, (slat, slon, s_id) in STATIONS.items():
    d = np.sqrt((u_lat-slat)**2 + (u_lon-slon)**2)
    if d < d_min: d_min, sid = d, s_id

# --- CALCULS ---
df = fetch_meteoswiss()
if df is not None:
    data = df[df['Station/Location'] == sid]
    if not data.empty:
        r = data.iloc[0]
        t, p, h = float(r['tre200s0']), float(r['rre150z0']), float(r['ure200s0'])
        m_emoji, illum = get_moon_emoji(datetime.now())
        
        # Algorithme Alpha
        f_t = 0.1 + ((t-4)/4)*0.9 if 4<=t<=8 else (1.0 if t>8 else 0.05)
        f_p = 1.0 if p>0 else (0.8 if h>85 else 0.2)
        f_m = {1:0.1, 2:0.6, 3:1.0, 4:1.0, 5:0.5}.get(datetime.now().month, 0.0)
        prob = int(min(100, (f_t * f_p * f_m * (1+(illum*0.2))) * 100))

        st.subheader(f"📍 Conditions à {u_ville} (Station {sid})")
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Temp.", f"{t}°C")
        col2.metric("Pluie", f"{p}mm")
        col3.metric("Humidité", f"{h}%")
        col4.metric("Lune", f"{m_emoji}")

        st.divider()
        st.markdown(f"<h1 style='text-align:center;'>{' 🐸 ' * (max(1, prob//20))}</h1>", unsafe_allow_html=True)
        st.write(f"### Probabilité de migration : **{prob}%**")
        st.progress(prob/100)
    else:
        st.error("Station météo temporairement hors ligne.")

st.sidebar.caption("© n+p wildlife ecology")
