#!/usr/bin/env python3
import pandas as pd
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_PATH = BASE_DIR / "neighborhoods_model_features.csv"


def min_max(series: pd.Series) -> pd.Series:
    """Normalització min-max a [0,1]. Si tots els valors són iguals → 0.5."""
    s = series.astype(float)
    mn, mx = s.min(), s.max()
    if pd.isna(mn) or pd.isna(mx) or mn == mx:
        return pd.Series(0.5, index=s.index)
    return (s - mn) / (mx - mn)


def load_and_prepare_data() -> pd.DataFrame:
    df = pd.read_csv(DATA_PATH)

    # --- Demografia ---
    df["income_norm"] = min_max(df["median_income"])
    df["age_norm"] = min_max(df["median_age"])
    # No tenim àrea → usem població com a proxy de densitat
    df["density_norm"] = min_max(df["population"])

    # --- Crim / seguretat ---
    # Si hi ha algun NA o 0 estrany, els substituïm per la mediana
    if "crime_rate_per_1000" in df.columns:
        cr = df["crime_rate_per_1000"].copy()
        cr = cr.replace(0, pd.NA)
        cr = cr.fillna(cr.median())
        df["crime_rate_clean"] = cr
        df["crime_norm"] = min_max(df["crime_rate_clean"])
        df["safety_norm"] = 1 - df["crime_norm"]
    else:
        df["safety_norm"] = 0.5

    # --- Soroll / tranquil·litat ---
    noise = df["noise_db_centroid"].copy()

    # Converteix qualsevol cosa a float si és possible
    noise = pd.to_numeric(noise, errors="coerce")

    # Reemplaçar zeros per NA si significa manca de dades
    noise = noise.mask(noise == 0)

    # Inferir tipus per evitar warnings futurs
    noise = noise.infer_objects(copy=False)

    # Calcular mediana real (float)
    median_noise = float(noise.median())

    # IMPORTANT: evitar el warning → forcem dtype abans i després del fillna
    noise = noise.astype("float64")
    noise = noise.fillna(median_noise).astype("float64")

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
    # Més carreteres grans = pot voler dir accesible però també soroll → ho deixem descriptiu
    df["roads_norm"] = min_max(df["major_roads_count"])

    return df


# ---------- MAPATGE RESPOSTES → PREFERÈNCIES (0-1 per barri) ----------

def pref_low_mid_high(norm_series: pd.Series, level: str) -> pd.Series:
    """
    Donada una sèrie normalitzada (0=baix,1=alt) i preferència 'baixa'|'mitjana'|'alta',
    torna un score 0-1.
    """
    level = (level or "").strip().lower()
    if level in ("baixa", "baix", "low"):
        return 1 - norm_series
    if level in ("alta", "alt", "high", "excel·lent", "excelent"):
        return norm_series
    # 'mitjana', 'mitjà' → preferim valors propers a 0.5
    return 1 - (norm_series - 0.5).abs() * 2  # 0.5 → 1, 0 o 1 → 0


