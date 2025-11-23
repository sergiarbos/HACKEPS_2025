#!/usr/bin/env python3
import pandas as pd
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_PATH = BASE_DIR / "neighborhoods_model_features.csv"


# ==========================
#  UTILITATS BÀSIQUES
# ==========================

def min_max(series: pd.Series) -> pd.Series:
    """Normalització min-max a [0,1]. Si tots els valors són iguals → 0.5."""
    s = series.astype(float)
    mn, mx = s.min(), s.max()
    if pd.isna(mn) or pd.isna(mx) or mn == mx:
        return pd.Series(0.5, index=s.index)
    return (s - mn) / (mx - mn)


def pref_low_mid_high(norm_series: pd.Series, level: str) -> pd.Series:
    """
    Donada una sèrie normalitzada (0=baix,1=alt) i preferència 'baixa'|'mitjana'|'alta',
    torna un score 0-1.
    """
    if level is None:
        level = ""
    level = level.strip().lower()

    if level in ("baixa", "baix", "low"):
        # preferim valors baixos
        return 1 - norm_series

    if level in ("alta", "alt", "high", "excel·lent", "excelent"):
        # preferim valors alts
        return norm_series

    # 'mitjana', 'mitjà' o qualsevol altre → preferim valors propers a 0.5
    return 1 - (norm_series - 0.5).abs() * 2  # 0.5 -> 1, 0/1 -> 0


# ==========================
#  CARREGA I FEATURE ENGINEERING
# ==========================

def load_and_prepare_data() -> pd.DataFrame:
    """
    Carrega neighborhoods_model_features.csv i construeix totes les columnes normalitzades
    necessàries per al model.
    """
    df = pd.read_csv(DATA_PATH)

    # --- Demografia ---
    df["income_norm"] = min_max(df["median_income"])
    df["age_norm"] = min_max(df["median_age"])
    # No tenim àrea → usem població com a proxy de densitat
    df["density_norm"] = min_max(df["population"])

    # --- Crim / seguretat ---
    if "crime_rate_per_1000" in df.columns:
        cr = df["crime_rate_per_1000"].copy()
        cr = cr.replace(0, pd.NA)
        cr = cr.fillna(cr.median())
        df["crime_rate_clean"] = cr
        df["crime_norm"] = min_max(df["crime_rate_clean"])
        # com menys crim, millor
        df["safety_norm"] = 1 - df["crime_norm"]
    else:
        df["safety_norm"] = 0.5

    # --- Soroll / tranquil·litat ---
    noise = df["noise_db_centroid"].copy()
    # Converteix a float
    noise = pd.to_numeric(noise, errors="coerce")
    # Considerem 0 com a "sense dada" i el posem a la mediana
    noise = noise.mask(noise == 0)
    # Inferim tipus
    noise = noise.infer_objects(copy=False)
    median_noise = float(noise.median())
    noise = noise.astype("float64").fillna(median_noise).astype("float64")

    df["noise_norm"] = min_max(noise)
    df["quiet_norm"] = 1 - df["noise_norm"]

    # --- Nightlife / gastronomia / cultura / conveniència ---
    df["nightlife_norm"] = min_max(df["nightlife_places"])
    df["restaurants_norm"] = min_max(df["restaurants_count"])
    df["culture_norm"] = min_max(df["culture_count"])
    df["gyms_norm"] = min_max(df["gyms_count"])
    df["shops_norm"] = min_max(df["shops_count"])

    df["convenience_norm"] = min_max(
        df["restaurants_count"].fillna(0)
        + df["shops_count"].fillna(0)
        + df["gyms_count"].fillna(0)
    )

    # --- Verd / parcs ---
    # Parcs per càpita aproximat
    parks_per_capita = df["parks_count"].fillna(0) / df["population"].replace({0: pd.NA})
    parks_per_capita = parks_per_capita.fillna(parks_per_capita.median())
    df["green_norm"] = min_max(parks_per_capita)

    # --- Mobilitat ---
    df["pt_norm"] = min_max(df["pt_stops_count"])
    df["bike_norm"] = min_max(df["bike_infra_count"])
    df["walk_norm"] = min_max(df["walkability_features_count"])
    df["roads_norm"] = min_max(df["major_roads_count"])

    return df


