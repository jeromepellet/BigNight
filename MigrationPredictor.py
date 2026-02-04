import streamlit as st
import pandas as pd
import numpy as np
import requests
import plotly.express as px
from datetime import datetime, timedelta

# --- CONFIGURATION ---
st.set_page_config(page_title="Radar des migrations d'amphibiens", page_icon="🐸", layout="centered")

# --- PARAMÈTRES DU MODÈLE ---
SATURATION_THRESHOLD = 0.5  # Seuil où la pluie devient "trop forte"
W_SEASON = 0.20
W_TEMP_8H = 0.25      # Moyenne temp 8h avant
W_FEEL_2H = 0.25      # Temp ressentie 2h avant
W_RAIN_8H = 0.15      # Pluie cumulée 8h avant
W_RAIN_CURR = 0.15    # Pluie actuelle

CITY_DATA = {
    "Lausanne": (46.520, 6.634), "Genève": (46.202, 6.147), "Sion": (46.231, 7.359),
    "Neuchâtel": (47.000, 6.933), "Fribourg": (46.800, 7.150), "Berne": (46.948, 7.447),
    "Zurich": (47.374, 8.541), "Morges": (46.509, 6.498), "Yverdon": (46.779, 6.641)
}

DAYS_FR = {"Mon": "Lun", "Tue": "Mar", "Wed": "Mer", "Thu": "Jeu", "Fri": "Ven", "Sat": "Sam", "Sun": "Dim"}
MONTHS_FR = {"Jan": "Janv.", "Feb": "Févr.", "Mar": "Mars", "Apr": "Avril", "May": "Mai", "Jun": "Juin",
             "Jul": "Juil.", "Aug": "Août", "Sep": "Sept.", "Oct": "Oct.", "Nov": "Nov.", "Dec": "Déc."}

def format_date_fr(dt):
    return f"{DAYS_FR.get(dt.strftime('%a'), dt.strftime('%a'))} {dt.day} {MONTHS_FR.get(dt.strftime('%b'), dt.strftime('%b'))}"

def calculate_migration_probability(temp_8h_avg, feel_2h, rain_8h_total, rain_curr, month):
    # 1. Facteur Température (Idéal 5-15°C)
    f_temp_8h = min(1.0, max(0, (temp_8h_avg - 2) / 10)) 
    f_feel_2h = min(1.0, max(0, (feel_2h - 2) / 10))
    
    # 2. Facteur Pluie 8h
    f_rain_8h = min(1.0, rain_8h_total / 5.0)
    
    # 3. Logique de Saturation (Drizzle vs Heavy Rain)
    if rain_curr <= 0.05:
        f_rain_curr = 0.1  # Trop sec
    elif rain_curr <= SATURATION_THRESHOLD:
        f_rain_curr = 1.0  # Pluie fine idéale
    else:
        # Décroissance si la pluie est trop forte
        f_rain_curr = max(0.1, 1.0 - (rain_curr - SATURATION_THRESHOLD) / 2.0)
    
    # 4. Saisonnalité
    seasonal_map = {2: 0.6, 3: 1.0, 4: 0.9, 5: 0.4, 9: 0.3, 10: 0.5}
    f_season = seasonal_map.get(month, 0.05)
    
    score = (f_season * W_SEASON + f_temp_8h * W_TEMP_8H + 
             f_feel_2h * W_FEEL_2H + f_rain_8h * W_RAIN_8H + 
             f_rain_curr * W_RAIN_CURR) * 100

    # Multiplicateurs de sécurité
    if feel_2h < 2.5: score *= 0.1
    if rain_8h_total < 0.1 and rain_curr < 0.1: score *= 0.2
    
    return int(min(100, max(0, score)))

def get_label(prob):
    if prob < 20: return "Migration peu probable", "❌"
    if prob < 45: return "Migration faible", "🐸"
    if prob < 75: return "Migration modérée", "🐸🐸"
    return "Forte migration attendue", "🐸🐸🐸🐸"

# --- INTERFACE ---
st.title("Radar des migrations d'amphibiens")
st.caption("Modèle basé sur la température 8h prior, le ressenti 2h prior et la saturation par forte pluie.")

ville = st.selectbox("📍 Station météo de référence :", list(CITY_DATA.keys()))
LAT, LON = CITY_DATA[ville]

