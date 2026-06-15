import json
import os
from supabase import create_client

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("Missing SUPABASE_URL/SUPABASE_KEY environment variables.")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

with open("generations.json") as f:
    GENERATIONS = json.load(f)

def get_generation(model, date_voiture):
    if not date_voiture or date_voiture == "N/A":
        return None
    try:
        year = int(date_voiture.split("/")[-1])
    except:
        return None
    for g in GENERATIONS.get(model, []):
        if g["from"] <= year <= g["to"]:
            return g["gen"]
    return None

rows = supabase.table("annonces").select("id, modele_unifie, date_voiture").eq("generation", "N/A").execute().data
print(f"{len(rows)} annonces à corriger")

updated = 0
for row in rows:
    new_gen = get_generation(row["modele_unifie"], row["date_voiture"])
    if new_gen:
        result = supabase.table("annonces").update({"generation": new_gen}).eq("id", row["id"]).execute()
        updated += 1

print(f"{updated} annonces mises à jour")