import streamlit as st
import requests
import pandas as pd
import numpy as np
from datetime import datetime

# --- CONFIGURATION & INTERFACE ---
st.set_page_config(page_title="Prédicteur de Crapauds Pro", page_icon="🐸", layout="wide")

st.title("🐸 Prédiction de Migration des Batraciens (Suisse)")

# Section explicative
st.write("""
Cet outil prédit la probabilité de migration du crapaud commun (*Bufo bufo*) durant la "fenêtre du coucher du soleil". 
Le modèle utilise les données météo haute résolution d'Open-Meteo, intégrant l'historique et les prévisions à 7 jours.

**Le Calcul :** La probabilité finale est le **produit** de six facteurs : le mois, la pluie (8h et 2h), la température (8h et 2h ressentie) et le **cycle lunaire**.
Si un seul facteur est défavorable (ex: température < 4°C), la probabilité chute vers zéro.
""")
st.divider()

# --- INTERFACE LATÉRALE ---
st.sidebar.header("Localisation et Horaire")

villes = {
    "Lausanne": {"lat": 46.516, "lon": 6.632},
    "Genève": {"lat": 46.204, "lon": 6.143},
    "Zurich": {"lat": 47.376, "lon": 8.541},
    "Berne": {"lat": 46.948, "lon": 7.447},
    "Bâle": {"lat": 47.559, "lon": 7.588},
    "Lugano": {"lat": 46.003, "lon": 8.951},
    "Sion": {"lat": 46.229, "lon": 7.359},
    "Neuchâtel": {"lat": 46.990, "lon": 6.929}
}

nom_ville = st.sidebar.selectbox("Choisir une ville :", list(villes.keys()))
LAT = villes[nom_ville]["lat"]
LON = villes[nom_ville]["lon"]

with st.sidebar.expander("Coordonnées personnalisées"):
    LAT = st.number_input("Latitude", value=LAT, format="%.4f")
    LON = st.number_input("Longitude", value=LON, format="%.4f")

HEURE_CIBLE = st.sidebar.slider("Heure du relevé (24h) :", 16, 22, 19)

# --- FONCTIONS DE CALCUL ---
def get_linear_score(value, min_val, max_val):
    if value <= min_val: return 0.1
    if value >= max_val: return 1.0
    return 0.1 + ((value - min_val) / (max_val - min_val)) * 0.9

def get_moon_factor(date):
    # Référence : Nouvelle lune le 28 février 2025
    ref_new_moon = datetime(2025, 2, 28)
    lunar_cycle = 29.53059
    diff = (date - ref_new_moon).total_seconds() / (24 * 3600)
    phase = (diff % lunar_cycle) / lunar_cycle
    illumination = (1 - np.cos(2 * np.pi * phase)) / 2
    # Boost de 20% max lors de la pleine lune
    return 1.0 + (illumination * 0.2)

def get_frog_emoji(prob):
    if prob >= 80: return "🐸🐸🐸🐸"
    if prob >= 50: return "🐸🐸🐸"
    if prob >= 20: return "🐸🐸"
    if prob > 0: return "🐸"
    return "❌"

# --- RÉCUPÉRATION DES DONNÉES ---
url = "https://api.open-meteo.com/v1/forecast"
params = {
    "latitude": LAT, "longitude": LON,
    "hourly": "temperature_2m,precipitation,apparent_temperature",
    "timezone": "Europe/Berlin",
    "past_days": 14,
    "forecast_days": 7
}

try:
    response = requests.get(url, params=params)
    data = response.json()

    if 'hourly' in data:
        df = pd.DataFrame(data['hourly'])
        df['time'] = pd.to_datetime(df['time'])
        maintenant = datetime.now()

        all_results = []
        for i in range(len(df)):
            if df.iloc[i]['time'].hour == HEURE_CIBLE:
                idx = i
                if idx < 8: continue 
                
                row = df.iloc[idx]
                date_dt = row['time'].to_pydatetime()
                
                # 1. Facteur Mois
                month_map = {1: 0.1, 2: 0.5, 3: 1.0, 4: 1.0, 5: 0.4}
                f_month = month_map.get(row['time'].month, 0.0)
                
                # 2. Facteurs Pluie (Somme 8h et 2h)
                rain_8h = df.iloc[idx-8 : idx]['precipitation'].sum()
                f_rain8 = 1.0 if rain_8h >= 10 else (0.1 if rain_8h == 0 else 0.1 + (rain_8h/10)*0.9)
                
                rain_2h = df.iloc[idx-2 : idx]['precipitation'].sum()
                f_rain2 = 1.0 if rain_2h >= 4 else (0.1 if rain_2h == 0 else 0.1 + (rain_2h/4)*0.9)
                
                # 3. Facteurs Température (Moyenne 8h et 2h ressentie)
                temp_8h = df.iloc[idx-8 : idx]['temperature_2m'].mean()
                f_temp8 = get_linear_score(temp_8h, 4, 8)
                
                felt_2h = df.iloc[idx-2 : idx]['apparent_temperature'].mean()
                f_felt2 = get_linear_score(felt_2h, 4, 8)
                
                # 4. Facteur Lune
                f_moon = get_moon_factor(date_dt)
                
                # Calcul Probabilité Finale
                prob_meteo = (f_month * f_rain8 * f_rain2 * f_temp8 * f_felt2)
                final_prob = int(min(100, (prob_meteo * f_moon) * 100))
                
                all_results.append({
                    "Date": row['time'],
                    "Mois": f"{int(f_month*100)}%",
                    "Pluie 8h": f"{rain_8h:.1f}mm",
                    "Temp 8h": f"{temp_8h:.1f}°C",
                    "Lune (Boost)": f"+{int((f_moon-1)*100)}%",
                    "Prob": final_prob,
                    "Résumé": f"{final_prob}% {get_frog_emoji(final_prob)}"
                })

        full_df = pd.DataFrame(all_results)
        past_df = full_df[full_df['Date'].dt.date < maintenant.date()].copy()
        future_df = full_df[full_df['Date'].dt.date >= maintenant.date()].copy()

        # Formatage des dates pour les tableaux
        future_df['Date_Fr'] = future_df['Date'].dt.strftime('%d %b (%a)')
        past_df['Date_Fr'] = past_df['Date'].dt.strftime('%d %b (%a)')

        # --- AFFICHAGE PRINCIPAL ---
        st.subheader(f"🔮 Prévisions pour {nom_ville} (7 prochains jours)")
        st.table(future_df.drop(columns=['Prob', 'Date']).rename(columns={'Date_Fr': 'Date'}))

        st.divider()

        st.subheader(f"📜 Historique pour {nom_ville} (14 derniers jours)")
        st.table(past_df.drop(columns=['Prob', 'Date']).rename(columns={'Date_Fr': 'Date'}))
        
        # Pied de page
        st.markdown("<p style='text-align: center; color: grey; margin-top: 50px;'>© n+p wildlife ecology | Données : Open-Meteo</p>", unsafe_allow_html=True)

    else:
        st.error("Erreur lors de la connexion à l'API météo.")
except Exception as e:
    st.error(f"Erreur Technique : {e}")
