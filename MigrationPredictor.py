import requests
import pandas as pd
from datetime import datetime

# Settings for Lausanne
LAT, LON = 46.516, 6.632
START_DATE = "2025-02-01"  # Migration started early in 2025
END_DATE = "2025-05-31"
TARGET_HOUR = 20 # Predicting for 8:00 PM

def get_linear_score(value, min_val, max_val):
    if value <= min_val: return 0.1
    if value >= max_val: return 1.0
    return 0.1 + ((value - min_val) / (max_val - min_val)) * 0.9

# --- FETCH HISTORICAL DATA ---
# Using the Archive API for past years
url = "https://archive-api.open-meteo.com/v1/archive"
params = {
    "latitude": LAT, "longitude": LON,
    "start_date": START_DATE,
    "end_date": END_DATE,
    "hourly": "temperature_2m,precipitation,apparent_temperature",
    "timezone": "Europe/Berlin"
}

print(f"Fetching historical data for Lausanne...")
response = requests.get(url, params=params)
data = response.json()

if 'hourly' in data:
    df = pd.DataFrame(data['hourly'])
    df['time'] = pd.to_datetime(df['time'])
    
    historical_results = []
    
    # Iterate through hours to calculate probabilities
    for i in range(len(df)):
        if df.iloc[i]['time'].hour == TARGET_HOUR:
            idx = i
            if idx < 8: continue 
            
            # 1. Month Factor
            m = df.iloc[idx]['time'].month
            month_map = {1: 0.1, 2: 0.5, 3: 1.0, 4: 1.0, 5: 0.4} # Scale down in May
            f_month = month_map.get(m, 0.0)
            
            # 2. Rain Factors
            rain_8h = df.iloc[idx-8 : idx]['precipitation'].sum()
            f_rain8 = 1.0 if rain_8h >= 10 else (0.1 if rain_8h == 0 else 0.1 + (rain_8h/10)*0.9)
            
            rain_2h = df.iloc[idx-2 : idx]['precipitation'].sum()
            f_rain2 = 1.0 if rain_2h >= 4 else (0.1 if rain_2h == 0 else 0.1 + (rain_2h/4)*0.9)
            
            # 3. Temp Factors
            temp_8h = df.iloc[idx-8 : idx]['temperature_2m'].mean()
            f_temp8 = get_linear_score(temp_8h, 4, 8)
            
            felt_2h = df.iloc[idx-2 : idx]['apparent_temperature'].mean()
            f_felt2 = get_linear_score(felt_2h, 4, 8)
            
            prob = int((f_month * f_rain8 * f_rain2 * f_temp8 * f_felt2) * 100)
            
            historical_results.append({
                "Date": df.iloc[idx]['time'].strftime('%Y-%m-%d'),
                "Temp_Mean_8h": round(temp_8h, 1),
                "Rain_Sum_8h": round(rain_8h, 1),
                "Probability_%": prob
            })

    # Save to CSV for your comparison
    result_df = pd.DataFrame(historical_results)
    result_df.to_csv("Lausanne_Spring_2025_Migration.csv", index=False)
    print("Success! Created 'Lausanne_Spring_2025_Migration.csv'.")
    
    # Display the peaks
    print("\nTop 5 Potential Migration Nights in Spring 2025:")
    print(result_df.sort_values(by="Probability_%", ascending=False).head(5))

else:
    print("Error: Could not retrieve archive data.")
