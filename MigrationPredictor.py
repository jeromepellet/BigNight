import streamlit as st
import pandas as pd
import numpy as np
import requests
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta

# --- CONFIGURATION DE LA PAGE ---
st.set_page_config(page_title="Radar Migration Amphibiens", page_icon="🐸", layout="centered")

# --- TRADUCTION DES DATES ---
DAYS_FR = {0: "Lundi", 1: "Mardi", 2: "Mercredi", 3: "Jeudi", 4: "Vendredi", 5: "Samedi", 6: "Dimanche"}
MONTHS_FR = {1: "janvier", 2: "février", 3: "mars", 4: "avril", 5: "mai", 6: "juin", 
             7: "juillet", 8: "août", 9: "septembre", 10: "octobre", 11: "novembre", 12: "décembre"}

def format_date_fr_complet(dt):
    return f"{DAYS_FR[dt.weekday()]} {dt.day:02d} {MONTHS_FR[dt.month]}"

# --- STATIONS OFFICIELLES METEOSUISSE (SwissMetNet) ---
CITY_DATA = {
    "Aigle (AIG)": (46.342, 6.925),
    "Altdorf (ALT)": (46.887, 8.622),
    "Bâle / Binningen (BAS)": (47.541, 7.584),
    "Berne / Zollikofen (BER)": (46.991, 7.464),
    "Bulle (BUL)": (46.615, 7.059),
    "Château-d'Oex (CHO)": (46.484, 7.135),
    "Coire (CHU)": (46.871, 9.531),
    "Fribourg / Posieux (FRE)": (46.772, 7.104),
    "Genève / Cointrin (GVE)": (46.234, 6.109),
    "La Chaux-de-Fonds (CDF)": (47.084, 6.792),
    "Lausanne / Pully (PUY)": (46.512, 6.668), # Index 10
    "Locarno / Monti (OTL)": (46.173, 8.788),
    "Lugano (LUG)": (45.998, 8.960),
    "Lucerne (LUZ)": (47.036, 8.301),
    "Magadino / Cadenazzo (MAG)": (46.160, 8.934),
    "Neuchâtel (NEU)": (46.990, 6.953),
    "Nyon / Changins (CHA)": (46.397, 6.239),
    "Payerne (PAY)": (46.811, 6.942),
    "Sion (SIO)": (46.219, 7.330),
    "Saint-Gall (STG)": (47.425, 9.399),
    "Viège / Visp (VIS)": (46.300, 7.850),
    "Zurich / Fluntern (SMA)": (47.378, 8.566)
}

# --- LOGIQUE SCIENTIFIQUE ---
def get_lunar_phase_emoji(dt):
    ref_new_moon = datetime(2026, 1, 19, 14, 0) 
    cycle = 29.53059
    diff = (dt - ref_new_moon).total_seconds() / 86400
    phase = (diff % cycle) / cycle 
    if phase < 0.0625 or phase > 0.9375: return "🌑"
    if phase < 0.1875: return "🌒"
    if phase < 0.3125: return "🌓"
    if phase < 0.4375: return "🌔"
    if phase < 0.5625: return "🌕"
    if phase < 0.6875: return "🌖"
    if phase < 0.8125: return "🌗"
    return "🌘"

def calculate_migration_probability(temp_8h_avg, feel_2h, rain_8h_total, rain_curr, month, dt):
    f_temp = min(1.0, max(0, (feel_2h - 4) / 6))
    f_hydrique = max(0.05, (min(1.0, rain_8h_total / 2.0) * 0.6) + (min(1.0, rain_curr / 1.0) * 0.4))
    f_season = {1: 0.8, 2: 0.9, 3: 1.0, 4: 0.8, 9: 0.7, 10: 0.7}.get(month, 0.01)
    f_lune = 1.1 if get_lunar_phase_emoji(dt) in ["🌔", "🌕", "🌖"] else 1.0
    score = (f_temp * f_hydrique * f_season * f_lune) * 100
    return int(min(100, max(0, score))) if feel_2h >= 4.0 else 0

@st.cache_data(ttl=3600)
def fetch_weather(lat, lon):
    url = "https://api.open-meteo.com/v1/forecast"
    params = {"latitude": lat, "longitude": lon, "hourly": ["temperature_2m", "apparent_temperature", "precipitation"], "timezone": "Europe/Berlin", "forecast_days": 8}
    try:
        r = requests.get(url, params=params, timeout=15)
        return r.json()
    except: return None

# --- INTERFACE ---
st.title("Radar des migrations 🐸")
st.caption("Modèle prédictif basé sur les stations SwissMetNet | Données ICON-CH")

# Sélection avec Lausanne (PUY) par défaut
liste_villes = list(CITY_DATA.keys())
index_defaut = liste_villes.index("Lausanne / Pully (PUY)")
ville = st.selectbox("📍 Station météo :", liste_villes, index=index_defaut)
LAT, LON = CITY_DATA[ville]

