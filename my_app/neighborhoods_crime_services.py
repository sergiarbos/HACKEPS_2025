import csv
import io
import math
from typing import Dict, Any, List

import requests

CRIME_URL = "https://data.lacity.org/resource/2nrs-mtv8.json"

# Radi (metres) aproximat al voltant del centre del neighborhood
CRIME_RADIUS_M = 1500

# Data mínima (igual que al test que et funciona)
CRIME_START_DATE = "2024-01-01"

# Mateixa llista de neighborhoods que a la resta de scripts
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


def bbox_for_radius(lat: float, lon: float, radius_m: float) -> tuple[float, float, float, float]:
    """
    Construeix un bounding box aproximat (lat_min, lat_max, lon_min, lon_max)
    per a un radi donat en metres al voltant (lat, lon).
    """
    # 1 grau de latitud ~ 111 km
    delta_lat = radius_m / 111000.0

    # 1 grau de longitud ~ 111 km * cos(lat)
    lat_rad = math.radians(lat)
    delta_lon = radius_m / (111000.0 * math.cos(lat_rad))

    lat_min = lat - delta_lat
    lat_max = lat + delta_lat
    lon_min = lon - delta_lon
    lon_max = lon + delta_lon

    return lat_min, lat_max, lon_min, lon_max


def get_crime_stats_for_bbox(lat: float, lon: float, radius_m: int, start_date: str) -> dict:
    """
    Fa el mateix estil de consulta que el test que et funciona,
    però afegint un filtre per lat/lon (bounding box) per aprox. el barri.

    Retorna:
      - crime_count
      - crime_examples (fins a 5 descripcions més freqüents)
    """
    lat_min, lat_max, lon_min, lon_max = bbox_for_radius(lat, lon, radius_m)

    # El dataset té columnes 'lat' i 'lon' numèriques, així que filtrarem per això
    where = (
        f"date_occ >= '{start_date}' "
        f"AND lat IS NOT NULL AND lon IS NOT NULL "
        f"AND lat BETWEEN {lat_min} AND {lat_max} "
        f"AND lon BETWEEN {lon_min} AND {lon_max}"
    )

    # 1) Nombre total de delictes
    params_count = {
        "$select": "count(*) as crime_count",
        "$where": where,
    }
    resp_count = requests.get(CRIME_URL, params=params_count)
    print("  [count] Status code:", resp_count.status_code)

    if resp_count.status_code >= 400:
        print("  [count] ERROR:", resp_count.text[:200], "...")
        crime_count = 0
    else:
        data_count = resp_count.json()
        if data_count and "crime_count" in data_count[0]:
            try:
                crime_count = int(data_count[0]["crime_count"])
            except ValueError:
                crime_count = 0
        else:
            crime_count = 0

    # 2) Tipus de delicte més freqüents
    params_examples = {
        "$select": "crm_cd_desc, count(*) as cnt",
        "$where": where,
        "$group": "crm_cd_desc",
        "$order": "cnt DESC",
        "$limit": 5,
    }
    resp_ex = requests.get(CRIME_URL, params=params_examples)
    print("  [examples] Status code:", resp_ex.status_code)

    crime_examples_list: List[str] = []
    if resp_ex.status_code >= 400:
        print("  [examples] ERROR:", resp_ex.text[:200], "...")
    else:
        data_ex = resp_ex.json()
        crime_examples_list = [
            row["crm_cd_desc"] for row in data_ex if row.get("crm_cd_desc")
        ]

    return {
        "crime_count": crime_count,
        "crime_examples": " | ".join(crime_examples_list),
    }


def main():
    reader = csv.DictReader(io.StringIO(NEIGHBORHOODS_CSV.strip()))
    results: List[Dict[str, Any]] = []

    for n in reader:
        display_name = n["display_name"]
        lat = float(n["lat"])
        lon = float(n["lon"])

        print(f"\n=== {display_name} ===")
        print(f"Centre approx.: lat={lat}, lon={lon}")
        print(f"Radi crims aprox.: {CRIME_RADIUS_M} m des de {CRIME_START_DATE}")

        stats = get_crime_stats_for_bbox(lat, lon, CRIME_RADIUS_M, CRIME_START_DATE)

        print(f"  Nombre de delictes: {stats['crime_count']}")
        if stats["crime_examples"]:
            print(f"  Tipus més freqüents: {stats['crime_examples']}")

        row_out = {
            "id": n["id"],
            "name": n["name"],
            "display_name": display_name,
            "lat": lat,
            "lon": lon,
            "crime_count": stats["crime_count"],
            "crime_examples": stats["crime_examples"],
        }
        results.append(row_out)

    fieldnames = [
        "id", "name", "display_name", "lat", "lon",
        "crime_count", "crime_examples",
    ]

    with open("neighborhoods_crime_services.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

    print("\nFitxer 'neighborhoods_crime_services.csv' creat amb èxit.")


if __name__ == "__main__":
    main()
