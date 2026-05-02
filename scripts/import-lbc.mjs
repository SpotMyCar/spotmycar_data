// Usage:
//   node scripts/import-lbc.mjs                        → importe tous les JSON de scripts/data/
//   node scripts/import-lbc.mjs scripts/data/foo.json  → importe un fichier précis
//   node scripts/import-lbc.mjs foo.json bar.json       → importe plusieurs fichiers

import fs from 'fs';
import path from 'path';
import { config } from 'dotenv';

config({ path: path.resolve('.env') });

const SUPABASE_URL         = "https://lrlskgxzrkjotcxevzag.supabase.co";
const SUPABASE_SERVICE_KEY = process.env.SUPABASE_SERVICE_KEY;

if (!SUPABASE_SERVICE_KEY || SUPABASE_SERVICE_KEY === 'colle_ta_service_role_key_ici') {
  console.error('Clé manquante — remplis SUPABASE_SERVICE_KEY dans le fichier .env');
  process.exit(1);
}

// Correction de l'encodage mojibake (UTF-8 lu comme latin-1)
function fixEncoding(str) {
  if (!str) return '';
  try {
    const bytes = Buffer.alloc(str.length);
    for (let i = 0; i < str.length; i++) bytes[i] = str.charCodeAt(i) & 0xFF;
    return bytes.toString('utf8');
  } catch {
    return str;
  }
}

// Extraction du prix depuis "24 999 €" ou "24â¯999Â â¬"
function parsePrice(raw) {
  if (!raw) return null;
  const digits = fixEncoding(raw).replace(/[^\d]/g, '');
  const val = parseInt(digits);
  return isNaN(val) ? null : val;
}

// Extraction du kilométrage depuis "29414 km"
function parseMileage(raw) {
  if (!raw) return null;
  const digits = fixEncoding(raw).replace(/[^\d]/g, '');
  const val = parseInt(digits);
  return isNaN(val) ? null : val;
}

// Liste des marques connues (ordre important : les plus longues en premier)
const BRANDS = [
  'Alfa Romeo', 'Aston Martin', 'Land Rover', 'Mercedes-Benz',
  'Rolls-Royce', 'Abarth',
  'Peugeot', 'Renault', 'Citroën', 'Citroen', 'Volkswagen', 'VW',
  'Mercedes', 'BMW', 'Audi', 'Toyota', 'Ford', 'Fiat', 'Volvo',
  'Opel', 'Seat', 'Skoda', 'Hyundai', 'Kia', 'Nissan', 'Honda',
  'Mazda', 'Dacia', 'Jeep', 'Subaru', 'Mitsubishi', 'Suzuki',
  'Porsche', 'Lexus', 'Infiniti', 'Maserati', 'Ferrari', 'Lamborghini',
  'Bentley', 'Tesla', 'Mini', 'Smart', 'Cupra', 'DS',
];

function extractBrandModel(rawTitle) {
  const title = fixEncoding(rawTitle || '').trim();
  const titleLower = title.toLowerCase();

  for (const brand of BRANDS) {
    if (titleLower.startsWith(brand.toLowerCase())) {
      const rest  = title.slice(brand.length).trim();
      const model = rest.split(/\s+/)[0] || '';
      return { marque: brand, modele: model };
    }
  }

  // Marque absente du titre (ex: "Clio 2 en l'état", "C4 Grand Picasso")
  // On tente de retrouver via des modèles connus
  const MODEL_TO_BRAND = {
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
  };

  const firstWord = titleLower.split(/\s+/)[0];
  if (MODEL_TO_BRAND[firstWord]) {
    return { marque: MODEL_TO_BRAND[firstWord], modele: title.split(/\s+/)[0] };
  }

  return { marque: null, modele: title.split(/\s+/)[0] || null };
}

// Résolution des fichiers à importer
const DATA_DIR = path.resolve('scripts/data');
let files = process.argv.slice(2).map(f => path.resolve(f));
if (files.length === 0) {
  // Aucun argument → tous les JSON du dossier data/
  files = fs.readdirSync(DATA_DIR)
    .filter(f => f.endsWith('.json'))
    .map(f => path.join(DATA_DIR, f));
  if (files.length === 0) {
    console.error('Aucun fichier JSON trouvé dans scripts/data/');
    process.exit(1);
  }
}

console.log(`Fichiers à importer : ${files.map(f => path.basename(f)).join(', ')}\n`);

const raw = files.flatMap(filePath => {
  console.log(`Lecture de ${path.basename(filePath)}...`);
  return JSON.parse(fs.readFileSync(filePath, 'utf8'));
});

const annonces = raw
  .filter(item => item['text-body-2'] && item['text-body-2 (2)']) // doit avoir année + km
  .map(item => {
    const { marque, modele } = extractBrandModel(item['text-body-1']);
    const prix       = parsePrice(item['text-callout']);
    const kilometrage = parseMileage(item['text-body-2 (2)']);
    const annee      = parseInt(item['text-body-2']);
    const carburant  = fixEncoding(item['text-body-2 (3)'] || '');

    const titre = fixEncoding(item['text-body-1'] || '').trim();
    return {
      titre,
      prix,
      kilometrage,
      date_voiture:  isNaN(annee) ? null : annee,
      marque,
      modele,
      modele_unifie: modele,
      lien_annonce:  item['absolute href']  || null,
      lien_image:    item['absolute src']   || null,
      source:        'LeBonCoin',
      carburant,
    };
  })
  .filter(a => a.prix && a.kilometrage && a.marque);

console.log(`${annonces.length} annonces valides sur ${raw.length} entrées`);
if (annonces.length === 0) process.exit(0);

// Aperçu des 3 premières
console.log('\nAperçu :');
annonces.slice(0, 3).forEach(a =>
  console.log(`  ${a.marque} ${a.modele} — ${a.prix}€ — ${a.kilometrage}km — ${a.date_voiture} — ${a.carburant}`)
);

// Insertion dans Supabase (par batch de 50)
let inserted = 0;
for (let i = 0; i < annonces.length; i += 50) {
  const batch = annonces.slice(i, i + 50);
  const res = await fetch(`${SUPABASE_URL}/rest/v1/annonces?on_conflict=lien_annonce`, {
    method: 'POST',
    headers: {
      'apikey':        SUPABASE_SERVICE_KEY,
      'Authorization': `Bearer ${SUPABASE_SERVICE_KEY}`,
      'Content-Type':  'application/json',
      'Prefer':        'resolution=ignore-duplicates,return=minimal',
    },
    body: JSON.stringify(batch),
  });

  if (!res.ok) {
    console.error(`Erreur batch ${i}-${i + batch.length}:`, await res.text());
  } else {
    inserted += batch.length;
    console.log(`Inséré : ${inserted}/${annonces.length}`);
  }
}

console.log('\nImport terminé.');
