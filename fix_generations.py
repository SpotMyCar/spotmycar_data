import json

with open('generations.json', 'r') as f:
    gens = json.load(f)

to_add = {
    "ONE": [
        {"gen": "Mini One R50", "from": 2001, "to": 2006},
        {"gen": "Mini One R56", "from": 2006, "to": 2014},
        {"gen": "Mini One F56", "from": 2014, "to": 2027},
    ],
    "118": [
        {"gen": "Serie 1 E87", "from": 2004, "to": 2011},
        {"gen": "Serie 1 F20", "from": 2011, "to": 2019},
        {"gen": "Serie 1 F40", "from": 2019, "to": 2027},
    ],
    "M4": [
        {"gen": "M4 F82", "from": 2014, "to": 2020},
        {"gen": "M4 G82", "from": 2020, "to": 2027},
    ],
    "M3": [
        {"gen": "M3 E90", "from": 2007, "to": 2013},
        {"gen": "M3 F80", "from": 2014, "to": 2018},
        {"gen": "M3 G80", "from": 2021, "to": 2027},
    ],
    "M2": [
        {"gen": "M2 F87", "from": 2016, "to": 2021},
        {"gen": "M2 G87", "from": 2022, "to": 2027},
    ],
    "G6": [{"gen": "Xpeng G6 1", "from": 2023, "to": 2030}],
    "SIERRA": [
        {"gen": "Sierra 1500 4", "from": 2014, "to": 2018},
        {"gen": "Sierra 1500 5", "from": 2018, "to": 2030},
    ],
    "RAM": [
        {"gen": "RAM 1500 4", "from": 2009, "to": 2018},
        {"gen": "RAM 1500 5", "from": 2018, "to": 2030},
    ],
    "BRONCO": [{"gen": "Bronco 6", "from": 2021, "to": 2030}],
    "TACOMA": [
        {"gen": "Tacoma 2", "from": 2005, "to": 2015},
        {"gen": "Tacoma 3", "from": 2015, "to": 2023},
        {"gen": "Tacoma 4", "from": 2023, "to": 2030},
    ],
    "SILVERADO": [
        {"gen": "Silverado 4", "from": 2014, "to": 2018},
        {"gen": "Silverado 5", "from": 2018, "to": 2030},
    ],
    "CANYON": [
        {"gen": "Canyon 2", "from": 2015, "to": 2022},
        {"gen": "Canyon 3", "from": 2022, "to": 2030},
    ],
    "SYMBIOZ": [{"gen": "Symbioz 1", "from": 2023, "to": 2030}],
    "DURANGO": [{"gen": "Durango 3", "from": 2011, "to": 2030}],
}

added = []
for key, entries in to_add.items():
    if key not in gens:
        gens[key] = entries
        added.append(key)

with open('generations.json', 'w', encoding='utf-8') as f:
    json.dump(gens, f, ensure_ascii=False, indent=2)
print(f"generations.json OK — {len(added)} cles ajoutees: {added}")