# ==========================
#  MAPPING FORMULARI → PREFERÈNCIES
# ==========================

def score_from_answers(df: pd.DataFrame, answers: dict) -> pd.DataFrame:
    """
    Implementa el mapping de les preguntes del formulari a un score per barri.

    Claus esperades a `answers` (INTERNES, no les del <form>):

      income: 'baixa'|'mitjana'|'alta'
      density: 'baixa'|'mitjana'|'alta'
      age: 'jove'|'mitjana'|'envellida'

      gastronomy: 'escassa'|'moderada'|'molt alta'/'molt_alta'
      green: 'poques'/'pocs'|'algunes'/'alguns'|'moltes'/'molts'
      culture: 'baixa'|'mitjana'|'alta'

      pt_access: 'baix'|'bo'|'excel·lent'
      bus_availability: 'limitada'|'correcta'|'molt abundant'/'molt_abundant'
      bike_lanes: 'inexistent'|'basic'|'bàsic'|'extens'
      walkability: 'baixa'|'mitjana'|'alta'

      safety: 'estandard'|'alta'|'molt alta'/'molt_alta'
      main_priority: 'comunitat'|'privacitat i luxe'/'privacitat_luxe'
                     |'accessibilitat'|'cultura i gastronomia'/'cultura'
    """

    df = df.copy()

    # ---------- 1) SCORES PER DIMENSIÓ SEGONS DIRECCIÓ DE PREFERÈNCIA ----------

    # 1. Renda mitjana
    income_ans = (answers.get("income") or "").strip().lower()
    if income_ans == "baixa":
        df["score_income"] = 1 - df["income_norm"]
    elif income_ans == "alta":
        df["score_income"] = df["income_norm"]
    else:  # 'mitjana' o qualsevol altre
        df["score_income"] = 1 - (df["income_norm"] - 0.5).abs() * 2

    # 2. Densitat de població
    density_ans = (answers.get("density") or "").strip().lower()
    df["score_density"] = pref_low_mid_high(df["density_norm"], density_ans)

    # 3. Edat mitjana
    age_ans = (answers.get("age") or "").strip().lower()
    if age_ans == "jove":
        df["score_age"] = 1 - df["age_norm"]
    elif age_ans == "envellida":
        df["score_age"] = df["age_norm"]
    else:  # 'mitjana'
        df["score_age"] = 1 - (df["age_norm"] - 0.5).abs() * 2

    # 4. Oferta gastronòmica
    gastr_ans = (answers.get("gastronomy") or "").strip().lower()
    # acceptem 'molt alta' i 'molt_alta'
    if gastr_ans.startswith("escassa"):
        df["score_gastronomy"] = 1 - df["restaurants_norm"]
    elif "molt" in gastr_ans:
        df["score_gastronomy"] = df["restaurants_norm"]
    else:  # 'moderada'
        df["score_gastronomy"] = 1 - (df["restaurants_norm"] - 0.5).abs() * 2

    # 5. Zones verdes
    green_ans = (answers.get("green") or "").strip().lower()
    # permetem 'pocs/poques', 'alguns/algunes', 'molts/moltes'
    if green_ans.startswith(("pocs", "poques")):
        df["score_green"] = 1 - df["green_norm"]
    elif green_ans.startswith(("molts", "moltes")):
        df["score_green"] = df["green_norm"]
    else:  # 'alguns', 'algunes' o altre
        df["score_green"] = 1 - (df["green_norm"] - 0.5).abs() * 2

    # 6. Oferta cultural
    culture_ans = (answers.get("culture") or "").strip().lower()
    df["score_culture"] = pref_low_mid_high(df["culture_norm"], culture_ans)

    # 7. Accés transport públic
    pt_ans = (answers.get("pt_access") or "").strip().lower()
    df["score_pt"] = pref_low_mid_high(df["pt_norm"], pt_ans)

    # 8. Disponibilitat bus (des d'HTML: 'limitada', 'correcta', 'molt_abundant')
    bus_ans = (answers.get("bus_availability") or "").strip().lower()
    if bus_ans.startswith("limitada"):
        df["score_bus"] = 1 - df["pt_norm"]
    elif "molt" in bus_ans:
        df["score_bus"] = df["pt_norm"]
    else:  # 'correcta'
        df["score_bus"] = 1 - (df["pt_norm"] - 0.5).abs() * 2

    # 9. Carrils bici
    bike_ans = (answers.get("bike_lanes") or "").strip().lower()
    if bike_ans.startswith("inexistent"):
        df["score_bike"] = 1 - df["bike_norm"]
    elif bike_ans.startswith("extens"):
        df["score_bike"] = df["bike_norm"]
    else:  # 'basic', 'bàsic'
        df["score_bike"] = 1 - (df["bike_norm"] - 0.5).abs() * 2

    # 10. Caminabilitat
    walk_ans = (answers.get("walkability") or "").strip().lower()
    df["score_walk"] = pref_low_mid_high(df["walk_norm"], walk_ans)

    # 11. Nivell de seguretat requerit
    safety_ans = (answers.get("safety") or "").strip().lower()
    # Tothom vol seguretat, però després ajustarem el PES
    df["score_safety"] = df["safety_norm"]

    # 11bis. Tranquil·litat (no l'han preguntat explícitament, però la vincularem a soroll)
    df["score_quiet"] = df["quiet_norm"]

    # ---------- 2) PESOS BASE PER CADA DIMENSIÓ ----------

    weights = {
        "income": 0.7,       # no massa important per defecte
        "density": 0.5,
        "age": 0.4,
        "gastronomy": 0.7,
        "green": 0.8,
        "culture": 0.7,
        "pt": 0.7,
        "bus": 0.6,
        "bike": 0.5,
        "walk": 0.8,
        "safety": 0.9,
        "quiet": 0.7,
    }

    # Ajustem importància segons resposta de seguretat
    if safety_ans in ("molt alta", "molt_alta"):
        weights["safety"] *= 1.5
    elif safety_ans == "alta":
        weights["safety"] *= 1.2

    # ---------- 3) PRIORITAT PRINCIPAL (Q12) ----------

    main_prio = (answers.get("main_priority") or "").strip().lower()

    if main_prio.startswith("comunitat"):
        # Comunitat: caminabilitat, verd, cultura, seguretat
        weights["walk"] *= 1.4
        weights["green"] *= 1.3
        weights["culture"] *= 1.2
        weights["safety"] *= 1.1
        weights["income"] *= 0.7

    elif main_prio.startswith(("privacitat", "privacitat_luxe")):
        # Privacitat i luxe: renda alta, baixa densitat, tranquil·litat, seguretat
        weights["income"] *= 1.4
        weights["density"] *= 1.3  # però ja preferim densitat baixa via score
        weights["quiet"] *= 1.4
        weights["safety"] *= 1.3

    elif main_prio.startswith("accessibilitat"):
        # Accessibilitat: PT, bus, bici, caminabilitat
        weights["pt"] *= 1.5
        weights["bus"] *= 1.3
        weights["bike"] *= 1.3
        weights["walk"] *= 1.2
        weights["quiet"] *= 0.7

    elif main_prio.startswith("cultura"):
        # Cultura i gastronomia: restaurants, nightlife, cultura
        weights["gastronomy"] *= 1.4
        weights["culture"] *= 1.5
        # tolerem més soroll i densitat
        weights["quiet"] *= 0.6
        weights["density"] *= 0.8

    # ---------- 4) COMBINAR EN UN SCORE FINAL ----------

    total_w = sum(weights.values())
    norm_w = {k: v / total_w for k, v in weights.items()}

    df["score_final"] = (
        df["score_income"] * norm_w["income"]
        + df["score_density"] * norm_w["density"]
        + df["score_age"] * norm_w["age"]
        + df["score_gastronomy"] * norm_w["gastronomy"]
        + df["score_green"] * norm_w["green"]
        + df["score_culture"] * norm_w["culture"]
        + df["score_pt"] * norm_w["pt"]
        + df["score_bus"] * norm_w["bus"]
        + df["score_bike"] * norm_w["bike"]
        + df["score_walk"] * norm_w["walk"]
        + df["score_safety"] * norm_w["safety"]
        + df["score_quiet"] * norm_w["quiet"]
    )

    return df


