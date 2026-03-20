import json, os
from normalize import normalize_make, normalize_model

AS24_PATH   = os.path.join("output_autoscout", "results.json")
ARAMIS_PATH = os.path.join("output_aramis",    "results.json")

def test_source(path, source):
    if not os.path.exists(path):
        print(f"Fichier introuvable : {path}")
        return
    with open(path, encoding="utf-8") as f:
        records = json.load(f)

    print(f"\n{'='*70}")
    print(f"  {source} — {len(records)} annonces")
    print(f"{'='*70}")
    print(f"  {'MARQUE BRUTE':<18} {'MODELE BRUT':<20} {'MODELE UNIFIE':<22} STATUS")
    print(f"  {'-'*66}")

    matched   = 0
    unmatched = []

    for r in records:
        marque        = r.get("marque", "")
        modele        = r.get("modele", "")
        modele_unifie = normalize_model(marque, modele)
        # "trouve" = le modele est dans la DB de mytracks (peu importe si le nom change)
        import json as _json
        _db = _json.load(open("mytracks_raw.json", encoding="utf-8"))
        _models = _db.get(normalize_make(marque), [])
        found = modele_unifie in _models
        if found:
            matched += 1
        else:
            unmatched.append((marque, modele))
        status = "OK" if found else "non trouve"
        print(f"  {marque:<18} {modele:<20} {modele_unifie:<22} {status}")

    pct = matched / len(records) * 100 if records else 0
    print(f"\n  Resultat : {matched}/{len(records)} matches ({pct:.0f}%)")

    if unmatched:
        print(f"  Non trouves :")
        for make, mod in dict.fromkeys(unmatched):
            print(f"    {make} / {mod}")

test_source(AS24_PATH,   "AutoScout24")
test_source(ARAMIS_PATH, "Aramis")
print("\nVoir missing_models.log pour le detail.")