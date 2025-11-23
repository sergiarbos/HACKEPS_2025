import csv
import io
from typing import Dict, Any, List

import requests
import time  # per fer pauses

# ========================
# CONFIG
# ========================

OVERPASS_URL = "https://overpass-api.de/api/interpreter"

# Radius de cerca al voltant del centre del neighborhood (en metres)
SEARCH_RADIUS_M = 1250

# Mateixa llista de neighborhoods que ja estàs fent servir
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
# OVERPASS QUERY
# ========================

def build_overpass_query(lat: float, lon: float, radius_m: int) -> str:
    """
    Construeix una consulta Overpass per a POIs d'estil de vida al voltant d'un punt.
    """
    r = radius_m
    query = f"""
    [out:json][timeout:60];
    (
      // Restaurants, bars, cafès
      node["amenity"="restaurant"](around:{r},{lat},{lon});
      way["amenity"="restaurant"](around:{r},{lat},{lon});
      node["amenity"="fast_food"](around:{r},{lat},{lon});
      way["amenity"="fast_food"](around:{r},{lat},{lon});
      node["amenity"="cafe"](around:{r},{lat},{lon});
      way["amenity"="cafe"](around:{r},{lat},{lon});
      node["amenity"="bar"](around:{r},{lat},{lon});
      way["amenity"="bar"](around:{r},{lat},{lon});

      // Cultura: museus, teatres, cinemes, arts
      node["tourism"="museum"](around:{r},{lat},{lon});
      way["tourism"="museum"](around:{r},{lat},{lon});
      node["amenity"="theatre"](around:{r},{lat},{lon});
      way["amenity"="theatre"](around:{r},{lat},{lon});
      node["amenity"="cinema"](around:{r},{lat},{lon});
      way["amenity"="cinema"](around:{r},{lat},{lon});
      node["amenity"="arts_centre"](around:{r},{lat},{lon});
      way["amenity"="arts_centre"](around:{r},{lat},{lon});

      // Gimnasos / fitness
      node["leisure"="fitness_centre"](around:{r},{lat},{lon});
      way["leisure"="fitness_centre"](around:{r},{lat},{lon});
      node["sport"="fitness"](around:{r},{lat},{lon});
      way["sport"="fitness"](around:{r},{lat},{lon});
      node["amenity"="gym"](around:{r},{lat},{lon});
      way["amenity"="gym"](around:{r},{lat},{lon});

      // Botigues (qualsevol shop=*)
      node["shop"](around:{r},{lat},{lon});
      way["shop"](around:{r},{lat},{lon});
    );
    out center;
    """
    return query.strip()


def fetch_pois_for_neighborhood(lat: float, lon: float, radius_m: int) -> List[Dict[str, Any]]:
    """
    Executa la consulta Overpass i retorna la llista d'elements (nodes/ways).
    Gestiona:
      - 429 Too Many Requests -> espera i reintenta
      - 5xx (504, 502, 500, etc.) -> espera i reintenta
    Si després dels intents segueix fallant, retorna [] per no petar el script.
    """
    query = build_overpass_query(lat, lon, radius_m)

    max_retries = 3
    wait_seconds = 30  # ajustable

    for attempt in range(1, max_retries + 1):
        resp = requests.post(OVERPASS_URL, data={"data": query})
        status = resp.status_code

        # Rate-limit o error de servidor -> espera i reintenta
        if status in (429, 500, 502, 503, 504):
            print(f"[Overpass] Error {status} (intent {attempt}/{max_retries}) per lat={lat}, lon={lon}. "
                  f"Esperant {wait_seconds} s abans de reintentar...")
            time.sleep(wait_seconds)
            continue

        # Altres errors (4xx que no siguin 429, etc.)
        try:
            resp.raise_for_status()
        except requests.HTTPError as e:
            print(f"[Overpass] Error HTTP definitiu per lat={lat}, lon={lon}: {e}. "
                  f"No es comptaran POIs en aquest barri.")
            return []

        data = resp.json()
        return data.get("elements", [])

    print(f"[Overpass] No s'ha pogut obtenir dades després de {max_retries} intents "
          f"per lat={lat}, lon={lon}. Retorno llista buida.")
    return []


