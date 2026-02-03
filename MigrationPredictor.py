import streamlit as st
import pandas as pd
import numpy as np
import requests
from datetime import datetime, timedelta

# --- CONFIGURATION DE LA PAGE ---
st.set_page_config(
    page_title="Radar des migrations d'amphibiens", 
    page_icon="🐸", 
    layout="centered"
)

# --- PARAMÈTRES DU MODÈLE ---
WEIGHT_TEMP_APP    = 0.25  
WEIGHT_STABILITY   = 0.20  
WEIGHT_RAIN_8H     = 0.20  
WEIGHT_HUMIDITY    = 0.15  
WEIGHT_SEASON      = 0.10  
LUNAR_BOOST_MAX    = 0.10  

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

def get_moon_phase_data(date):
    ref_new_moon = datetime(2000, 1, 6, 18, 14)
    lunar_cycle = 29.530588861
    time_diff = (date - ref_new_moon).total_seconds() / 86400.0
    phase = (time_diff % lunar_cycle) / lunar_cycle
    emojis = ["🌑", "🌒", "🌓", "🌔", "🌕", "🌖", "🌗", "🌘"]
    emoji = emojis[int(((phase + 0.0625) % 1) * 8)]
    f_lunar = 1.0 + LUNAR_BOOST_MAX * np.cos(2 * np.pi * abs(phase - 0.5))
    return emoji, f_lunar

def calculate_migration_probability(temp_app, temps_72h, rain_8h, humidity, month, f_lunar):
    temp_app = 0 if pd.isna(temp_app) else temp_app
    
    # 1. Base : Courbe de température (Optimum 12-15°C)
    if 2 < temp_app < 20:
        n = (temp_app - 2) / 16
        f_temp = min(1.0, max(0.05, ((n**2.5) * ((1-n)**1.5)) / 0.35))
    else:
        f_temp = 0.05
    
    # 2. Base : Stabilité (sol dégelé)
    f_stab = 1.0 if np.mean(temps_72h[~np.isnan(temps_72h)]) > 5 else 0.2
    
    # 3. Base : Pluie (Logarithmique)
    f_rain = min(1.0, np.log1p(rain_8h * 2) / 3.5) if rain_8h > 0.1 else 0.05
    
    # 4. Base : Humidité (Exponentielle)
    f_hum = (humidity / 95)**2
    
    # 5. Base : Saison
    seasonal_weights = {2: 0.5, 3: 1.0, 4: 0.8, 10: 0.3}
    f_seas = seasonal_weights.get(month, 0.05)
    
    # Calcul du score initial
    score = (f_temp * WEIGHT_TEMP_APP + f_stab * WEIGHT_STABILITY + 
             f_rain * WEIGHT_RAIN_8H + f_hum * WEIGHT_HUMIDITY + f_seas * WEIGHT_SEASON)
    score = score * f_seas * f_lunar * 100
    
    # --- COUPE-CIRCUITS (Facteurs limitants) ---
    if temp_app < 5.0: score *= 0.3 # Malus froid sévère
    if rain_8h < 0.3 and humidity < 80: score *= 0.2 # Malus sécheresse
    
    return int(min(100, max(0, score)))

def get_label(prob):
    if prob < 20: return "Migration peu probable", "❌"
    if prob < 45: return "Migration faible", "🐸"
    if prob < 75: return "Migration modérée", "🐸🐸"
    return "Forte migration attendue", "🐸🐸🐸🐸"

# --- INTERFACE ---
st.title("🐸 Radar des migrations d'amphibiens")
st.caption("Analyse nocturne (18h-02h) basée sur les modèles MétéoSuisse")

ville = st.selectbox("📍 Station de référence :", list(CITY_DATA.keys()))
LAT, LON = CITY_DATA[ville]

