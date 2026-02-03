import streamlit as st
import requests
import pandas as pd
from datetime import datetime

# --- SETTINGS & UI ---
st.set_page_config(page_title="Toad Predictor Pro", page_icon="🐸", layout="wide")

st.title("🐸 Swiss Toad Migration Predictor")

# Explanatory Section
st.write("""
This tool predicts the probability of common toad (*Bufo bufo*) migration during the evening "sunset window." 
The model uses high-resolution weather data from Open-Meteo, integrating historical records and 7-day forecasts.

**The Math:** The final probability is the **product** of five factors: Month, 8h Rainfall, 2h Rainfall, 8h Mean Temperature, and 2h Mean Felt Temperature. 
If any single factor is unfavorable (e.g., it's December or the temperature is below 4°C), the final probability drops toward zero.
""")
st.divider()

# --- SIDEBAR INTERFACE ---
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

city_name = st.sidebar.selectbox("Pick a city in Switzerland:", list(locations.keys()))
LAT = locations[city_name]["lat"]
LON = locations[city_name]["lon"]

with st.sidebar.expander("Or enter custom coordinates"):
    LAT = st.number_input("Latitude", value=LAT, format="%.4f")
    LON = st.number_input("Longitude", value=LON, format="%.4f")

TARGET_HOUR = st.sidebar.slider("Time of Survey (24h format):", 16, 22, 18)

# --- DATA FETCHING & PROCESSING ---
url = "https://api.open-meteo.com/v1/forecast"
params = {
    "latitude": LAT, "longitude": LON,
    "hourly": "temperature_2m,precipitation,apparent_temperature",
    "timezone": "Europe/Berlin",
    "past_days": 14,
    "forecast_days": 7
}

def get_linear_score(value, min_val, max_val):
    if value <= min_val: return 0.1
    if value >= max_val: return 1.0
    return 0.1 + ((value - min_val) / (max_val - min_val)) * 0.9

def get_frog_emoji(prob):
    if prob >= 80: return "🐸🐸🐸🐸"
    if prob >= 50: return "🐸🐸🐸"
    if prob >= 20: return "🐸🐸"
    if prob > 0: return "🐸"
    return "❌"

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
                # Month Factor
                month_map = {1: 0.1, 2: 0.5, 3: 1.0, 4: 1.0}
                f_month = month_map.get(row['time'].month, 0.0)
                
                # Rainfall 8h (Sum)
                rain_8h = df.iloc[idx-8 : idx]['precipitation'].sum()
                f_rain8 = 1.0 if rain_8h >= 10 else (0.1 if rain_8h == 0 else 0.1 + (rain_8h/10)*0.9)
                
                # Rainfall 2h (Sum)
                rain_2h = df.iloc[idx-2 : idx]['precipitation'].sum()
                f_rain2 = 1.0 if rain_2h >= 4 else (0.1 if rain_2h == 0 else 0.1 + (rain_2h/4)*0.9)
                
                # Mean Temp 8h
                temp_8h = df.iloc[idx-8 : idx]['temperature_2m'].mean()
                f_temp8 = get_linear_score(temp_8h, 4, 8)
                
                # Mean Felt Temp 2h
                felt_2h = df.iloc[idx-2 : idx]['apparent_temperature'].mean()
                f_felt2 = get_linear_score(felt_2h, 4, 8)
                
                # Probability calculation (The product of all 5 factors)
                final_prob = int((f_month * f_rain8 * f_rain2 * f_temp8 * f_felt2) * 100)
                
                all_results.append({
                    "Date": row['time'],
                    "Month (%)": f"{int(f_month*100)}%",
                    "Rain 8h": f"{rain_8h:.1f}mm ({int(f_rain8*100)}%)",
                    "Rain 2h": f"{rain_2h:.1f}mm ({int(f_rain2*100)}%)",
                    "Temp 8h": f"{temp_8h:.1f}C ({int(f_temp8*100)}%)",
                    "Felt 2h": f"{felt_2h:.1f}C ({int(f_felt2*100)}%)",
                    "Prob": final_prob,
                    "Summary": f"{final_prob}% {get_frog_emoji(final_prob)}"
                })

        full_df = pd.DataFrame(all_results)
        past_df = full_df[full_df['Date'].dt.date < now.date()].copy()
        future_df = full_df[full_df['Date'].dt.date >= now.date()].copy()

        # Date formatting for clean tables
        future_df['Date_Str'] = future_df['Date'].dt.strftime('%a, %b %d')
        past_df['Date_Str'] = past_df['Date'].dt.strftime('%a, %b %d')

        # --- MAIN DISPLAY ---
        st.subheader(f"🔮 Forecast for {city_name} (Next 7 Days)")
        st.table(future_df.drop(columns=['Prob', 'Date']).rename(columns={'Date_Str': 'Date'}))

        st.divider()

        st.subheader(f"📜 History for {city_name} (Last 14 Days)")
        st.table(past_df.drop(columns=['Prob', 'Date']).rename(columns={'Date_Str': 'Date'}))
        
        # Copyright Footer
        st.markdown("<p style='text-align: center; color: grey; margin-top: 50px;'>© n+p wildlife ecology</p>", unsafe_allow_html=True)

    else:
        st.error("Error connecting to weather API.")
except Exception as e:
    st.error(f"Technical Error: {e}")
