import streamlit as st
import requests
import pandas as pd

st.set_page_config(page_title="Toad Tracker", page_icon="🐸")

st.title("🐸 Lausanne Toad Migration Predictor")
st.write("Using high-resolution MeteoSwiss data to find the 'Big Night'.")

# 1. Fetch data with the specific string format the API needs
url = "https://api.open-meteo.com/v1/meteoswiss"
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

    # Check if 'hourly' is actually in the response
    if 'hourly' in data:
        df = pd.DataFrame(data['hourly'])
        df['time'] = pd.to_datetime(df['time'])

        results = []
        for day in range(7):
            # Window: 18:00 (6 PM) to 22:00 (10 PM)
            start_hour = 18 + (day * 24)
            window = df.iloc[start_hour : start_hour + 4]
            
            avg_temp = window['temperature_2m'].mean()
            total_rain = window['precipitation'].sum()
            
            # Logic: 6C and Rain are the triggers
            t_score = 100 if avg_temp >= 6 else (50 if avg_temp >= 3 else 0)
            r_score = 100 if total_rain >= 1 else (50 if total_rain > 0 else 10)
            prob = int((t_score * 0.4) + (r_score * 0.6))
            
            results.append({
                "Date": window['time'].iloc[0].strftime('%A, %b %d'),
                "Evening Temp": f"{avg_temp:.1f}°C",
                "Rain Forecast": f"{total_rain:.1f} mm",
                "Migration Prob": f"{prob}%"
            })

        # Display results
        st.subheader("7-Day Forecast")
        st.table(pd.DataFrame(results))
    else:
        # If the API sent an error message, show it here
        st.error(f"API Error: {data.get('reason', 'Unknown reason')}")

except Exception as e:
    st.error(f"Technical Error: {e}")

st.info("Migration is most likely when the probability is above 70%.")
