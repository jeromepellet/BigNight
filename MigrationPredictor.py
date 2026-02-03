import streamlit as st
import requests
import pandas as pd
import numpy as np
from datetime import datetime

# --- CONFIGURATION & UI ---
st.set_page_config(page_title="Toad Predictor Pro", page_icon="🐸", layout="wide")

st.title("🐸 Swiss Toad Migration Predictor")

st.write("""
This tool predicts common toad (*Bufo bufo*) migration. 
**The Math:** Probability = Month × Rain × Temp × Moon.
""")
st.divider()

# --- SIDEBAR ---
st.sidebar.header("Location & Timing")

locations = {
    "Lausanne": {"lat": 46.516, "lon": 6.632},
    "Geneva": {"lat": 46.204, "lon": 6.143},
    "Zurich": {"lat": 47.376, "lon": 8.541},
    "Bern": {"lat": 46.948, "lon": 7.447},
    "Basel": {"lat": 47.559, "lon": 7.588},
    "Lugano": {"lat": 46.003, "lon": 8.951},
    "Sion": {"lat": 46.229, "lon": 7.359},
    "Neuchâtel": {"lat": 46.990, "lon": 6.929}
}

city_name = st.sidebar.selectbox("Pick a city:", list(locations.keys()))
LAT = locations[city_name]["lat"]
LON = locations[city_name]["lon"]

TARGET_HOUR = st.sidebar.slider("Time of Survey (24h):", 16, 22, 19)

# --- FUNCTIONS ---
def get_moon_info(date):
    # Reference: New Moon on Feb 28, 2025
    ref_new_moon = datetime(2025, 2, 28)
    diff = (date - ref_new_moon).total_seconds() / (24 * 3600)
    phase = (diff % 29.53) / 29.53
    illum = (1 - np.cos(2 * np.pi * phase)) / 2
    if phase < 0.06 or phase > 0.94: emoji = "🌑"
    elif phase < 0.19: emoji = "🌒"
    elif phase < 0.31: emoji = "🌓"
    elif phase < 0.44: emoji = "🌔"
    elif phase < 0.56: emoji = "🌕"
    elif phase < 0.69: emoji = "🌖"
    elif phase < 0.81: emoji = "🌗"
    else: emoji = "🌘"
    return illum, emoji

def get_linear_score(value, min_val, max_val):
    if value <= min_val: return 0.1
    if value >= max_val: return 1.0
    return 0.1 + ((value - min_val) / (max_val - min_val)) * 0.9

def get_frog_emoji(prob):
    if prob >= 80: return "🐸🐸🐸"
    if prob >= 50: return "🐸🐸"
    if prob >= 20: return "🐸"
    return "❌"

# --- DATA FETCHING ---
url = "https://api.open-meteo.com/v1/forecast"
params = {
    "latitude": LAT, "longitude": LON,
    "hourly": "temperature_2m,precipitation,apparent_temperature",
    "timezone": "Europe/Berlin", "past_days": 7, "forecast_days": 7
}

try:
    response = requests.get(url, params=params)
    data = response.json()

    if 'hourly' in data:
        df = pd.DataFrame(data['hourly'])
        df['time'] = pd.to_datetime(df['time'])
        now = datetime.now()

        all_results = []
        for i in range(len(df)):
            if df.iloc[i]['time'].hour == TARGET_HOUR:
                idx = i
                if idx < 8: continue 
                
                row = df.iloc[idx]
                dt_obj = row['time'].to_pydatetime()
                
                # Factors
                f_month = {1:0.1, 2:0.5, 3:1.0, 4:1.0, 5:0.5}.get(dt_obj.month, 0.0)
                rain_8h = df.iloc[idx-8 : idx]['precipitation'].sum()
                f_rain = 1.0 if rain_8h >= 10 else (0.1 if rain_8h == 0 else 0.1 + (rain_8h/10)*0.9)
                temp_8h = df.iloc[idx-8 : idx]['temperature_2m'].mean()
                f_temp = get_linear_score(temp_8h, 4, 8)
                
                illum, moon_emoji = get_moon_info(dt_obj)
                f_moon = 1.0 + (illum * 0.2)
                
                prob = int(min(100, (f_month * f_rain * f_temp * f_moon) * 100))
                
                all_results.append({
                    "Date": dt_obj.strftime('%a, %b %d'),
                    "Rain 8h": f"{rain_8h:.1f}mm",
                    "Temp 8h": f"{temp_8h:.1f}C",
                    "Moon": moon_emoji,
                    "Summary": f"{prob}% {get_frog_emoji(prob)}"
                })

        st.subheader(f"🔮 Forecast for {city_name}")
        st.table(pd.DataFrame(all_results).set_index("Date"))
        st.markdown("<p style='text-align: center; color: grey;'>© n+p wildlife ecology</p>", unsafe_allow_html=True)
except Exception as e:
    st.error(f"Technical Error: {e}")
