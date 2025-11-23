import csv
import io
from typing import Dict, Any, List

import requests

# ========================
# CONFIG
# ========================

# ⚠️ POSA AQUÍ LA TEVA API KEY DEL CENSUS
API_KEY = "4238c4f51f0749e95aea647f47ba6bcd05084e4b"

ACS_YEAR = 2023
ACS_URL = f"https://api.census.gov/data/{ACS_YEAR}/acs/acs5"
GEOCODER_URL = "https://geocoding.geo.census.gov/geocoder/geographies/coordinates"

# Mateixa llista de neighborhoods
NEIGHBORHOODS_CSV = """id,name,display_name,admin_level,lat,lon
15048390,North Hills East Neighborhood Council District,North Hills East,10,34.2326161,-118.4625011
15048391,North Hills West Neighborhood Council District,North Hills West,10,34.2351485,-118.4857186
15059477,Panorama City Neighborhood Council District,Panorama City,10,34.2286517,-118.4451755
15059478,Mission Hills Neighborhood Council District,Mission Hills,10,34.2713002,-118.4529373
15059522,Sylmar Neighborhood Council District,Sylmar,10,34.3083124,-118.4514186
15339539,Van Nuys Neighborhood Council District,Van Nuys,10,34.1907345,-118.4505332
15339540,Lake Balboa Neighborhood Council District,Lake Balboa,10,34.1912118,-118.4931452
15339541,Reseda,Reseda,10,34.2037901,-118.5404374
15339542,Northridge South Neighborhood Council District,Northridge South,10,34.2221591,-118.5336501
15339543,Northridge East Neighborhood Council District,Northridge East,10,34.2568239,-118.5105726
15339544,Granada Hills South Neighborhood Council District,Granada Hills South,10,34.2641803,-118.5007291
15339545,Northridge West Neighborhood Council District,Northridge West,10,34.2535248,-118.5501567
15339546,Granada Hills North Neighborhood Council District,Granada Hills North,10,34.3006103,-118.5073097
15899803,Arleta Neighborhood Council District,Arleta,10,34.243174,-118.429436
15899804,Pacoima Neighborhood Council,Pacoima,10,34.2663229,-118.4065859
16741092,West Hills Neighborhood Council District,West Hills,10,34.2096098,-118.6354439
17307354,Los Feliz Neighborhood Council District,Los Feliz,10,34.1286081,-118.2985312
18194737,Sherman Oaks Neighborhood Council District,Sherman Oaks,10,34.1492572,-118.4446675
18284559,Encino Neighborhood Council District,Encino,10,34.1564268,-118.5046272
18284560,Tarzana Neighborhood Council District,Tarzana,10,34.1562105,-118.5490233
18284570,Chatsworth Neighborhood Council District,Chatsworth,10,34.2571339,-118.6048777
18284571,Porter Ranch Neighborhood Council District,Porter Ranch,10,34.2878806,-118.5592008
18302562,Winnetka Neighborhood Council District,Winnetka,10,34.2106154,-118.5754189
18302563,Canoga Park Neighborhood Council District,Canoga Park,10,34.2146219,-118.6015988
18302564,Woodland Hills-Warner Center Neighborhood Council District,Woodland Hills-Warner Center,10,34.163131,-118.614793
18303949,Greater Valley Glen Neighborhood Council District,Greater Valley Glen,10,34.1866407,-118.4144391
18303950,North Hollywood West Neighborhood Council District,North Hollywood West,10,34.2041704,-118.4135017
18303951,North Hollywood Northeast Neighborhood Council District,North Hollywood Northeast,10,34.2036986,-118.3829272
18303952,North Hollywood Neighborhood Council District,North Hollywood,10,34.1694729,-118.3786499
18303953,Valley Village Neighborhood Council District,Valley Village,10,34.163285,-118.3956874
18303954,Greater Toluca Lake Neighborhood Council District,Greater Toluca Lake,10,34.154927,-118.3622738
18303955,Studio City Neighborhood Council District,Studio City,10,34.137897,-118.3910959
"""


