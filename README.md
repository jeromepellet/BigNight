# 🐸 Radar Migration Amphibiens

A predictive tool for amphibian migration activity in Switzerland based on weather conditions.

## Overview

This Streamlit application forecasts amphibian migration probability across Swiss weather stations using temperature, precipitation, lunar phase, and seasonal factors.

## Features

- **7-day forecast** for 22 MeteoSwiss stations
- **Tonight's detailed view** with hourly probability curve
- **Multi-factor analysis**: temperature, rainfall, moon phase, season
- **Interactive charts** showing weather conditions and migration probability

## Installation

```bash
pip install streamlit pandas numpy requests plotly
```

## Usage

```bash
streamlit run app.py
```

Then select a weather station from the dropdown to view migration forecasts.

## How It Works

The model combines:
- **Temperature threshold**: Migration unlikely below 4°C
- **Precipitation synergy**: Recent rainfall + active rain
- **Seasonal factor**: Peak activity in February-April
- **Lunar influence**: Higher probability near full moon

# Mathematical Model & Algorithms

## Overview

The amphibian migration prediction model uses a **multiplicative synergy approach** where environmental factors interact rather than simply add together. This reflects the biological reality that amphibians require both warmth AND moisture to migrate effectively.

---

## Core Algorithm: Migration Probability

### Function Signature
```python
calculate_migration_probability(temp_8h_avg, feel_2h, rain_8h_total, rain_curr, month, dt)
```

### Complete Mathematical Formula

```
P_migration = min(100, max(0, f_temp × f_hydrique × f_season × f_lune × 100))

With hard constraint: if feel_2h < 4°C, then P_migration = 0
```

Where each factor is calculated as follows:

---

## 1. Thermal Factor (f_temp)

**Physiological basis**: Amphibian metabolism is temperature-dependent. Below 4°C, activity ceases; optimal above 10°C.

```
f_temp = min(1.0, max(0, (T_felt - 4) / 6))
```

Where:
- `T_felt` = apparent temperature at current time (°C)
- Denominator `6` represents the range from threshold (4°C) to optimal (10°C)

**Behavior**:
- `T_felt ≤ 4°C` → f_temp = 0.0 (no migration)
- `T_felt = 7°C` → f_temp = 0.5 (50% thermal optimum)
- `T_felt ≥ 10°C` → f_temp = 1.0 (full thermal optimum)

**Example**:
```
T_felt = 6°C  → f_temp = (6-4)/6 = 0.33
T_felt = 12°C → f_temp = min(1.0, (12-4)/6) = 1.0
```

---

## 2. Hydric Factor (f_hydrique)

**Biological basis**: Amphibians require moisture to prevent desiccation. The model uses a weighted combination of soil moisture (from recent rainfall) and active precipitation.

```
f_hydrique = max(0.1, (h_sol × 0.6) + (p_active × 0.4))
```

Where:

### Soil Humidity Component
```
h_sol = min(1.0, R_8h / 2.0)
```
- `R_8h` = cumulative precipitation over past 8 hours (mm)
- Saturates at 2mm (considered optimal soil moisture)

### Active Precipitation Component
```
p_active = min(1.0, R_curr / 1.0)
```
- `R_curr` = current hourly precipitation (mm)
- Saturates at 1mm/hour (light to moderate rain)

**Weighting rationale**:
- 60% weight to soil moisture (longer-term condition)
- 40% weight to active rain (immediate trigger)
- Minimum floor of 0.1 (10%) even in dry conditions

**Example**:
```
R_8h = 3mm, R_curr = 0.5mm
h_sol = min(1.0, 3/2) = 1.0
p_active = min(1.0, 0.5/1) = 0.5
f_hydrique = (1.0 × 0.6) + (0.5 × 0.4) = 0.6 + 0.2 = 0.8
```

---

## 3. Seasonal Factor (f_season)

**Ecological basis**: Amphibian breeding seasons vary by species but generally peak in late winter/early spring and have secondary activity in autumn.

```
f_season = seasonal_map[month]
```

### Seasonal Mapping
```python
{
    1:  0.8,   # January   - Pre-migration buildup
    2:  0.9,   # February  - Early migration
    3:  1.0,   # March     - PEAK migration season
    4:  0.8,   # April     - Late migration
    9:  0.7,   # September - Autumn movements
    10: 0.7,   # October   - Autumn movements
    *:  0.01   # All other months - minimal activity
}
```

