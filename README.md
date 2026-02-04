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

## Data Source

Weather data from [Open-Meteo API](https://open-meteo.com/) using MeteoSwiss ICON-CH model.

## Scientific References

Based on peer-reviewed research on amphibian breeding phenology and migration triggers (Reading 1998, Arnfield et al. 2012, Grant et al. 2021, and others).

---

**Note**: This is a predictive model for educational and planning purposes. Always verify local conditions before field observations.
