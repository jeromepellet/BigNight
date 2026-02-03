import streamlit as st
import pandas as pd
import numpy as np
import requests
from datetime import datetime, timedelta
import pgeocode

# --- CONFIGURATION ---
st.set_page_config(
    page_title="Radar Batraciens MétéoSuisse", 
    page_icon="🐸", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- CONSTANTES ---
STATIONS_METEO = {
    "Lausanne-Pully": (46.5119, 6.6672, "PUY"),
    "Genève-Cointrin": (46.2330, 6.1090, "GVE"),
    "Sion": (46.2187, 7.3303, "SIO"),
    "Neuchâtel": (46.9907, 6.9356, "NEU"),
    "Fribourg-Posieux": (46.7718, 7.1038, "FRE"),
    "Payerne": (46.8115, 6.9423, "PAY"),
    "Aigle": (46.3193, 6.9248, "AIG"),
    "Chaux-de-Fonds": (47.0837, 6.7925, "CDF")
}

# --- FONCTIONS LUNAIRES ---
def get_moon_data(date):
    """Calcule l'illumination et renvoie l'emoji correspondant."""
    ref_new_moon = datetime(2025, 2, 28)
    lunar_cycle = 29.53059
    diff = (date - ref_new_moon).total_seconds() / (24 * 3600)
    phase = (diff % lunar_cycle) / lunar_cycle
    illumination = (1 - np.cos(2 * np.pi * phase)) / 2
    
    # Sélection de l'emoji selon la phase
    if phase < 0.06 or phase > 0.94:
        emoji = "🌑"  # Nouvelle lune
        phase_name = "Nouvelle lune"
    elif phase < 0.19:
        emoji = "🌒"
        phase_name = "Premier croissant"
    elif phase < 0.31:
        emoji = "🌓"  # Premier quartier
        phase_name = "Premier quartier"
    elif phase < 0.44:
        emoji = "🌔"
        phase_name = "Lune gibbeuse croissante"
    elif phase < 0.56:
        emoji = "🌕"  # Pleine lune
        phase_name = "Pleine lune"
    elif phase < 0.69:
        emoji = "🌖"
        phase_name = "Lune gibbeuse décroissante"
    elif phase < 0.81:
        emoji = "🌗"  # Dernier quartier
        phase_name = "Dernier quartier"
    else:
        emoji = "🌘"
        phase_name = "Dernier croissant"
    
    return illumination, emoji, phase_name

# --- FONCTIONS MÉTÉO ---
@st.cache_data(ttl=600, show_spinner="🌤️ Récupération données MétéoSuisse...")
def fetch_meteoswiss_live():
    """Récupère les données météo actuelles avec gestion d'erreurs."""
    try:
        url = "https://data.geo.admin.ch/ch.meteoschweiz.messwerte-aktuell/ch.meteoschweiz.messwerte-aktuell_en.csv"
        df = pd.read_csv(url, sep=';', timeout=15)
        if df.empty:
            st.warning("⚠️ Aucune donnée retournée par MétéoSuisse")
            return None
        return df
    except requests.exceptions.Timeout:
        st.error("⏱️ Délai d'attente dépassé - MétéoSuisse ne répond pas")
        return None
    except requests.exceptions.RequestException as e:
        st.error(f"🌐 Erreur réseau : {e}")
        return None
    except Exception as e:
        st.error(f"❌ Erreur inattendue : {e}")
        return None

def validate_meteo_data(temp, pluie, humi):
    """Valide les données météo et retourne des warnings si nécessaire."""
    warnings = []
    
    if not (-30 <= temp <= 45):
        warnings.append(f"⚠️ Température anormale : {temp}°C")
    if not (0 <= humi <= 100):
        warnings.append(f"⚠️ Humidité anormale : {humi}%")
    if pluie < 0:
        warnings.append(f"⚠️ Précipitations négatives : {pluie}mm")
    
    return warnings

# --- CALCUL DE PROBABILITÉ ---
def calculate_migration_probability(temp, pluie, humi, illum, month):
    """
    Calcul de probabilité basé sur des facteurs écologiques.
    
    Paramètres:
    - temp: température en °C
    - pluie: précipitations en mm
    - humi: humidité relative en %
    - illum: illumination lunaire (0-1)
    - month: mois (1-12)
    """
    
    # Facteur température (courbe gaussienne centrée sur 10°C, optimale 8-12°C)
    if temp < 4:
        f_temp = 0.05  # Trop froid
    elif temp > 20:
        f_temp = 0.3   # Trop chaud
    else:
        # Gaussienne centrée sur 10°C
        f_temp = np.exp(-0.5 * ((temp - 10) / 4) ** 2)
    
    # Facteur précipitations + humidité combiné
    if pluie > 0.1:
        f_pluie = min(1.0, 0.6 + pluie * 0.2)  # Pluie active = boost
    elif humi > 85:
        f_pluie = 0.7  # Humidité élevée = favorable
    elif humi > 70:
        f_pluie = 0.4  # Humidité moyenne
    else:
        f_pluie = 0.15  # Trop sec
    
    # Facteur saisonnier (pic février-avril)
    seasonal_factors = {
        1: 0.1,   # Janvier - encore froid
        2: 0.7,   # Février - début migration
        3: 1.0,   # Mars - pic principal
        4: 0.9,   # Avril - fin migration printanière
        5: 0.3,   # Mai - déclin
        6: 0.05,  # Juin - rare
        7: 0.02,  # Été - très rare
        8: 0.02,
        9: 0.1,   # Septembre - début retour
        10: 0.4,  # Octobre - migration automnale
        11: 0.2,  # Novembre - fin saison
        12: 0.05  # Décembre - hiver
    }
    f_mois = seasonal_factors.get(month, 0.0)
    
    # Boost lunaire nuancé (nuits sombres = meilleure orientation)
    # Nouvelle lune légèrement favorisée
    if illum < 0.3:
        boost_lune = 1.15  # Nuit noire favorable
    elif illum < 0.7:
        boost_lune = 1.0   # Phase intermédiaire neutre
    else:
        boost_lune = 0.95  # Pleine lune légèrement défavorable
    
    # Calcul final
    prob = (f_temp * f_pluie * f_mois * boost_lune) * 100
    
    return int(min(100, max(0, prob)))

def get_migration_advice(prob, temp, pluie, humi, month):
    """Retourne des conseils contextuels selon les conditions."""
    
    # Analyse des conditions limitantes
    if temp < 4:
        return "❄️ **Trop froid pour migrer** : Les batraciens restent en hibernation", "info"
    
    if temp > 20:
        return "☀️ **Température élevée** : Migration peu probable en journée", "info"
    
    if pluie == 0 and humi < 70:
        return "🏜️ **Conditions trop sèches** : Attendez des précipitations ou une forte humidité", "warning"
    
    if month not in [2, 3, 4, 10, 11]:
        return "📅 **Hors saison de migration** : Période peu favorable", "info"
    
    # Conseils selon probabilité
    if prob > 75:
        return "🚨 **ALERTE MIGRATION MAJEURE** : Conditions optimales ! Évitez de circuler près des zones humides, étangs et cours d'eau. Ralentissez sur les routes forestières.", "error"
    elif prob > 60:
        return "⚠️ **MIGRATION PROBABLE** : Forte activité attendue. Vigilance recommandée en soirée et nuit près des points d'eau.", "warning"
    elif prob > 40:
        return "ℹ️ **Activité possible** : Conditions favorables, quelques déplacements probables. Soyez attentifs.", "info"
    elif prob > 20:
        return "😴 **Activité faible** : Migration peu probable mais pas impossible.", "info"
    else:
        return "🔴 **Conditions défavorables** : Très peu d'activité attendue.", "info"

def get_frog_display(prob):
    """Retourne le nombre de grenouilles à afficher."""
    if prob > 80:
        return 5, "🐸🐸🐸🐸🐸"
    elif prob > 60:
        return 4, "🐸🐸🐸🐸"
    elif prob > 40:
        return 3, "🐸🐸🐸"
    elif prob > 20:
        return 2, "🐸🐸"
    else:
        return 1, "🐸"

# --- LOCALISATION ---
@st.cache_resource
def get_geocoder():
    """Initialise le geocoder une seule fois."""
    return pgeocode.Nominatim('ch')

def find_nearest_station(lat, lon):
    """Trouve la station météo la plus proche."""
    dist_min = float('inf')
    nearest_station = None
    nearest_name = None
    
    for nom, (slat, slon, sid) in STATIONS_METEO.items():
        # Distance euclidienne approximative
        d = np.sqrt((lat - slat)**2 + (lon - slon)**2)
        if d < dist_min:
            dist_min = d
            nearest_station = sid
            nearest_name = nom
    
    # Conversion approximative en km (1 degré ≈ 111 km)
    dist_km = dist_min * 111
    
    return nearest_station, nearest_name, dist_km

# --- INTERFACE PRINCIPALE ---
def main():
    # En-tête avec info temporelle
    col_header1, col_header2, col_header3 = st.columns([3, 1, 1])
    with col_header1:
        st.title("🐸 Radar de Migration des Batraciens")
    with col_header2:
        st.markdown(f"**📅 {datetime.now().strftime('%d.%m.%Y')}**")
    with col_header3:
        st.markdown(f"**🕐 {datetime.now().strftime('%H:%M')}**")
    
    st.markdown("*Prévisions en temps réel basées sur MétéoSuisse et phases lunaires*")
    st.divider()
    
    # --- SIDEBAR ---
    with st.sidebar:
        st.header("⚙️ Configuration")
        
        # Input NPA
        npa_input = st.text_input(
            "Code Postal (NPA) :", 
            "1010",
            help="Entrez votre code postal suisse pour localiser la station météo la plus proche"
        )
        
        # Geocodage
        nomi = get_geocoder()
        info_npa = nomi.query_postal_code(npa_input)
        
        if pd.isna(info_npa.latitude):
            st.warning(f"⚠️ NPA '{npa_input}' non trouvé, utilisation de Lausanne par défaut")
            LAT, LON, VILLE = 46.516, 6.632, "Lausanne"
        else:
            LAT, LON, VILLE = info_npa.latitude, info_npa.longitude, info_npa.place_name
        
        st.success(f"📍 **{VILLE}**")
        st.caption(f"Coordonnées: {LAT:.4f}°N, {LON:.4f}°E")
        
        st.divider()
        
        # Options d'affichage
        st.subheader("🎛️ Options")
        show_details = st.checkbox("Afficher détails techniques", value=False)
        show_history = st.checkbox("Afficher tendance 7 jours", value=False)
        
        st.divider()
        
        # Aide
        with st.expander("ℹ️ Comment ça marche ?"):
            st.markdown("""
            **Facteurs analysés :**
            - 🌡️ **Température** : Optimale entre 8-12°C
            - 💧 **Précipitations** : Pluie active ou humidité >85%
            - 🌙 **Phase lunaire** : Influence l'orientation
            - 📅 **Saison** : Pic février-avril (printemps)
            
            **Échelle de probabilité :**
            - 0-20% : Très peu probable
            - 21-40% : Possible
            - 41-60% : Probable
            - 61-80% : Très probable
            - 81-100% : Migration majeure
            
            **Espèces concernées :**
            Grenouilles rousses, crapauds communs, 
            tritons alpestres, salamandres tachetées
            """)
        
        with st.expander("🔬 Méthodologie scientifique"):
            st.markdown("""
            Le calcul repose sur des études écologiques :
            
            - **Température** : Activation métabolique à partir de 4°C
            - **Humidité** : Prévention de la déshydratation cutanée
            - **Lune** : Influence sur l'orientation nocturne
            - **Phénologie** : Cycles de reproduction annuels
            
            Sources : karch.ch, info fauna
            """)
    
    # --- RÉCUPÉRATION DONNÉES ---
    station_id, station_name, distance_km = find_nearest_station(LAT, LON)
    
    st.subheader(f"📡 Station météo : **{station_name}** ({station_id})")
    st.caption(f"Distance : {distance_km:.1f} km de {VILLE}")
    
    # Fetch données
    df_live = fetch_meteoswiss_live()
    
    if df_live is None:
        st.error("❌ Impossible de récupérer les données MétéoSuisse. Réessayez dans quelques minutes.")
        st.stop()
    
    # Filtrer pour la station
    data_station = df_live[df_live['Station/Location'] == station_id]
    
    if data_station.empty:
        st.error(f"❌ Aucune donnée disponible pour la station {station_id}")
        st.info("Stations disponibles : " + ", ".join(df_live['Station/Location'].unique()))
        st.stop()
    
    # --- EXTRACTION DONNÉES MÉTÉO ---
    try:
        row = data_station.iloc[0]
        temp = float(row['tre200s0'])
        pluie = float(row['rre150z0'])
        humi = float(row['ure200s0'])
        
        # Validation
        warnings = validate_meteo_data(temp, pluie, humi)
        for warning in warnings:
            st.warning(warning)
        
    except (ValueError, KeyError) as e:
        st.error(f"❌ Données météo corrompues ou manquantes : {e}")
        st.stop()
    
    # --- CALCUL PHASE LUNAIRE ---
    illum, moon_emoji, phase_name = get_moon_data(datetime.now())
    
    # --- CALCUL PROBABILITÉ ---
    current_month = datetime.now().month
    prob = calculate_migration_probability(temp, pluie, humi, illum, current_month)
    
    # --- AFFICHAGE PRINCIPAL ---
    st.divider()
    
    # Tableau de synthèse
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            label="🌡️ Température",
            value=f"{temp:.1f} °C",
            delta=f"{'Optimal' if 8 <= temp <= 12 else 'Hors optimal'}"
        )
    
    with col2:
        st.metric(
            label="💧 Précipitations",
            value=f"{pluie:.1f} mm",
            delta=f"{'Actives' if pluie > 0.1 else 'Aucune'}"
        )
    
    with col3:
        st.metric(
            label="💨 Humidité",
            value=f"{humi:.0f} %",
            delta=f"{'Favorable' if humi > 85 else 'Modérée' if humi > 70 else 'Faible'}"
        )
    
    with col4:
        st.metric(
            label=f"{moon_emoji} Lune",
            value=f"{int(illum*100)} %",
            delta=phase_name
        )
    
    st.divider()
    
    # Grenouilles visuelles
    num_frogs, frog_display = get_frog_display(prob)
    st.markdown(f"<h1 style='text-align: center; font-size: 4em;'>{frog_display}</h1>", unsafe_allow_html=True)
    
    # Probabilité principale
    st.markdown(f"<h2 style='text-align: center;'>Probabilité de migration</h2>", unsafe_allow_html=True)
    
    # Couleur selon probabilité
    if prob > 75:
        color = "red"
    elif prob > 60:
        color = "orange"
    elif prob > 40:
        color = "blue"
    else:
        color = "gray"
    
    st.markdown(f"<h1 style='text-align: center; color: {color};'>{prob} %</h1>", unsafe_allow_html=True)
    st.progress(prob / 100)
    
    st.divider()
    
    # Conseils
    advice, advice_type = get_migration_advice(prob, temp, pluie, humi, current_month)
    
    if advice_type == "error":
        st.error(advice)
    elif advice_type == "warning":
        st.warning(advice)
    else:
        st.info(advice)
    
    # --- DÉTAILS TECHNIQUES ---
    if show_details:
        st.divider()
        st.subheader("🔬 Détails du calcul")
        
        # Facteurs détaillés
        f_temp_detail = np.exp(-0.5 * ((temp - 10) / 4) ** 2) if 4 <= temp <= 20 else 0.05
        f_pluie_detail = min(1.0, 0.6 + pluie * 0.2) if pluie > 0.1 else (0.7 if humi > 85 else 0.4 if humi > 70 else 0.15)
        seasonal_factors = {1:0.1, 2:0.7, 3:1.0, 4:0.9, 5:0.3, 6:0.05, 7:0.02, 8:0.02, 9:0.1, 10:0.4, 11:0.2, 12:0.05}
        f_mois_detail = seasonal_factors.get(current_month, 0.0)
        boost_lune_detail = 1.15 if illum < 0.3 else (1.0 if illum < 0.7 else 0.95)
        
        detail_data = {
            "Facteur": ["Température", "Précipitations/Humidité", "Saison", "Lune"],
            "Valeur": [f"{f_temp_detail:.2f}", f"{f_pluie_detail:.2f}", f"{f_mois_detail:.2f}", f"{boost_lune_detail:.2f}"],
            "Impact": [
                "Activation métabolique" if f_temp_detail > 0.5 else "Limitant",
                "Hydratation cutanée" if f_pluie_detail > 0.5 else "Limitant",
                "Cycle reproductif" if f_mois_detail > 0.5 else "Hors saison",
                "Orientation nocturne"
            ]
        }
        st.table(pd.DataFrame(detail_data))
        
        st.caption(f"Formule : Probabilité = (Temp × Pluie × Saison × Lune) × 100 = {prob}%")
    
    # --- TENDANCE HISTORIQUE ---
    if show_history:
        st.divider()
        st.subheader("📊 Tendance 7 derniers jours")
        
        # Simulation historique (à remplacer par vraies données si disponible)
        dates = pd.date_range(end=datetime.now(), periods=7, freq='D')
        
        # Générer des probabilités réalistes autour de la valeur actuelle
        hist_prob = []
        for i in range(7):
            variation = np.random.randint(-15, 15)
            hist_val = min(100, max(0, prob + variation))
            hist_prob.append(hist_val)
        
        chart_data = pd.DataFrame({
            'Date': dates.strftime('%d.%m'),
            'Probabilité (%)': hist_prob
        })
        
        st.line_chart(chart_data.set_index('Date'), height=200)
        st.caption("⚠️ Données simulées - Historique réel nécessite stockage de données")
    
    # --- EXPORT ---
    st.divider()
    
    col_export1, col_export2 = st.columns(2)
    
    with col_export1:
        if st.button("📥 Exporter le rapport"):
            rapport = {
                'timestamp': datetime.now().isoformat(),
                'localisation': {
                    'ville': VILLE,
                    'npa': npa_input,
                    'latitude': LAT,
                    'longitude': LON
                },
                'station': {
                    'id': station_id,
                    'nom': station_name,
                    'distance_km': round(distance_km, 1)
                },
                'meteo': {
                    'temperature_c': round(temp, 1),
                    'precipitations_mm': round(pluie, 1),
                    'humidite_pct': int(humi)
                },
                'lune': {
                    'phase': phase_name,
                    'illumination_pct': int(illum * 100)
                },
                'resultat': {
                    'probabilite_pct': prob,
                    'conseil': advice
                }
            }
            
            import json
            rapport_json = json.dumps(rapport, indent=2, ensure_ascii=False)
            
            st.download_button(
                label="💾 Télécharger JSON",
                data=rapport_json,
                file_name=f"migration_batraciens_{datetime.now().strftime('%Y%m%d_%H%M')}.json",
                mime="application/json"
            )
    
    with col_export2:
        # Lien vers ressources externes
        st.markdown("""
        **📚 Ressources utiles :**
        - [karch.ch](https://www.karch.ch) - Centre de coordination pour la protection des amphibiens
        - [info fauna](https://www.infofauna.ch) - Données faunistiques suisses
        """)
    
    # --- FOOTER ---
    st.divider()
    st.caption(f"🌐 Sources : MétéoSuisse (Station {station_id}) | 🐸 Logiciel n+p wildlife ecology")
    st.caption(f"⏰ Dernière mise à jour : {datetime.now().strftime('%d.%m.%Y à %H:%M:%S')}")
    st.caption("⚠️ Cet outil est indicatif. Pour des actions de conservation, consultez les autorités locales.")

if __name__ == "__main__":
    main()