def score_from_answers(df: pd.DataFrame, answers: dict) -> pd.DataFrame:
    """
    Implementa el mapping de les 12 preguntes del formulari a un score per barri.
    'answers' és un dict amb claus:
      income, density, age, gastronomy, green, culture,
      pt_access, bus_availability, bike_lanes, walkability,
      safety, main_priority
    Valors esperats (Català):
      income: 'baixa'|'mitjana'|'alta'
      density: 'baixa'|'mitjana'|'alta'
      age: 'jove'|'mitjana'|'envellida'
      gastronomy: 'escassa'|'moderada'|'molt alta'
      green: 'poques'|'algunes'|'moltes'
      culture: 'baixa'|'mitjana'|'alta'
      pt_access: 'baix'|'bo'|'excel·lent'
      bus_availability: 'limitada'|'correcta'|'molt abundant'
      bike_lanes: 'inexistent'|'basic'|'extens'
      walkability: 'baixa'|'mitjana'|'alta'
      safety: 'estandard'|'alta'|'molt alta'
      main_priority: 'comunitat'|'privacitat i luxe'|'accessibilitat'|'cultura i gastronomia'
    """

    # ---------- 1) SCORES PER DIMENSIÓ SEGONS DIRECCIÓ DE PREFERÈNCIA ----------

    # 1. Renda mitjana
    income_ans = (answers.get("income") or "").strip().lower()
    if income_ans == "baixa":
        df["score_income"] = 1 - df["income_norm"]
    elif income_ans == "alta":
        df["score_income"] = df["income_norm"]
    else:  # 'mitjana' o qualsevol altre
        df["score_income"] = 1 - (df["income_norm"] - 0.5).abs() * 2

    # 2. Densitat de població (usem població com a proxy)
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

    # 4. Oferta gastronòmica (restaurants)
    gastr_ans = (answers.get("gastronomy") or "").strip().lower()
    if gastr_ans.startswith("escassa"):
        df["score_gastronomy"] = 1 - df["restaurants_norm"]
    elif "molt" in gastr_ans:
        df["score_gastronomy"] = df["restaurants_norm"]
    else:  # 'moderada'
        df["score_gastronomy"] = 1 - (df["restaurants_norm"] - 0.5).abs() * 2

    # 5. Zones verdes
    green_ans = (answers.get("green") or "").strip().lower()
    if green_ans.startswith("poques"):
        df["score_green"] = 1 - df["green_norm"]
    elif green_ans.startswith("moltes"):
        df["score_green"] = df["green_norm"]
    else:  # 'algunes'
        df["score_green"] = 1 - (df["green_norm"] - 0.5).abs() * 2

    # 6. Oferta cultural
    culture_ans = (answers.get("culture") or "").strip().lower()
    df["score_culture"] = pref_low_mid_high(df["culture_norm"], culture_ans)

    # 7. Accés transport públic
    pt_ans = (answers.get("pt_access") or "").strip().lower()
    df["score_pt"] = pref_low_mid_high(df["pt_norm"], pt_ans)

    # 8. Disponibilitat bus (la representem també amb parades PT)
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
    else:  # 'basic'
        df["score_bike"] = 1 - (df["bike_norm"] - 0.5).abs() * 2

    # 10. Caminabilitat
    walk_ans = (answers.get("walkability") or "").strip().lower()
    df["score_walk"] = pref_low_mid_high(df["walk_norm"], walk_ans)

    # 11. Nivell de seguretat requerit
    safety_ans = (answers.get("safety") or "").strip().lower()
    # Tothom vol seguretat, però canvia la importància
    df["score_safety"] = df["safety_norm"]

    # 11bis. Tranquil·litat (no estava explícit, però la vincularem a soroll)
    df["score_quiet"] = df["quiet_norm"]

    # ---------- 2) PESOS BASE PER CADA DIMENSIÓ ----------

    # Pesos "raonables" abans de la prioritat principal
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
    if safety_ans == "molt alta":
        weights["safety"] *= 1.5
    elif safety_ans == "alta":
        weights["safety"] *= 1.2

    # ---------- 3) PRIORITAT PRINCIPAL (Q12) → AJUST GLOBAL DE PESOS ----------

    main_prio = (answers.get("main_priority") or "").strip().lower()

    if main_prio.startswith("comunitat"):
        # Comunitat: caminabilitat, verd, cultura, seguretat
        weights["walk"] *= 1.4
        weights["green"] *= 1.3
        weights["culture"] *= 1.2
        weights["safety"] *= 1.1
        # menys pes a renda
        weights["income"] *= 0.7

    elif main_prio.startswith("privacitat"):
        # Privacitat i luxe: renda alta, baixa densitat, tranquil·litat, seguretat
        weights["income"] *= 1.4
        weights["density"] *= 1.3  # però preferint valors baixos (ja ho hem codificat)
        weights["quiet"] *= 1.4
        weights["safety"] *= 1.3
        # nightlife i cultura perden pes implícitament (no apareixen aquí)

    elif main_prio.startswith("accessibilitat"):
        # Accessibilitat: PT, bus, bici, caminabilitat
        weights["pt"] *= 1.5
        weights["bus"] *= 1.3
        weights["bike"] *= 1.3
        weights["walk"] *= 1.2
        # soroll i densitat passen a segon pla
        weights["quiet"] *= 0.7

    elif main_prio.startswith("cultura"):
        # Cultura i gastronomia: restaurants, nightlife, cultura
        weights["gastronomy"] *= 1.4
        weights["culture"] *= 1.5
        # tolerem més soroll i densitat
        weights["quiet"] *= 0.6
        weights["density"] *= 0.8

    # ---------- 4) COMBINAR EN UN SCORE FINAL ----------

    # Ens assegurem que la suma de pesos sigui 1 per fer la mitjana ponderada
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


def recommend_neighborhoods_from_answers(answers: dict, top_n: int = 5) -> pd.DataFrame:
    df = load_and_prepare_data()
    df = score_from_answers(df, answers)

    cols_to_show = [
        "rel_id",
        "display_name",
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


if __name__ == "__main__":
    # Exemple: perfil que vol bastanta vida, però també certa seguretat
    example_answers = {
        # BLOC 1
        "income": "mitjana",
        "density": "mitjana",
        "age": "jove",
        # BLOC 2
        "gastronomy": "molt alta",
        "green": "algunes",
        "culture": "alta",
        # BLOC 3
        "pt_access": "bo",
        "bus_availability": "molt abundant",
        "bike_lanes": "extens",
        "walkability": "alta",
        # BLOC 4
        "safety": "alta",
        "main_priority": "cultura i gastronomia",
    }

    recs = recommend_neighborhoods_from_answers(example_answers, top_n=5)
    print("=== Recomanació segons respostes de l'usuari ===")
    print(recs.to_string(index=False))
