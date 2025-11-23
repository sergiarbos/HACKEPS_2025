import csv
import io
from typing import Dict, Any, List

import requests
import time

# ========================
# CONFIG
# ========================

OVERPASS_URL = "https://overpass-api.de/api/interpreter"

# Radi de cerca al voltant del centre del neighborhood (en metres)
SEARCH_RADIUS_M = 1500

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
    Consulta Overpass per a mobilitat al voltant d'un punt:
      - transport públic (parades, estacions)
      - infra de bici (cycleways)
      - accessibilitat a peu (footways, pedestrian, paths, crossings)
      - autopistes / vies principals (motorway, trunk, primary)
    """
    r = radius_m
    query = f"""
    [out:json][timeout:60];
    (
      // TRANSPORT PÚBLIC
      node["highway"="bus_stop"](around:{r},{lat},{lon});
      node["amenity"="bus_station"](around:{r},{lat},{lon});
      node["public_transport"~"platform|stop_position|stop|station"](around:{r},{lat},{lon});
      node["railway"~"station|halt|tram_stop|subway_entrance"](around:{r},{lat},{lon});
      way["railway"~"station|halt|tram_stop"](around:{r},{lat},{lon});

      // BICI: carrils bici i infra relacionada
      way["highway"="cycleway"](around:{r},{lat},{lon});
      way["bicycle"="designated"](around:{r},{lat},{lon});
      way["cycleway"](around:{r},{lat},{lon});

      // CAMINAR: voreres, carrers per vianants, camins, passos zebra
      way["highway"~"footway|pedestrian|path"](around:{r},{lat},{lon});
      node["highway"="crossing"](around:{r},{lat},{lon});

      // AUTOPISTES / VIES PRINCIPALS
      way["highway"~"motorway|trunk|primary"](around:{r},{lat},{lon});
    );
    out center;
    """
    return query.strip()


def fetch_mobility_elements(lat: float, lon: float, radius_m: int) -> List[Dict[str, Any]]:
    """
    Executa la consulta Overpass i retorna la llista d'elements.
    Gestiona 429 i 5xx amb reintents.
    """
    query = build_overpass_query(lat, lon, radius_m)

    max_retries = 3
    wait_seconds = 30

    for attempt in range(1, max_retries + 1):
        resp = requests.post(OVERPASS_URL, data={"data": query})
        status = resp.status_code

        if status in (429, 500, 502, 503, 504):
            print(f"[Overpass] Error {status} (intent {attempt}/{max_retries}) per lat={lat}, lon={lon}. "
                  f"Esperant {wait_seconds} s abans de reintentar...")
            time.sleep(wait_seconds)
            continue

        try:
            resp.raise_for_status()
        except requests.HTTPError as e:
            print(f"[Overpass] Error definitiu per lat={lat}, lon={lon}: {e}")
            return []

        data = resp.json()
        return data.get("elements", [])

    print(f"[Overpass] Sense dades després de {max_retries} intents per lat={lat}, lon={lon}.")
    return []


# ========================
# CLASSIFICACIÓ
# ========================

def classify_mobility_feature(elem: Dict[str, Any]) -> List[str]:
    """
    Assigna una o més categories a un element:
      - "pt"  (transport públic)
      - "bike"
      - "walk"
      - "roads"

    Retorna llista de categories (pot estar buida).
    """
    tags = elem.get("tags", {})
    highway = tags.get("highway")
    amenity = tags.get("amenity")
    public_transport = tags.get("public_transport")
    railway = tags.get("railway")
    bicycle = tags.get("bicycle")
    cycleway = tags.get("cycleway")

    cats: List[str] = []

    # TRANSPORT PÚBLIC
    if highway == "bus_stop" or amenity == "bus_station":
        cats.append("pt")
    if public_transport in {"platform", "stop_position", "stop", "station"}:
        cats.append("pt")
    if railway in {"station", "halt", "tram_stop", "subway_entrance"}:
        cats.append("pt")

    # BICI
    if highway == "cycleway":
        cats.append("bike")
    if bicycle == "designated":
        cats.append("bike")
    if cycleway is not None:
        cats.append("bike")

    # CAMINAR
    if highway in {"footway", "pedestrian", "path", "living_street"}:
        cats.append("walk")
    if highway == "crossing":
        cats.append("walk")

    # AUTOPISTES / VIES PRINCIPALS
    if highway in {"motorway", "trunk", "primary"}:
        cats.append("roads")

    # Eliminem duplicats
    return list(set(cats))


def summarize_mobility(elems: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Conta elements per categoria i guarda alguns exemples de noms.
    """
    summary = {
        "pt_stops_count": 0,
        "bike_infra_count": 0,
        "walkability_features_count": 0,
        "major_roads_count": 0,
        "pt_examples": [],
        "bike_examples": [],
        "walk_examples": [],
        "roads_examples": [],
    }

    for e in elems:
        cats = classify_mobility_feature(e)
        if not cats:
            continue

        tags = e.get("tags", {})
        name = tags.get("name")

        if "pt" in cats:
            summary["pt_stops_count"] += 1
            if name and len(summary["pt_examples"]) < 5:
                summary["pt_examples"].append(name)

        if "bike" in cats:
            summary["bike_infra_count"] += 1
            # per exemple de bici també podem guardar el nom si existeix
            if name and len(summary["bike_examples"]) < 5:
                summary["bike_examples"].append(name)

        if "walk" in cats:
            summary["walkability_features_count"] += 1
            if name and len(summary["walk_examples"]) < 5:
                summary["walk_examples"].append(name)

        if "roads" in cats:
            summary["major_roads_count"] += 1
            if name and len(summary["roads_examples"]) < 5:
                summary["roads_examples"].append(name)

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
        print(f"Radi mobilitat: {SEARCH_RADIUS_M} m")

        elems = fetch_mobility_elements(lat, lon, SEARCH_RADIUS_M)
        print(f"Elements de mobilitat trobats (bruts): {len(elems)}")

        summary = summarize_mobility(elems)

        print(f"Transport públic (parades/estacions): {summary['pt_stops_count']} "
              f"{' | Ex: ' + ', '.join(summary['pt_examples']) if summary['pt_examples'] else ''}")
        print(f"Infra bici (ways amb cycleway/bicycle): {summary['bike_infra_count']} "
              f"{' | Ex: ' + ', '.join(summary['bike_examples']) if summary['bike_examples'] else ''}")
        print(f"Accessibilitat a peu (footway/pedestrian/path/crossing): {summary['walkability_features_count']} "
              f"{' | Ex: ' + ', '.join(summary['walk_examples']) if summary['walk_examples'] else ''}")
        print(f"Autopistes / vies principals: {summary['major_roads_count']} "
              f"{' | Ex: ' + ', '.join(summary['roads_examples']) if summary['roads_examples'] else ''}")

        row_out = {
            "id": n["id"],
            "name": n["name"],
            "display_name": display_name,
            "lat": lat,
            "lon": lon,
            "pt_stops_count": summary["pt_stops_count"],
            "bike_infra_count": summary["bike_infra_count"],
            "walkability_features_count": summary["walkability_features_count"],
            "major_roads_count": summary["major_roads_count"],
            "pt_examples": " | ".join(summary["pt_examples"]),
            "bike_examples": " | ".join(summary["bike_examples"]),
            "walk_examples": " | ".join(summary["walk_examples"]),
            "roads_examples": " | ".join(summary["roads_examples"]),
        }
        results.append(row_out)

        # Petita pausa per no saturar Overpass
        time.sleep(10)

    fieldnames = [
        "id", "name", "display_name", "lat", "lon",
        "pt_stops_count", "bike_infra_count",
        "walkability_features_count", "major_roads_count",
        "pt_examples", "bike_examples", "walk_examples", "roads_examples",
    ]

    with open("neighborhoods_mobility_transport.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

    print("\nFitxer 'neighborhoods_mobility_transport.csv' creat amb èxit.")


if __name__ == "__main__":
    main()
