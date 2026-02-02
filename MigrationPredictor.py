import streamlit as st
import requests
import pandas as pd

# --- PARAMETERS ---
LAT, LON = 46.516, 6.632
TARGET_HOUR = 18  

st.set_page_config(page_title="Toad Predictor Pro", page_icon="🐸", layout="wide")
st.title("🐸 Lausanne Toad Migration Pro")
st.write(f"Comprehensive product-based model for the {TARGET_HOUR}:00 sunset window.")

url = "https://api.open-meteo.com/v1/forecast"
params = {
    "latitude": LAT, "longitude": LON,
    "hourly": "temperature_2m,precipitation,apparent_temperature",
    "timezone": "Europe/Berlin",
    "forecast_days": 7
}

def get_linear_score(value, min_val, max_val):
    """Calculates linear score between 0.1 (10%) and 1.0 (100%)"""
    if value <= min_val: return 0.1
    if value >= max_val: return 1.0
    return 0.1 + ((value - min_val) / (max_val - min_val)) * 0.9

def get_frog_emoji(prob):
    """Returns frog emojis based on probability strength"""
    if prob >= 80: return "🐸🐸🐸🐸"
    if prob >= 50: return "🐸🐸🐸"
    if prob >= 20: return "🐸🐸"
    if prob > 0: return "🐸"
    return "❌"

try:
    data = requests.get(url, params=params).json()
    df = pd.DataFrame(data['hourly'])
    df['time'] = pd.to_datetime(df['time'])

    results = []
    for day in range(7):
        idx = TARGET_HOUR + (day * 24)
        if idx < 8: continue 
        
        row = df.iloc[idx]
        month = row['time'].month
        
        # 1. Month Factor (M)
        month_map = {1: 0.1, 2: 0.5, 3: 1.0, 4: 1.0}
        f_month = month_map.get(month, 0.0)
        
        # 2. Rainfall 8h prior (R8)
        rain_8h = df.iloc[idx-8 : idx]['precipitation'].sum()
        f_rain8 = 1.0 if rain_8h >= 10 else (0.1 if rain_8h == 0 else 0.1 + (rain_8h/10)*0.9)
        
        # 3. Rainfall 2h prior (R2)
        rain_2h = df.iloc[idx-2 : idx]['precipitation'].sum()
        f_rain2 = 1.0 if rain_2h >= 4 else (0.1 if rain_2h == 0 else 0.1 + (rain_2h/4)*0.9)
        
        # 4. Mean Temp 8h prior (T8)
        temp_8h = df.iloc[idx-8 : idx]['temperature_2m'].mean()
        f_temp8 = get_linear_score(temp_8h, 4, 8)
        
        # 5. Mean Felt Temp 2h prior (FT2)
        felt_2h = df.iloc[idx-2 : idx]['apparent_temperature'].mean()
        f_felt2 = get_linear_score(felt_2h, 4, 8)
        
        # Calculate Final Probability
        final_prob_raw = f_month * f_rain8 * f_rain2 * f_temp8 * f_felt2
        prob_pct = int(final_prob_raw *
