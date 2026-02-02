import streamlit as st
import requests
import pandas as pd

# Set page title
st.set_page_config(page_title="Toad Migration Predictor")

st.title("🐸 Lausanne Toad Migration Predictor")
st.write("Calculates probability based on 6°C at sunset + rainfall.")

# Fetch Weather Data
url = "https://api.open-meteo.com/v1/meteoswiss"
params = {
    "latitude": 46.516,
    "longitude": 6.632,
    "hourly": ["temperature_2m", "precipitation"],
    "timezone": "Europe/Berlin",
    "forecast_days": 7
}

try:
    response = requests.get(url, params=params)
    data = response.json()
    
    # Process the data
    hourly_data = data['hourly']
    df = pd.DataFrame(hourly_data)
    df['time'] = pd.to_datetime(df['time'])

    results = []
    
    # Loop through 7 days
    for day in range(7):
        # We look at the window from 18:00 (6 PM) to 22:00 (10 PM)
        start_hour = 18 + (day * 24)
        window = df.iloc[start_hour : start_hour + 4]
        
        avg_temp = window['temperature_2m'].mean()
        total_rain = window['precipitation'].sum()
        date_label = window['time'].iloc[0].strftime('%A, %b %d')
        
        # Scoring logic
        # Temperature: Optimal is 6C or more
        t_score = 100 if avg_temp >= 6 else (50 if avg_temp >= 3 else 0)
        
        # Rain: Optimal is 1mm or more
        r_score = 100 if total_rain >= 1 else (50 if total_rain > 0 else 10)
        
        # Final Probability (Weighted: 40% Temp, 60% Rain)
        prob = (t_score * 0.4) + (r_score * 0.6)
        
        results.append({
            "Date": date_label,
            "Evening Temp": f"{avg_temp:.1f}°C",
            "Rain Forecast": f"{total_rain:.1f} mm",
            "Migration Prob": int(prob)
        })

    # Create table
    res_df = pd.DataFrame(results)

    # Display a visual gauge for "Today"
    today_prob = results[0]["Migration Prob"]
    st.metric(label="Tonight's Probability", value=f"{today_prob}%")

    # Display the full week
    st.table(res_df)

except Exception as e:
    st.error(f"Could not fetch weather data: {e}")

st.info("Migration is most likely when the probability is above 70%.")