try:
    data = fetch_weather(LAT, LON)
    if not data:
        st.error("Données indisponibles.")
    else:
        h = data['hourly']
        df = pd.DataFrame({'time': pd.to_datetime(h['time']), 'temp': h['apparent_temperature'], 'precip': h['precipitation']})
        
        daily_summary = []
        tonight_curve_data = []
        now_dt = datetime.now().date()

        for d_idx, d in enumerate(sorted(df['time'].dt.date.unique())):
            # Calculs simplifiés pour le résumé
            start_night = datetime.combine(d, datetime.min.time()) + timedelta(hours=20)
            night_df = df[(df['time'] >= start_night) & (df['time'] <= start_night + timedelta(hours=10))].copy()
            
            if night_df.empty: continue

            hourly_probs = []
            for idx, row in night_df.iterrows():
                rain_8h = df.iloc[max(0, int(idx)-8):int(idx)]['precip'].sum()
                p = calculate_migration_probability(0, row['temp'], rain_8h, row['precip'], row['time'].month, row['time'])
                hourly_probs.append({"Heure": row['time'], "Probabilité": p, "Temp": row['temp'], "Pluie": row['precip']})
                if d == now_dt: tonight_curve_data.append(hourly_probs[-1])

            best = max(hourly_probs, key=lambda x: x['Probabilité'])
            
            # Étiquettes
            if best['Probabilité'] < 20: label, icon, color = "Peu probable", "❌", "gray"
            elif best['Probabilité'] < 45: label, icon, color = "Faible", "🐸", "orange"
            elif best['Probabilité'] < 75: label, icon, color = "Modérée", "🐸🐸", "#2ECC71"
            else: label, icon, color = "Forte", "🐸🐸🐸🐸", "#1E8449"

            daily_summary.append({"Date": format_date_fr_complet(d), "dt_obj": d, "Probab.": f"{best['Probabilité']}%", "Activité": icon, "Color": color, "Label": label})

        # --- GRAPHIQUE DE LA NUIT ---
        tonight = next((x for x in daily_summary if x["dt_obj"] == now_dt), None)
        if tonight and tonight_curve_data:
            st.markdown(f'<div style="padding:15px; border-radius:10px; border-left: 8px solid {tonight["Color"]}; background:rgba(0,0,0,0.05);"><h3>{tonight["Label"]} {tonight["Activité"]}</h3></div>', unsafe_allow_html=True)
            
            plot_df = pd.DataFrame(tonight_curve_data)
            fig = make_subplots(specs=[[{"secondary_y": True}]])
            
            fig.add_trace(go.Scatter(x=plot_df['Heure'], y=plot_df['Probabilité'], fill='tozeroy', name="Probabilité (%)", line=dict(width=0), fillcolor=tonight['Color'], opacity=0.2), secondary_y=False)
            fig.add_trace(go.Bar(x=plot_df['Heure'], y=plot_df['Pluie'], name="Pluie (mm)", marker_color='#3498DB', opacity=0.7), secondary_y=False)
            fig.add_trace(go.Scatter(x=plot_df['Heure'], y=plot_df['Temp'], name="Temp. (°C)", line=dict(color='#E74C3C', width=3)), secondary_y=True)
            
            fig.update_yaxes(title_text="<b>Probabilité / Pluie (mm)</b>", title_font=dict(color="#3498DB"), tickfont=dict(color="#3498DB"), secondary_y=False, range=[0, 100])
            fig.update_yaxes(title_text="<b>Température (°C)</b>", title_font=dict(color="#E74C3C"), tickfont=dict(color="#E74C3C"), secondary_y=True, range=[min(plot_df['Temp'].min()-2, 0), max(plot_df['Temp'].max()+2, 12)])
            fig.update_layout(height=300, margin=dict(l=0,r=0,b=0,t=30), hovermode="x unified", legend=dict(orientation="h", y=1.1, x=1, xanchor="right"))
            st.plotly_chart(fig, use_container_width=True)

        st.subheader("📅 Prévisions 7 jours")
        st.table(pd.DataFrame(daily_summary).set_index("Date")[["Probab.", "Activité"]])

        with st.expander("🔬 Fondements scientifiques"):
            st.markdown("""
            * **Reading, C. J. (2003).** *Migration date and egg laying in common toads.* [Lien](https://doi.org/10.1046/j.1365-2486.2003.00550.x)
            * **Kovar, R., et al. (2009).** *Climate and weather on amphibian migration.* [Lien](https://doi.org/10.1016/j.biocon.2009.03.014)
            * **Info Fauna karch.** *Base de données ZSDB.* [lepus.infofauna.ch/zsdb](https://lepus.infofauna.ch/zsdb)
            """)
except Exception as e:
    st.error(f"Erreur : {e}")
