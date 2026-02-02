import streamlit as st
import requests
import pandas as pd
from datetime import datetime

# --- USER PARAMETERS (Adjustable) ---
LATITUDE = 46.516
LONGITUDE = 6.632
TARGET_HOUR = 18  # 6 PM (Sunset)
TEMP_IDEAL = 8.0  # 100% score if Temp >= this
RAIN_IDEAL = 5.0  # 100% score if Rain >= this
WEIGHT_TEMP = 0.5
WEIGHT_RAIN = 0.5
# ------------------------------------

st.set_page_config(page_title="Toad Tracker", page_icon="🐸")
st.title("🐸 Lausanne Toad Migration Predictor")
st.write(f"Calculates 'Big Night' probability for the sunset window ({TARGET_HOUR}:00).")

url = "https://api.open-meteo.com/v1/forecast"
params = {
    "latitude": LATITUDE,
    "longitude": LONGITUDE,
    "hourly": "temperature_2m,precipitation",
    "timezone": "Europe/Berlin",
    "forecast_days": 7
}

try:
    response = requests.get(url, params=params)
    data = response.json()

    if 'hourly' in data:
        df = pd.DataFrame(data['hourly'])
        df['time'] = pd.to_datetime(df['time'])
        results = []

        for day in range(7):
            idx = TARGET_HOUR + (day * 24)
            row = df.iloc[idx]
            
            current_date = row['time']
            temp = row['temperature_2m']
            rain = row['precipitation']
            
            # 1. Season Gate: Probability is 0% from April to December
            # (Only active in January, February, March)
            if current_date.month >= 4:
                prob = 0
            else:
                # 2. Temperature Score (Max at 8°C)
                t_score = min((temp / TEMP_IDEAL) * 100, 100) if temp > 0 else 0
                
                # 3. Rain Score (Max at 5mm)
                r_score = min((rain / RAIN_IDEAL) * 100, 100)
                
                # 4. Final Calculation
                prob = int((t_score * WEIGHT_TEMP) + (r_score * WEIGHT_RAIN))

            results.append({
                "Date": current_date.strftime('%A, %b %d'),
                "Temp (18:00)": f"{temp:.1f}°C",
                "Rain (18:00)": f"{rain:.1f} mm",
                "Migration Prob": f"{prob}%"
            })

        st.subheader("7-Day Forecast")
        st.table(pd.DataFrame(results))
        
    else:
        st.error("Weather Data Error: Could not parse response.")

except Exception as e:
    st.error(f"Technical Error: {e}")

st.info("**Thresholds:** 100% is reached if rain > 5mm and temp > 8°C. Migration is deactivated April–December.")
