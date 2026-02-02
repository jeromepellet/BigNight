import streamlit as st
import requests
import pandas as pd

# --- PARAMETERS ---
LAT, LON = 46.516, 6.632
TARGET_HOUR = 18  # Sunset target

st.set_page_config(page_title="Toad Predictor Pro", page_icon="🐸")
st.title("🐸 Lausanne Toad Migration Pro")
st.write(f"Sophisticated product-based model for the {TARGET_HOUR}:00 sunset window.")

# 1. Fetch data (including Apparent Temp for 'felt' temperature)
url = "https://api.open-meteo.com/v1/forecast"
params = {
    "latitude": LAT, "longitude": LON,
    "hourly": "temperature_2m,precipitation,apparent_temperature",
    "timezone": "Europe/Berlin",
    "forecast_days": 7
}

def get_linear_score(value, min_val, max_val):
    """Calculates linear score between 10% (0.1) and 100% (1.0)"""
    if value <= min_val: return 0.1
    if value >= max_val: return 1.0
    # Linear interpolation: 0.1 + (progress_between_min_max * 0.9)
    return 0.1 + ((value - min_val) / (max_val - min_val)) * 0.9

try:
    data = requests.get(url, params=params).json()
    df = pd.DataFrame(data['hourly'])
    df['time'] = pd.to_datetime(df['time'])

    results = []
    # Loop through forecast days
    for day in range(7):
        idx = TARGET_HOUR + (day * 24)
        if idx < 8: continue # Skip if not enough history
        
        row = df.iloc[idx]
        month = row['time'].month
        
        # 1. Month Factor
        month_map = {1: 0.1, 2: 0.5, 3: 1.0, 4: 1.0}
        f_month = month_map.get(month, 0.0)
        
        # 2. Rainfall 8h prior (Sum)
        rain_8h = df.iloc[idx-8 : idx]['precipitation'].sum()
        f_rain8 = 1.0 if rain_8h >= 10 else (0.1 if rain_8h == 0 else 0.1 + (rain_8h/10)*0.9)
        
        # 3. Rainfall 2h prior (Sum)
        rain_2h = df.iloc[idx-2 : idx]['precipitation'].sum()
        f_rain2 = 1.0 if rain_2h >= 4 else (0.1 if rain_2h == 0 else 0.1 + (rain_2h/4)*0.9)
        
        # 4. Mean Temp 8h prior
        temp_8h = df.iloc[idx-8 : idx]['temperature_2m'].mean()
        f_temp8 = get_linear_score(temp_8h, 4, 8)
        
        # 5. Mean Felt Temp 2h prior
        felt_2h = df.iloc[idx-2 : idx]['apparent_temperature'].mean()
        f_felt2 = get_linear_score(felt_2h, 4, 8)
        
        # FINAL PROBABILITY (Product of all factors)
        final_prob = f_month * f_rain8 * f_rain2 * f_temp8 * f_felt2
        percentage = int(final_prob * 100)

        results.append({
            "Date": row['time'].strftime('%A, %b %d'),
            "Month Factor": f"{int(f_month*100)}%",
            "Rain 8h (Sum)": f"{rain_8h:.1f}mm",
            "Temp 8h (Avg)": f"{temp_8h:.1f}°C",
            "Felt Temp 2h": f"{felt_2h:.1f}°C",
            "Final Prob": f"{percentage}%"
        })

    st.table(pd.DataFrame(results))

except Exception as e:
    st.error(f"Error: {e}")

st.info("This model uses a **Product Logic**: if any condition is poor, the total probability drops sharply.")
