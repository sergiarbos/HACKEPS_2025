# my_app/user_profile_config.py
from copy import deepcopy

BASE_WEIGHTS = {
    "income_level": 0.08,
    "density":      0.05,
    "age":          0.04,
    "gastronomy":   0.14,
    "green":        0.10,
    "culture":      0.10,
    "noise":        0.10,
    "pt_access":    0.12,
    "bike":         0.06,
    "walk":         0.08,
    "safety":       0.13,
}

# --- 1. Grups de features del model (normalitzats 0-1 en el teu codi) ---
# Et suggereixo aquests grups lògics:
# - income_level      → median_income / median_rent / median_home_value (a la pràctica miraràs sobretot median_income)
# - density           → population
# - age               → median_age
# - gastronomy        → restaurants_count + nightlife_places
# - green             → parks_count
# - culture           → culture_count
# - noise             → noise_db_centroid  (preferència sol ser "low noise")
# - pt_access         → pt_stops_count
# - bike              → bike_infra_count
# - walk              → walkability_features_count
# - safety            → crime_rate_per_1000 (recorda invertir-ho quan normalitzis)

BASE_WEIGHTS = {
    "income_level": 0.08,
    "density":      0.05,
    "age":          0.04,
    "gastronomy":   0.14,
    "green":        0.10,
    "culture":      0.10,
    "noise":        0.10,
    "pt_access":    0.12,
    "bike":         0.06,
    "walk":         0.08,
    "safety":       0.13,
}

# --- 2. Config de cada PREGUNTA del formulari ---
# Clau = name del <select> al HTML
# Per cada opció:
#   - "target_level": low / medium / high (o None si no aplica)
#   - "weight_delta": factor relatiu (+0.1 = +10% d’importància, -0.2 = -20%, etc.)

ANSWER_CONFIG = {
    # Bloc 1 — Demografia
    "renda_mediana": {
        # prefereixo barris assequibles → ingressos baixos
        "baixa": {
            "income_level": {
                "target_level": "low",
                "weight_delta": +0.3,
            }
        },
        # neutral: busquem rang intermedi
        "mitjana": {
            "income_level": {
                "target_level": "medium",
                "weight_delta": 0.0,
            }
        },
        # prefereixo zones cares → ingressos alts
        "alta": {
            "income_level": {
                "target_level": "high",
                "weight_delta": +0.3,
            }
        },
    },

    "densitat_poblacio": {
        "baixa": {
            "density": {
                "target_level": "low",   # menys població
                "weight_delta": +0.3,
            }
        },
        "mitjana": {
            "density": {
                "target_level": "medium",
                "weight_delta": 0.0,
            }
        },
        "alta": {
            "density": {
                "target_level": "high",  # més gent, més vida
                "weight_delta": +0.3,
            }
        },
    },

    "edat_mediana": {
        "jove": {
            "age": {
                "target_level": "low",   # edat mitjana baixa
                "weight_delta": +0.2,
            }
        },
        "mitjana": {
            "age": {
                "target_level": "medium",
                "weight_delta": 0.0,
            }
        },
        "envellida": {
            "age": {
                "target_level": "high",  # edat mitjana alta
                "weight_delta": +0.2,
            }
        },
    },

    # Bloc 2 — Estil de vida i entorn
    "oferta_gastronomica": {
        "escassa": {
            "gastronomy": {
                "target_level": "low",     # no cal tanta oferta
                "weight_delta": -0.2,
            }
        },
        "moderada": {
            "gastronomy": {
                "target_level": "medium",
                "weight_delta": 0.0,
            }
        },
        "molt_alta": {
            "gastronomy": {
                "target_level": "high",
                "weight_delta": +0.3,
            }
        },
    },

    "zones_verdes": {
        "poques": {
            "green": {
                "target_level": "low",
                "weight_delta": -0.1,
            }
        },
        "algunes": {
            "green": {
                "target_level": "medium",
                "weight_delta": 0.0,
            }
        },
        "moltes": {
            "green": {
                "target_level": "high",
                "weight_delta": +0.3,
            }
        },
    },

    "oferta_cultural": {
        "baixa": {
            "culture": {
                "target_level": "low",
                "weight_delta": -0.1,
            }
        },
        "mitjana": {
            "culture": {
                "target_level": "medium",
                "weight_delta": 0.0,
            }
        },
        "alta": {
            "culture": {
                "target_level": "high",
                "weight_delta": +0.3,
            }
        },
    },

    "soroll_sensibilitat": {
        # Indiferent → no cal donar gaire pes al soroll
        "indiferent": {
            "noise": {
                # com que el feature és "quiet_norm" (soroll baix = millor),
                # posem target "medium" i baixem importància
                "target_level": "medium",
                "weight_delta": -0.2,
            }
        },
        "moderat": {
            "noise": {
                "target_level": "low",    # menys soroll
                "weight_delta": 0.0,
            }
        },
        "molt_sensible": {
            "noise": {
                "target_level": "low",    # encara menys soroll
                "weight_delta": +0.4,
            }
        },
    },

    # Bloc 3 — Mobilitat
    "transport_public": {
        "baix": {
            "pt_access": {
                "target_level": "low",
                "weight_delta": -0.2,
            }
        },
        "bo": {
            "pt_access": {
                "target_level": "medium",
                "weight_delta": 0.0,
            }
        },
        "excel·lent": {
            "pt_access": {
                "target_level": "high",
                "weight_delta": +0.3,
            }
        },
    },

    "metro_bus": {
        "limitada": {
            "pt_access": {
                "target_level": "low",
                "weight_delta": -0.1,
            }
        },
        "correcta": {
            "pt_access": {
                "target_level": "medium",
                "weight_delta": 0.0,
            }
        },
        "molt_abundant": {
            "pt_access": {
                "target_level": "high",
                "weight_delta": +0.2,
            }
        },
    },

    "carrils_bici": {
        "inexistent": {
            "bike": {
                "target_level": "low",
                "weight_delta": -0.2,
            }
        },
        "basic": {
            "bike": {
                "target_level": "medium",
                "weight_delta": 0.0,
            }
        },
        "extens": {
            "bike": {
                "target_level": "high",
                "weight_delta": +0.3,
            }
        },
    },

    "caminabilitat": {
        "baixa": {
            "walk": {
                "target_level": "low",
                "weight_delta": -0.2,
            }
        },
        "mitjana": {
            "walk": {
                "target_level": "medium",
                "weight_delta": 0.0,
            }
        },
        "alta": {
            "walk": {
                "target_level": "high",
                "weight_delta": +0.3,
            }
        },
    },

    # Bloc 4 — Perfil
    "seguretat_requerida": {
        "estandard": {
            "safety": {
                "target_level": "medium",    # no extrem
                "weight_delta": 0.0,
            }
        },
        "alta": {
            "safety": {
                "target_level": "high",      # molt segura
                "weight_delta": +0.3,
            }
        },
        "molt_alta": {
            "safety": {
                "target_level": "high",
                "weight_delta": +0.5,
            }
        },
    },
}

