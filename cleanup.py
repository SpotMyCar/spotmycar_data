import os
import json
import urllib.request
from datetime import datetime, timedelta, timezone

SUPABASE_URL = "https://lrlskgxzrkjotcxevzag.supabase.co/rest/v1/annonces"
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")

HEADERS = {
    "apikey":        SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type":  "application/json",
}

SAFE_THRESHOLDS = {
    "autoscout24": 350,  
    "aramisauto":  350   
}

def delete_stale():
    # Le .replace(tzinfo=None) retire le "+00:00" final pour ne pas casser l'URL
    limit_date = (datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=24)).isoformat()

    for source in ["autoscout24", "aramisauto"]:
        print(f"\n⚙️ Traitement de la source : {source}")
        
        # 1. FAIL-SAFE : Compter les annonces récemment mises à jour
        url_count = f"{SUPABASE_URL}?source=eq.{source}&last_seen_at=gte.{limit_date}"
        headers_count = HEADERS.copy()
        headers_count["Prefer"] = "count=exact"
        
        recent_count = 0
        try:
            req_count = urllib.request.Request(url_count, headers=headers_count, method="HEAD")
            with urllib.request.urlopen(req_count, timeout=30) as r:
                content_range = r.headers.get("Content-Range", "")
                if "/" in content_range:
                    recent_count = int(content_range.split("/")[-1])
        except Exception as e:
            print(f"⚠️ Erreur lors du comptage pour {source} : {e}")
            continue

        print(f"🔍 {recent_count} annonces récentes (gardées) pour {source}.")

        if recent_count < SAFE_THRESHOLDS.get(source, 350):
            print(f"🛑 SÉCURITÉ : Trop peu d'annonces. Nettoyage annulé.")
            continue

        # 2. VÉRIFICATION VISUELLE : On récupère les liens des annonces expirées (limité à 10 pour le test)
        url_verify = f"{SUPABASE_URL}?select=lien_annonce,last_seen_at&source=eq.{source}&last_seen_at=lt.{limit_date}&limit=10"
        
        try:
            req_verify = urllib.request.Request(url_verify, headers=HEADERS, method="GET")
            with urllib.request.urlopen(req_verify, timeout=30) as r:
                stale_data = json.loads(r.read())
                
            if not stale_data:
                print("   -> ✨ Aucune annonce périmée trouvée ! (Rien à supprimer)")
            else:
                print("   -> 🗑️ Voici un échantillon des annonces qui SERAIENT supprimées :")
                for item in stale_data:
                    date_vue = item.get('last_seen_at', '')[:16].replace('T', ' à ')
                    lien = item.get('lien_annonce', 'Pas de lien')
                    print(f"      - {lien} (Dernière vue : {date_vue})")
                    
        except Exception as e:
            print(f"❌ Erreur lors de la récupération des annonces à supprimer : {e}")

if __name__ == "__main__":
    if not SUPABASE_KEY:
        print("⚠️ ATTENTION : La variable d'environnement SUPABASE_KEY n'est pas définie.")
    else:
        delete_stale()