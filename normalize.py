import json, os, re, logging
from difflib import get_close_matches, SequenceMatcher

_DIR        = os.path.dirname(os.path.abspath(__file__))
DB_PATH     = os.path.join(_DIR, "mytracks_raw.json")
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
    if not s:
        return ""
    s = s.lower().strip()
    s = s.replace("/", " ")
    s = re.sub(r"[-_\s]+", " ", s).strip()
    return s


def _load():
    global _DB, _LOADED
    if _LOADED:
        return
    if not os.path.exists(DB_PATH):
        print("Warning: mytracks_raw.json not found")
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

    # Exact slug match — compare slug de l'input avec slug de chaque cle DB
    for make_display in _DB:
        if _slug(make_display) == slug_in:
            return make_display

    # Aliases manuels
    ALIASES = {
        "vw":           "Volkswagen",
        "mercedes benz":"Mercedes-Benz",
        "mercedes":     "Mercedes-Benz",
        "mb":           "Mercedes-Benz",
        "alfa":         "Alfa Romeo",
        "land rover":   "Land Rover",
        "landrover":    "Land Rover",
        "mg":           "MG/MG Motor",
        "mg motor":     "MG/MG Motor",
        "mg mg motor":  "MG/MG Motor",
    }
    if slug_in in ALIASES and ALIASES[slug_in] in _DB:
        return ALIASES[slug_in]

    # Fuzzy sur les slugs de marques
    make_slugs = {_slug(m): m for m in _DB}
    matches = get_close_matches(slug_in, make_slugs.keys(), n=1, cutoff=0.8)
    if matches:
        return make_slugs[matches[0]]

    # Substring
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

    # 1. Exact
    if slug_in in slug_map:
        return slug_map[slug_in]

    # 2. Sans separateurs
    slug_clean = re.sub(r"[-_]+", " ", slug_in).strip()
    if slug_clean in slug_map:
        return slug_map[slug_clean]

    # 3. Fuzzy
    matches = get_close_matches(slug_in, slug_map.keys(), n=1, cutoff=FUZZY_THRESHOLD)
    if matches:
        return slug_map[matches[0]]

    # 4. Substring DB dans input ("clio" dans "clio 5")
    for db_slug, db_model in sorted(slug_map.items(), key=lambda x: -len(x[0])):
        if len(db_slug) >= 2 and db_slug in slug_in:
            return db_model

    # 5. Substring input dans DB ("c3" dans "c3 aircross")
    for db_slug, db_model in sorted(slug_map.items(), key=lambda x: -len(x[0])):
        if len(slug_in) >= 2 and slug_in in db_slug:
            return db_model

    _log.info("%s | %s | %s", make_display, slug_in, modele)
    return modele