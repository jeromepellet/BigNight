import streamlit as st
import pandas as pd
import numpy as np
import requests
import plotly.express as px
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

CITY_DATA = {
    "Lausanne": (46.520, 6.634), "Genève": (46.202, 6.147), "Sion": (46.231, 7.359),
    "Neuchâtel": (47.000, 6.933), "Fribourg": (46.800, 7.150), "Berne": (46.948, 7.447),
    "Zurich": (47.374, 8.541), "Morges": (46.509, 6.498), "Yverdon": (46.779, 6.641),
    "Bulle": (46.615, 7.059), "Martigny": (46.103, 7.073), "Sierre": (46.292, 7.532)
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
    humidite_sol = min(1.0, rain_8h_total / 2.0)
    pluie_active = min(1.0, rain_curr / 1.0)
    f_hydrique = max(0.05, (humidite_sol * 0.6) + (pluie_active * 0.4))
    f_season = {1: 0.8, 2: 0.9, 3: 1.0, 4: 0.8, 9: 0.7, 10: 0.7}.get(month, 0.01)
    f_lune = 1.1 if get_lunar_phase_emoji(dt) in ["🌔", "🌕", "🌖"] else 1.0
    score = (f_temp * f_hydrique * f_season * f_lune) * 100
    return int(min(100, max(0, score))) if feel_2h >= 4.0 else 0

def get_label(prob):
    if prob < 20: return "Migration peu probable", "❌", "gray"
    if prob < 45: return "Migration faible", "🐸", "orange"
    if prob < 75: return "Migration modérée", "🐸🐸", "#2ECC71"
    return "Forte migration attendue", "🐸🐸🐸🐸", "#1E8449"

@st.cache_data(ttl=3600)
def fetch_weather(lat, lon):
    url = "https://api.open-meteo.com/v1/forecast"
    params = {"latitude": lat, "longitude": lon, "hourly": ["temperature_2m", "apparent_temperature", "precipitation"], "timezone": "Europe/Berlin", "forecast_days": 8}
    try:
        r = requests.get(url, params=params, timeout=15)
        return r.json()
    except: return None

# --- INTERFACE ---
st.title("Radar des migrations")
st.caption("Modèle prédictif des migrations d'amphibiens en Suisse | MétéoSuisse (ICON-CH)")

ville = st.selectbox("📍 Sélectionner une station météo :", list(CITY_DATA.keys()))
LAT, LON = CITY_DATA[ville]

try:
    data = fetch_weather(LAT, LON)
    if not data or 'hourly' not in data:
        st.error("Données météo indisponibles.")
    else:
        h = data['hourly']
        df = pd.DataFrame({'time': pd.to_datetime(h['time']), 'temperature_2m': h['temperature_2m'], 
                           'apparent_temperature': h['apparent_temperature'], 'precipitation': h['precipitation']})
        
        daily_summary = []
        tonight_curve_data = []
        now_dt = datetime.now().date()

        for d_idx, d in enumerate(sorted(df['time'].dt.date.unique())):
            mask_day = (df['time'] >= datetime.combine(d, datetime.min.time()) + timedelta(hours=12)) & (df['time'] <= datetime.combine(d, datetime.min.time()) + timedelta(hours=20))
            rain_mid_day = df[mask_day]['precipitation'].sum()
            
            mask_eve = (df['time'] >= datetime.combine(d, datetime.min.time()) + timedelta(hours=18)) & (df['time'] <= datetime.combine(d, datetime.min.time()) + timedelta(hours=22))
            temp_evening = df[mask_eve]['apparent_temperature'].mean()

            start_night = datetime.combine(d, datetime.min.time()) + timedelta(hours=20)
            night_df = df[(df['time'] >= start_night) & (df['time'] <= start_night + timedelta(hours=10))].copy()
            
            if night_df.empty: continue

            fiabilité = "Basse"
            if d_idx <= 1: fiabilité = "Très Haute"
            elif d_idx <= 3: fiabilité = "Haute"
            elif d_idx <= 5: fiabilité = "Moyenne"

            hourly_probs = []
            for idx, row in night_df.iterrows():
                i = int(idx)
                rain_8h = df.iloc[max(0, i-8):i]['precipitation'].sum()
                p = calculate_migration_probability(df.iloc[max(0, i-8):i]['temperature_2m'].mean(), row['apparent_temperature'], rain_8h, row['precipitation'], row['time'].month, row['time'])
                hourly_probs.append({"Heure": row['time'], "Probabilité": p, "Temp": row['apparent_temperature'], "Pluie": row['precipitation']})
                if d == now_dt: tonight_curve_data.append(hourly_probs[-1])

            best = max(hourly_probs, key=lambda x: x['Probabilité'])
            label, icon, color = get_label(best['Probabilité'])
            daily_summary.append({"Date": format_date_fr_complet(d), "dt_obj": d, "Pluie (12h-20h)": f"{round(rain_mid_day, 1)} mm", "T° ress. (18h-22h)": f"{round(temp_evening, 1)}°C", "Lune": get_lunar_phase_emoji(datetime.combine(d, datetime.min.time())), "Probab.": f"{best['Probabilité']}%", "Fiabilité": fiabilité, "Activité": icon, "Color": color, "Label": label, "Score": best['Probabilité'], "Heure Opt.": best['Heure'].strftime("%H:00")})

        # --- DASHBOARD DE LA NUIT ---
        tonight = next((x for x in daily_summary if x["dt_obj"] == now_dt), None)
        if tonight:
            st.markdown(f'<div style="padding:20px; border-radius:10px; border-left: 10px solid {tonight["Color"]}; background:rgba(0,0,0,0.05); margin-bottom:20px;"><h4 style="margin:0; opacity:0.8;">PRÉVISIONS POUR CETTE NUIT</h4><h2 style="margin:5px 0; color:{tonight["Color"]};">{tonight["Label"]} {tonight["Activité"]}</h2><p>Pic : <b>{tonight["Score"]}%</b> à <b>{tonight["Heure Opt."]}</b> | Fiabilité : {tonight["Fiabilité"]}</p></div>', unsafe_allow_html=True)
            
            if tonight_curve_data:
                plot_df = pd.DataFrame(tonight_curve_data)
                fig = make_subplots(specs=[[{"secondary_y": True}]])
                # Probabilité en arrière-plan
                fig.add_trace(go.Scatter(x=plot_df['Heure'], y=plot_df['Probabilité'], fill='tozeroy', name="Probabilité (%)", line=dict(width=0), fillcolor=tonight['Color'], opacity=0.2), secondary_y=False)
                # Précipitations en barres
                fig.add_trace(go.Bar(x=plot_df['Heure'], y=plot_df['Pluie'], name="Pluie (mm)", marker_color='#AED6F1', opacity=0.8), secondary_y=False)
                # Température en ligne
                fig.add_trace(go.Scatter(x=plot_df['Heure'], y=plot_df['Temp'], name="Temp. (°C)", line=dict(color='#E74C3C', width=3)), secondary_y=True)
                
                fig.update_yaxes(title_text="Probabilité / Pluie", secondary_y=False, range=[0, 100])
                fig.update_yaxes(title_text="Température (°C)", secondary_y=True, range=[min(plot_df['Temp'].min()-2, 0), max(plot_df['Temp'].max()+2, 12)])
                fig.update_layout(height=300, margin=dict(l=0,r=0,b=0,t=30), hovermode="x unified", legend=dict(orientation="h", y=1.1, x=1, xanchor="right"))
                st.plotly_chart(fig, use_container_width=True)

        st.subheader("📅 Prévisions à 7 jours")
        st.table(pd.DataFrame(daily_summary).set_index("Date")[["Pluie (12h-20h)", "T° ress. (18h-22h)", "Lune", "Probab.", "Fiabilité", "Activité"]])

        # --- NOTE SCIENTIFIQUE ---
        st.divider()
        with st.expander("🔬 Fondements scientifiques de la phénologie"):
            st.markdown("""
            La phénologie migratoire des amphibiens en Europe centrale est régie par des variables environnementales seuils.
            * **Reading, C. J. (2003).** *The effects of variation in climatic parameters on changing migration date and egg laying in common toads (Bufo bufo).* [Lien Wiley](https://doi.org/10.1046/j.1365-2486.2003.00550.x)
            * **Kovar, R., et al. (2009).** *Influence of climate and weather on amphibian migration.* [Lien ScienceDirect](https://doi.org/10.1016/j.biocon.2009.03.014)
            * **Info Fauna karch (2026).** *Base de données biographique ZSDB*. [https://lepus.infofauna.ch/zsdb](https://lepus.infofauna.ch/zsdb)
            """)

except Exception as e:
    st.error(f"Erreur d'exécution : {e}")
