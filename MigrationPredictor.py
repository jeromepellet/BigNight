import streamlit as st
import pandas as pd
import numpy as np
import requests
import plotly.express as px
from datetime import datetime, timedelta

# --- CONFIGURATION DE LA PAGE ---
st.set_page_config(
    page_title="Radar des migrations d'amphibiens", 
    page_icon="🐸", 
    layout="centered"
)

# --- PARAMÈTRES DU MODÈLE (STRICT) ---
SATURATION_THRESHOLD = 0.5  
W_SEASON = 0.15       
W_TEMP_8H = 0.30      
W_FEEL_2H = 0.25      
W_RAIN_8H = 0.15      
W_RAIN_CURR = 0.15    

CITY_DATA = {
    "Lausanne": (46.520, 6.634), "Genève": (46.202, 6.147), "Sion": (46.231, 7.359),
    "Neuchâtel": (47.000, 6.933), "Fribourg": (46.800, 7.150), "Berne": (46.948, 7.447),
    "Zurich": (47.374, 8.541), "Morges": (46.509, 6.498), "Yverdon": (46.779, 6.641),
    "Bulle": (46.615, 7.059), "Martigny": (46.103, 7.073), "Sierre": (46.292, 7.532)
}

DAYS_FR = {"Mon": "Lun", "Tue": "Mar", "Wed": "Mer", "Thu": "Jeu", "Fri": "Ven", "Sat": "Sam", "Sun": "Dim"}
MONTHS_FR = {"Jan": "Janv.", "Feb": "Févr.", "Mar": "Mars", "Apr": "Avril", "May": "Mai", "Jun": "Juin",
             "Jul": "Juil.", "Aug": "Août", "Sep": "Sept.", "Oct": "Oct.", "Nov": "Nov.", "Dec": "Déc."}

def format_date_fr(dt):
    return f"{DAYS_FR.get(dt.strftime('%a'), dt.strftime('%a'))} {dt.day} {MONTHS_FR.get(dt.strftime('%b'), dt.strftime('%b'))}"

# --- LOGIQUE SCIENTIFIQUE ---

def calculate_migration_probability(temp_8h_avg, feel_2h, rain_8h_total, rain_curr, month):
    # Température (Pénalité sous 4°C)
    f_feel_2h = min(1.0, max(0, (feel_2h - 3) / 10))
    f_temp_8h = min(1.0, max(0, (temp_8h_avg - 3) / 10))
    
    # Pluie Cumulée 8h
    f_rain_8h = min(1.0, rain_8h_total / 3.0)
    
    # Pluie Actuelle (Saturation Drizzle)
    if rain_curr < 0.05:
        f_rain_curr = 0.0
    elif rain_curr <= SATURATION_THRESHOLD:
        f_rain_curr = 1.0
    else:
        f_rain_curr = max(0.2, 1.0 - (rain_curr - SATURATION_THRESHOLD) / 2.0)
    
    # Saison
    seasonal_map = {2: 0.5, 3: 1.0, 4: 0.9, 10: 0.4}
    f_season = seasonal_map.get(month, 0.05)
    
    score = (f_season * W_SEASON + f_temp_8h * W_TEMP_8H + 
             f_feel_2h * W_FEEL_2H + f_rain_8h * W_RAIN_8H + 
             f_rain_curr * W_RAIN_CURR) * 100

    # Pénalités Critiques
    if rain_curr < 0.1 and rain_8h_total < 0.1: score *= 0.15 
    if feel_2h < 3.5: score *= 0.1
    if feel_2h < 1.0: score = 0

    return int(min(100, max(0, score)))

def get_label(prob):
    if prob < 20: return "Migration peu probable", "❌"
    if prob < 45: return "Migration faible", "🐸"
    if prob < 75: return "Migration modérée", "🐸🐸"
    return "Forte migration attendue", "🐸🐸🐸🐸"

# --- INTERFACE ---
st.title("Radar des migrations d'amphibiens en Suisse")
st.caption("Prévisions de l'activité migratrice nocturne (20h-06h) basée sur les modèles MétéoSuisse")

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
    tonight_curve = []
    now_dt = datetime.now().date()

    for i, d in enumerate(sorted(df['time'].dt.date.unique())):
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
            if d == now_dt: tonight_curve.append({"Heure": row['time'], "Probabilité": p})

        best = max(hourly_results, key=lambda x: x['p'])
        label, icon = get_label(best['p'])
        conf_label = "Très Haute" if i == 0 else "Haute" if i < 3 else "Moyenne"

        daily_summary.append({
            "Date": format_date_fr(start_night),
            "dt_obj": d,
            "Heure Opt.": best['time'].strftime("%H:00"),
            "T° ressentie": f"{round(night_df['apparent_temperature'].max(), 1)}°C",
            "Pluie nuit": f"{round(night_df['precipitation'].sum(), 1)}mm",
            "Probab.": f"{best['p']}%",
            "Fiabilité": conf_label,
            "Activité": icon,
            "Label": label,
            "Score": best['p']
        })

    res_df = pd.DataFrame(daily_summary)

    # --- DASHBOARD (EXACT ORIGINAL STYLE) ---
    tonight = res_df[res_df['dt_obj'] == now_dt]
    if not tonight.empty:
        row = tonight.iloc[0]
        score = row['Score']
        color = "red" if score > 70 else "orange" if score > 40 else "green"
        st.markdown(f"""
            <div style="padding:20px; border-radius:10px; border-left: 10px solid {color}; background:rgba(0,0,0,0.05); margin-bottom:25px;">
                <h4 style="margin:0; opacity:0.8;">PRÉVISIONS POUR LA NUIT A VENIR</h4>
                <h2 style="margin:5px 0; color:{color};">{row['Label']} {row['Activité']}</h2>
                <p style="margin:0;">Pic de probabilité : <b>{score}%</b> à <b>{row['Heure Opt.']}</b> | Fiabilité : <b>{row['Fiabilité']}</b></p>
            </div>
        """, unsafe_allow_html=True)

        # --- GRAPH (AXIS 0-100) ---
        if tonight_curve:
            c_df = pd.DataFrame(tonight_curve)
            fig = px.area(c_df, x="Heure", y="Probabilité", range_y=[0, 100])
            fig.update_traces(line_color=color)
            fig.update_layout(height=180, margin=dict(l=0,r=0,b=0,t=0), yaxis_title="%")
            st.plotly_chart(fig, use_container_width=True)

    # --- TABLEAU DES PROCHAINES NUITS ---
    st.subheader("📅 Prévisions à 7 jours")
    st.table(res_df[res_df['dt_obj'] >= now_dt].head(7).drop(columns=['dt_obj', 'Label', 'Score']).set_index('Date'))

except Exception as e:
    st.error(f"Erreur : {e}")
