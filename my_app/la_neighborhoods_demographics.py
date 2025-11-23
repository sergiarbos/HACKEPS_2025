#!/usr/bin/env python3
import csv
import time
import requests
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
INPUT_CSV = BASE_DIR / "la_neighborhoods_admin_9_10.csv"
OUTPUT_CSV = BASE_DIR / "la_neighborhoods_demographics.csv"

# URLs
GEOCODER_URL = "https://geocoding.geo.census.gov/geocoder/geographies/coordinates"
ACS_API_URL = "https://api.census.gov/data/2020/acs/acs5"

# Variables ACS que volem
ACS_VARS = {
    "median_household_income": "B19013_001E",  # $
    "total_population": "B01003_001E",         # total residents
    "median_age": "B01002_001E",              # anys
}


def load_neighborhoods(path: Path):
    rows = []
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    return rows


def geocode_to_tract(lat: float, lon: float):
    """
    Donades (lat, lon), retorna info de Census Tract:
    state, county, tract, geoid.
    Utilitza benchmark=4, vintage=4 (Public_AR_Current / Current_Current).
    """
    params = {
        "x": lon,   # IMPORTANT: x = lon, y = lat
        "y": lat,
        "benchmark": 4,
        "vintage": 4,
        "format": "json",
    }

    r = requests.get(GEOCODER_URL, params=params, timeout=10)
    # Debug opcional:
    # print("[DEBUG] Geocoder URL:", r.url)
    r.raise_for_status()
    data = r.json()

    geogs = data.get("result", {}).get("geographies", {})

    # Consultem "Census Tracts" (així ens assegurem d’estar al nivell de tract)
    tracts = geogs.get("Census Tracts") or geogs.get("Census Tract") or []
    if not tracts:
        raise ValueError("No s'ha trobat cap 'Census Tracts' al resultat")

    tr = tracts[0]
    state = tr.get("STATE")
    county = tr.get("COUNTY")
    tract = tr.get("TRACT")
    geoid = tr.get("GEOID")

    if not (state and county and tract and geoid):
        raise ValueError("Tracte amb informació incompleta")

    return state, county, tract, geoid


def get_acs_data(state: str, county: str, tract: str):
    """
    Demana a ACS 2020 5-year les estadístiques demogràfiques per un tracte.
    """
    get_vars = ["NAME"] + list(ACS_VARS.values())
    params = {
        "get": ",".join(get_vars),
        "for": f"tract:{tract}",
        "in": f"state:{state}+county:{county}",
    }

    r = requests.get(ACS_API_URL, params=params, timeout=10)
    # Debug opcional:
    # print("[DEBUG] ACS URL:", r.url)
    r.raise_for_status()
    data = r.json()

    if len(data) < 2:
        raise ValueError("Resposta ACS sense files de dades")

    header = data[0]
    values = data[1]
    row = dict(zip(header, values))

    return row


def main():
    if not INPUT_CSV.exists():
        raise FileNotFoundError(f"No s'ha trobat {INPUT_CSV}")

    neighborhoods = load_neighborhoods(INPUT_CSV)
    print(f"[Info] Barris carregats des de {INPUT_CSV.name}: {len(neighborhoods)}")

    out_rows = []

    for idx, nb in enumerate(neighborhoods, start=1):
        nb_id = nb["id"]
        name = nb["display_name"]
        lat = float(nb["lat"])
        lon = float(nb["lon"])

        print(f"[{idx}/{len(neighborhoods)}] Processant barri {nb_id} ({name})...")

        state = county = tract = geoid = ""
        acs_name = ""
        median_income = ""
        total_pop = ""
        median_age = ""

        try:
            # 1) Coordenades -> tracte
            state, county, tract, geoid = geocode_to_tract(lat, lon)
            # petita pausa per no saturar el geocoder
            time.sleep(0.2)

            # 2) Census tract -> dades ACS
            acs_row = get_acs_data(state, county, tract)
            acs_name = acs_row.get("NAME", "")

            # extreure valors bruts
            raw_income = acs_row.get(ACS_VARS["median_household_income"])
            raw_pop = acs_row.get(ACS_VARS["total_population"])
            raw_age = acs_row.get(ACS_VARS["median_age"])

            # convertir a tipus numèrics controlant valors especials
            def clean_num(v, to_type):
                if v in (None, "", "-666666666", "-666666666.0"):
                    return ""
                try:
                    return to_type(v)
                except ValueError:
                    return ""

            median_income = clean_num(raw_income, float)
            total_pop = clean_num(raw_pop, int)
            median_age = clean_num(raw_age, float)

        except Exception as e:
            print(f"   [Warn] Error obtenint dades per {name}: {e}")

        out_rows.append({
            "id": nb_id,
            "name": nb["name"],
            "display_name": nb["display_name"],
            "lat": lat,
            "lon": lon,
            "state": state,
            "county": county,
            "tract": tract,
            "geoid": geoid,
            "acs_name": acs_name,
            "acs_year": 2020,
            "median_household_income": median_income,
            "total_population": total_pop,
            "median_age": median_age,
        })

        # una mica de throttling també per l'ACS
        time.sleep(0.2)

    # Escriure resultats
    fieldnames = [
        "id",
        "name",
        "display_name",
        "lat",
        "lon",
        "state",
        "county",
        "tract",
        "geoid",
        "acs_name",
        "acs_year",
        "median_household_income",
        "total_population",
        "median_age",
    ]

    with OUTPUT_CSV.open("w", newline="", encoding="utf-8") as f_out:
        writer = csv.DictWriter(f_out, fieldnames=fieldnames)
        writer.writeheader()
        for row in out_rows:
            writer.writerow(row)

    print(f"[Info] Resultats desats a {OUTPUT_CSV.name}")


if __name__ == "__main__":
    main()
