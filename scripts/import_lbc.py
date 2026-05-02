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


FUEL_KEYWORDS = {'diesel', 'essence', 'hybride', 'électrique', 'electrique', 'gpl', 'gaz', 'hydrogène'}


def detect_field_mapping(items):
    """
    Analyse l'ensemble des items pour déterminer quel champ text-body-2*
    correspond à l'année, aux km et au carburant, en scorant chaque champ
    selon la proportion de valeurs qui matchent chaque pattern.
    """
    candidate_fields = set()
    for item in items:
        for key in item:
            if key.startswith('text-body-2'):
                candidate_fields.add(key)

    scores = {f: {'annee': 0, 'km': 0, 'carburant': 0, 'total': 0} for f in candidate_fields}

    for item in items:
        for field in candidate_fields:
            raw = item.get(field)
            if not raw:
                continue
            val = fix_encoding(raw).strip()
            val_lower = val.lower()
            scores[field]['total'] += 1

            digits_only = re.sub(r'\D', '', val)

            if digits_only and re.fullmatch(r'\d{4}', digits_only) and 1990 <= int(digits_only) <= 2030:
                scores[field]['annee'] += 1

            if 'km' in val_lower:
                scores[field]['km'] += 1

            if any(kw in val_lower for kw in FUEL_KEYWORDS):
                scores[field]['carburant'] += 1

    mapping = {}
    for type_ in ('annee', 'km', 'carburant'):
        best_field = max(
            candidate_fields,
            key=lambda f: scores[f][type_] / max(scores[f]['total'], 1)
        )
        if scores[best_field][type_] > 0:
            mapping[type_] = best_field

    return mapping


# Ordre important : les plus longues en premier pour éviter les faux positifs
BRANDS = [
    'Alfa Romeo', 'Aston Martin', 'Land Rover', 'Land-rover', 'Mercedes-Benz',
    'Rolls-Royce', 'Range Rover',
    'Abarth', 'Alpine', 'Aixam',
    'Peugeot', 'Renault', 'Citroën', 'Citroen', 'Volkswagen', 'VW',
    'Mercedes', 'BMW', 'B.M.W.', 'Audi', 'Toyota', 'Ford', 'Fiat', 'Volvo',
    'Opel', 'Seat', 'Skoda', 'Hyundai', 'Kia', 'Nissan', 'Honda',
    'Mazda', 'Dacia', 'Jeep', 'Subaru', 'Mitsubishi', 'Suzuki',
    'Porsche', 'Lexus', 'Infiniti', 'Maserati', 'Ferrari', 'Lamborghini',
    'Bentley', 'Tesla', 'Mini', 'Smart', 'Cupra', 'DS',
    'Jaguar', 'Isuzu', 'Ligier',
    'MG', 'BYD',
]

BRAND_CANONICAL = {
    'land-rover':    'Land Rover',
    'range rover':   'Land Rover',
    'mercedes-benz': 'Mercedes',
    'citroen':       'Citroën',
    'vw':            'Volkswagen',
    'b.m.w.':        'BMW',
}

STRIP_PREFIXES = [
    'vend ', 'vends ', 'voiture ', 'belle ', 'beau ', 'magnifique ',
    'superbe ', 'urgent ', 'urgence ',
]

