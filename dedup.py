"""
dedup.py — Déduplication via Supabase.
Récupère tous les liens déjà présents dans la table annonces
et filtre les nouvelles annonces avant insertion.
"""

import json, urllib.request

SUPABASE_URL = "https://lrlskgxzrkjotcxevzag.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImxybHNrZ3h6cmtqb3RjeGV2emFnIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzQ0NzA3NjEsImV4cCI6MjA5MDA0Njc2MX0.IUPPMuth6KH1_wty_qEohsfjHFqomL_Gth-lw_Ju5dc"

_EXISTING_LINKS = None


def _fetch_existing_links() -> set:
    global _EXISTING_LINKS
    if _EXISTING_LINKS is not None:
        return _EXISTING_LINKS

    links = set()
    try:
        # Récupère uniquement la colonne lien_annonce, par pages de 1000
        offset = 0
        limit  = 1000
        while True:
            url = f"{SUPABASE_URL}/rest/v1/annonces?select=lien_annonce&offset={offset}&limit={limit}"
            req = urllib.request.Request(url, headers={
                "apikey":        SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}",
            })
            with urllib.request.urlopen(req, timeout=30) as r:
                rows = json.loads(r.read())

            for row in rows:
                lien = row.get("lien_annonce", "")
                if lien:
                    links.add(lien)

            if len(rows) < limit:
                break
            offset += limit

        print(f"  📋 Déduplication : {len(links)} liens déjà dans Supabase")

    except Exception as e:
        print(f"  ⚠️  Impossible de charger Supabase pour déduplication : {e}")
        print(f"  → Toutes les annonces seront envoyées")

    _EXISTING_LINKS = links
    return links


def filter_new_records(records: list) -> list:
    existing    = _fetch_existing_links()
    if not existing:
        return records
    new_records = [r for r in records if r.get("lien", "") not in existing]
    filtered    = len(records) - len(new_records)
    print(f"  🔍 {len(records)} scrappées → {filtered} doublons → {len(new_records)} nouvelles")
    return new_records


def reset_cache():
    global _EXISTING_LINKS
    _EXISTING_LINKS = None