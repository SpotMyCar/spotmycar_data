"""
checkexpired.py — Vérifie si les annonces sont toujours disponibles.

Stratégie de détection :
  - AutoScout24 : texte "n'est malheureusement plus disponible" dans le HTML
                  OU URL finale différente de l'URL enregistrée
  - Aramisauto  : URL finale contient "vehicle-not-available"

Usage :
  python checkexpired.py              -> verifie les annonces des dernières 24h
  python checkexpired.py --batch 200  -> limite à 200 annonces
  python checkexpired.py --dry-run    -> simulation sans modifier Supabase
  python checkexpired.py --source autoscout24
"""

import argparse
import json
import os
import time
import urllib.request
import urllib.error

SUPABASE_URL = "https://lrlskgxzrkjotcxevzag.supabase.co/rest/v1/annonces"
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")

HEADERS_SUPABASE = {
    "apikey":        SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type":  "application/json",
}

HEADERS_HTTP = {
    "User-Agent":      "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/124.0.0.0 Safari/537.36",
    "Accept":          "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
}


def fetch_annonces(batch: int, source: str = None) -> list:
    """Récupère les annonces actives vues dans les dernières 24h."""
    import urllib.parse
    from datetime import datetime, timezone, timedelta

    since = (datetime.now(timezone.utc) - timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%SZ")

    params = {
        "select": "id,lien_annonce,source,last_seen_at",
        "is_active": "eq.true",
        "last_seen_at": f"gt.{since}",
        "order": "last_seen_at.asc",
        "limit": str(batch),
    }

    if source:
        params["source"] = f"eq.{source}"
    else:
        params["source"] = "in.(autoscout24,aramisauto)"

    url = SUPABASE_URL + "?" + urllib.parse.urlencode(params)

    req = urllib.request.Request(url, headers=HEADERS_SUPABASE)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def flag_expired(annonce_id: int) -> bool:
    """Met is_active = false pour une annonce dans Supabase."""
    url     = f"{SUPABASE_URL}?id=eq.{annonce_id}"
    payload = json.dumps({"is_active": False}).encode("utf-8")
    headers = {**HEADERS_SUPABASE, "Prefer": "return=minimal"}

    req = urllib.request.Request(url, data=payload, headers=headers, method="PATCH")
    with urllib.request.urlopen(req, timeout=15) as r:
        return r.status in (200, 204)


def normalize_url(url: str) -> str:
    """Supprime les query params pour comparer les URLs proprement."""
    return url.split("?")[0].rstrip("/")


def check_url(lien: str, source: str) -> tuple[bool, str]:
    """
    Vérifie si une URL est expirée.
    Retourne (is_unavailable: bool, reason: str)
    """
    try:
        req = urllib.request.Request(lien, headers=HEADERS_HTTP)
        with urllib.request.urlopen(req, timeout=15) as resp:
            final_url = resp.url
            html      = resp.read().decode("utf-8", errors="ignore")

        if source == "autoscout24":
            # Signal 1 : texte d'expiration dans le HTML
            if "n'est malheureusement plus disponible" in html:
                return True, "texte expiration détecté"
            # Signal 2 : URL finale différente de l'URL enregistrée
            if normalize_url(final_url) != normalize_url(lien):
                return True, f"URL redirigée -> {final_url[:80]}"
            return False, "active"

        elif source == "aramisauto":
            if "vehicle-not-available" in final_url:
                return True, f"redirect -> {final_url[:80]}"
            return False, "active"

        return False, "source inconnue"

    except urllib.error.HTTPError as e:
        if e.code in (404, 410):
            return True, f"HTTP {e.code}"
        return False, f"HTTP {e.code} (ambigu — non flagué)"
    except urllib.error.URLError as e:
        return False, f"URLError: {e.reason} (non flagué)"
    except Exception as e:
        return False, f"erreur: {e} (non flagué)"


def run(batch: int, dry_run: bool, source: str = None):
    if not SUPABASE_KEY:
        print("❌ SUPABASE_KEY manquant — définis la variable d'environnement")
        return

    mode         = "🧪 DRY-RUN" if dry_run else "🚀 LIVE"
    source_label = source or "autoscout24 + aramisauto"

    print(f"\n🔍 checkexpired.py [{mode}]")
    print(f"   Batch  : {batch} annonces max")
    print(f"   Source : {source_label}")
    print(f"   Fenêtre: dernières 24h")
    print("─" * 65)

    try:
        annonces = fetch_annonces(batch, source)
    except Exception as e:
        print(f"❌ Impossible de récupérer les annonces : {e}")
        return

    print(f"📋 {len(annonces)} annonces récupérées\n")

    checked = 0
    expired = 0
    errors  = 0
    skipped = 0

    for ann in annonces:
        ann_id = ann["id"]
        lien   = ann.get("lien_annonce", "")
        src    = ann.get("source", "")

        if not lien or src not in ("autoscout24", "aramisauto"):
            skipped += 1
            continue

        is_exp, reason = check_url(lien, src)
        checked += 1

        if is_exp:
            expired += 1
            if not dry_run:
                try:
                    flag_expired(ann_id)
                    status = f"🔴 EXPIRÉ  — {reason}"
                except Exception as e:
                    errors += 1
                    status = f"🔴 EXPIRÉ  — flag échoué: {e}"
            else:
                status = f"🔴 EXPIRÉ  — {reason} (dry-run)"
        else:
            status = "✅ active" if "active" in reason else f"⚠️  {reason}"

        print(f"  [{src[:12]:12}] {status}")
        print(f"    {lien}")

        time.sleep(1)

    print("\n" + "─" * 65)
    print(f"📊 Résultats finaux :")
    print(f"   ✅ Vérifiées  : {checked}")
    print(f"   🔴 Expirées   : {expired}" + (" (non flaguées — dry-run)" if dry_run else " flaguées"))
    print(f"   ⚠️  Erreurs    : {errors}")
    if skipped:
        print(f"   ⏭️  Ignorées   : {skipped}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Vérifie et flag les annonces expirées dans Supabase."
    )
    parser.add_argument(
        "--batch", type=int, default=500,
        help="Nombre d'annonces max à vérifier (défaut: 500)"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Simulation — affiche les résultats sans modifier Supabase"
    )
    parser.add_argument(
        "--source", type=str, default=None,
        choices=["autoscout24", "aramisauto"],
        help="Restreindre à une source uniquement"
    )
    args = parser.parse_args()

    run(args.batch, args.dry_run, args.source)