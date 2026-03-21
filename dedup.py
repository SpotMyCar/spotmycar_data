"""
dedup.py — Déduplication des annonces avant envoi à Make.com

Télécharge le Google Sheet CSV, extrait les liens déjà présents,
et filtre les nouvelles annonces pour éviter les doublons.

Usage :
    from dedup import filter_new_records
    new_records = filter_new_records(records)
"""

import csv, io, urllib.request, os, json

# URL de publication CSV du Google Sheet (public)
# Format : https://docs.google.com/spreadsheets/d/SHEET_ID/export?format=csv
SHEET_CSV_URL = os.environ.get(
    "SHEET_CSV_URL",
    "https://docs.google.com/spreadsheets/d/e/2PACX-1vSb-ONkMlVcGyjgUezj66SptrWml_mbAGXZMshgEU7Dwg7hVJJNJ4WWeTPdhQBVkHFxxV2WyR_Kdxnf/pub?gid=0&single=true&output=csv"
)

# Colonne qui contient le lien dans le Google Sheet (nom de l'en-tête)
LINK_COLUMN = "lien_annonce"

# Cache local pour éviter de re-télécharger le sheet dans le même run
_EXISTING_LINKS: set = None


def _fetch_existing_links() -> set:
    """Télécharge le Google Sheet et retourne un set de tous les liens déjà présents."""
    global _EXISTING_LINKS
    if _EXISTING_LINKS is not None:
        return _EXISTING_LINKS

    links = set()
    try:
        req = urllib.request.Request(
            SHEET_CSV_URL,
            headers={"User-Agent": "Mozilla/5.0"}
        )
        with urllib.request.urlopen(req, timeout=30) as r:
            content = r.read().decode("utf-8", errors="ignore")

        reader = csv.DictReader(io.StringIO(content))
        for row in reader:
            lien = row.get(LINK_COLUMN, "").strip()
            if lien and lien != "N/A":
                links.add(lien)

        print(f"  📋 Déduplication : {len(links)} liens déjà dans le Google Sheet")

    except Exception as e:
        print(f"  ⚠️  Impossible de charger le Google Sheet pour déduplication : {e}")
        print(f"  → Toutes les annonces seront envoyées (pas de filtre)")

    _EXISTING_LINKS = links
    return links


def filter_new_records(records: list) -> list:
    """
    Filtre une liste d'annonces pour ne garder que celles
    dont le lien n'est pas déjà dans le Google Sheet.

    Args:
        records: liste de dicts avec au minimum une clé "lien"

    Returns:
        liste filtrée des nouvelles annonces uniquement
    """
    existing = _fetch_existing_links()

    if not existing:
        # Impossible de charger le sheet → on envoie tout pour ne rien perdre
        return records

    new_records = [r for r in records if r.get("lien", "") not in existing]

    total    = len(records)
    filtered = total - len(new_records)
    print(f"  🔍 {total} annonces scrappées → {filtered} doublons supprimés → {len(new_records)} nouvelles")

    return new_records


def reset_cache():
    """Réinitialise le cache (utile pour les tests)."""
    global _EXISTING_LINKS
    _EXISTING_LINKS = None