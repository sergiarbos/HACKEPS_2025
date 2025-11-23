import csv
import io
import math
from typing import Dict, Any, List

import requests
from pyproj import Transformer

# ========================
# CONFIG
# ========================

PARKS_URL = "https://data.lacity.org/resource/4jt3-efvk.json"

# Sistema de coordenadas de origen (proyectado, típico en LA)
# Segons el que havíem comentat, assumim EPSG:2229 (NAD83 / California zone 5 (ftUS))
SRC_CRS = "EPSG:2229"

# Sistema de destino: WGS84 (lon/lat)
DST_CRS = "EPSG:4326"

# always_xy=True => el transformer rep/dona (lon, lat)
transformer = Transformer.from_crs(SRC_CRS, DST_CRS, always_xy=True)

# Radi per comptar parcs al voltant del centre del neighborhood (en metres)
PARK_SEARCH_RADIUS_M = 1500

# Mateixa llista de neighborhoods que als altres scripts
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
# FUNCIONS GEO / PARCS
# ========================

def compute_centroid_from_multipolygon(geom: dict) -> tuple[float, float]:
    """
    geom:
      {
        "type": "MultiPolygon",
        "coordinates": [
          [
            [
              [x1, y1],
              [x2, y2],
              ...
            ]
          ]
        ]
      }

    Calcula un "centre" simple com la mitjana de tots els vèrtexs.
    No és el centreide geomètric perfecte, però és prou bo
    per tenir un punt representatiu del parc.
    """
    coords = geom["coordinates"]

    xs: List[float] = []
    ys: List[float] = []

    # MultiPolygon -> llista de polígons
    for polygon in coords:
        # polygon -> llista d'anells
        for ring in polygon:
            for x, y in ring:
                xs.append(x)
                ys.append(y)

    if not xs:
        raise ValueError("No hi ha coordenades a the_geom")

    x_centroid = sum(xs) / len(xs)
    y_centroid = sum(ys) / len(ys)
    return x_centroid, y_centroid


def fetch_parks(limit: int | None = None) -> List[Dict[str, Any]]:
    """
    Demana els parcs de l'API LA.
    Si limit és None, posem un límit gran per cobrir tots els parcs.
    """
    params: Dict[str, Any] = {}
    if limit is not None:
        params["$limit"] = limit
    else:
        params["$limit"] = 5000  # molt per sobre del nombre de parcs real

    resp = requests.get(PARKS_URL, params=params)
    print("Status code parks:", resp.status_code)
    resp.raise_for_status()
    data = resp.json()
    print(f"Parcs rebuts: {len(data)}")
    return data


def build_parks_centroids() -> List[Dict[str, Any]]:
    """
    Retorna una llista de parcs amb centroid en lat/lon:

      [
        {
          "name": ...,
          "address": ...,
          "lat": ...,
          "lon": ...,
        },
        ...
      ]
    """
    parks = fetch_parks(limit=None)
    out: List[Dict[str, Any]] = []

    for row in parks:
        name = row.get("name")
        address = row.get("address")
        geom = row.get("the_geom")

        if not geom:
            # algun parc podria no tenir geometria
            continue

        try:
            # 1) centroide en coordenades locals (X, Y)
            x_c, y_c = compute_centroid_from_multipolygon(geom)

            # 2) transformar a lon/lat (WGS84)
            lon, lat = transformer.transform(x_c, y_c)
        except Exception as e:
            print(f"[AVÍS] No s'ha pogut calcular centroid per al parc '{name}': {e}")
            continue

        out.append(
            {
                "name": name,
                "address": address,
                "lat": lat,
                "lon": lon,
            }
        )

    print(f"Parcs amb centroid calculat: {len(out)}")
    return out


def haversine_distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Distància entre dos punts (lat/lon graus) en metres.
    """
    R = 6371000.0  # radi de la Terra en metres

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = math.sin(dphi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c


# ========================
# MAIN: parcs per neighborhood
# ========================

def main():
    # 1) Precalculem els centroids de tots els parcs
    parks = build_parks_centroids()

    # 2) Llegim els neighborhoods
    reader = csv.DictReader(io.StringIO(NEIGHBORHOODS_CSV.strip()))
    results: List[Dict[str, Any]] = []

    for n in reader:
        display_name = n["display_name"]
        n_lat = float(n["lat"])
        n_lon = float(n["lon"])

        print(f"\n=== {display_name} ===")
        print(f"Centre approx. del neighborhood: lat={n_lat}, lon={n_lon}")
        print(f"Radi per comptar parcs: {PARK_SEARCH_RADIUS_M} m")

        parks_in_area: List[Dict[str, Any]] = []

        # 3) Per cada parc, mirem si cau dins el radi
        for p in parks:
            dist = haversine_distance_m(n_lat, n_lon, p["lat"], p["lon"])
            if dist <= PARK_SEARCH_RADIUS_M:
                parks_in_area.append(p)

        parks_count = len(parks_in_area)
        parks_examples = [p["name"] for p in parks_in_area[:5] if p["name"]]

        print(f"Parcs trobats: {parks_count}")
        if parks_examples:
            print("Exemples:", ", ".join(parks_examples))

        row_out = {
            "id": n["id"],
            "name": n["name"],
            "display_name": display_name,
            "lat": n_lat,
            "lon": n_lon,
            "parks_count": parks_count,
            "parks_examples": " | ".join(parks_examples),
        }
        results.append(row_out)

    # 4) Guardem-ho en CSV, estil lifestyle_services
    fieldnames = [
        "id", "name", "display_name", "lat", "lon",
        "parks_count", "parks_examples",
    ]

    with open("neighborhoods_parks_services.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

    print("\nFitxer 'neighborhoods_parks_services.csv' creat amb èxit.")


if __name__ == "__main__":
    main()