# --- 3. Config de PRIORITAT PRINCIPAL ---
# Aquí fem ajustos més globals: multipliquem alguns pesos
PRIORITY_CONFIG = {
    "comunitat": {
        # vida de barri: verd, cultura, seguretat, densitat mitjana
        "weight_multipliers": {
            "green":      1.2,
            "culture":    1.1,
            "safety":     1.1,
            "density":    1.1,
        },
        "target_overrides": {
            "density": "medium",
        },
    },
    "privacitat_luxe": {
        # renda alta, baixa densitat, molt segura, poc soroll
        "weight_multipliers": {
            "income_level": 1.2,
            "density":      1.2,
            "safety":       1.2,
            "noise":        1.2,
        },
        "target_overrides": {
            "income_level": "high",
            "density":      "low",
            "noise":        "low",
        },
    },
    "accessibilitat": {
        # mobilitat i caminabilitat
        "weight_multipliers": {
            "pt_access": 1.3,
            "bike":      1.2,
            "walk":      1.2,
        },
        "target_overrides": {},
    },
    "cultura": {
        # cultura, gastronomia, nightlife
        "weight_multipliers": {
            "culture":    1.3,
            "gastronomy": 1.3,
        },
        "target_overrides": {
            "culture":    "high",
            "gastronomy": "high",
        },
    },
}

def build_user_profile(user_answers: dict):
    """
    Rep les respostes tal qual del front (valors dels <select>)
    i retorna:
      - weights: {grup_feature -> pes normalitzat}
      - targets: {grup_feature -> 'low'/'medium'/'high'}
    """
    weights = deepcopy(BASE_WEIGHTS)
    targets = {group: "medium" for group in BASE_WEIGHTS.keys()}

    for question, answer in user_answers.items():
        if question == "prioritat":
            continue

        config_for_q = ANSWER_CONFIG.get(question, {})
        config_for_answer = config_for_q.get(answer)
        if not config_for_answer:
            continue

        for group, cfg in config_for_answer.items():
            target_level = cfg.get("target_level")
            if target_level is not None:
                targets[group] = target_level

            delta = cfg.get("weight_delta", 0.0)
            weights[group] = max(0.0, weights[group] * (1.0 + delta))

    priority = user_answers.get("prioritat")
    if priority and priority in PRIORITY_CONFIG:
        pconf = PRIORITY_CONFIG[priority]

        for group, mult in pconf.get("weight_multipliers", {}).items():
            if group in weights:
                weights[group] *= mult

        for group, t in pconf.get("target_overrides", {}).items():
            targets[group] = t

    total_w = sum(weights.values())
    if total_w > 0:
        for g in weights:
            weights[g] /= total_w

    return weights, targets
