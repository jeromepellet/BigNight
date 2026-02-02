import streamlit as st
import requests
import pandas as pd

st.set_page_config(page_title="Toad Tracker", page_icon="🐸")

st.title("🐸 Lausanne Toad Migration Predictor")
st.write("Calculates the 'Big Night' probability based on 6°C at sunset and rain.")

# 1. Use the standard reliable endpoint
# This still covers Lausanne with high accuracy
url = "https://api.open-meteo.com/v1/forecast"
params = {
    "latitude": 46.516,
    "longitude": 6.632,
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
            # Focus on the evening window: 18:00 to 22:00
            start_hour = 18 + (day * 24)
            window = df.iloc[start_hour : start_hour + 4]
            
            avg_temp = window['temperature_2m'].mean()
            total_rain = window['precipitation'].sum()
            
            # Migration Logic
            t_score = 100 if avg_temp >= 6 else (50 if avg_temp >= 3 else 0)
            r_score = 100 if total_rain >= 1 else (50 if total_rain > 0 else 10)
            prob = int((t_score * 0.2) + (r_score * 0.8))
            
            results.append({
                "Date": window['time'].iloc[0].strftime('%A, %b %d'),
                "Evening Temp": f"{avg_temp:.1f}°C",
                "Rain Forecast": f"{total_rain:.1f} mm",
                "Migration Prob": f"{prob}%"
            })

        # Display the 7-day table
        st.subheader("7-Day Migration Forecast")
        st.table(pd.DataFrame(results))
        
    else:
        st.error(f"Weather Data Error: {data.get('message', 'Check connection')}")

except Exception as e:
    st.error(f"Technical Error: {e}")

st.info("💡 Tip: Common Toads usually move when evening temps are 6°C+ with steady rain.")
