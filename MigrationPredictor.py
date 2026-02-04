import streamlit as st
import pandas as pd
import numpy as np
import requests
import plotly.express as px
from datetime import datetime, timedelta

# --- CONFIGURATION DE LA PAGE ---
st.set_page_config(page_title="Radar Migration Amphibiens", page_icon="🐸", layout="centered")

# --- 1. PARAMÈTRES DE PONDÉRATION (STRICTS) ---
W_SEASON    = 0.10  
W_TEMP_8H   = 0.30  
W_FEEL_2H   = 0.20  
W_RAIN_8H   = 0.20  
W_RAIN_CURR = 0.15  
W_LUNAR     = 0.05  

CITY_DATA = {
    "Lausanne": (46.520, 6.634), "Genève": (46.202, 6.147), "Sion": (46.231, 7.359),
    "Neuchâtel": (47.000, 6.933), "Fribourg": (46.800, 7.150), "Berne": (46.948, 7.447),
    "Zurich": (47.374, 8.541), "Morges": (46.509, 6.498), "Yverdon": (46.779, 6.641),
    "Bulle": (46.615, 7.059), "Martigny": (46.103, 7.073), "Sierre": (46.292, 7.532)
}

# --- 2. FONCTIONS DE CALCUL ---

def get_lunar_factor_binary(dt):
    # Référence pleine lune 2026
    ref_full_moon = datetime(2026, 1, 3, 11, 22) 
    cycle = 29.53059
    diff = (dt - ref_full_moon).total_seconds() / 86400
    phase = (diff % cycle) / cycle 
    return 1.0 if (0.43 < phase < 0.57) else 0.0

def calculate_migration_probability(temp_8h_avg, feel_2h, rain_8h_total, rain_curr, month, dt):
    f_feel_2h = min(1.0, max(0, (feel_2h - 5) / 10))
    f_temp_8h = min(1.0, max(0, (temp_8h_avg - 5) / 10))
    f_rain_8h = min(1.0, rain_8h_total / 3.0)
    f_rain_curr = min(1.0, rain_curr / 3.0)
    f_lune = get_lunar_factor_binary(dt)
    
    seasonal_map = {1: 0.8, 2: 0.9, 3: 1.0, 4: 0.8, 9: 0.7, 10: 0.7}
    f_season = seasonal_map.get(month, 0.01)
    
    score = (f_season * W_SEASON + f_temp_8h * W_TEMP_8H + f_feel_2h * W_FEEL_2H + 
             f_rain_8h * W_RAIN_8H + f_rain_curr * W_RAIN_CURR + f_lune * W_LUNAR) * 100

    if rain_curr < 0.1 and rain_8h_total < 0.5:
        score *= 0.2

    if feel_2h < 4.0:
        score = 0
    return int(min(100, max(0, score)))

def get_label(prob):
    if prob < 20: return "Migration peu probable", "❌", "gray"
    if prob < 45: return "Migration faible", "🐸", "orange"
    if prob < 75: return "Migration modérée", "🐸🐸", "#2ECC71"
    return "Forte migration attendue", "🐸🐸🐸🐸", "#1E8449"

# --- 3. RÉCUPÉRATION DES DONNÉES ---

@st.cache_data(ttl=3600)
def fetch_weather(lat, lon):
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat, "longitude": lon,
        "hourly": ["temperature_2m", "apparent_temperature", "precipitation"],
        "timezone": "Europe/Berlin", "forecast_days": 8
    }
    try:
        r = requests.get(url, params=params, timeout=15)
        r.raise_for_status()
        return r.json()
    except:
        return None

# --- 4. INTERFACE ---

st.title("🐸 Radar Migration Amphibiens")
st.caption("Modèle Strict | MétéoSuisse (ICON-CH) | Kill-switch 4°C")

ville = st.selectbox("📍 Sélectionner une station météo :", list(CITY_DATA.keys()))
LAT, LON = CITY_DATA[ville]

try:
    data = fetch_weather(LAT, LON)
    
    if not data or 'hourly' not in data:
        st.error("Données indisponibles.")
    else:
        h = data['hourly']
        df = pd.DataFrame({
            'time': pd.to_datetime(h['time']),
            'temperature_2m': h['temperature_2m'],
            'apparent_temperature': h['apparent_temperature'],
            'precipitation': h['precipitation']
        })
        
        daily_summary = []
        tonight_curve = []
        now_dt = datetime.now().date()

        for d in sorted(df['time'].dt.date.unique()):
            start_night = datetime.combine(d, datetime.min.time()) + timedelta(hours=20)
            end_night = start_night + timedelta(hours=10)
            night_df = df[(df['time'] >= start_night) & (df['time'] <= end_night)].copy()
            
            if night_df.empty: continue

            hourly_results = []
            for idx, row in night_df.iterrows():
                i = int(idx)
                rain_8h = df.iloc[max(0, i-8):i]['precipitation'].sum()
                p = calculate_migration_probability(df.iloc[max(0, i-8):i]['temperature_2m'].mean(),
                                                    row['apparent_temperature'], rain_8h, row['precipitation'],
                                                    row['time'].month, row['time'])
                hourly_results.append({"time": row['time'], "p": p})
                if d == now_dt: tonight_curve.append({"Heure": row['time'], "Probabilité": p})

            best = max(hourly_results, key=lambda x: x['p'])
            label, icon, color = get_label(best['p'])
            
            # FORMAT EXACT DU TABLEAU INITIAL
            daily_summary.append({
                "Date": d.strftime("%d %b"),
                "dt_obj": d,
                "Heure Opt.": best['time'].strftime("%H:00"),
                "T° max nuit": f"{round(night_df['apparent_temperature'].max(), 1)}°C",
                "Pluie nuit": f"{round(night_df['precipitation'].sum(), 1)}mm",
                "Probab.": f"{best['p']}%",
                "Activité": icon,
                "Label": label,
                "Color": color,
                "Score": best['p']
            })

        # Dashboard
        tonight_res = next((x for x in daily_summary if x["dt_obj"] == now_dt), None)
        if tonight_res:
            st.markdown(f"""
                <div style="padding:20px; border-radius:10px; border-left: 10px solid {tonight_res['Color']}; background:rgba(0,0,0,0.05); margin-bottom:20px;">
                    <h4 style="margin:0; opacity:0.8;">PRÉVISIONS POUR CETTE NUIT</h4>
                    <h2 style="margin:5px 0; color:{tonight_res['Color']};">{tonight_res['Label']} {tonight_res['Activité']}</h2>
                    <p style="margin:0;">Pic : <b>{tonight_res['Score']}%</b> à <b>{tonight_res['Heure Opt.']}</b> | Fiabilité : Haute</p>
                </div>
            """, unsafe_allow_html=True)

            if tonight_curve:
                fig = px.area(pd.DataFrame(tonight_curve), x="Heure", y="Probabilité", range_y=[0, 100])
                fig.update_traces(line_color=tonight_res['Color']).update_layout(height=180, margin=dict(l=0,r=0,b=0,t=0))
                st.plotly_chart(fig, use_container_width=True)

        # TABLEAU FINAL (REPRISE EXACTE DU FORMAT)
        st.subheader("📅 Prévisions à 7 jours")
        table_df = pd.DataFrame(daily_summary).drop(columns=['dt_obj', 'Label', 'Score', 'Color'])
        st.table(table_df.set_index('Date'))

except Exception as e:
    st.error(f"Erreur : {e}")
