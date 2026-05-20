import json, os, time, urllib.request, urllib.error
from normalize import normalize_model

SUPABASE_URL = "https://lrlskgxzrkjotcxevzag.supabase.co/rest/v1/annonces"
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")
HEADERS = {
    "apikey":        SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type":  "application/json",
}

def fetch_all():
    """Récupère toutes les annonces avec marque, modele, modele_unifie."""
    rows = []
    offset, limit = 0, 1000
    while True:
        url = (
            f"{SUPABASE_URL}"
            f"?select=id,marque,modele,modele_unifie"
            f"&offset={offset}&limit={limit}"
        )
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req) as r:
            batch = json.loads(r.read())
        rows.extend(batch)
        if len(batch) < limit:
            break
        offset += limit
    return rows

def patch_row(row_id, new_modele_unifie):
    payload = json.dumps({"modele_unifie": new_modele_unifie}).encode("utf-8")
    req = urllib.request.Request(
        f"{SUPABASE_URL}?id=eq.{row_id}",
        data=payload,
        headers=HEADERS,
        method="PATCH",
    )
    urllib.request.urlopen(req)

def run(dry_run=False):
    print("Chargement des annonces...")
    rows = fetch_all()
    print(f"{len(rows)} annonces récupérées")

    updated = 0
    skipped = 0
    errors  = 0

    for row in rows:
        row_id         = row["id"]
        marque         = row.get("marque") or ""
        modele         = row.get("modele") or ""
        modele_unifie  = row.get("modele_unifie") or ""

        if not marque or not modele:
            skipped += 1
            continue

        new_modele_unifie = normalize_model(marque, modele)

        if new_modele_unifie == modele_unifie:
            skipped += 1
            continue

        print(f"  [{row_id}] {marque} | {modele!r:20} | {modele_unifie!r:20} → {new_modele_unifie!r}")

        if not dry_run:
            try:
                patch_row(row_id, new_modele_unifie)
                updated += 1
                time.sleep(0.05)  # éviter le rate limit Supabase
            except Exception as e:
                print(f"  ✗ Erreur row {row_id}: {e}")
                errors += 1
        else:
            updated += 1

    label = "[DRY RUN] " if dry_run else ""
    print(f"\n{label}Terminé : {updated} mis à jour, {skipped} inchangés, {errors} erreurs")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true",
                        help="Affiche les changements sans écrire en base")
    args = parser.parse_args()
    run(dry_run=args.dry_run)