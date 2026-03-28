import json, os, time, urllib.request, urllib.error
from normalize import get_generation

SUPABASE_URL = "https://lrlskgxzrkjotcxevzag.supabase.co/rest/v1/annonces"
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")

HEADERS = {
    "apikey":        SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type":  "application/json",
}

# Fetch all rows missing generation
req = urllib.request.Request(
    f"{SUPABASE_URL}?select=id,modele_unifie,date_voiture&generation=is.null&limit=10000",
    headers=HEADERS
)
with urllib.request.urlopen(req) as resp:
    rows = json.loads(resp.read())

print(f"Found {len(rows)} rows to backfill")

for row in rows:
    generation = get_generation(row.get("modele_unifie", ""), row.get("date_voiture", ""))
    if not generation:
        continue
    payload = json.dumps({"generation": generation}).encode("utf-8")
    patch_req = urllib.request.Request(
        f"{SUPABASE_URL}?id=eq.{row['id']}",
        data=payload,
        headers=HEADERS,
        method="PATCH"
    )
    with urllib.request.urlopen(patch_req) as r:
        pass

print("✅ Backfill done")