# ========================
# HELPERS
# ========================

def to_float(value: Any) -> float | None:
    try:
        v = float(value)
        if v < -1e7:
            return None
        return v
    except (TypeError, ValueError):
        return None


def to_int(value: Any) -> int | None:
    try:
        v = int(value)
        if v < -1e7:
            return None
        return v
    except (TypeError, ValueError):
        return None


# ========================
# CENSUS GEOCODER
# ========================

def lookup_zcta_from_coords(lat: float, lon: float) -> str:
    """
    Donat lat, lon (graus), retorna el ZCTA5 (ZIP code tabulation area)
    mitjançant el Census Geocoder.
    """
    params = {
        "x": lon,
        "y": lat,
        "benchmark": "Public_AR_Current",
        "vintage": "Current_Current",
        "layers": "all",
        "format": "json",
    }
    resp = requests.get(GEOCODER_URL, params=params)
    resp.raise_for_status()
    data = resp.json()

    geogs = data["result"]["geographies"]
    zcta_layer = None
    for key, value in geogs.items():
        if "ZIP Code Tabulation Areas" in key:
            zcta_layer = value
            break

    if not zcta_layer:
        raise RuntimeError(f"No ZCTA found for coords lat={lat}, lon={lon}")

    zcta_info = zcta_layer[0]
    zcta = zcta_info.get("ZCTA5") or zcta_info.get("GEOID")
    if not zcta:
        raise RuntimeError("ZCTA5/GEOID missing in geocoder response")

    return zcta


# ========================
# ACS: INCOME + AGE + HOUSING
# ========================

def get_zip_full_stats(zip_code: str) -> Dict[str, Any]:
    """
    Demana al ACS 5-year dades socioeconòmiques i d'habitatge per un ZCTA.

    Retorna:
      - median_income
      - median_age
      - population
      - median_rent
      - median_home_value
      - owner_share, renter_share
      - single_family_pct, small_multi_pct, large_multi_pct
    """
    params = {
        "get": ",".join([
            "NAME",
            # Renda, edat, població
            "B19013_001E",   # Median household income
            "B01002_001E",   # Median age
            "B01003_001E",   # Total population
            # Lloguer i compra
            "B25064_001E",   # Median gross rent
            "B25077_001E",   # Median home value
            # Tinença (owner vs renter)
            "B25003_001E",   # Total occupied housing units
            "B25003_002E",   # Owner-occupied
            "B25003_003E",   # Renter-occupied
            # Tipus d'habitatge (units in structure)
            "B25024_001E",   # Total housing units
            "B25024_002E",   # 1-unit detached
            "B25024_003E",   # 1-unit attached
            "B25024_004E",   # 2 units
            "B25024_005E",   # 3 or 4 units
            "B25024_006E",   # 5 to 9 units
            "B25024_007E",   # 10 to 19 units
            "B25024_008E",   # 20 to 49 units
            "B25024_009E",   # 50 or more units
        ]),
        "for": f"zip code tabulation area:{zip_code}",
        "key": API_KEY,
    }

    resp = requests.get(ACS_URL, params=params)
    resp.raise_for_status()
    data = resp.json()

    if len(data) < 2:
        raise RuntimeError(f"No ACS data for ZCTA {zip_code}")

    headers = data[0]
    values = data[1]
    row = dict(zip(headers, values))

    median_income = to_float(row["B19013_001E"])
    median_age = to_float(row["B01002_001E"])
    population = to_int(row["B01003_001E"])

    median_rent = to_float(row["B25064_001E"])
    median_home_value = to_float(row["B25077_001E"])

    occupied_total = to_int(row["B25003_001E"]) or 0
    owners = to_int(row["B25003_002E"]) or 0
    renters = to_int(row["B25003_003E"]) or 0

    total_units = to_int(row["B25024_001E"]) or 0
    u_1_detached = to_int(row["B25024_002E"]) or 0
    u_1_attached = to_int(row["B25024_003E"]) or 0
    u_2 = to_int(row["B25024_004E"]) or 0
    u_3_4 = to_int(row["B25024_005E"]) or 0
    u_5_9 = to_int(row["B25024_006E"]) or 0
    u_10_19 = to_int(row["B25024_007E"]) or 0
    u_20_49 = to_int(row["B25024_008E"]) or 0
    u_50_plus = to_int(row["B25024_009E"]) or 0

    if occupied_total > 0:
        owner_share = owners / occupied_total * 100.0
        renter_share = renters / occupied_total * 100.0
    else:
        owner_share = renter_share = None

    if total_units > 0:
        single_family = u_1_detached + u_1_attached
        small_multi = u_2 + u_3_4 + u_5_9
        large_multi = u_10_19 + u_20_49 + u_50_plus

        single_family_pct = single_family / total_units * 100.0
        small_multi_pct = small_multi / total_units * 100.0
        large_multi_pct = large_multi / total_units * 100.0
    else:
        single_family_pct = small_multi_pct = large_multi_pct = None

    return {
        "zip": zip_code,
        "name": row["NAME"],
        "median_income": median_income,
        "median_age": median_age,
        "population": population,
        "median_rent": median_rent,
        "median_home_value": median_home_value,
        "owner_share": owner_share,
        "renter_share": renter_share,
        "single_family_pct": single_family_pct,
        "small_multi_pct": small_multi_pct,
        "large_multi_pct": large_multi_pct,
    }


