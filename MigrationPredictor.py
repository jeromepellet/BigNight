# --- NOUVEAUX PARAMÈTRES DE PONDÉRATION ---
W_SEASON    = 0.15       
W_TEMP_8H   = 0.25      
W_FEEL_2H   = 0.20      
W_RAIN_8H   = 0.15      
W_RAIN_CURR = 0.15    
W_LUNAR     = 0.10  # Nouveau paramètre de pondération lunaire (10%)

def get_lunar_factor_binary(dt):
    """Retourne 1.0 si on est en période de pleine lune, sinon 0.0"""
    ref_full_moon = datetime(2024, 1, 25, 18, 54) 
    cycle = 29.53059
    diff = (dt - ref_full_moon).total_seconds() / 86400
    phase = (diff % cycle) / cycle 
    # Fenêtre de 4 jours autour de la pleine lune
    if 0.43 < phase < 0.57:
        return 1.0
    return 0.0

def calculate_migration_probability(temp_8h_avg, feel_2h, rain_8h_total, rain_curr, month, dt):
    # 1. Normalisation des facteurs (0.0 à 1.0)
    f_feel_2h = min(1.0, max(0, (feel_2h - 3) / 10))
    f_temp_8h = min(1.0, max(0, (temp_8h_avg - 3) / 10))
    f_rain_8h = min(1.0, rain_8h_total / 3.0)
    f_rain_curr = min(1.0, rain_curr / 3.0)
    f_lune = get_lunar_factor_binary(dt)
    
    # Saisonnalité selon tes critères
    seasonal_map = {1: 0.8, 2: 0.9, 3: 1.0, 4: 0.8, 9: 0.7, 10: 0.7}
    f_season = seasonal_map.get(month, 0.01)
    
    # 2. APPLICATION DE L'ÉQUATION DE PONDÉRATION
    score = (
        f_season    * W_SEASON + 
        f_temp_8h   * W_TEMP_8H + 
        f_feel_2h   * W_FEEL_2H + 
        f_rain_8h   * W_RAIN_8H + 
        f_rain_curr * W_RAIN_CURR +
        f_lune      * W_LUNAR
    ) * 100

    # 3. UNIQUE KILL-SWITCH (FROID)
    if feel_2h < 1.0:
        score = 0

    return int(min(100, max(0, score)))
