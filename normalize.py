import json, os, re, unicodedata, logging
from difflib import get_close_matches

_DIR        = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(_DIR, "mytracks_raw.json")
MISSING_LOG = os.path.join(_DIR, "missing_models.log")

_handler = logging.FileHandler(MISSING_LOG, encoding="utf-8")
_handler.setFormatter(logging.Formatter("%(asctime)s  %(message)s", "%Y-%m-%d %H:%M"))
_log = logging.getLogger("missing_models")
_log.setLevel(logging.INFO)
if not _log.handlers:
    _log.addHandler(_handler)

_DB     = {}
_LOADED = False
FUZZY_THRESHOLD = 0.6


def _slug(s):
    """Lowercase, strip accents (é→e, ç→c, ë→e…), normalize separators."""
    if not s:
        return ""
    s = s.lower().strip()
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = s.replace("/", " ")
    s = re.sub(r"[-_\s]+", " ", s).strip()
    return s


def _is_short_or_numeric(s):
    """Retourne True si le slug est trop court ou purement numérique/alphanumérique
    court pour être fiable en fuzzy match (ex: '116', 'cls', '992')."""
    s = s.strip()
    if len(s) <= 4:
        return True
    if re.match(r'^[a-z0-9\s]{1,6}$', s) and re.search(r'\d', s):
        return True
    return False


def _load():
    global _DB, _LOADED
    if _LOADED:
        return
    if not os.path.exists(DB_PATH):
        print("Warning: mytracksraw.json not found")
        _LOADED = True
        return
    with open(DB_PATH, encoding="utf-8") as f:
        _DB = json.load(f)
    _LOADED = True


def normalize_make(marque):
    _load()
    if not marque or not _DB:
        return marque

    slug_in = _slug(marque)

    # 1. Exact slug match (gère les accents grâce à _slug)
    for make_display in _DB:
        if _slug(make_display) == slug_in:
            return make_display

    # 2. Aliases manuels pour abréviations et cas particuliers
    ALIASES = {
        "vw":            "Volkswagen",
        "mercedes benz": "Mercedes-Benz",
        "mercedes":      "Mercedes-Benz",
        "mb":            "Mercedes-Benz",
        "alfa":          "Alfa Romeo",
        "land rover":    "Land Rover",
        "landrover":     "Land Rover",
        "mg":            "MG/MG Motor",
        "mg motor":      "MG/MG Motor",
        "mg mg motor":   "MG/MG Motor",
        "bmw":           "BMW",
        "ds automobiles":"DS",
        "alfa-romeo":    "Alfa Romeo",
        "citroen":       "Citroën",
        "citroen":       "Citroën",
        "ds automobiles":"DS",
        "ds":            "DS",
        "mercedes":      "Mercedes-Benz",
        "mg":            "MG",
    }
    if slug_in in ALIASES and ALIASES[slug_in] in _DB:
        return ALIASES[slug_in]

    # 3. Fuzzy match sur les slugs de marques
    make_slugs = {_slug(m): m for m in _DB}
    matches = get_close_matches(slug_in, make_slugs.keys(), n=1, cutoff=0.8)
    if matches:
        return make_slugs[matches[0]]

    # 4. Substring
    for db_slug, db_display in make_slugs.items():
        if slug_in in db_slug or db_slug in slug_in:
            return db_display

    return marque


def normalize_model(marque, modele):
    _load()
    if not modele or not _DB:
        return modele

    make_display = normalize_make(marque)
    models_list  = _DB.get(make_display, [])
    if not models_list:
        _log.info("UNKNOWN_MAKE | %s | %s", marque, modele)
        return modele

    slug_in  = _slug(modele)
    slug_map = {_slug(m): m for m in models_list}

    # 1. Exact slug
    if slug_in in slug_map:
        return slug_map[slug_in]

    # 2. Sans tirets/underscores
    slug_clean = re.sub(r"[-_]+", " ", slug_in).strip()
    if slug_clean in slug_map:
        return slug_map[slug_clean]

    # 3. Sans espaces ("ds 3" → "ds3", "c3 aircross" → "c3aircross")
    nospace     = re.sub(r"\s+", "", slug_in)
    nospace_map = {re.sub(r"\s+", "", k): v for k, v in slug_map.items()}
    if nospace in nospace_map:
        return nospace_map[nospace]

    # 4. Fuzzy — désactivé pour les modèles courts ou numériques
    #    pour éviter 116→118, 992→924, CLS→CL, etc.
    if not _is_short_or_numeric(slug_in):
        matches = get_close_matches(slug_in, slug_map.keys(), n=1, cutoff=FUZZY_THRESHOLD)
        if matches:
            return slug_map[matches[0]]

    # 5. Substring DB dans input ("clio" dans "clio 5")
    for db_slug, db_model in sorted(slug_map.items(), key=lambda x: -len(x[0])):
        if len(db_slug) >= 2 and db_slug in slug_in:
            return db_model

    # 6. Substring input dans DB ("c3" dans "c3 aircross")
    for db_slug, db_model in sorted(slug_map.items(), key=lambda x: -len(x[0])):
        if len(slug_in) >= 2 and slug_in in db_slug:
            return db_model

    _log.info("%s | %s | %s", make_display, slug_in, modele)
    return modele


# ── GENERATION MAPPING ─────────────────────────────────────────────────

_GENERATIONS = {}
_GEN_LOADED  = False
GEN_PATH     = os.path.join(_DIR, "generations.json")


def _load_generations():
    global _GENERATIONS, _GEN_LOADED
    if _GEN_LOADED:
        return
    if not os.path.exists(GEN_PATH):
        print("Warning: generations.json not found")
        _GEN_LOADED = True
        return
    with open(GEN_PATH, encoding="utf-8") as f:
        _GENERATIONS = json.load(f)
    _GEN_LOADED = True


def get_generation(modele_unifie: str, annee) -> str:
    """
    Retourne le label de génération pour un modèle unifié et une année.
    Ex : get_generation("GOLF", 2015) → "Golf 7"
    Retourne "N/A" si introuvable.
    """
    _load_generations()
    if not modele_unifie or not _GENERATIONS:
        return "N/A"

    try:
        year = int(str(annee).strip()[:4])
    except (ValueError, TypeError):
        return "N/A"

    key  = modele_unifie.upper().strip()
    gens = _GENERATIONS.get(key)

    if not gens:
        for k, v in _GENERATIONS.items():
            if _slug(k) == _slug(key):
                gens = v
                break

    if not gens:
        return "N/A"

    for entry in gens:
        if entry["from"] <= year <= entry["to"]:
            return entry["gen"]

    return "N/A"