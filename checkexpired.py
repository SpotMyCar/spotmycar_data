"""
checkexpired.py — Vérifie si les annonces sont toujours disponibles.
"""

import argparse
import json
import os
import time
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime, timezone, timedelta

SUPABASE_URL = "https://lrlskgxzrkjotcxevzag.supabase.co/rest/v1/annonces"
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")

HEADERS_SUPABASE = {
    "apikey":        SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type":  "application/json",
}

HEADERS_HTTP = {
    "User-Agent":      "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept":          "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
}


def fetch_stale_annonces(batch: int, stale_days: int, source: str = None) -> list:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=stale_days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    params = {
        "select":       "id,lien_annonce,source,last_seen_at",
        "is_expired":   "eq.false",
        "last_seen_at": f"lt.{cutoff}",
        "order":        "last_seen_at.asc",
        "limit":        str(batch),
    }
    if source:
        params["source"] = f"eq.{source}"
    else:
        params["source"] = "in.(autoscout24,aramisauto)"

    url = SUPABASE_URL + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers=HEADERS_SUPABASE)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def fetch_lbc_to_expire(lbc_ttl_days: int) -> list:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=lbc_ttl_days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    params = {
        "select":       "id,lien_annonce,last_seen_at",
        "is_expired":   "eq.false",
        "source":       "eq.leboncoin",
        "last_seen_at": f"lt.{cutoff}",
    }
    url = SUPABASE_URL + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers=HEADERS_SUPABASE)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def flag_expired(annonce_id, reason: str) -> bool:
    """Met is_expired=true et expire_reason pour une annonce."""
    url     = f"{SUPABASE_URL}?id=eq.{annonce_id}"
    payload = json.dumps({
        "is_expired":    True,
    }).encode("utf-8")
    headers = {**HEADERS_SUPABASE, "Prefer": "return=minimal"}

    print(f"    DEBUG URL     → {url}")
    print(f"    DEBUG payload → {payload}")

    req = urllib.request.Request(url, data=payload, headers=headers, method="PATCH")
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status in (200, 204)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="ignore")
        print(f"    DEBUG error body → {body}")
        raise


def normalize_url(url: str) -> str:
    return url.split("?")[0].rstrip("/")


def check_url(lien: str, source: str) -> tuple[bool, str]:
    try:
        req = urllib.request.Request(lien, headers=HEADERS_HTTP)
        opener = urllib.request.build_opener(urllib.request.HTTPRedirectHandler())
        with opener.open(req, timeout=15) as resp:
            final_url = resp.url
            html      = resp.read().decode("utf-8", errors="ignore")

        if source == "autoscout24":
            if "n'est malheureusement plus disponible" in html:
                return True, "texte_expiration"
            if normalize_url(final_url) != normalize_url(lien):
                return True, "url_redirect"
            return False, "active"

        elif source == "aramisauto":
            if "vehicle-not-available" in final_url:
                return True, "url_redirect"
            return False, "active"

        return False, "source_inconnue"

    except urllib.error.HTTPError as e:
        if e.code in (404, 410):
            return True, f"http_{e.code}"
        return False, f"http_{e.code}_ambigu"
    except urllib.error.URLError:
        return False, "url_error"
    except Exception:
        return False, "erreur_inconnue"