@st.cache_data(ttl=3600)
def get_weather_data(lat, lon):
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat, "longitude": lon,
        "hourly": "temperature_2m,apparent_temperature,precipitation,relative_humidity_2m",
        "timezone": "Europe/Berlin", "past_days": 7, "forecast_days": 8, "models": "best_match"
    }
    resp = requests.get(url, params=params).json()
    if 'apparent_temperature' not in resp['hourly']:
        resp['hourly']['apparent_temperature'] = resp['hourly']['temperature_2m']
    return resp

try:
    data = get_weather_data(LAT, LON)
    df = pd.DataFrame(data['hourly'])
    df['time'] = pd.to_datetime(df['time'])
    
    daily_summary = []
    unique_days = sorted(df['time'].dt.date.unique())

    for d in unique_days:
        # Fenêtre de la nuit : 18h à 02h (le lendemain)
        start = datetime.combine(d, datetime.min.time()) + timedelta(hours=18)
        end = start + timedelta(hours=8)
        night_mask = (df['time'] >= start) & (df['time'] <= end)
        night_df = df[night_mask].copy()
        
        if len(night_df) < 5: continue
            
        probs = []
        for idx, row in night_df.iterrows():
            idx_i = int(idx)
            m_emoji, f_lunar = get_moon_phase_data(row['time'])
            p = calculate_migration_probability(
                row['apparent_temperature'],
                df.iloc[idx_i-72:idx_i]['temperature_2m'].values,
                df.iloc[idx_i-8:idx_i]['precipitation'].sum(),
                row['relative_humidity_2m'],
                row['time'].month,
                f_lunar
            )
            probs.append(p)
            
        max_p = max(probs)
        label, icon = get_label(max_p)
        
        daily_summary.append({
            "Date": format_date_fr(start),
            "dt_obj": d,
            "T° max nuit": f"{round(night_df['apparent_temperature'].max(), 1)}°C",
            "Pluie nuit": f"{round(night_df['precipitation'].sum(), 1)}mm",
            "Lune": get_moon_phase_data(start)[0],
            "Probab.": f"{max_p}%",
            "Activité": icon,
            "Label": label,
            "Score": max_p
        })

    res_df = pd.DataFrame(daily_summary)
    now_dt = datetime.now().date()
    
    # --- DASHBOARD ---
    tonight = res_df[res_df['dt_obj'] == now_dt]
    if not tonight.empty:
        row = tonight.iloc[0]
        score = row['Score']
        color = "red" if score > 70 else "orange" if score > 40 else "green"
        st.markdown(f"""
            <div style="padding:20px; border-radius:10px; border-left: 10px solid {color}; background:rgba(0,0,0,0.05); margin-bottom:25px;">
                <h4 style="margin:0; opacity:0.8;">PRÉVISIONS CETTE NUIT</h4>
                <h2 style="margin:5px 0; color:{color};">{row['Label']} {row['Activité']}</h2>
                <p style="margin:0;">Pic de probabilité : <b>{score}%</b> | Pluie prévue : <b>{row['Pluie nuit']}</b></p>
            </div>
        """, unsafe_allow_html=True)

    # --- TABLEAUX ---
    st.subheader("📅 Prochaines nuits")
    st.table(res_df[res_df['dt_obj'] >= now_dt].head(7).drop(columns=['dt_obj', 'Label', 'Score']).set_index('Date'))

    st.subheader("📜 Historique des nuits")
    st.table(res_df[res_df['dt_obj'] < now_dt].tail(5).iloc[::-1].drop(columns=['dt_obj', 'Label', 'Score']).set_index('Date'))

except Exception as e:
    st.error(f"Erreur : {e}")

# --- ONGLETS ---
st.divider()
tab1, tab2 = st.tabs(["💡 Aide", "🔬 Modèle"])
with tab1:
    st.markdown("L'indice est calculé sur la fenêtre **18h-02h**. Si une pluie arrive à minuit, le radar le détectera.")
with tab2:
    st.markdown("**Coupe-circuits appliqués :** Si T < 5°C ou si Pluie < 0.3mm + Humidité < 80%, le score chute drastiquement.")

st.caption(f"© n+p wildlife ecology | {datetime.now().strftime('%d.%m.%Y')}")
