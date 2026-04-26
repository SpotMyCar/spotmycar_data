import json

with open("generations.json", "r") as f:
    gens = json.load(f)

# ── Modèles à AJOUTER entièrement ──────────────────────────────────────────
new_entries = {
    "208": [
        { "gen": "208 1", "from": 2012, "to": 2019 },
        { "gen": "208 2", "from": 2019, "to": 9999 }
    ],
    "2008": [
        { "gen": "2008 1", "from": 2013, "to": 2019 },
        { "gen": "2008 2", "from": 2019, "to": 9999 }
    ],
    "RAM": [
        { "gen": "RAM 1500 DS", "from": 2009, "to": 2018 },
        { "gen": "RAM 1500 DT", "from": 2018, "to": 9999 }
    ],
    "TIGUAN": [
        { "gen": "Tiguan 1", "from": 2007, "to": 2016 },
        { "gen": "Tiguan 2", "from": 2016, "to": 2023 },
        { "gen": "Tiguan 3", "from": 2023, "to": 9999 }
    ],
    "BRONCO": [
        { "gen": "Bronco 6G", "from": 2021, "to": 9999 }
    ],
    "GLADIATOR": [
        { "gen": "Gladiator JT", "from": 2019, "to": 9999 }
    ],
    "MUSTANG": [  # Remplace l'entrée existante
        { "gen": "Mustang S197", "from": 2004, "to": 2014 },
        { "gen": "Mustang S550", "from": 2014, "to": 2023 },
        { "gen": "Mustang S650", "from": 2023, "to": 9999 }
    ],
    "TACOMA": [
        { "gen": "Tacoma 3", "from": 2015, "to": 2023 },
        { "gen": "Tacoma 4", "from": 2023, "to": 9999 }
    ],
    "SILVERADO": [
        { "gen": "Silverado 4", "from": 2013, "to": 2018 },
        { "gen": "Silverado 5", "from": 2018, "to": 9999 }
    ],
    "SIERRA": [
        { "gen": "Sierra 4", "from": 2013, "to": 2023 },
        { "gen": "Sierra 5", "from": 2023, "to": 9999 }
    ],
    "CANYON": [
        { "gen": "Canyon 2", "from": 2014, "to": 2022 },
        { "gen": "Canyon 3", "from": 2022, "to": 9999 }
    ],
    "DURANGO": [
        { "gen": "Durango WD", "from": 2011, "to": 9999 }
    ],
    "D-MAX": [
        { "gen": "D-Max 2", "from": 2011, "to": 2020 },
        { "gen": "D-Max 3", "from": 2020, "to": 9999 }
    ],
    "ASX": [
        { "gen": "ASX 1", "from": 2010, "to": 2022 },
        { "gen": "ASX 2", "from": 2022, "to": 9999 }
    ],
    "S-CROSS": [
        { "gen": "S-Cross 1", "from": 2013, "to": 2021 },
        { "gen": "S-Cross 2", "from": 2021, "to": 9999 }
    ],
    "SYMBIOZ": [
        { "gen": "Symbioz 1", "from": 2024, "to": 9999 }
    ],
    "RAFALE": [
        { "gen": "Rafale 1", "from": 2023, "to": 9999 }
    ],
    "JUNIOR": [
        { "gen": "Junior 1", "from": 2024, "to": 9999 }
    ],
    "COOPER E": [
        { "gen": "Cooper E F56", "from": 2021, "to": 9999 }
    ],
    "AVENGER": [
        { "gen": "Avenger 1", "from": 1994, "to": 2000 },
        { "gen": "Avenger 2", "from": 2007, "to": 2014 },
        { "gen": "Avenger 3", "from": 2022, "to": 9999 }
    ],
    "TUCSON": [
        { "gen": "Tucson 2", "from": 2009, "to": 2015 },
        { "gen": "Tucson 3", "from": 2015, "to": 2020 },
        { "gen": "Tucson 4", "from": 2020, "to": 9999 }
    ],
    "STONIC": [
        { "gen": "Stonic 1", "from": 2017, "to": 2023 },
        { "gen": "Stonic 2", "from": 2023, "to": 9999 }
    ],
    "MULTIVAN": [
        { "gen": "Multivan T6", "from": 2015, "to": 2021 },
        { "gen": "Multivan T7", "from": 2021, "to": 9999 }
    ],
}

# ── Générations existantes dont il faut juste étendre le "to" à 9999 ────────
extend_to_9999 = {
    "TRANSIT COURIER": "Transit Courier 2",
    "TOURNEO COURIER": "Tourneo Courier 2",
    "TOURNEO CONNECT": "Tourneo Connect 3",
    "I20":             "i20 3",
    "CORSA":           "Corsa F",
    "C3 AIRCROSS":     "C3 Aircross 2",
    "C5 AIRCROSS":     "C5 Aircross 2",
    "SCUDO":           "Scudo 3",
    "600":             "600 1",
    "STONIC":          "Stonic 1",   # au cas où
}

for model, gen_name in extend_to_9999.items():
    if model in gens:
        for g in gens[model]:
            if g["gen"] == gen_name:
                g["to"] = 9999
                print(f"✅ Étendu : {model} → {gen_name}")

# Applique les nouvelles entrées (écrase si déjà présent)
for model, data in new_entries.items():
    action = "Remplacé" if model in gens else "Ajouté"
    gens[model] = data
    print(f"✅ {action} : {model}")

with open("generations.json", "w", encoding="utf-8") as f:
    json.dump(gens, f, ensure_ascii=False, indent=2)

print("\n✅ generations.json mis à jour avec succès !")