MODEL_TO_BRAND = {
    # Renault
    'clio': 'Renault', 'megane': 'Renault', 'mégane': 'Renault',
    'scenic': 'Renault', 'scénic': 'Renault', 'captur': 'Renault',
    'kangoo': 'Renault', 'twingo': 'Renault', 'zoe': 'Renault',
    'laguna': 'Renault', 'arkana': 'Renault', 'espace': 'Renault',
    'koleos': 'Renault', 'talisman': 'Renault', 'fluence': 'Renault',
    # Peugeot
    '208': 'Peugeot', '308': 'Peugeot', '3008': 'Peugeot', '5008': 'Peugeot',
    '508': 'Peugeot', '2008': 'Peugeot', '107': 'Peugeot', '207': 'Peugeot',
    '206': 'Peugeot', '205': 'Peugeot', '106': 'Peugeot', '307': 'Peugeot',
    '406': 'Peugeot', '408': 'Peugeot', '4008': 'Peugeot', '301': 'Peugeot',
    # Citroën
    'c1': 'Citroën', 'c2': 'Citroën', 'c3': 'Citroën', 'c4': 'Citroën',
    'c5': 'Citroën', 'berlingo': 'Citroën', 'xsara': 'Citroën',
    'ds3': 'Citroën', 'ds4': 'Citroën', 'ds5': 'Citroën',
    # Volkswagen
    'golf': 'Volkswagen', 'polo': 'Volkswagen', 'passat': 'Volkswagen',
    'tiguan': 'Volkswagen', 'touareg': 'Volkswagen', 't-roc': 'Volkswagen',
    'touran': 'Volkswagen', 'sharan': 'Volkswagen', 'caddy': 'Volkswagen',
    'arteon': 'Volkswagen', 'taigo': 'Volkswagen', 'id.3': 'Volkswagen',
    'id.4': 'Volkswagen',
    # BMW
    'series 1': 'BMW', 'series 2': 'BMW', 'series 3': 'BMW',
    'series 4': 'BMW', 'series 5': 'BMW', 'series 6': 'BMW',
    'x1': 'BMW', 'x2': 'BMW', 'x3': 'BMW', 'x4': 'BMW',
    'x5': 'BMW', 'x6': 'BMW', 'x7': 'BMW', 'i3': 'BMW', 'i4': 'BMW',
    # Audi
    'a1': 'Audi', 'a3': 'Audi', 'a4': 'Audi', 'a5': 'Audi',
    'a6': 'Audi', 'a7': 'Audi', 'a8': 'Audi',
    'q2': 'Audi', 'q3': 'Audi', 'q5': 'Audi', 'q7': 'Audi', 'q8': 'Audi',
    'tt': 'Audi', 'e-tron': 'Audi',
    # Mercedes
    'cla': 'Mercedes', 'gla': 'Mercedes', 'glc': 'Mercedes', 'gle': 'Mercedes',
    'gls': 'Mercedes', 'glb': 'Mercedes', 'eqa': 'Mercedes', 'eqb': 'Mercedes',
    # Fiat
    '500': 'Fiat', 'punto': 'Fiat', 'tipo': 'Fiat', 'bravo': 'Fiat',
    'panda': 'Fiat', '500x': 'Fiat', '500l': 'Fiat',
    # Dacia
    'sandero': 'Dacia', 'duster': 'Dacia', 'logan': 'Dacia',
    'jogger': 'Dacia', 'spring': 'Dacia', 'lodgy': 'Dacia', 'bigster': 'Dacia',
    # Opel
    'corsa': 'Opel', 'astra': 'Opel', 'insignia': 'Opel',
    'mokka': 'Opel', 'crossland': 'Opel', 'grandland': 'Opel',
    # Ford
    'fiesta': 'Ford', 'focus': 'Ford', 'kuga': 'Ford', 'puma': 'Ford',
    'mondeo': 'Ford', 'mustang': 'Ford', 'explorer': 'Ford',
    # Toyota
    'yaris': 'Toyota', 'corolla': 'Toyota', 'rav4': 'Toyota',
    'c-hr': 'Toyota', 'prius': 'Toyota', 'aygo': 'Toyota', 'proace': 'Toyota',
    # Seat / Cupra
    'ibiza': 'Seat', 'leon': 'Seat', 'arona': 'Seat', 'ateca': 'Seat',
    'tarraco': 'Seat', 'formentor': 'Cupra',
    # Hyundai
    'i10': 'Hyundai', 'i20': 'Hyundai', 'i30': 'Hyundai', 'i40': 'Hyundai',
    'tucson': 'Hyundai', 'santa': 'Hyundai', 'ioniq': 'Hyundai', 'kona': 'Hyundai',
    # Kia
    'picanto': 'Kia', 'rio': 'Kia', 'ceed': 'Kia', 'sportage': 'Kia',
    'stonic': 'Kia', 'sorento': 'Kia', 'niro': 'Kia', 'ev6': 'Kia',
    # Nissan
    'micra': 'Nissan', 'juke': 'Nissan', 'qashqai': 'Nissan',
    'leaf': 'Nissan', 'x-trail': 'Nissan', 'navara': 'Nissan',
    # Honda
    'jazz': 'Honda', 'civic': 'Honda', 'hr-v': 'Honda',
    'cr-v': 'Honda', 'accord': 'Honda',
    # Mazda
    'mazda2': 'Mazda', 'mazda3': 'Mazda', 'mazda6': 'Mazda',
    'cx-3': 'Mazda', 'cx-5': 'Mazda', 'cx-30': 'Mazda',
    # Skoda
    'fabia': 'Skoda', 'octavia': 'Skoda', 'superb': 'Skoda',
    'karoq': 'Skoda', 'kodiaq': 'Skoda', 'kamiq': 'Skoda',
    # Volvo
    'v40': 'Volvo', 'v60': 'Volvo', 'v90': 'Volvo',
    's60': 'Volvo', 's90': 'Volvo', 'xc40': 'Volvo', 'xc60': 'Volvo', 'xc90': 'Volvo',
    # Suzuki
    'swift': 'Suzuki', 'vitara': 'Suzuki', 'sx4': 'Suzuki', 'ignis': 'Suzuki',
    # Mitsubishi
    'asx': 'Mitsubishi', 'outlander': 'Mitsubishi', 'eclipse': 'Mitsubishi',
    # Subaru
    'impreza': 'Subaru', 'forester': 'Subaru', 'outback': 'Subaru', 'xv': 'Subaru',
    # Jeep
    'renegade': 'Jeep', 'compass': 'Jeep', 'wrangler': 'Jeep', 'cherokee': 'Jeep',
    # Tesla
    'model': 'Tesla',
    # Land Rover / Range Rover
    'defender': 'Land Rover', 'discovery': 'Land Rover', 'freelander': 'Land Rover',
    'range': 'Land Rover', 'evoque': 'Land Rover',
    # Autres
    'mini': 'Mini', 'countryman': 'Mini', 'clubman': 'Mini',
}


