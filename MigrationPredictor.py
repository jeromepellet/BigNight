import streamlit as st
import requests
import pandas as pd
from datetime import datetime

# --- PARAMETERS ---
LAT, LON = 46.516, 6.632
TARGET_HOUR = 18  

st.set_page_config(page_title="Toad Predictor Pro", page_icon="🐸", layout="wide")
st.title("🐸 Lausanne Toad Migration Pro: Past & Future")
st.write(f"Model for the {TARGET_HOUR}:00 sunset window (14 days past + 7 days forecast).")

# 1. Fetch data including 14 days of history
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
        
        # Get current time to split Past vs Future
        now = datetime.now()

        all_results = []
        # Calculate indices for the 21-day range (14 past + 7 future)
        for i in range(len(df)):
            # We only care about the TARGET_HOUR (18:00) of each day
            if df.iloc[i]['time'].hour == TARGET_HOUR:
                idx = i
                if idx < 8: continue # Ensure history for rolling calcs
                
                row = df.iloc[idx]
                
                # 1. Month Factor
                month_map = {1: 0.1, 2: 0.5, 3: 1.0, 4: 1.0}
                f_month = month_map.get(row['time'].month, 0.0)
                
                # 2. Rainfall 8h prior
                rain_8h = df.iloc[idx-8 : idx]['precipitation'].sum()
                f_rain8 = 1.0 if rain_8h >= 10 else (0.1 if rain_8h == 0 else 0.1 + (rain_8h/10)*0.9)
                
                # 3. Rainfall 2h prior
                rain_2h = df.iloc[idx-2 : idx]['precipitation'].sum()
                f_rain2 = 1.0 if rain_2h >= 4 else (0.1 if rain_2h == 0 else 0.1 + (rain_2h/4)*0.9)
                
                # 4. Mean Temp 8h prior
                temp_8h = df.iloc[idx-8 : idx]['temperature_2m'].mean()
                f_temp8 = get_linear_score(temp_8h, 4, 8)
                
                # 5. Mean Felt Temp 2h prior
                felt_2h = df.iloc[idx-2 : idx]['apparent_temperature'].mean()
                f_felt2 = get_linear_score(felt_2h, 4, 8)
                
                final_prob = int((f_month * f_rain8 * f_rain2 * f_temp8 * f_felt2) * 100)
                
                all_results.append({
                    "Date": row['time'],
                    "Month (%)": f"{int(f_month*100)}%",
                    "Rain 8h": f"{rain_8h:.1f}mm ({int(f_rain8*100)}%)",
                    "Rain 2h": f"{rain_2h:.1f}mm ({int(f_rain2*100)}%)",
                    "Temp 8h": f"{temp_8h:.1f}°C ({int(f_temp8*100)}%)",
                    "Felt 2h": f"{felt_2h:.1f}°C ({int(f_felt2*100)}%)",
                    "Prob": final_prob,
                    "Summary": f"{final_prob}% {get_frog_emoji(final_prob)}"
                })

        # Separate Tables
        full_df = pd.DataFrame(all_results)
        past_df = full_df[full_df['Date'].dt.date < now.date()].copy()
        future_df = full_df[full_df['Date'].dt.date >= now.date()].copy()

        # Format Date for display
        past_df['Date'] = past_df['Date'].dt.strftime('%a, %b %d')
        future_df['Date'] = future_df['Date'].dt.strftime('%a, %b %d')

        st.subheader("🔮 Upcoming Migration Forecast (Next 7 Days)")
        st.table(future_df.drop(columns=['Prob']))

        st.divider()

        st.subheader("📜 Historical Migration Conditions (Last 14 Days)")
        st.table(past_df.drop(columns=['Prob']))
        
    else:
        st.error("Data error.")

except Exception as e:
    st.error(f"Technical Error: {e}")