@st.cache_data(ttl=3600)
def get_weather_data(lat, lon):
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat, "longitude": lon,
        "hourly": "temperature_2m,apparent_temperature,precipitation",
        "timezone": "Europe/Berlin", "forecast_days": 8
    }
    return requests.get(url, params=params).json()

try:
    data = get_weather_data(LAT, LON)
    df = pd.DataFrame(data['hourly'])
    df['time'] = pd.to_datetime(df['time'])
    
    daily_summary = []
    tonight_curve_data = []
    now_dt = datetime.now().date()

    unique_days = sorted(df['time'].dt.date.unique())

    for i, d in enumerate(unique_days):
        start_night = datetime.combine(d, datetime.min.time()) + timedelta(hours=20)
        end_night = start_night + timedelta(hours=10)
        
        night_df = df[(df['time'] >= start_night) & (df['time'] <= end_night)].copy()
        if night_df.empty: continue

        hourly_results = []
        for idx, row in night_df.iterrows():
            idx_i = int(idx)
            p = calculate_migration_probability(
                df.iloc[max(0, idx_i-8):idx_i]['temperature_2m'].mean(),
                df.iloc[max(0, idx_i-2)]['apparent_temperature'],
                df.iloc[max(0, idx_i-8):idx_i]['precipitation'].sum(),
                row['precipitation'],
                row['time'].month
            )
            hourly_results.append({"time": row['time'], "p": p})
            
            # Sauvegarder les données pour le graphique de ce soir
            if d == now_dt:
                tonight_curve_data.append({"Heure": row['time'], "Probabilité": p})

        # Analyse de la nuit
        best_hour_data = max(hourly_results, key=lambda x: x['p'])
        max_p = best_hour_data['p']
        label, icon = get_label(max_p)
        
        conf_score = max(10, 100 - (i * 12))
        conf_label = "Très Haute" if conf_score > 85 else "Haute" if conf_score > 70 else "Moyenne"
        
        daily_summary.append({
            "Date": format_date_fr(start_night),
            "dt_obj": d,
            "Heure Opt.": best_hour_data['time'].strftime("%H:00"),
            "T° ressentie": f"{round(night_df['apparent_temperature'].mean(), 1)}°C",
            "Pluie nuit": f"{round(night_df['precipitation'].sum(), 1)}mm",
            "Probab.": f"{max_p}%",
            "Fiabilité": conf_label,
            "Activité": icon,
            "Label": label,
            "Score": max_p
        })

    res_df = pd.DataFrame(daily_summary)

    # --- DASHBOARD PRINCIPAL ---
    tonight = res_df[res_df['dt_obj'] == now_dt]
    if not tonight.empty:
        row = tonight.iloc[0]
        color = "#2ECC71" if row['Score'] > 70 else "#F39C12" if row['Score'] > 40 else "#E74C3C"
        st.markdown(f"""
            <div style="padding:20px; border-radius:10px; border-left: 10px solid {color}; background:rgba(0,0,0,0.05); margin-bottom:10px;">
                <h4 style="margin:0; opacity:0.8;">CETTE NUIT À {ville.upper()}</h4>
                <h2 style="margin:5px 0; color:{color};">{row['Label']} {row['Activité']}</h2>
                <p style="margin:0;">Pic de probabilité : <b>{row['Score']}%</b> à <b>{row['Heure Opt.']}</b> | Fiabilité : <b>{row['Fiabilité']}</b></p>
            </div>
        """, unsafe_allow_html=True)

        # --- PETIT GRAPHIQUE HORAIRE ---
        if tonight_curve_data:
            c_df = pd.DataFrame(tonight_curve_data)
            fig = px.area(c_df, x="Heure", y="Probabilité", height=200)
            fig.update_traces(line_color=color)
            fig.update_layout(margin=dict(l=0, r=0, t=0, b=0), xaxis_title=None, yaxis_title="Prob. %")
            st.plotly_chart(fig, use_container_width=True)

    # --- TABLEAU DES PROCHAINES NUITS ---
    st.subheader("📅 Prévisions à 7 jours")
    st.table(res_df[res_df['dt_obj'] >= now_dt].head(7).drop(columns=['dt_obj', 'Label', 'Score']).set_index('Date'))

except Exception as e:
    st.error(f"Erreur technique : {e}")