def extract_brand_model(raw_title):
    title = fix_encoding(raw_title or '').strip()

    title_stripped = title
    for prefix in STRIP_PREFIXES:
        if title_stripped.lower().startswith(prefix):
            title_stripped = title_stripped[len(prefix):].strip()
            break

    title_lower = title_stripped.lower()

    for brand in BRANDS:
        if title_lower.startswith(brand.lower()):
            canonical = BRAND_CANONICAL.get(brand.lower(), brand)
            rest = title_stripped[len(brand):].strip()
            model = rest.split()[0] if rest.split() else ''
            return canonical, model

    first_word = title_lower.split()[0] if title_lower.split() else ''
    if first_word in MODEL_TO_BRAND:
        return MODEL_TO_BRAND[first_word], title_stripped.split()[0]

    return None, (title_stripped.split()[0] if title_stripped.split() else None)


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

# Auto-détection des champs sur l'ensemble du dataset
mapping = detect_field_mapping(raw)
f_annee    = mapping.get('annee')
f_km       = mapping.get('km')
f_carburant = mapping.get('carburant')
print(f"\nChamps détectés  : année={f_annee}  km={f_km}  carburant={f_carburant}")

if not f_km or not f_annee:
    print("Impossible de détecter les champs année/km — vérifier le format du JSON.", file=sys.stderr)
    sys.exit(1)

annonces = []
for item in raw:
    if not item.get(f_annee) or not item.get(f_km):
        continue
    marque, modele = extract_brand_model(item.get('text-body-1'))
    # Annonces particuliers : prix dans text-callout ; annonces pros : dans text-success
    prix        = parse_price(item.get('text-callout')) or parse_price(item.get('text-success'))
    kilometrage = parse_mileage(item.get(f_km))
    try:
        annee = int(re.sub(r'\D', '', fix_encoding(item.get(f_annee, '') or '')))
    except (ValueError, TypeError):
        annee = None
    carburant = fix_encoding(item.get(f_carburant) or '') if f_carburant else ''
    titre     = fix_encoding(item.get('text-body-1') or '').strip()

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
