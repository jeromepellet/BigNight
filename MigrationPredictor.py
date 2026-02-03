import streamlit as st
import requests
import pandas as pd
from datetime import datetime

import streamlit as st

# Data for top 100 Swiss cities (Name: (Latitude, Longitude))
CITY_DATA = {
    "Zurich": (47.374, 8.541), "Geneva": (46.202, 6.147), "Basel": (47.555, 7.591),
    "Lausanne": (46.520, 6.634), "Bern": (46.948, 7.447), "Winterthur": (47.499, 8.729),
    "Lucerne": (47.050, 8.300), "St. Gallen": (47.424, 9.371), "Lugano": (46.004, 8.951),
    "Biel/Bienne": (47.133, 7.250), "Bellinzona": (46.195, 9.030), "Thun": (46.767, 7.633),
    "Köniz": (46.922, 7.413), "La Chaux-de-Fonds": (47.112, 6.838), "Fribourg": (46.800, 7.150),
    "Uster": (47.350, 8.717), "Schaffhausen": (47.700, 8.633), "Chur": (46.850, 9.533),
    "Vernier": (46.200, 6.100), "Sion": (46.231, 7.359), "Neuchâtel": (47.000, 6.933),
    "Lancy": (46.184, 6.122), "Baden": (47.467, 8.300), "Zug": (47.168, 8.517),
    "Yverdon-les-Bains": (46.779, 6.641), "Emmen": (47.083, 8.300), "Olten": (47.350, 7.900),
    "Dübendorf": (47.417, 8.617), "Kriens": (47.034, 8.281), "Dietikon": (47.400, 8.400),
    "Rapperswil-Jona": (47.217, 8.817), "Montreux": (46.431, 6.913), "Frauenfeld": (47.550, 8.900),
    "Wetzikon": (47.317, 8.800), "Baar": (47.189, 8.526), "Bülach": (47.517, 8.533),
    "Meyrin": (46.233, 6.082), "Wil": (47.465, 9.049), "Horgen": (47.260, 8.598),
    "Carouge": (46.183, 6.133), "Kreuzlingen": (47.633, 9.167), "Wädenswil": (47.233, 8.667),
    "Aarau": (47.400, 8.050), "Riehen": (47.583, 7.633), "Allschwil": (47.550, 7.533),
    "Renens": (46.533, 6.583), "Wettingen": (47.467, 8.333), "Nyon": (46.383, 6.233),
    "Vevey": (46.467, 6.850), "Reinach": (47.483, 7.583), "Bulle": (46.615, 7.059),
    "Adliswil": (47.317, 8.533), "Schlieren": (47.400, 8.450), "Volketswil": (47.383, 8.700),
    "Regensdorf": (47.433, 8.467), "Thalwil": (47.283, 8.567), "Pully": (46.517, 6.667),
    "Muttenz": (47.525, 7.648), "Ostermundigen": (46.958, 7.491), "Martigny": (46.103, 7.073),
    "Sierre": (46.292, 7.532), "Solothurn": (47.217, 7.533), "Grenchen": (47.197, 7.397),
    "Pratteln": (47.519, 7.694), "Burgdorf": (47.059, 7.623), "Freienbach": (47.200, 8.750),
    "Wallisellen": (47.417, 8.600), "Binningen": (47.537, 7.570), "Wohlen": (47.350, 8.283),
    "Herisau": (47.386, 9.279), "Langenthal": (47.212, 7.789), "Morges": (46.509, 6.498),
    "Steffisburg": (46.777, 7.635), "Lyss": (47.072, 7.305), "Schwyz": (47.021, 8.654),
    "Arbon": (47.517, 9.433), "Locarno": (46.167, 8.783), "Liestal": (47.484, 7.735),
    "Küsnacht": (47.317, 8.583), "Stäfa": (47.240, 8.723), "Horw": (47.016, 8.311),
    "Meilen": (47.270, 8.643), "Thônex": (46.188, 6.198), "Oftringen": (47.313, 7.921),
    "Ebikon": (47.081, 8.341), "Amriswil": (47.548, 9.300), "Richterswil": (47.206, 8.704),
    "Versoix": (46.277, 6.169), "Zollikon": (47.340, 8.577), "Glarus Nord": (47.119, 9.066),
    "Ebikon": (47.081, 8.341), "Ecublens": (46.526, 6.562), "Buchs (SG)": (47.168, 9.479),
    "Villars-sur-Glâne": (46.793, 7.125), "Neuhausen": (47.684, 8.615), "Le Locle": (47.056, 6.745),
    "Münchenstein": (47.519, 7.621), "Zofingen": (47.288, 7.946), "Davos": (46.804, 9.837)
}

# Dropdown UI
selected_city = st.selectbox("Select a city for the toad migration forecast:", list(CITY_DATA.keys()))

# Update coordinates automatically
LAT, LON = CITY_DATA[selected_city]
st.write(f"Showing results for {selected_city} ({LAT}, {LON})")
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
