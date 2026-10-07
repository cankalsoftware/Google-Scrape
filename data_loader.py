"""
data_loader.py - Configuration & Reference Data Loader
Loads and manages domain mapping tables, search presets, dork cheatsheets, and open data registries.
Includes built-in default fallbacks to ensure zero crashes if external JSON files are modified or missing.
"""

import json
import os

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
DOMAINS_FILE = os.path.join(DATA_DIR, "domains.json")
PRESETS_FILE = os.path.join(DATA_DIR, "presets.json")
CHEATSHEET_FILE = os.path.join(DATA_DIR, "dorks_cheatsheet.json")
REGISTRY_SOURCES_FILE = os.path.join(DATA_DIR, "registry_sources.json")

# In-Memory Cache
_DOMAINS_CACHE = None
_PRESETS_CACHE = None
_CHEATSHEET_CACHE = None


def load_all_domains(reload: bool = False) -> dict:
    """Loads domain dictionaries from data/domains.json with cached in-memory access."""
    global _DOMAINS_CACHE
    if _DOMAINS_CACHE is not None and not reload:
        return _DOMAINS_CACHE

    if os.path.exists(DOMAINS_FILE):
        try:
            with open(DOMAINS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict) and len(data) > 0:
                    _DOMAINS_CACHE = data
                    return _DOMAINS_CACHE
        except Exception:
            pass

    # Fallback minimal default
    _DOMAINS_CACHE = {
        "fire_services": {"london fire brigade": "london-fire.gov.uk"},
        "nhs": {"nhs england": "england.nhs.uk"},
        "councils": {"birmingham city council": "birmingham.gov.uk"},
        "police": {"metropolitan police": "met.police.uk"},
        "environment": {"environment agency": "environment.data.gov.uk"},
        "transport_highways": {"national highways": "nationalhighways.co.uk"}
    }
    return _DOMAINS_CACHE


def get_domain_lookup(industry: str = "all") -> dict:
    """
    Returns a flattened dictionary of domain mappings for the requested industry sector.
    """
    domains = load_all_domains()
    ind = industry.lower() if industry else "all"

    if ind in ("nhs", "health", "hospital"):
        return domains.get("nhs", {})
    elif ind in ("council", "gov", "local_gov"):
        return domains.get("councils", {})
    elif ind in ("police", "constabulary", "law"):
        return domains.get("police", {})
    elif ind in ("waste", "environment", "recycling", "ea", "sepa", "nrw"):
        return domains.get("environment", {})
    elif ind in ("transport", "highways", "national_highways", "roads"):
        return domains.get("transport_highways", {})
    elif ind in ("tourism", "hospitality", "hotel", "hotels", "restaurant", "restaurants", "travel"):
        return domains.get("hospitality_tourism", {})
    elif ind in ("fire", "fire_services", "rescue"):
        return domains.get("fire_services", {})
    else:
        # Combined public sector, infrastructure and major sectors
        combined = {}
        for sector in ["fire_services", "environment", "transport_highways", "hospitality_tourism", "police", "nhs", "councils"]:
            combined.update(domains.get(sector, {}))
        return combined


def load_presets(reload: bool = False) -> dict:
    """Loads targeted and generalized search presets from data/presets.json."""
    global _PRESETS_CACHE
    if _PRESETS_CACHE is not None and not reload:
        return _PRESETS_CACHE

    if os.path.exists(PRESETS_FILE):
        try:
            with open(PRESETS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    _PRESETS_CACHE = data
                    return _PRESETS_CACHE
        except Exception:
            pass

    _PRESETS_CACHE = {"targeted_presets": {}, "generalized_presets": {}}
    return _PRESETS_CACHE


def get_preset_data(preset_key: str) -> tuple:
    """
    Retrieves preset configuration by key.
    Returns: (mode: str ['targeted'|'generalized'], config_dict: dict)
    """
    presets = load_presets()
    targeted = presets.get("targeted_presets", {})
    generalized = presets.get("generalized_presets", {})

    if preset_key in targeted:
        return "targeted", targeted[preset_key]
    elif preset_key in generalized:
        return "generalized", generalized[preset_key]
    return "unknown", {}


def load_cheatsheet(reload: bool = False) -> dict:
    """Loads search operators and dork cheat sheet examples from data/dorks_cheatsheet.json."""
    global _CHEATSHEET_CACHE
    if _CHEATSHEET_CACHE is not None and not reload:
        return _CHEATSHEET_CACHE

    if os.path.exists(CHEATSHEET_FILE):
        try:
            with open(CHEATSHEET_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    _CHEATSHEET_CACHE = data
                    return _CHEATSHEET_CACHE
        except Exception:
            pass

    _CHEATSHEET_CACHE = {"basic_operators": [], "dev_dorks": [], "security_dorks": [], "lead_gen_dorks": []}
    return _CHEATSHEET_CACHE


def load_registry_sources() -> list:
    """Loads open data register sources from data/registry_sources.json."""
    if os.path.exists(REGISTRY_SOURCES_FILE):
        try:
            with open(REGISTRY_SOURCES_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list) and len(data) > 0:
                    return data
        except Exception:
            pass
    return []


def save_registry_sources(sources_list: list) -> bool:
    """Saves updated registry sources list to data/registry_sources.json."""
    try:
        os.makedirs(os.path.dirname(REGISTRY_SOURCES_FILE), exist_ok=True)
        with open(REGISTRY_SOURCES_FILE, "w", encoding="utf-8") as f:
            json.dump(sources_list, f, indent=2)
        return True
    except Exception:
        return False
