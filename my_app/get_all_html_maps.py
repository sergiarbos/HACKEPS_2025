import overpy
import folium
import csv
import time

from shapely.geometry import LineString, Polygon, MultiPolygon
from shapely.ops import unary_union, polygonize

REL_ID = 15048390
REL_DISPLAY_NAME = "North Hills East"

def run_query(query: str) -> overpy.Result:
    api = overpy.Overpass()
    api.timeout = 120

    max_retries = 5

    for attempt in range(1, max_retries + 1):
        try:
            return api.query(query)
        except overpy.exception.OverpassGatewayTimeout as e:
            print(f"[INTENT {attempt}] OverpassGatewayTimeout (server load too high): {e}")
            # Esperem una mica abans de reintentar (augmentem la pausa cada cop)
            sleep_secs = 30 * attempt
            print(f"Esperant {sleep_secs} segons abans de reintentar...")
            time.sleep(sleep_secs)
        except overpy.exception.OverpassTooManyRequests as e:
            print(f"[INTENT {attempt}] Massa peticions: {e}")
            sleep_secs = 60 * attempt
            print(f"Esperant {sleep_secs} segons abans de reintentar...")
            time.sleep(sleep_secs)
    # Si no ha funcionat després de tots els intents, tornem a llençar l’error
    raise RuntimeError("No s'ha pogut completar la consulta a Overpass després de diversos intents")


def get_relation_polygons(rel_id: int):
    """
    Retorna una llista de polígons (shapely.Polygon) per una relació OSM.
    Reconstrueix la geometria a partir de les ways amb Shapely.
    """
    query = f"""
    [out:json][timeout:60];
    rel({rel_id});
    out body;
    >;
    out skel qt;
    """

    result = run_query(query)

    if not result.relations:
        raise ValueError(f"No s'ha trobat la relació {rel_id}")

    rel = result.relations[0]

    lines = []

    for mem in rel.members:
        # Ens quedem amb ways que formen la frontera
        if isinstance(mem, overpy.RelationWay):
            # Si vols ser més fi, podries filtrar per mem.role == "outer"
            way = mem.resolve()
            coords = [(float(n.lon), float(n.lat)) for n in way.nodes]
            if len(coords) >= 2:
                lines.append(LineString(coords))

    if not lines:
        raise ValueError(f"La relació {rel_id} no té ways amb nodes associats")

    # Unim totes les línies
    merged = unary_union(lines)

    polys = []

    if isinstance(merged, Polygon):
        polys = [merged]
    elif isinstance(merged, MultiPolygon):
        polys = list(merged.geoms)
    else:
        # Si el resultat són línies separades, intentem "polygonitzar-les"
        polys = list(polygonize(merged))

    if not polys:
        print(f"No s'han pogut construir polígons per la relació {rel_id}")
        #raise ValueError(f"No s'han pogut construir polígons per la relació {rel_id}")
        return None

    return polys












if __name__ == "__main__":
    print("PRE")

    barris = []
    
    with open("la_neighborhoods_admin_9_10.csv", newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            barris.append({"id":row["id"], "name":row["display_name"]})

    print(len(barris))
    print(barris)
    print("\n")
    
    for item in barris:
        print(item["name"])
        shapely_polys = get_relation_polygons(int(item["id"]))
        if shapely_polys == None:
            continue

        # Agafem el primer polígon per centrar el mapa
        main_poly = shapely_polys[0]
        center_lon, center_lat = main_poly.centroid.x, main_poly.centroid.y

        m = folium.Map(location=[center_lat, center_lon], zoom_start=13)

        # Dibuixem tots els polígons (per si hi ha multipolígon)
        for poly in shapely_polys:
            # poly.exterior.coords → seqüència (lon, lat)
            latlon_ring = [(lat, lon) for (lon, lat) in poly.exterior.coords]
            folium.Polygon(
                locations=latlon_ring,
                weight=2,
                fill=True,
                fill_opacity=0.2,
            ).add_to(m)

            # Si té forats (holes), també els podríem dibuixar:
            for interior in poly.interiors:
                latlon_ring_hole = [(lat, lon) for (lon, lat) in interior.coords]
                folium.Polygon(
                    locations=latlon_ring_hole,
                    weight=1,
                    fill=False,
                ).add_to(m)

        folium.Marker(
            location=[center_lat, center_lon],
            popup=f"Relació {item['id']}",
        ).add_to(m)

        name_array = item["name"].split(" ")
        name = ""
        name_length = len(name_array)
        idx = 0
        for part in name_array:
            name += part
            if idx < (name_length - 1):
                name += "_"
            idx += 1

        print("\nNAME: "+name+"\n")

        m.save("html_barris/"+name+".html")
        print("Mapa desat a "+name+".html")
    print("POST")