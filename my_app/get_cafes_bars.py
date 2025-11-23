import csv
import os
import time
import overpy

# Fitxers
INPUT_CSV = "la_neighborhoods_admin_9_10.csv"
OUTPUT_CSV = "la_neighborhoods_cafes_bars_pubs.csv"

# Endpoints d'Overpass
OVERPASS_ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.openstreetmap.fr/api/interpreter",
]


def overpass_area_id_from_relation_id(rel_id: int) -> int:
    """
    Converteix l'id de relació OSM (rel_id) a l'id d'àrea d'Overpass.
    Fórmula estàndard: 3600000000 + rel_id
    """
    return 3600000000 + rel_id


def run_overpass_query(query: str,
                       max_retries_per_endpoint: int = 3,
                       base_wait_seconds: int = 5) -> overpy.Result:
    """
    Executa una consulta Overpass provant diversos endpoints.
    - Si l'error conté "Too many requests", espera i reintenta el mateix endpoint
      amb backoff exponencial (5s, 10s, 20s...).
    - Si és un altre error, passa al següent endpoint.
    Compatible amb versions antigues d'overpy.
    """
    last_exc = None

    for url in OVERPASS_ENDPOINTS:
        retries = 0
        while retries < max_retries_per_endpoint:
            try:
                print(f"[Overpass] Endpoint {url}, intent {retries+1}/{max_retries_per_endpoint}")
                api = overpy.Overpass()
                api.url = url
                api.timeout = 120

                res = api.query(query)
                print(f"[Overpass] OK a {url}")
                return res

            except Exception as e:
                msg = str(e)
                last_exc = e

                if "Too many requests" in msg or "429" in msg:
                    wait = base_wait_seconds * (2 ** retries)
                    print(f"[Overpass] Too many requests a {url}. Esperant {wait} s abans de reintentar...")
                    time.sleep(wait)
                    retries += 1
                    continue
                else:
                    print(f"[Overpass] Error a {url} (no es reintenta aquest endpoint): {e}")
                    break  # sortim del while i anem al següent endpoint

        # si arribem aquí, aquest endpoint ha fallat tots els intents -> passem al següent
        print(f"[Overpass] Endpoint {url} descartat després de {max_retries_per_endpoint} intents.")

    # si cap endpoint ha funcionat
    raise last_exc if last_exc else RuntimeError("No s'ha pogut contactar amb cap endpoint Overpass")


def count_cafes_bars_pubs_in_neighborhood(rel_id: int):
    """
    Retorna (num_cafes, num_bars, num_pubs) dins de l'àrea corresponent a la relació rel_id.
    """
    area_id = overpass_area_id_from_relation_id(rel_id)

    query = f"""
    [out:json][timeout:60];
    area({area_id})->.searchArea;
    nwr["amenity"~"^(cafe|bar|pub)$"](area.searchArea);
    out center;
    """

    result = run_overpass_query(query)

    cafes = 0
    bars = 0
    pubs = 0

    for coll in (result.nodes, result.ways, result.relations):
        for e in coll:
            amenity = e.tags.get("amenity")
            if amenity == "cafe":
                cafes += 1
            elif amenity == "bar":
                bars += 1
            elif amenity == "pub":
                pubs += 1

    return cafes, bars, pubs


def main():
    # Carreguem barris de l'input
    neighborhoods = []
    with open(INPUT_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            neighborhoods.append({
                "rel_id": int(row["id"]),
                "name": row.get("display_name") or row.get("name"),
                "admin_level": row.get("admin_level"),
                "lat": float(row["lat"]),
                "lon": float(row["lon"]),
            })

    print(f"[Info] Barris carregats des de {INPUT_CSV}: {len(neighborhoods)}")

    # Si ja existeix l'output, l'esborrem per començar de zero (format nou)
    if os.path.exists(OUTPUT_CSV):
        print(f"[Info] Esborrant fitxer existent {OUTPUT_CSV} (format nou)...")
        os.remove(OUTPUT_CSV)

    # Preparem fitxer de sortida
    fieldnames = [
        "rel_id",
        "name",
        "admin_level",
        "lat",
        "lon",
        "num_cafes",
        "num_bars",
        "num_pubs",
        "num_cafes_bars_pubs_total",
    ]
    out_file = open(OUTPUT_CSV, "w", newline="", encoding="utf-8")
    writer = csv.DictWriter(out_file, fieldnames=fieldnames)
    writer.writeheader()

    try:
        total = len(neighborhoods)
        for i, nb in enumerate(neighborhoods, start=1):
            rel_id = nb["rel_id"]
            print(f"[{i}/{total}] Processant barri {rel_id} ({nb['name']})...")

            cafes, bars, pubs = count_cafes_bars_pubs_in_neighborhood(rel_id)
            print(f"   Cafès: {cafes}, Bars: {bars}, Pubs: {pubs}")

            row = {
                "rel_id": rel_id,
                "name": nb["name"],
                "admin_level": nb["admin_level"],
                "lat": nb["lat"],
                "lon": nb["lon"],
                "num_cafes": cafes,
                "num_bars": bars,
                "num_pubs": pubs,
                "num_cafes_bars_pubs_total": cafes + bars + pubs,
            }
            writer.writerow(row)
            out_file.flush()

            # petita pausa entre barris per ser amables amb l'API
            time.sleep(1)

    finally:
        out_file.close()
        print(f"[Info] Resultats desats a {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