**Rationale**:
- March receives maximum weight (1.0) as primary breeding migration
- February/April have high weight (0.8-0.9) for early/late migrants
- Autumn months (Sept/Oct) reflect dispersal movements
- Summer/winter months effectively suppressed (0.01)

---

## 4. Lunar Factor (f_lune)

**Behavioral basis**: Research shows amphibians synchronize breeding migrations with lunar cycles, particularly around full moon (Grant et al. 2021).

```
f_lune = 1.1 if moon_phase ∈ {🌔, 🌕, 🌖} else 1.0
```

**10% bonus applied during**:
- 🌔 Waxing Gibbous
- 🌕 Full Moon  
- 🌖 Waning Gibbous

### Lunar Phase Calculation

The algorithm uses precise astronomical calculation:

```python
def get_lunar_phase_emoji(dt):
    ref_new_moon = datetime(2026, 1, 19, 14, 0)  # Reference new moon
    cycle = 29.53059  # Synodic month in days
    
    diff_days = (dt - ref_new_moon).total_seconds() / 86400
    phase = (diff_days % cycle) / cycle  # Normalized [0, 1)
    
    # Map to 8 lunar phases
    if phase < 0.0625 or phase > 0.9375: return "🌑"  # New Moon
    if phase < 0.1875: return "🌒"  # Waxing Crescent
    if phase < 0.3125: return "🌓"  # First Quarter
    if phase < 0.4375: return "🌔"  # Waxing Gibbous
    if phase < 0.5625: return "🌕"  # Full Moon
    if phase < 0.6875: return "🌖"  # Waning Gibbous
    if phase < 0.8125: return "🌗"  # Last Quarter
    return "🌘"  # Waning Crescent
```

**Phase ranges** (each covers ~3.69 days):
```
New Moon:           [0.000, 0.0625) ∪ [0.9375, 1.000)
Waxing Crescent:    [0.0625, 0.1875)
First Quarter:      [0.1875, 0.3125)
Waxing Gibbous:     [0.3125, 0.4375) ← BONUS
Full Moon:          [0.4375, 0.5625) ← BONUS  
Waning Gibbous:     [0.5625, 0.6875) ← BONUS
Last Quarter:       [0.6875, 0.8125)
Waning Crescent:    [0.8125, 0.9375)
```

---

## Complete Working Example

**Scenario**: March 15, 2026, 21:00
- Apparent temperature: 8°C
- Rain last 8h: 2.5mm
- Current rain: 0.8mm/h
- Lunar phase: Full Moon (🌕)

### Step-by-step calculation:

**1. Thermal factor**
```
f_temp = (8 - 4) / 6 = 4/6 = 0.667
```

**2. Hydric factor**
```
h_sol = min(1.0, 2.5/2.0) = 1.0
p_active = min(1.0, 0.8/1.0) = 0.8
f_hydrique = (1.0 × 0.6) + (0.8 × 0.4) = 0.6 + 0.32 = 0.92
```

**3. Seasonal factor**
```
f_season = 1.0  (March = peak)
```

**4. Lunar factor**
```
f_lune = 1.1  (Full moon bonus)
```

**5. Final probability**
```
P = 0.667 × 0.92 × 1.0 × 1.1 × 100
P = 0.675 × 100 = 67.5%
P_final = 68% (rounded)
```

**Result**: "Migration modérée" (Moderate migration) 🐸🐸

---

## Classification Thresholds

The continuous probability score is mapped to discrete activity levels:

```python
def get_label(prob):
    if prob < 20:  return "Migration peu probable", "❌", "gray"
    if prob < 45:  return "Migration faible", "🐸", "orange"  
    if prob < 75:  return "Migration modérée", "🐸🐸", "#2ECC71"
    return "Forte migration attendue", "🐸🐸🐸🐸", "#1E8449"
```

| Probability | Label | Visual | Color |
|-------------|-------|--------|-------|
| 0-19% | Peu probable | ❌ | Gray |
| 20-44% | Faible | 🐸 | Orange |
| 45-74% | Modérée | 🐸🐸 | Green |
| 75-100% | Forte | 🐸🐸🐸🐸 | Dark Green |

---

## Temporal Analysis

### Nightly Window
The algorithm evaluates a 10-hour migration window:
```
start_time = date @ 20:00 (8 PM)
end_time = date+1 @ 06:00 (6 AM)
```

### Hourly Iteration
For each hour in the window:
1. Calculate 8-hour rolling averages (temperature, precipitation)
2. Compute probability using current conditions
3. Track maximum probability and optimal hour

