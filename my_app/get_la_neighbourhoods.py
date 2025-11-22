import overpy
import csv


OVERPASS_ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.openstreetmap.fr/api/interpreter",
]


def run_overpass_query(query: str) -> overpy.Result:
    """
    Executa una consulta Overpass provant diversos endpoints.
    Funciona en versions antigues d'overpy perquè no fem servir paràmetres al constructor.
    """
    last_exc = None

    for url in OVERPASS_ENDPOINTS:
        try:
            print(f"\n[Overpass] Provant endpoint: {url}")
            api = overpy.Overpass()        # <<< IMPORTANT: sense paràmetres
            api.url = url                  # <<< assignem després
            api.timeout = 120              # <<< assignem després

            res = api.query(query)
            print(f"[Overpass] Endpoint OK: {url}")
            return res

        except Exception as e:
            print(f"[Overpass] Error a {url}: {e}")
            last_exc = e

    raise last_exc if last_exc else RuntimeError("No s'ha pogut contactar amb cap endpoint Overpass")


def get_la_neighborhoods():

    query_divisions = """
    [out:json][timeout:60];
    area["name"="Los Angeles"]["boundary"="administrative"]["admin_level"=8]->.la;

    rel(area.la)
      ["boundary"="administrative"]
      ["admin_level"~"^(9|10)$"];

    out center;
    """

    print("Executant consulta d'Overpass per obtenir barris de Los Angeles...")
    res = run_overpass_query(query_divisions)
    print(f"Relacions retornades: {len(res.relations)}")

    neighborhoods = []

    for r in res.relations:
        raw_name = r.tags.get("name", "")
        admin_level = r.tags.get("admin_level", "")

        display_name = raw_name
        for suffix in [
            " Neighborhood Council District",
            " Neighborhood Council",
            " Neighborhood",
            " neighborhood council district",
            " neighborhood council",
            " neighborhood",
        ]:
            if display_name.endswith(suffix):
                display_name = display_name[:-len(suffix)]

        neighborhoods.append({
            "id": r.id,
            "name": raw_name,
            "display_name": display_name.strip(),
            "admin_level": admin_level,
            "lat": float(r.center_lat),
            "lon": float(r.center_lon),
        })

    return neighborhoods


def save_neighborhoods_to_csv(neighborhoods, path: str):

    fieldnames = ["id", "name", "display_name", "admin_level", "lat", "lon"]

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(neighborhoods)

    print(f"S'han desat {len(neighborhoods)} barris al fitxer: {path}")


def main():
    neighborhoods = get_la_neighborhoods()

    print("\nBarris trobats:", len(neighborhoods))
    print("Primeres 10 entrades:\n")
    for n in neighborhoods[:10]:
        print(
            f"  id={n['id']}, level={n['admin_level']}, "
            f"name='{n['name']}', display_name='{n['display_name']}', "
            f"center=({n['lat']}, {n['lon']})"
        )

    save_neighborhoods_to_csv(neighborhoods, "la_neighborhoods_admin_9_10.csv")


if __name__ == "__main__":
    main()
