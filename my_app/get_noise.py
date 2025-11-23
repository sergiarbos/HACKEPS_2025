import csv
import glob
import os

import numpy as np
import rasterio
from pyproj import Transformer

# --- CONFIGURACIÓ ---

# CSV de barris del pas 1
INPUT_NEIGH_CSV = "la_neighborhoods_admin_9_10.csv"

# Carpeta on tens descomprimit el ZIP de soroll
NOISE_DIR = "CONUS_rail_road_and_aviation_noise_2020.Overviews"

# Fitxer de sortida
OUTPUT_CSV = "la_neighborhoods_noise_centroid_2020.csv"


def load_neighborhoods(csv_path):
    neighborhoods = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            neighborhoods.append({
                "rel_id": int(row["id"]),
                "name": row.get("display_name") or row.get("name"),
                "admin_level": row.get("admin_level"),
                "lat": float(row["lat"]),
                "lon": float(row["lon"]),
            })
    return neighborhoods


def load_noise_rasters(noise_dir):
    """
    Carrega tots els .tif dins de noise_dir com a rasterio.DatasetReader.
    Retorna una llista de (path, dataset).
    """
    tif_paths = sorted(glob.glob(os.path.join(noise_dir, "*.tif")))
    if not tif_paths:
        raise RuntimeError(f"No s'han trobat .tif dins de {noise_dir}")

    rasters = []
    for path in tif_paths:
        ds = rasterio.open(path)
        rasters.append((path, ds))
        print(f"[Info] Carregat raster: {os.path.basename(path)}  CRS={ds.crs}  bounds={ds.bounds}")
    return rasters


def main():
    # 1) Llegeix barris
    neighborhoods = load_neighborhoods(INPUT_NEIGH_CSV)
    print(f"[Info] Barris carregats: {len(neighborhoods)}")

    # 2) Carrega rasters de soroll
    rasters = load_noise_rasters(NOISE_DIR)
    raster_crs = rasters[0][1].crs

    # 3) Transformador WGS84 -> CRS del raster
    transformer = Transformer.from_crs("EPSG:4326", raster_crs, always_xy=True)

    # 4) CSV de sortida
    fieldnames = [
        "rel_id",
        "name",
        "admin_level",
        "lat",
        "lon",
        "noise_db_centroid",
    ]
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f_out:
        writer = csv.DictWriter(f_out, fieldnames=fieldnames)
        writer.writeheader()

        # 5) Processament barri per barri
        for i, nb in enumerate(neighborhoods, start=1):
            lon = nb["lon"]
            lat = nb["lat"]

            # Transformar lon/lat -> x, y del raster
            x, y = transformer.transform(lon, lat)

            noise_value = None

            # Buscar quin raster conté el punt
            for path, ds in rasters:
                bounds = ds.bounds
                if not (bounds.left <= x <= bounds.right and bounds.bottom <= y <= bounds.top):
                    continue

                try:
                    row, col = ds.index(x, y)
                    # Llegir un sol píxel
                    val = ds.read(1, window=((row, row+1), (col, col+1)))[0, 0]
                except Exception as e:
                    print(f"[Warn] Error llegint {path} per barri {nb['name']}: {e}")
                    continue

                # Comprovar NoData
                if ds.nodata is not None and val == ds.nodata:
                    continue
                if np.isnan(val):
                    continue

                noise_value = float(val)
                break

            print(f"[{i}/{len(neighborhoods)}] {nb['name']}: noise_db_centroid={noise_value}")

            writer.writerow({
                "rel_id": nb["rel_id"],
                "name": nb["name"],
                "admin_level": nb["admin_level"],
                "lat": nb["lat"],
                "lon": nb["lon"],
                "noise_db_centroid": "" if noise_value is None else round(noise_value, 2),
            })

    # 6) Tancar datasets
    for _, ds in rasters:
        ds.close()

    print(f"[Info] Resultats desats a {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