### Peak Detection
```python
best_hour = max(hourly_results, key=lambda x: x['probability'])
```

---

## Data Processing Pipeline

### 1. Weather Data Acquisition
```
Source: Open-Meteo API (ICON-CH model)
Frequency: Hourly
Forecast: 8 days (192 hours)
Variables: temperature_2m, apparent_temperature, precipitation
```

### 2. Daily Aggregation
For each date, calculate:
- **Daytime rain** (12h-20h): Indicator of soil preparation
- **Evening temperature** (18h-22h): Pre-migration thermal state
- **Night window** (20h-06h): Active migration period

### 3. Rolling Windows
```python
# 8-hour lookback for contextual conditions
rain_8h = df.iloc[max(0, i-8):i]['precipitation'].sum()
temp_8h_avg = df.iloc[max(0, i-8):i]['temperature_2m'].mean()
```

---

## Model Assumptions & Limitations

### Assumptions
1. **Temperature threshold**: 4°C is universal critical minimum
2. **Precipitation saturation**: 2mm (8h) and 1mm/h (current) are optimal
3. **Multiplicative interaction**: All factors must be favorable
4. **Lunar synchronization**: 10% enhancement near full moon
5. **Species generalization**: Model averaged across common Swiss species

### Limitations
1. **Species-specific variation**: Model doesn't differentiate between toads, frogs, newts
2. **Microhabitat**: Local conditions (pond proximity, vegetation) not considered
3. **Population dynamics**: No accounting for population size or breeding site saturation
4. **Wind effects**: Not included (can suppress migration)
5. **Snow cover**: Not explicitly modeled (partially captured via temperature)

### Forecast Reliability
```python
if day_index <= 1:  reliability = "Très Haute"   # 0-48h
elif day_index <= 3: reliability = "Haute"       # 48-96h  
elif day_index <= 5: reliability = "Moyenne"     # 96-144h
else:                reliability = "Basse"       # >144h
```

---

## Validation Against Literature

### Temperature Threshold
- **Reading (1998)**: Migration occurs >5°C, peaks 8-10°C
- **Model**: Threshold 4°C, optimal ≥10°C ✓

### Precipitation Trigger  
- **Dervo et al. (2016)**: Positive correlation with rainfall
- **Model**: Multiplicative rain factor, weighted soil+active ✓

### Lunar Effect
- **Grant et al. (2021)**: Peak migrations ±3 days of full moon
- **Model**: 10% bonus for gibbous/full phases ✓

### Seasonal Timing
- **Arnfield et al. (2012)**: Feb-April peak in UK populations
- **Model**: March = 1.0, Feb/Apr = 0.8-0.9 ✓

---

## Future Enhancements

Potential model improvements:
1. **Species-specific models**: Separate parameters for Bufo, Rana, Triturus
2. **Machine learning**: Train on historical migration count data
3. **Wind speed**: Incorporate as suppressing factor
4. **Photoperiod**: Day length as additional seasonal cue
5. **Barometric pressure**: Rapid changes may trigger migration
6. **Soil temperature**: Better predictor than air temperature
7. **Validation**: Compare predictions against actual migration counts

---

## References

1. **Reading, C. J. (1998).** Effect of winter temperatures on timing of breeding activity in common toad. *Oecologia*, 117, 469-475.

2. **Arnfield, H., et al. (2012).** Factors influencing timing of spring migration in common toads. *Journal of Zoology*, 288(2), 112-118.

3. **Dervo, B. K., et al. (2016).** Effects of temperature and precipitation on breeding migrations. *Scientifica*, 2016, 3174316.

4. **Grant, R., et al. (2021).** Lunar phase as cue for migrations in explosive breeding amphibians. *European Journal of Wildlife Research*, 67, 11.

5. **Bison, M., et al. (2021).** Earlier snowmelt advances breeding phenology but increases risks. *Frontiers in Ecology and Evolution*, 9, 645585.

6. **Loman, J. (2016).** Breeding phenology in Rana temporaria. *Ecology and Evolution*, 6(17), 6202-6209.


## Data Source

Weather data from [Open-Meteo API](https://open-meteo.com/) using MeteoSwiss ICON-CH model.

## Scientific References

Based on peer-reviewed research on amphibian breeding phenology and migration triggers (Reading 1998, Arnfield et al. 2012, Grant et al. 2021, and others).

---

**Note**: This is a predictive model for educational and planning purposes. Always verify local conditions before field observations.
