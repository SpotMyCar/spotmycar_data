# Usage:
#   python scripts/import_lbc.py                        → importe tous les JSON de scripts/data/
#   python scripts/import_lbc.py scripts/data/foo.json  → importe un fichier précis
#   python scripts/import_lbc.py foo.json bar.json       → importe plusieurs fichiers

import json
import os
import re
import sys
import urllib.request
from pathlib import Path

# Charge .env manuellement (même format que dotenv)
env_path = Path('.env')
if env_path.exists():
    for line in env_path.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            key, _, val = line.partition('=')
            os.environ.setdefault(key.strip(), val.strip())

SUPABASE_URL         = "https://lrlskgxzrkjotcxevzag.supabase.co"
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")

if not SUPABASE_SERVICE_KEY:
    print("Clé manquante — remplis SUPABASE_SERVICE_KEY dans le fichier .env", file=sys.stderr)
    sys.exit(1)

HEADERS = {
    "apikey":        SUPABASE_SERVICE_KEY,
    "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
    "Content-Type":  "application/json",
    "Prefer":        "resolution=ignore-duplicates,return=minimal",
}


def fix_encoding(s):
    if not s:
        return ''
    try:
        return s.encode('latin-1').decode('utf-8')
    except (UnicodeEncodeError, UnicodeDecodeError):
        return s


def parse_price(raw):
    if not raw:
        return None
    digits = re.sub(r'\D', '', fix_encoding(raw))
    return int(digits) if digits else None


def parse_mileage(raw):
    if not raw:
        return None
    digits = re.sub(r'\D', '', fix_encoding(raw))
    return int(digits) if digits else None


BRANDS = [
    'Alfa Romeo', 'Aston Martin', 'Land Rover', 'Mercedes-Benz',
    'Rolls-Royce', 'Abarth',
    'Peugeot', 'Renault', 'Citroën', 'Citroen', 'Volkswagen', 'VW',
    'Mercedes', 'BMW', 'Audi', 'Toyota', 'Ford', 'Fiat', 'Volvo',
    'Opel', 'Seat', 'Skoda', 'Hyundai', 'Kia', 'Nissan', 'Honda',
    'Mazda', 'Dacia', 'Jeep', 'Subaru', 'Mitsubishi', 'Suzuki',
    'Porsche', 'Lexus', 'Infiniti', 'Maserati', 'Ferrari', 'Lamborghini',
    'Bentley', 'Tesla', 'Mini', 'Smart', 'Cupra', 'DS',
]

MODEL_TO_BRAND = {
    'clio': 'Renault', 'megane': 'Renault', 'scenic': 'Renault', 'captur': 'Renault',
    'kangoo': 'Renault', 'twingo': 'Renault', 'zoe': 'Renault', 'laguna': 'Renault',
    '208': 'Peugeot', '308': 'Peugeot', '3008': 'Peugeot', '5008': 'Peugeot',
    '508': 'Peugeot', '2008': 'Peugeot', '107': 'Peugeot', '207': 'Peugeot',
    'c3': 'Citroën', 'c4': 'Citroën', 'c5': 'Citroën', 'berlingo': 'Citroën',
    'xsara': 'Citroën', 'ds3': 'Citroën', 'ds4': 'Citroën',
    'golf': 'Volkswagen', 'polo': 'Volkswagen', 'passat': 'Volkswagen',
    'tiguan': 'Volkswagen', 'touareg': 'Volkswagen', 't-roc': 'Volkswagen',
    'series 1': 'BMW', 'series 3': 'BMW', 'series 5': 'BMW',
    '500': 'Fiat', 'punto': 'Fiat', 'tipo': 'Fiat',
    'sandero': 'Dacia', 'duster': 'Dacia', 'logan': 'Dacia',
    'corsa': 'Opel', 'astra': 'Opel', 'insignia': 'Opel',
    'fiesta': 'Ford', 'focus': 'Ford', 'kuga': 'Ford', 'puma': 'Ford',
    'yaris': 'Toyota', 'corolla': 'Toyota', 'rav4': 'Toyota',
}


def extract_brand_model(raw_title):
    title = fix_encoding(raw_title or '').strip()
    title_lower = title.lower()

    for brand in BRANDS:
        if title_lower.startswith(brand.lower()):
            rest = title[len(brand):].strip()
            model = rest.split()[0] if rest.split() else ''
            return brand, model

    first_word = title_lower.split()[0] if title_lower.split() else ''
    if first_word in MODEL_TO_BRAND:
        return MODEL_TO_BRAND[first_word], title.split()[0]

    return None, (title.split()[0] if title.split() else None)


# Résolution des fichiers à importer
DATA_DIR = Path('scripts/data')
args = sys.argv[1:]
if args:
    files = [Path(f) for f in args]
else:
    files = sorted(DATA_DIR.glob('*.json'))
    if not files:
        print("Aucun fichier JSON trouvé dans scripts/data/", file=sys.stderr)
        sys.exit(1)

print(f"Fichiers à importer : {', '.join(f.name for f in files)}\n")

raw = []
for file_path in files:
    print(f"Lecture de {file_path.name}...")
    raw.extend(json.loads(file_path.read_text(encoding='utf-8')))

annonces = []
for item in raw:
    if not item.get('text-body-2') or not item.get('text-body-2 (2)'):
        continue
    marque, modele = extract_brand_model(item.get('text-body-1'))
    prix       = parse_price(item.get('text-callout'))
    kilometrage = parse_mileage(item.get('text-body-2 (2)'))
    try:
        annee = int(item.get('text-body-2', ''))
    except (ValueError, TypeError):
        annee = None
    carburant = fix_encoding(item.get('text-body-2 (3)') or '')
    titre = fix_encoding(item.get('text-body-1') or '').strip()

    if prix and kilometrage and marque:
        annonces.append({
            'titre':         titre,
            'prix':          prix,
            'kilometrage':   kilometrage,
            'date_voiture':  annee,
            'marque':        marque,
            'modele':        modele,
            'modele_unifie': modele,
            'lien_annonce':  item.get('absolute href'),
            'lien_image':    item.get('absolute src'),
            'source':        'LeBonCoin',
            'carburant':     carburant,
        })

print(f"{len(annonces)} annonces valides sur {len(raw)} entrées")
if not annonces:
    sys.exit(0)

print("\nAperçu :")
for a in annonces[:3]:
    print(f"  {a['marque']} {a['modele']} — {a['prix']}€ — {a['kilometrage']}km — {a['date_voiture']} — {a['carburant']}")

# Insertion dans Supabase (par batch de 50)
url = f"{SUPABASE_URL}/rest/v1/annonces?on_conflict=lien_annonce"
inserted = 0
for i in range(0, len(annonces), 50):
    batch = annonces[i:i + 50]
    body = json.dumps(batch).encode('utf-8')
    req = urllib.request.Request(url, data=body, headers=HEADERS, method='POST')
    try:
        with urllib.request.urlopen(req) as resp:
            resp.read()
        inserted += len(batch)
        print(f"Inséré : {inserted}/{len(annonces)}")
    except urllib.error.HTTPError as e:
        print(f"Erreur batch {i}-{i + len(batch)}: {e.read().decode()}", file=sys.stderr)

print("\nImport terminé.")
