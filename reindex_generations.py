import json
from supabase import create_client

SUPABASE_URL = "https://lrlskgxzrkjotcxevzag.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImxybHNrZ3h6cmtqb3RjeGV2emFnIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3NDQ3MDc2MSwiZXhwIjoyMDkwMDQ2NzYxfQ.CUkVj_NA8GXehEL2yM57gaMVUqgxKmZ6Bq6uZqvue_s"

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