# ========================
# CLASSIFICACIÓ DE POIS
# ========================

def classify_poi(elem: Dict[str, Any]) -> str | None:
    """
    Etiqueta un element OSM en una categoria:
      'restaurants', 'culture', 'gyms', 'shops'
    o retorna None si no encaixa.
    """
    tags = elem.get("tags", {})
    amenity = tags.get("amenity")
    tourism = tags.get("tourism")
    leisure = tags.get("leisure")
    sport = tags.get("sport")
    shop = tags.get("shop")

    # Restaurants / bars / cafès
    if amenity in {"restaurant", "fast_food", "cafe", "bar"}:
        return "restaurants"

    # Cultura
    if tourism == "museum" or amenity in {"theatre", "cinema", "arts_centre"}:
        return "culture"

    # Gimnasos
    if leisure == "fitness_centre" or sport == "fitness" or amenity == "gym":
        return "gyms"

    # Botigues
    if shop is not None:
        return "shops"

    return None


def summarize_pois(elems: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Contabilitza nombres per categoria i guarda alguns exemples de noms.
    """
    summary = {
        "restaurants_count": 0,
        "culture_count": 0,
        "gyms_count": 0,
        "shops_count": 0,
        "restaurants_examples": [],
        "culture_examples": [],
        "gyms_examples": [],
        "shops_examples": [],
    }

    for e in elems:
        cat = classify_poi(e)
        if not cat:
            continue

        summary[f"{cat}_count"] += 1

        name = e.get("tags", {}).get("name")
        if name and len(summary[f"{cat}_examples"]) < 5:
            summary[f"{cat}_examples"].append(name)

    return summary


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
        print(f"Centre approx.: lat={lat}, lon={lon}")
        print(f"Radius de cerca: {SEARCH_RADIUS_M} m")

        elems = fetch_pois_for_neighborhood(lat, lon, SEARCH_RADIUS_M)
        print(f"POIs trobats (bruts): {len(elems)}")

        summary = summarize_pois(elems)

        print(f"Restaurants: {summary['restaurants_count']} "
              f"{' | Ex: ' + ', '.join(summary['restaurants_examples']) if summary['restaurants_examples'] else ''}")
        print(f"Cultura:    {summary['culture_count']} "
              f"{' | Ex: ' + ', '.join(summary['culture_examples']) if summary['culture_examples'] else ''}")
        print(f"Gimnasos:   {summary['gyms_count']} "
              f"{' | Ex: ' + ', '.join(summary['gyms_examples']) if summary['gyms_examples'] else ''}")
        print(f"Botigues:   {summary['shops_count']} "
              f"{' | Ex: ' + ', '.join(summary['shops_examples']) if summary['shops_examples'] else ''}")

        row_out = {
            "id": n["id"],
            "name": n["name"],
            "display_name": display_name,
            "lat": lat,
            "lon": lon,
            "restaurants_count": summary["restaurants_count"],
            "culture_count": summary["culture_count"],
            "gyms_count": summary["gyms_count"],
            "shops_count": summary["shops_count"],
            "restaurants_examples": " | ".join(summary["restaurants_examples"]),
            "culture_examples": " | ".join(summary["culture_examples"]),
            "gyms_examples": " | ".join(summary["gyms_examples"]),
            "shops_examples": " | ".join(summary["shops_examples"]),
        }
        results.append(row_out)

        # pausa entre barris per no saturar Overpass
        time.sleep(15)

    # Guardem-ho en CSV per usar-ho després a l’algoritme / informe
    fieldnames = [
        "id", "name", "display_name", "lat", "lon",
        "restaurants_count", "culture_count", "gyms_count", "shops_count",
        "restaurants_examples", "culture_examples", "gyms_examples", "shops_examples",
    ]

    with open("neighborhoods_lifestyle_services.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

    print("\nFitxer 'neighborhoods_lifestyle_services.csv' creat amb èxit.")


if __name__ == "__main__":
    main()
