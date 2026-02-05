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

# --- STATIONS OFFICIELLES METEOSUISSE (SwissMetNet) ---
CITY_DATA = {
    "Aigle (AIG)": (46.342, 6.925),
    "Altdorf (ALT)": (46.887, 8.622),
    "Bale / Binningen (BAS)": (47.541, 7.584),
    "Berne / Zollikofen (BER)": (46.991, 7.464),
    "Bulle (BUL)": (46.615, 7.059),
    "Chateau-d'Oex (CHO)": (46.484, 7.135),
    "Coire (CHU)": (46.871, 9.531),
    "Fribourg / Posieux (FRE)": (46.772, 7.104),
    "Genève / Cointrin (GVE)": (46.234, 6.109),
    "La Chaux-de-Fonds (CDF)": (47.084, 6.792),
    "Lausanne / Pully (PUY)": (46.512, 6.668),
    "Locarno / Monti (OTL)": (46.173, 8.788),
    "Lugano (LUG)": (45.998, 8.960),
    "Lucerne (LUZ)": (47.036, 8.301),
    "Magadino / Cadenazzo (MAG)": (46.160, 8.934),
    "Neuchâtel (NEU)": (46.990, 6.953),
    "Nyon / Changins (CHA)": (46.397, 6.239),
    "Payerne (PAY)": (46.811, 6.942),
    "Sion (SIO)": (46.219, 7.330),
    "Saint-Gall (STG)": (47.425, 9.399),
    "Viège / Visp (VIS)": (46.300, 7.850),
    "Zurich / Fluntern (SMA)": (47.378, 8.566)
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
st.caption("Modèle prédictif des migrations d'amphibiens en Suisse | Données Open-Meteo & SwissMetNet")

ville = st.selectbox("📍 Sélectionner une station météo :", list(CITY_DATA.keys()), index=10)
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
        all_nights_data = {} # Dictionnaire pour stocker les courbes de chaque nuit
        now_dt = datetime.now().date()

        for d_idx, d in enumerate(sorted(df['time'].dt.date.unique())):
            # Fenêtre de migration (20h le soir à 06h le lendemain)
            start_night = datetime.combine(d, datetime.min.time()) + timedelta(hours=20)
            end_night = start_night + timedelta(hours=10)
            night_df = df[(df['time'] >= start_night) & (df['time'] <= end_night)].copy()
            
            if night_df.empty: continue

            # Fiabilité (simple estimation basée sur l'horizon temporel)
            fiabilité = ["Très Haute", "Haute", "Moyenne", "Basse"][min(d_idx // 2, 3)]

            hourly_results = []
            for idx, row in night_df.iterrows():
                i = int(idx)
                rain_8h = df.iloc[max(0, i-8):i]['precipitation'].sum()
                p = calculate_migration_probability(
                    df.iloc[max(0, i-8):i]['temperature_2m'].mean(),
                    row['apparent_temperature'], rain_8h, row['precipitation'],
                    row['time'].month, row['time']
                )
                hourly_results.append({"Heure": row['time'], "Probabilité": p, "Temp": row['apparent_temperature'], "Pluie": row['precipitation']})

            best = max(hourly_results, key=lambda x: x['Probabilité'])
            label, icon, color = get_label(best['Probabilité'])
            
            # Stockage pour le tableau
            date_str = format_date_fr_complet(d)
            all_nights_data[date_str] = pd.DataFrame(hourly_results)
            
            daily_summary.append({
                "Date": date_str,
                "Lune": get_lunar_phase_emoji(datetime.combine(d, datetime.min.time())),
                "Probab.": f"{best['Probabilité']}%",
                "Activité": icon,
                "Fiabilité": fiabilité,
                "Color": color,
                "Label": label,
                "Score": best['Probabilité'],
                "Heure Opt.": best['Heure'].strftime("%H:00")
            })

# --- AFFICHAGE DU TABLEAU INTERACTIF ---
        st.subheader("📅 Prévisions à 7 jours")
        st.info("💡 Cliquez sur une ligne pour visualiser le détail horaire de la nuit.")
        
        table_df = pd.DataFrame(daily_summary)
        
        # Configuration de la sélection corrigée
        selection = st.dataframe(
            table_df[["Date", "Lune", "Probab.", "Activité", "Fiabilité"]],
            use_container_width=True,
            hide_index=True,
            on_select="rerun",
            selection_mode="single-row"
        )

        # Déterminer quelle date afficher (sélectionnée ou aujourd'hui)
        selected_date = None
        if selection and "selection" in selection and selection["selection"]["rows"]:
            selected_row_idx = selection["selection"]["rows"][0]
            selected_date = table_df.iloc[selected_row_idx]["Date"]
        else:
            # Par défaut, on cherche aujourd'hui dans le tableau
            today_str = format_date_fr_complet(now_dt)
            if today_str in all_nights_data:
                selected_date = today_str
            else:
                # Si aujourd'hui n'est pas trouvé, on prend la première ligne dispo
                selected_date = table_df.iloc[0]["Date"]

        # Déterminer quelle date afficher (sélectionnée ou aujourd'hui)
        selected_date = None
        if selection and selection.get("selection", {}).get("rows"):
            selected_row_idx = selection["selection"]["rows"][0]
            selected_date = table_df.iloc[selected_row_idx]["Date"]
        else:
            # Par défaut, on cherche aujourd'hui dans le tableau
            today_str = format_date_fr_complet(now_dt)
            if today_str in all_nights_data:
                selected_date = today_str

        # --- DASHBOARD & GRAPHIQUE ---
        if selected_date:
            res = table_df[table_df["Date"] == selected_date].iloc[0]
            c_df = all_nights_data[selected_date]

            st.markdown(f"""
                <div style="padding:20px; border-radius:10px; border-left: 10px solid {res['Color']}; background:rgba(0,0,0,0.05); margin:20px 0;">
                    <h4 style="margin:0; opacity:0.8;">DÉTAILS DU {selected_date.upper()}</h4>
                    <h2 style="margin:5px 0; color:{res['Color']};">{res['Label']} {res['Activité']}</h2>
                    <p style="margin:0;">Pic : <b>{res['Score']}%</b> à <b>{res['Heure Opt.']}</b> | Fiabilité : {res['Fiabilité']}</p>
                </div>
            """, unsafe_allow_html=True)

            # Création du graphique Plotly
            from plotly.subplots import make_subplots
            import plotly.graph_objects as go

            fig = make_subplots(specs=[[{"secondary_y": True}]])
            fig.add_trace(go.Scatter(x=c_df['Heure'], y=c_df['Probabilité'], fill='tozeroy', name="Probabilité (%)", 
                                     line=dict(width=0), fillcolor=res['Color'], opacity=0.3), secondary_y=False)
            fig.add_trace(go.Bar(x=c_df['Heure'], y=c_df['Pluie'], name="Pluie (mm)", marker_color='#3498DB', opacity=0.7), secondary_y=False)
            fig.add_trace(go.Scatter(x=c_df['Heure'], y=c_df['Temp'], name="Temp. (°C)", line=dict(color='#E74C3C', width=3)), secondary_y=True)

            fig.update_layout(height=300, margin=dict(l=0, r=0, b=0, t=10), hovermode="x unified",
                              legend=dict(orientation="h", y=1.1), xaxis=dict(tickformat="%H:%M"))
            fig.update_yaxes(range=[0, 100], secondary_y=False)
            
            st.plotly_chart(fig, use_container_width=True)

        # --- NOTE SCIENTIFIQUE (DÉPLACÉE À L'INTÉRIEUR DU TRY) ---
        st.divider()
        with st.expander("🔬 Pour comprendre le radar"):
            st.markdown("""
            L'activité migratoire des amphibiens est un phénomène multi-factoriel. Ce radar utilise une approche basée sur la synergie entre les seuils physiologiques et les déclencheurs environnementaux.
            ### Paramètrage
            * **Seuils :** En deçà de 4°C, le métabolisme ralentit. Le modèle réduit drastiquement toute prévision d'activité sous ce seuil, de même que si les conditions deviennent soudainement plus sèches après une pluie.
            * **Démarrage de la migration et inertie  :** Le modèle s'appuie en partie sur la température moyenne et la pluviométrie des 8 dernières heures (humidité du sol et température de "démarrage").
            * **Maintien de la migration  :** Fonction multiplicative : les scores thermiques et d'humidité horaire durant la nuit maintient ou stoppe la migration. Une migration peut être stoppée par une chute brutale des températures ressenties (avec prise en compte du vent).
            * **Influence lunaire :** Facteur de facilitation : les pics migratoires sont souvent observés autour de la pleine lune.

            ### Références
            * **Reading, C. J. (1998).** The effect of winter temperatures on the timing of breeding activity in the common toad Bufo bufo. *Oecologia*, 117, 469-475. [Lien](https://doi.org/10.1007/s004420050682)
            * **Arnfield, H., Grant, R., Monk, C., & Uller, T. (2012).** Factors influencing the timing of spring migration in common toads (Bufo bufo). *Journal of Zoology*, 288(2), 112-118. [Lien](https://doi.org/10.1111/j.1469-7998.2012.00933.x)
            * **Loman, J. (2016).** Breeding phenology in Rana temporaria. Local variation is due to pond temperature and population size. *Ecology and Evolution*, 6(17), 6202-6209. [Lien](https://doi.org/10.1002/ece3.2356)
            * **Bison, M., et al. (2021).** Earlier snowmelt advances breeding phenology of the common frog (Rana temporaria) but increases the risk of frost exposure and wetland drying. *Frontiers in Ecology and Evolution*, 9, 645585. [Lien](https://doi.org/10.3389/fevo.2021.645585)
            * **Dervo, B. K., et al. (2016).** Effects of Temperature and Precipitation on Breeding Migrations of Amphibian Species in Southeastern Norway. *Scientifica*, 2016, 3174316. [Lien](https://doi.org/10.1155/2016/3174316)
            * **Grant, R., Jarvis, L., & Sengupta, A. (2021).** Lunar phase as a cue for migrations to two species of explosive breeding amphibians (*Bufo bufo* and *Rana temporaria*)—implications for conservation. *European Journal of Wildlife Research*, 67, 11. [Lien](https://doi.org/10.1007/s10344-020-01453-3)
            
            ### Ressources
            * **Base de données sur les voies de migration en Suisse (ZSDB)**. [https://lepus.infofauna.ch/zsdb](https://lepus.infofauna.ch/zsdb)
            * **Points de conflits liés au trafic.** [https://map.geo.admin.ch](https://s.geo.admin.ch/cwvc8ynhjv0j)
            """)

except Exception as e:
    st.error(f"Erreur lors de l'exécution : {e}")
    import traceback
    st.code(traceback.format_exc())