# ========================
# MAIN
# ========================

def main():
    reader = csv.DictReader(io.StringIO(NEIGHBORHOODS_CSV.strip()))
    results: List[Dict[str, Any]] = []

    for n in reader:
        display_name = n["display_name"]
        lat = float(n["lat"])
        lon = float(n["lon"])

        print(f"\n=== {display_name} ===")
        print(f"Coords: lat={lat}, lon={lon}")

        # 1) coords → ZCTA
        zcta = lookup_zcta_from_coords(lat, lon)
        print(f"ZCTA / ZIP: {zcta}")

        # 2) ZCTA → ACS (totes les mètriques)
        stats = get_zip_full_stats(zcta)

        print(f"ACS area name: {stats['name']}")
        print(f"  Renda mitjana:         {stats['median_income']}")
        print(f"  Edat mitjana:          {stats['median_age']}")
        print(f"  Població total:        {stats['population']}")
        print(f"  Lloguer mitjà:         {stats['median_rent']}")
        print(f"  Valor mitjà habitatge: {stats['median_home_value']}")
        print(f"  % propietaris:         {stats['owner_share']}")
        print(f"  % llogaters:           {stats['renter_share']}")
        print(f"  % cases unifamiliars:  {stats['single_family_pct']}")
        print(f"  % blocs petits (2–9):  {stats['small_multi_pct']}")
        print(f"  % blocs grans (10+):   {stats['large_multi_pct']}")

        row_out = {
            "id": n["id"],
            "name": n["name"],
            "display_name": display_name,
            "lat": lat,
            "lon": lon,
            "zcta": zcta,
            "acs_name": stats["name"],
            "median_income": stats["median_income"],
            "median_age": stats["median_age"],
            "population": stats["population"],
            "median_rent": stats["median_rent"],
            "median_home_value": stats["median_home_value"],
            "owner_share": stats["owner_share"],
            "renter_share": stats["renter_share"],
            "single_family_pct": stats["single_family_pct"],
            "small_multi_pct": stats["small_multi_pct"],
            "large_multi_pct": stats["large_multi_pct"],
        }
        results.append(row_out)

    fieldnames = [
        "id", "name", "display_name", "lat", "lon",
        "zcta", "acs_name",
        "median_income", "median_age", "population",
        "median_rent", "median_home_value",
        "owner_share", "renter_share",
        "single_family_pct", "small_multi_pct", "large_multi_pct",
    ]

    with open("neighborhoods_full_stats.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

    print("\nFitxer 'neighborhoods_full_stats.csv' creat amb totes les dades combinades.")


if __name__ == "__main__":
    main()
