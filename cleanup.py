import os, urllib.request, json

SUPABASE_URL = "https://lrlskgxzrkjotcxevzag.supabase.co/rest/v1/annonces"
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")

def delete_stale():
    # PostgREST filter syntax for last_seen_at < now() - 6 hours
    url = f"{SUPABASE_URL}?last_seen_at=lt.{get_cutoff()}"
    headers = {
        "apikey":        SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Prefer":        "return=representation",
    }
    req = urllib.request.Request(url, headers=headers, method="DELETE")
    with urllib.request.urlopen(req, timeout=30) as resp:
        print(f"✅ Stale rows deleted — HTTP {resp.status}")

def get_cutoff():
    from datetime import datetime, timezone, timedelta
    cutoff = datetime.now(timezone.utc) - timedelta(hours=6)
    return cutoff.isoformat()

if __name__ == "__main__":
    delete_stale()
