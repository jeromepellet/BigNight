import streamlit as st
import pandas as pd
import numpy as np
import requests
import plotly.express as px
from datetime import datetime, timedelta

# --- CONFIGURATION DE LA PAGE ---
st.set_page_config(page_title="Radar Migration Amphibiens", page_icon="🐸", layout="centered")

# --- TRADUCTION DES DATES EN FRANÇAIS ---
DAYS_FR = {
    0: "Lundi", 1: "Mardi", 2: "Mercredi", 3: "Jeudi", 
    4: "Vendredi", 5: "Samedi", 6: "Dimanche"
}

MONTHS_FR = {
    1: "janvier", 2: "février", 3: "mars", 4: "avril", 5: "mai", 6: "juin",
    7: "juillet", 8: "août", 9: "septembre", 10: "octobre", 11: "novembre", 12: "décembre"
}

def format_date_fr_complet(dt):
    """Retourne la date au format 'Mardi 04 février'"""
    jour_semaine = DAYS_FR[dt.weekday()]
    mois = MONTHS_FR[dt.month]
    return f"{jour_semaine} {dt.day:02d} {mois}"

# --- 1. PARAMÈTRES DE VILLES ---
CITY_DATA = {
    "Lausanne": (46.520, 6.634), "Genève": (46.202, 6.147), "Sion": (46.231, 7.359),
    "Neuchâtel": (47.000, 6.933), "Fribourg": (46.800, 7.150), "Berne": (46.948, 7.447),
    "Zurich": (47.374, 8.541), "Morges": (46.509, 6.498), "Yverdon": (46.779, 6.641),
    "Bulle": (46.615, 7.059), "Martigny": (46.103, 7.073), "Sierre": (46.292, 7.532)
}

# --- 2. FONCTIONS DE CALCUL ---

def get_lunar_phase_emoji(dt):
    """Calcule la phase lunaire précise pour 2026"""
    ref_new_moon = datetime(2026, 1, 19, 14, 0) 
    cycle = 29.53059
    diff = (dt - ref_new_moon).total_seconds() / 86400
    phase = (diff % cycle) / cycle 
    
    if phase < 0.0625 or phase > 0.9375: return "🌑"
    if phase < 0.1875: return "🌒"
    if phase < 0.3125: return "🌓"
    if phase < 0.4375: return "🌔"
    if phase < 0.5625: return "🌕"
    if phase < 0.6875: return "🌖"
    if phase < 0.8125: return "🌗"
    return "🌘"

def calculate_migration_probability(temp_8h_avg, feel_2h, rain_8h_total, rain_curr, month, dt):
    """Logique synergique : Température * Humidité"""
    # 1. Base Thermique (0.0 à 4°C, 1.0 dès 10°C)
    f_temp = min(1.0, max(0, (feel_2h - 4) / 6))
    
    # 2. Facteur Hydrique (Synergie pluie récente et pluie active)
    humidite_sol = min(1.0, rain_8h_total / 2.0)
    pluie_active = min(1.0, rain_curr / 1.0)
    f_hydrique = max(0.1, (humidite_sol * 0.6) + (pluie_active * 0.4))
    
    # 3. Bonus Saison et Lune
    seasonal_map = {1: 0.8, 2: 0.9, 3: 1.0, 4: 0.8, 9: 0.7, 10: 0.7}
    f_season = seasonal_map.get(month, 0.01)
    
    emoji = get_lunar_phase_emoji(dt)
    f_lune = 1.1 if emoji in ["🌔", "🌕", "🌖"] else 1.0

    # Calcul final
    score = (f_temp * f_hydrique * f_season * f_lune) * 100
    if feel_2h < 4.0: score = 0
    return int(min(100, max(0, score)))

def get_label(prob):
    if prob < 20: return "Migration peu probable", "❌", "gray"
    if prob < 45: return "Migration faible", "🐸", "orange"
    if prob < 75: return "Migration modérée", "🐸🐸", "#2ECC71"
    return "Forte migration attendue", "🐸🐸🐸🐸", "#1E8449"

# --- 3. RÉCUPÉRATION DES DONNÉES ---

