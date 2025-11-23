import requests

CRIME_URL = "https://data.lacity.org/resource/2nrs-mtv8.json"

def test_crime_points():
    """
    Ejemplo 1:
    Pedimos solo lat, lon, date_occ, area_name
    para algunos delitos recientes.
    """
    params = {
        "$select": "lat, lon, date_occ, area_name",
        "$where": "date_occ >= '2024-01-01'",
        "$limit": 10,  # solo 10 filas para probar
    }

    resp = requests.get(CRIME_URL, params=params)
    print("Status code:", resp.status_code)
    resp.raise_for_status()

    data = resp.json()
    print("Registros recibidos:", len(data))
    print("Primeros resultados:")
    for row in data:
        print(row)


def test_crime_index_by_area():
    """
    Ejemplo 2:
    Pedimos el número de delitos por area_name
    (índice bruto de criminalidad por área).
    """
    params = {
        "$select": "area_name, count(*) as crime_count",
        "$where": "date_occ >= '2024-01-01'",
        "$group": "area_name",
        "$order": "crime_count DESC",
        "$limit": 40,  # top 10 áreas con más delitos
    }

    resp = requests.get(CRIME_URL, params=params)
    print("Status code:", resp.status_code)
    resp.raise_for_status()

    data = resp.json()
    print("Áreas recibidas:", len(data))
    print("Top áreas por número de delitos:")
    for row in data:
        # crime_count viene como string, lo convertimos a int solo por comodidad
        row["crime_count"] = int(row["crime_count"])
        print(f"{row['area_name']}: {row['crime_count']}")


if __name__ == "__main__":
    print("=== Test puntos individuales ===")
    test_crime_points()
    print("\n=== Test índice por área ===")
    test_crime_index_by_area()
