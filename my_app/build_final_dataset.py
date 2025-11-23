#!/usr/bin/env python3
import pandas as pd
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

def main():
    print("[Info] Carregant fitxers...")

    # 1) Barris base (id + nom + centroid)
    base = pd.read_csv(BASE_DIR / "la_neighborhoods_admin_9_10.csv")
    base = base.rename(columns={"id": "rel_id"})
    # Ens quedem amb el que necessitem
    base = base[["rel_id", "display_name", "lat", "lon"]]

    # 2) Cafès, bars, pubs (nightlife)
    cafes = pd.read_csv(BASE_DIR / "la_neighborhoods_cafes_bars_pubs.csv")
    cafes = cafes.rename(columns={"rel_id": "rel_id"})
    cafes_sel = cafes[
        ["rel_id", "num_cafes", "num_bars", "num_pubs", "num_cafes_bars_pubs_total"]
    ].copy()
    cafes_sel = cafes_sel.rename(columns={
        "num_cafes_bars_pubs_total": "nightlife_places"
    })

    # 3) Soroll (dB al centroid)
    noise = pd.read_csv(BASE_DIR / "la_neighborhoods_noise_centroid_2020.csv")
    noise = noise.rename(columns={"rel_id": "rel_id"})
    noise_sel = noise[["rel_id", "noise_db_centroid"]]

    # 4) Crim: l’agafem de neighborhoods_crime_services.csv
    crime = pd.read_csv(BASE_DIR / "neighborhoods_crime_services.csv")
    # en aquest fitxer la clau es diu "id"
    crime_sel = crime[["id", "crime_count"]].rename(columns={"id": "rel_id"})

    # 5) Demografia + habitatge: neighborhoods_full_stats.csv
    demo = pd.read_csv(BASE_DIR / "neighborhoods_full_stats.csv")
    # Aquest fitxer ja té les columnes que t’ha ensenyat el warning
    demo_sel = demo[
        [
            "id",
            "median_income",
            "median_age",
            "population",
            "median_rent",
            "median_home_value",
            "owner_share",
            "renter_share",
            "single_family_pct",
            "small_multi_pct",
            "large_multi_pct",
        ]
    ].rename(columns={"id": "rel_id"})

    # 6) Lifestyle (restaurants, cultura, gimnasos, botigues)
    life = pd.read_csv(BASE_DIR / "neighborhoods_lifestyle_services.csv")
    life_sel = life[
        [
            "id",
            "restaurants_count",
            "culture_count",
            "gyms_count",
            "shops_count",
        ]
    ].rename(columns={"id": "rel_id"})

    # 7) Mobilitat
    mob = pd.read_csv(BASE_DIR / "neighborhoods_mobility_transport.csv")
    mob_sel = mob[
        [
            "id",
            "pt_stops_count",
            "bike_infra_count",
            "walkability_features_count",
            "major_roads_count",
        ]
    ].rename(columns={"id": "rel_id"})

    # 8) Parcs
    parks = pd.read_csv(BASE_DIR / "neighborhoods_parks_services.csv")
    parks_sel = parks[["id", "parks_count"]].rename(columns={"id": "rel_id"})

    # ---------- FUSIÓ DE TOT ----------

    df = base.copy()

    df = df.merge(demo_sel, on="rel_id", how="left")
    df = df.merge(crime_sel, on="rel_id", how="left")
    df = df.merge(cafes_sel, on="rel_id", how="left")
    df = df.merge(noise_sel, on="rel_id", how="left")
    df = df.merge(life_sel, on="rel_id", how="left")
    df = df.merge(mob_sel, on="rel_id", how="left")
    df = df.merge(parks_sel, on="rel_id", how="left")

    # 9) Feature derivada: crim per 1000 habitants (si tenim població i crim)
    if "crime_count" in df.columns and "population" in df.columns:
        df["crime_rate_per_1000"] = (
            df["crime_count"] / df["population"].replace({0: pd.NA})
        ) * 1000

    # 10) Ordenem columnes per llegibilitat
    cols_order = [
        "rel_id",
        "display_name",
        "lat",
        "lon",
        # demografia / habitatge
        "median_income",
        "median_age",
        "population",
        "median_rent",
        "median_home_value",
        "owner_share",
        "renter_share",
        "single_family_pct",
        "small_multi_pct",
        "large_multi_pct",
        # crim
        "crime_count",
        "crime_rate_per_1000",
        # soroll
        "noise_db_centroid",
        # nightlife / serveis
        "nightlife_places",
        "num_cafes",
        "num_bars",
        "num_pubs",
        "restaurants_count",
        "culture_count",
        "gyms_count",
        "shops_count",
        # mobilitat
        "pt_stops_count",
        "bike_infra_count",
        "walkability_features_count",
        "major_roads_count",
        # parcs
        "parks_count",
    ]

    # Ens quedem només amb les columnes que existeixen realment (per si algun fitxer falta)
    cols_order = [c for c in cols_order if c in df.columns]
    df = df[cols_order]

    out_path = BASE_DIR / "neighborhoods_model_features.csv"
    df.to_csv(out_path, index=False)
    print(f"[Info] Dataset final desat a {out_path}")

if __name__ == "__main__":
    main()