def run_http_check(batch: int, stale_days: int, dry_run: bool, source: str = None):
    source_label = source or "autoscout24 + aramisauto"
    print(f"\n🌐 HTTP CHECK")
    print(f"   Annonces non vues depuis : {stale_days}j")
    print(f"   Source                   : {source_label}")
    print(f"   Batch max                : {batch}")
    print("─" * 65)

    try:
        annonces = fetch_stale_annonces(batch, stale_days, source)
    except Exception as e:
        print(f"❌ Impossible de récupérer les annonces : {e}")
        return

    print(f"📋 {len(annonces)} annonces à vérifier\n")

    if not annonces:
        print("   Rien à vérifier — tout est à jour ✅")
        return

    checked = expired = errors = skipped = 0

    for ann in annonces:
        ann_id = ann["id"]
        lien   = ann.get("lien_annonce", "")
        src    = ann.get("source", "")
        seen   = ann.get("last_seen_at", "?")[:10]

        if not lien or src not in ("autoscout24", "aramisauto"):
            skipped += 1
            continue

        is_exp, reason = check_url(lien, src)
        checked += 1

        if is_exp:
            expired += 1
            if not dry_run:
                try:
                    flag_expired(ann_id, f"http_check:{reason}")
                    status = f"🔴 EXPIRÉ  [{reason}]"
                except Exception as e:
                    errors += 1
                    status = f"🔴 EXPIRÉ  [flag échoué: {e}]"
            else:
                status = f"🔴 EXPIRÉ  [{reason}] (dry-run)"
        else:
            status = "✅ active" if reason == "active" else f"⚠️  {reason} (non flagué)"

        print(f"  [{src[:12]:12}] [vu: {seen}] {status}")
        print(f"    {lien[:90]}")

        time.sleep(1)

    print("\n" + "─" * 65)
    print(f"📊 HTTP check terminé :")
    print(f"   ✅ Vérifiées : {checked}")
    print(f"   🔴 Expirées  : {expired}" + (" (dry-run)" if dry_run else ""))
    print(f"   ⚠️  Erreurs   : {errors}")
    if skipped:
        print(f"   ⏭️  Ignorées  : {skipped}")


def run_ttl_check(lbc_ttl_days: int, dry_run: bool):
    print(f"\n⏱️  TTL CHECK — LeBonCoin")
    print(f"   TTL : {lbc_ttl_days} jours sans last_seen_at → is_expired=true")
    print("─" * 65)

    try:
        annonces = fetch_lbc_to_expire(lbc_ttl_days)
    except Exception as e:
        print(f"❌ Impossible de récupérer les annonces LBC : {e}")
        return

    print(f"📋 {len(annonces)} annonces LBC à expirer\n")

    if not annonces:
        print("   Rien à expirer ✅")
        return

    expired = errors = 0

    for ann in annonces:
        ann_id = ann["id"]
        seen   = ann.get("last_seen_at", "?")[:10]
        lien   = ann.get("lien_annonce", "")[:70]

        if not dry_run:
            try:
                flag_expired(ann_id, f"lbc_ttl:{lbc_ttl_days}j")
                status = f"🔴 EXPIRÉ  [TTL {lbc_ttl_days}j dépassé]"
                expired += 1
            except Exception as e:
                errors += 1
                status = f"🔴 EXPIRÉ  [flag échoué: {e}]"
        else:
            status = f"🔴 EXPIRÉ  [TTL {lbc_ttl_days}j dépassé] (dry-run)"
            expired += 1

        print(f"  [leboncoin   ] [vu: {seen}] {status}")
        print(f"    {lien}")

    print("\n" + "─" * 65)
    print(f"📊 TTL check terminé :")
    print(f"   🔴 Expirées : {expired}" + (" (dry-run)" if dry_run else ""))
    if errors:
        print(f"   ⚠️  Erreurs  : {errors}")


def run(args):
    if not SUPABASE_KEY:
        print("❌ SUPABASE_KEY manquant — définis la variable d'environnement")
        return

    mode = "🧪 DRY-RUN" if args.dry_run else "🚀 LIVE"
    print(f"\n{'='*65}")
    print(f"  checkexpired.py [{mode}]  —  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*65}")

    if args.mode in ("http", "all"):
        run_http_check(args.batch, args.stale_days, args.dry_run, args.source)

    if args.mode in ("ttl", "all"):
        run_ttl_check(args.lbc_ttl_days, args.dry_run)

    print(f"\n✅ Terminé\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Vérifie et flag les annonces expirées dans Supabase.")
    parser.add_argument("--mode", type=str, default="all", choices=["all", "http", "ttl"])
    parser.add_argument("--stale-days", type=int, default=2)
    parser.add_argument("--lbc-ttl-days", type=int, default=7)
    parser.add_argument("--batch", type=int, default=500)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--source", type=str, default=None, choices=["autoscout24", "aramisauto"])
    args = parser.parse_args()
    run(args)