@st.cache_data(ttl=3600)
def fetch_weather(lat, lon):
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat, "longitude": lon,
        "hourly": ["temperature_2m", "apparent_temperature", "precipitation"],
        "timezone": "Europe/Berlin", "forecast_days": 8
    }
    try:
        r = requests.get(url, params=params, timeout=15)
        r.raise_for_status()
        return r.json()
    except:
        return None

# --- 4. INTERFACE ---

st.title("Radar des migrations")
st.caption("Modèle prédictif des migrations d'amphibiens en Suisse | MétéoSuisse (ICON-CH)")

ville = st.selectbox("📍 Sélectionner une station météo :", list(CITY_DATA.keys()))
LAT, LON = CITY_DATA[ville]

try:
    data = fetch_weather(LAT, LON)
    
    if not data or 'hourly' not in data:
        st.error("Données indisponibles.")
    else:
        h = data['hourly']
        df = pd.DataFrame({
            'time': pd.to_datetime(h['time']),
            'temperature_2m': h['temperature_2m'],
            'apparent_temperature': h['apparent_temperature'],
            'precipitation': h['precipitation']
        })
        
        daily_summary = []
        tonight_curve = []
        now_dt = datetime.now().date()

        for d_idx, d in enumerate(sorted(df['time'].dt.date.unique())):
            # Données météo spécifiques
            rain_mid_day = df[(df['time'] >= datetime.combine(d, datetime.min.time()) + timedelta(hours=12)) & 
                              (df['time'] <= datetime.combine(d, datetime.min.time()) + timedelta(hours=20))]['precipitation'].sum()
            
            temp_evening = df[(df['time'] >= datetime.combine(d, datetime.min.time()) + timedelta(hours=18)) & 
                              (df['time'] <= datetime.combine(d, datetime.min.time()) + timedelta(hours=22))]['apparent_temperature'].mean()

            # Fenêtre de migration
            start_night = datetime.combine(d, datetime.min.time()) + timedelta(hours=20)
            end_night = start_night + timedelta(hours=10)
            night_df = df[(df['time'] >= start_night) & (df['time'] <= end_night)].copy()
            
            if night_df.empty: continue

            # Fiabilité
            if d_idx <= 1: fiabilité = "Très Haute"
            elif d_idx <= 3: fiabilité = "Haute"
            elif d_idx <= 5: fiabilité = "Moyenne"
            else: fiabilité = "Basse"

            hourly_results = []
            for idx, row in night_df.iterrows():
                i = int(idx)
                rain_8h = df.iloc[max(0, i-8):i]['precipitation'].sum()
                p = calculate_migration_probability(df.iloc[max(0, i-8):i]['temperature_2m'].mean(),
                                                    row['apparent_temperature'], rain_8h, row['precipitation'],
                                                    row['time'].month, row['time'])
                hourly_results.append({"time": row['time'], "p": p})
                if d == now_dt: tonight_curve.append({"Heure": row['time'], "Probabilité": p})

            best = max(hourly_results, key=lambda x: x['p'])
            label, icon, color = get_label(best['p'])
            
            daily_summary.append({
                "Date": format_date_fr_complet(d),
                "dt_obj": d,
                "Pluie (12h-20h)": f"{round(rain_mid_day, 1)} mm",
                "T° ress. (18h-22h)": f"{round(temp_evening, 1)}°C",
                "Lune": get_lunar_phase_emoji(datetime.combine(d, datetime.min.time())),
                "Probab.": f"{best['p']}%",
                "Fiabilité": fiabilité,
                "Activité": icon,
                "Label": label,
                "Color": color,
                "Score": best['p'],
                "Heure Opt.": best['time'].strftime("%H:00")
            })

        # --- DASHBOARD ---
        tonight_res = next((x for x in daily_summary if x["dt_obj"] == now_dt), None)
        if tonight_res:
            st.markdown(f"""
                <div style="padding:20px; border-radius:10px; border-left: 10px solid {tonight_res['Color']}; background:rgba(0,0,0,0.05); margin-bottom:20px;">
                    <h4 style="margin:0; opacity:0.8;">PRÉVISIONS POUR CETTE NUIT ({tonight_res['Date']})</h4>
                    <h2 style="margin:5px 0; color:{tonight_res['Color']};">{tonight_res['Label']} {tonight_res['Activité']}</h2>
                    <p style="margin:0;">Pic : <b>{tonight_res['Score']}%</b> à <b>{tonight_res['Heure Opt.']}</b> | Fiabilité : {tonight_res['Fiabilité']}</p>
                </div>
            """, unsafe_allow_html=True)

            if tonight_curve:
                st.write("**Evolution des conditions de migrations durant la nuit**")
                c_df = pd.DataFrame(tonight_curve)
                fig = px.area(c_df, x="Heure", y="Probabilité", range_y=[0, 100])
                fig.update_traces(line_color=tonight_res['Color'])
                fig.update_layout(height=180, margin=dict(l=0,r=0,b=0,t=0), yaxis_title="%", xaxis=dict(tickformat="%H:%M"))
                st.plotly_chart(fig, use_container_width=True)

        # --- TABLEAU DES PRÉVISIONS ---
        st.subheader("📅 Prévisions à 7 jours")
        table_df = pd.DataFrame(daily_summary).drop(columns=['dt_obj', 'Label', 'Score', 'Color', 'Heure Opt.'])
        table_df = table_df[["Date", "Pluie (12h-20h)", "T° ress. (18h-22h)", "Lune", "Probab.", "Fiabilité", "Activité"]]
        st.table(table_df.set_index('Date'))

        # --- NOTE SCIENTIFIQUE (DÉPLACÉE À L'INTÉRIEUR DU TRY) ---
        st.divider()
        with st.expander("🔬 Pour comprendre le radar"):
            st.markdown("""
            L'activité migratoire des amphibiens est un phénomène multi-factoriel. Ce radar utilise une approche basée sur la synergie entre les seuils physiologiques et les déclencheurs environnementaux.
            ### Paramètres Bioclimatiques
            
            * **Seuil thermique :** En deçà de **4°C**, le métabolisme ralentit. Le modèle réduit drastiquement toute prévision d'activité sous ce seuil.
            * **Synergie Hydrique :** Le modèle utilise une fonction multiplicative : le score thermique est plafonné par l'humidité. Un sol sec réduit la probabilité, même par grande douceur.
            * **Influence lunaire :** Agit comme un synchronisateur. Les pics sont souvent observés aux abords de la pleine lune.

            ### Références
            * **Reading, C. J. (1998).** The effect of winter temperatures on the timing of breeding activity in the common toad Bufo bufo. *Oecologia*, 117, 469-475. [Lien](https://doi.org/10.1007/s004420050682)
            * **Arnfield, H., Grant, R., Monk, C., & Uller, T. (2012).** Factors influencing the timing of spring migration in common toads (Bufo bufo). *Journal of Zoology*, 288(2), 112-118. [Lien](https://doi.org/10.1111/j.1469-7998.2012.00933.x)
            * **Loman, J. (2016).** Breeding phenology in Rana temporaria. Local variation is due to pond temperature and population size. *Ecology and Evolution*, 6(17), 6202-6209. [Lien](https://doi.org/10.1002/ece3.2356)
            * **Bison, M., et al. (2021).** Earlier snowmelt advances breeding phenology of the common frog (Rana temporaria) but increases the risk of frost exposure and wetland drying. *Frontiers in Ecology and Evolution*, 9, 645585. [Lien](https://doi.org/10.3389/fevo.2021.645585)
            * **Dervo, B. K., et al. (2016).** Effects of Temperature and Precipitation on Breeding Migrations of Amphibian Species in Southeastern Norway. *Scientifica*, 2016, 3174316. [Lien](https://doi.org/10.1155/2016/3174316)
            * **Denoël, M., Mathieu, M., & Poncin, P. (2005).** Effect of water temperature on the courtship behavior of the Alpine newt Triturus alpestris. *Behavioral Ecology and Sociobiology*, 58, 121-127. [Lien](https://doi.org/10.1007/s00265-005-0924-8)

            ### Ressources et données en Suisse
            * Info Fauna karch. *Base de données sur les voies de migration en Suisse (ZSDB)*. [https://lepus.infofauna.ch/zsdb](https://lepus.infofauna.ch/zsdb)
            * Conflits liés au trafic. [https://map.geo.admin.ch](https://s.geo.admin.ch/cwvc8ynhjv0j)
            """)

except Exception as e:
    st.error(f"Erreur : {e}")
