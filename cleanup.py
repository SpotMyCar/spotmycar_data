import os, urllib.request
from datetime import datetime, timezone, timedelta

SUPABASE_URL = "https://lrlskgxzrkjotcxevzag.supabase.co/rest/v1/annonces"
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")

def delete_stale():
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=6)).strftime("%Y-%m-%dT%H:%M:%SZ")
    url = f"{SUPABASE_URL}?last_seen_at=lt.{cutoff}&last_seen_at=not.is.null"
    
    headers = {
        "apikey":        SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
    }
    req = urllib.request.Request(url, headers=headers, method="DELETE")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            print(f"✅ Stale rows deleted — HTTP {resp.status}")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="ignore")
        print(f"❌ HTTP {e.code}: {body}")
        raise

if __name__ == "__main__":
    delete_stale()