# ==========================
#  API PRINCIPAL DES DEL BACKEND
# ==========================

def recommend_neighborhoods_from_answers(answers: dict, top_n: int = 5) -> pd.DataFrame:
    """
    Funció principal: rep respostes (claus internes), calcula score_final i retorna top N.
    """
    df = load_and_prepare_data()
    df = score_from_answers(df, answers)

    cols_to_show = [
        "rel_id",
        "display_name",
        "lat",
        "lon",
        "score_final",
        "median_income",
        "median_age",
        "population",
        "crime_rate_per_1000",
        "noise_db_centroid",
        "nightlife_places",
        "restaurants_count",
        "culture_count",
        "parks_count",
        "pt_stops_count",
        "bike_infra_count",
        "walkability_features_count",
    ]
    cols_to_show = [c for c in cols_to_show if c in df.columns]

    return df.sort_values("score_final", ascending=False)[cols_to_show].head(top_n)


# ==========================
#  HELPER: MAPEIG FRONT → INTERN
# ==========================

def map_front_answers_to_internal(front_answers: dict) -> dict:
    """
    Converteix les claus del formulari HTML (name=...) a claus internes del model.
    Formulari HTML té:
      renda_mediana, densitat_poblacio, edat_mediana,
      oferta_gastronomica, zones_verdes, oferta_cultural,
      transport_public, metro_bus, carrils_bici, caminabilitat,
      seguretat_requerida, prioritat
    """
    return {
        "income": front_answers.get("renda_mediana"),
        "density": front_answers.get("densitat_poblacio"),
        "age": front_answers.get("edat_mediana"),

        "gastronomy": front_answers.get("oferta_gastronomica"),
        "green": front_answers.get("zones_verdes"),
        "culture": front_answers.get("oferta_cultural"),

        "pt_access": front_answers.get("transport_public"),
        "bus_availability": front_answers.get("metro_bus"),
        "bike_lanes": front_answers.get("carrils_bici"),
        "walkability": front_answers.get("caminabilitat"),

        "safety": front_answers.get("seguretat_requerida"),
        "main_priority": front_answers.get("prioritat"),
    }


# ==========================
#  TEST LOCAL / DEMO
# ==========================

if __name__ == "__main__":
    # Exemple de respostes tal com sortirien del FRONT (names del <select>)
    example_front_answers = {
        # BLOC 1
        "renda_mediana": "mitjana",
        "densitat_poblacio": "mitjana",
        "edat_mediana": "jove",
        # BLOC 2
        "oferta_gastronomica": "molt_alta",
        "zones_verdes": "alguns",
        "oferta_cultural": "alta",
        # BLOC 3
        "transport_public": "bo",
        "metro_bus": "molt_abundant",
        "carrils_bici": "extens",
        "caminabilitat": "alta",
        # BLOC 4
        "seguretat_requerida": "alta",
        "prioritat": "cultura",
    }

    internal_answers = map_front_answers_to_internal(example_front_answers)
    recs = recommend_neighborhoods_from_answers(internal_answers, top_n=5)

    print("=== Recomanació segons respostes de l'usuari ===")
    print(recs.to_string(index=False))

