import requests

GEOCODER_URL = "https://geocoding.geo.census.gov/geocoder/geographies/coordinates"

def geocode_to_tract(lat: float, lon: float):
    """
    Torna (state, county, tract, geoid_tract) per unes coordenades.
    Usa benchmark/vintage = 4 (Public_AR_Current / Current_Current).
    """
    params = {
        "x": lon,   # IMPORTANT: x = lon, y = lat
        "y": lat,
        "benchmark": 4,       # equival a Public_AR_Current
        "vintage": 4,         # equival a Current_Current
        "format": "json"
    }

    r = requests.get(GEOCODER_URL, params=params, timeout=10)
    r.raise_for_status()
    data = r.json()

    # Navegar fins a "Census Tracts"
    result = data["result"]
    geos = result["geographies"]

    tracts = geos.get("Census Tracts") or geos.get("Census Tract") or []
    if not tracts:
        return None

    tract = tracts[0]
    state = tract["STATE"]
    county = tract["COUNTY"]
    tract_code = tract["TRACT"]
    geoid = tract["GEOID"]

    return {
        "state": state,
        "county": county,
        "tract": tract_code,
        "geoid": geoid,
        "raw": tract,
    }


if __name__ == "__main__":
    # PROVA amb un dels teus barris (North Hills East)
    lat = 34.2326161
    lon = -118.4625011

    info = geocode_to_tract(lat, lon)
    print(info)
