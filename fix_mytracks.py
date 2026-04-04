import json

with open('mytracks_raw.json', 'r') as f:
    db = json.load(f)

additions = {
    "Xpeng": ["G3", "G6", "G9", "P5", "P7"],
    "GMC": ["Sierra", "Canyon", "Yukon", "Terrain", "Acadia"],
}
missing = {
    "BMW":  ["118", "M2", "M3", "M4", "M5", "M8"],
    "Mini": ["One", "John Cooper Works"],
}

for brand, models in additions.items():
    if brand not in db:
        db[brand] = models

for brand, models in missing.items():
    if brand in db:
        existing = set(db[brand])
        for m in models:
            if m not in existing:
                db[brand].append(m)

with open('mytracks_raw.json', 'w', encoding='utf-8') as f:
    json.dump(db, f, ensure_ascii=False, indent=2)
print("mytracks_raw.json OK")
