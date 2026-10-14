#!/usr/bin/env python3

import asyncio
import base64
import hmac
import html
import io
import json
import math
import os
import shutil
import smtplib
import sqlite3
import subprocess
import sys
import threading
import time
import itertools
from collections import OrderedDict, deque
from email.message import EmailMessage

APP_VERSION = "2.0"

def _check_dependencies():
    """Explain missing packages instead of failing with a bare traceback."""
    import importlib.util
    needed = {"requests": "requests", "websockets": "websockets",
              "flask": "Flask", "PIL": "Pillow"}
    missing = [pkg for mod, pkg in needed.items() if importlib.util.find_spec(mod) is None]
    if not missing:
        return
    here = os.path.dirname(os.path.abspath(__file__))
    req = os.path.join(here, "requirements.txt")
    lines = [
        "",
        "Missing Python package(s): " + ", ".join(missing),
        f"Python in use: {sys.executable}",
        "",
    ]
    if os.name == "nt":
        lines += [
            "Easiest fix: start the monitor with run.bat - it installs everything",
            "automatically on first run.  Or install manually:",
            f'  "{sys.executable}" -m pip install -r "{req}"',
        ]
    else:
        lines += [
            "Install them with:",
            f'  "{sys.executable}" -m pip install -r "{req}"',
            "(or create the venv as described in README.md and use ./run.sh)",
        ]
    raise SystemExit("\n".join(lines) + "\n")


_check_dependencies()

import requests
import websockets


# ============================================================
# CONSOLE ENCODING
# ============================================================
# Reverse-geocoded locality names can contain Czech/Slovak/Polish etc.
# characters.  Some shells (notably when started via sudo/su with an
# inherited non-UTF-8 locale) expose stdout/stderr as latin-1.  Force UTF-8
# with a non-fatal fallback so logging can never terminate the collector.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="backslashreplace")
    except (AttributeError, ValueError):
        pass
from flask import Flask, jsonify, render_template, request, send_file
from werkzeug.serving import make_server
from PIL import Image, ImageDraw, ImageFont


# ============================================================
# CONFIGURATION (JSON)
# ============================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.environ.get(
    "LIGHTNING_CONFIG",
    os.path.join(BASE_DIR, "config.json"),
)


DEFAULT_CONFIG = {
    "monitoring": {
        "center_lat": 49.22577,
        "center_lon": 17.65461,
        "max_radius_km": 100.0,
        "window_seconds": 600,
        "history_retention_days": 30,
        "send_interval_seconds": 30,
    },
    "zabbix": {"enabled": True, "server": "10.56.8.222", "host": "lightning-monitor"},
    "lightningmaps": {"ws_url": "wss://live2.lightningmaps.org/"},
    "web": {
        "host": "0.0.0.0", "port": 8097, "allow_config_write": True, "allow_restart": True,
        "admin_password": "",
    },
    "smtp": {
        "enabled": True, "send_startup_email": True,
        "server": "192.168.1.20", "port": 25,
        "mail_from": "lightning@example.local", "mail_to": "you@example.com",
    },
    "alerts": {
        "warning_radius_km": 25.0, "critical_radius_km": 10.0,
        "warning_cooldown_seconds": 1800, "critical_cooldown_seconds": 900,
        "max_strike_age_seconds": 180,
    },
    "database": {"path": "lightning.db"},
    "map": {
        "sat_tile_url": "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        "snapshot_zoom": 9, "snapshot_width": 900, "snapshot_height": 620, "tile_size": 256,
        "font_path": "",
    },
    "geocoding": {
        "enabled": True, "url": "https://nominatim.openstreetmap.org/reverse",
        "user_agent": "lightning-monitor/1.1", "timeout_seconds": 6,
        "min_interval_seconds": 1.1, "cache_decimals": 3,
        "backfill_history_on_start": True, "backfill_batch_size": 250, "queue_maxsize": 2000,
    },
    "localization": {"default_language": "en", "email_language": "en"},
    "intelligence": {
        "analysis_window_minutes": 30, "trend_slice_minutes": 10,
        "approaching_delta_km": 5.0, "activity_increase_ratio": 1.5,
        "burst_count_25km_10min": 5, "significant_closer_km": 5.0,
        "min_smart_resend_seconds": 300, "ws_stale_seconds": 120,
        "geocoder_retry_attempts": 3, "geocoder_retry_backoff_seconds": 15,
    },
}

CONFIG_LOCK = threading.RLock()


def _fill_missing(target, defaults):
    """Add only missing default keys. Existing user values are never overwritten."""
    changed = False
    for key, default in defaults.items():
        if key not in target:
            target[key] = json.loads(json.dumps(default))
            changed = True
        elif isinstance(default, dict) and isinstance(target.get(key), dict):
            changed = _fill_missing(target[key], default) or changed
    return changed


def _write_config(config):
    """Atomic UTF-8 config write; safe against partial/truncated JSON files."""
    directory = os.path.dirname(os.path.abspath(CONFIG_PATH)) or "."
    os.makedirs(directory, exist_ok=True)
    tmp = CONFIG_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(config, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, CONFIG_PATH)


def load_config():
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as fh:
            config = json.load(fh)
    except FileNotFoundError:
        raise SystemExit(
            f"Configuration file not found: {CONFIG_PATH}. "
            "Copy config.example.json to config.json and edit it."
        )
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid JSON in {CONFIG_PATH}: {exc}")

    if not isinstance(config, dict):
        raise SystemExit(f"Invalid configuration in {CONFIG_PATH}: root must be a JSON object")

    # Upgrade old configs in place: add new/missing options, preserve every existing value.
    if _fill_missing(config, DEFAULT_CONFIG):
        try:
            _write_config(config)
            print(f"Configuration upgraded with missing defaults: {CONFIG_PATH}", flush=True)
        except OSError as exc:
            # The monitor can still run from the merged in-memory config if the file is read-only.
            print(f"CONFIG WARNING: could not write missing defaults: {exc}", flush=True)
    return config

CONFIG = load_config()

# Monitoring
MON = CONFIG["monitoring"]
CENTER_LAT = float(MON["center_lat"])
CENTER_LON = float(MON["center_lon"])
MAX_RADIUS_KM = float(MON["max_radius_km"])
WINDOW_SECONDS = int(MON["window_seconds"])
HISTORY_RETENTION_DAYS = int(MON["history_retention_days"])
SEND_INTERVAL = int(MON["send_interval_seconds"])

# Zabbix
ZBX = CONFIG["zabbix"]
ZABBIX_ENABLED = bool(ZBX.get("enabled", True))
ZABBIX_SERVER = str(ZBX["server"])
ZABBIX_HOST = str(ZBX["host"])

# LightningMaps WebSocket
LGT = CONFIG["lightningmaps"]
WS_URL = str(LGT["ws_url"])

# Web dashboard
WEB = CONFIG["web"]
WEB_HOST = str(WEB["host"])
WEB_PORT = int(WEB["port"])

# SMTP
SMTP_CFG = CONFIG["smtp"]
SMTP_ENABLED = bool(SMTP_CFG.get("enabled", True))
SMTP_SEND_STARTUP = bool(SMTP_CFG.get("send_startup_email", True))
SMTP_SERVER = str(SMTP_CFG["server"])
SMTP_PORT = int(SMTP_CFG["port"])
MAIL_FROM = str(SMTP_CFG["mail_from"])
MAIL_TO = str(SMTP_CFG["mail_to"])

# Alerts
ALERT = CONFIG["alerts"]
WARNING_RADIUS_KM = float(ALERT["warning_radius_km"])
CRITICAL_RADIUS_KM = float(ALERT["critical_radius_km"])
WARNING_COOLDOWN = int(ALERT["warning_cooldown_seconds"])
CRITICAL_COOLDOWN = int(ALERT["critical_cooldown_seconds"])
ALERT_MAX_STRIKE_AGE_SECONDS = int(ALERT["max_strike_age_seconds"])

# Database
DB_CFG = CONFIG["database"]
_db_path = str(DB_CFG["path"])
DB_PATH = _db_path if os.path.isabs(_db_path) else os.path.join(BASE_DIR, _db_path)

# Satellite snapshot
MAP = CONFIG["map"]
SAT_TILE_URL = str(MAP["sat_tile_url"])
SNAPSHOT_ZOOM = int(MAP["snapshot_zoom"])
SNAPSHOT_WIDTH = int(MAP["snapshot_width"])
SNAPSHOT_HEIGHT = int(MAP["snapshot_height"])
TILE_SIZE = int(MAP["tile_size"])

# Reverse geocoding
GEO = CONFIG["geocoding"]
GEOCODING_ENABLED = bool(GEO["enabled"])
GEOCODER_URL = str(GEO["url"])
GEOCODER_USER_AGENT = str(GEO["user_agent"])
GEOCODER_TIMEOUT = float(GEO["timeout_seconds"])
GEOCODER_MIN_INTERVAL = float(GEO["min_interval_seconds"])
GEOCODER_CACHE_DECIMALS = int(GEO["cache_decimals"])
GEOCODER_BACKFILL_HISTORY = bool(GEO.get("backfill_history_on_start", True))
GEOCODER_BACKFILL_BATCH_SIZE = int(GEO.get("backfill_batch_size", 250))
GEOCODER_QUEUE_MAXSIZE = int(GEO.get("queue_maxsize", 2000))

# Localization
# ISO 639-1 uses "cs" for Czech.  "cz" is still accepted for backward
# compatibility with older config files and dashboard bookmarks.
def normalize_language(value, fallback="en"):
    value = str(value or "").strip().lower().replace("_", "-")
    if value in ("cz", "cs", "cs-cz"):
        return "cs"
    if value in ("en", "en-gb", "en-us"):
        return "en"
    return fallback

L10N = CONFIG.get("localization", {})
DEFAULT_LANGUAGE = normalize_language(L10N.get("default_language", "en"))
EMAIL_LANGUAGE = normalize_language(L10N.get("email_language", DEFAULT_LANGUAGE), DEFAULT_LANGUAGE)

# Storm intelligence / health
INTEL = CONFIG.get("intelligence", {})
ANALYSIS_WINDOW_MINUTES = int(INTEL.get("analysis_window_minutes", 30))
TREND_SLICE_MINUTES = int(INTEL.get("trend_slice_minutes", 10))
APPROACHING_DELTA_KM = float(INTEL.get("approaching_delta_km", 5.0))
ACTIVITY_INCREASE_RATIO = float(INTEL.get("activity_increase_ratio", 1.5))
BURST_COUNT_25KM = int(INTEL.get("burst_count_25km_10min", 5))
SIGNIFICANT_CLOSER_KM = float(INTEL.get("significant_closer_km", 5.0))
MIN_SMART_RESEND_SECONDS = int(INTEL.get("min_smart_resend_seconds", 300))
WS_STALE_SECONDS = int(INTEL.get("ws_stale_seconds", 120))
GEOCODER_RETRY_ATTEMPTS = int(INTEL.get("geocoder_retry_attempts", 3))
GEOCODER_RETRY_BACKOFF_SECONDS = int(INTEL.get("geocoder_retry_backoff_seconds", 15))


RESTART_REQUIRED_PATHS = {
    "web.host", "web.port", "database.path", "geocoding.queue_maxsize"
}


def _coerce_config_value(value, default, path):
    """Validate dashboard config edits using the type of the shipped default."""
    if isinstance(default, bool):
        if isinstance(value, bool):
            return value
        raise ValueError(f"{path} must be true or false")
    if isinstance(default, int) and not isinstance(default, bool):
        if isinstance(value, bool):
            raise ValueError(f"{path} must be an integer")
        try:
            return int(value)
        except (TypeError, ValueError):
            raise ValueError(f"{path} must be an integer")
    if isinstance(default, float):
        try:
            return float(value)
        except (TypeError, ValueError):
            raise ValueError(f"{path} must be a number")
    if isinstance(default, str):
        if not isinstance(value, str):
            raise ValueError(f"{path} must be text")
        return value
    return value


def _merge_user_update(target, update, defaults, prefix=""):
    """Merge known config keys only and return the changed dotted paths."""
    if not isinstance(update, dict):
        raise ValueError("Configuration update must be a JSON object")
    changed = []
    for key, value in update.items():
        path = f"{prefix}.{key}" if prefix else key
        if key not in defaults:
            raise ValueError(f"Unknown configuration key: {path}")
        default = defaults[key]
        if isinstance(default, dict):
            if not isinstance(value, dict):
                raise ValueError(f"{path} must be an object")
            if key not in target or not isinstance(target[key], dict):
                target[key] = {}
            changed.extend(_merge_user_update(target[key], value, default, path))
        else:
            coerced = _coerce_config_value(value, default, path)
            if target.get(key) != coerced:
                target[key] = coerced
                changed.append(path)
    return changed


def apply_runtime_config():
    """Apply settings that are safe to change while the collector is running."""
    global CENTER_LAT, CENTER_LON, MAX_RADIUS_KM, WINDOW_SECONDS, HISTORY_RETENTION_DAYS, SEND_INTERVAL
    global ZABBIX_ENABLED, ZABBIX_SERVER, ZABBIX_HOST, WS_URL
    global SMTP_ENABLED, SMTP_SEND_STARTUP, SMTP_SERVER, SMTP_PORT, MAIL_FROM, MAIL_TO
    global WARNING_RADIUS_KM, CRITICAL_RADIUS_KM, WARNING_COOLDOWN, CRITICAL_COOLDOWN, ALERT_MAX_STRIKE_AGE_SECONDS
    global SAT_TILE_URL, SNAPSHOT_ZOOM, SNAPSHOT_WIDTH, SNAPSHOT_HEIGHT, TILE_SIZE
    global GEOCODING_ENABLED, GEOCODER_URL, GEOCODER_USER_AGENT, GEOCODER_TIMEOUT, GEOCODER_MIN_INTERVAL
    global GEOCODER_CACHE_DECIMALS, GEOCODER_BACKFILL_HISTORY, GEOCODER_BACKFILL_BATCH_SIZE
    global DEFAULT_LANGUAGE, EMAIL_LANGUAGE
    global ANALYSIS_WINDOW_MINUTES, TREND_SLICE_MINUTES, APPROACHING_DELTA_KM, ACTIVITY_INCREASE_RATIO
    global BURST_COUNT_25KM, SIGNIFICANT_CLOSER_KM, MIN_SMART_RESEND_SECONDS, WS_STALE_SECONDS
    global GEOCODER_RETRY_ATTEMPTS, GEOCODER_RETRY_BACKOFF_SECONDS

    mon = CONFIG["monitoring"]
    CENTER_LAT = float(mon["center_lat"]); CENTER_LON = float(mon["center_lon"])
    MAX_RADIUS_KM = float(mon["max_radius_km"]); WINDOW_SECONDS = int(mon["window_seconds"])
    HISTORY_RETENTION_DAYS = int(mon["history_retention_days"]); SEND_INTERVAL = int(mon["send_interval_seconds"])

    zbx = CONFIG["zabbix"]; ZABBIX_ENABLED = bool(zbx["enabled"])
    ZABBIX_SERVER = str(zbx["server"]); ZABBIX_HOST = str(zbx["host"])
    WS_URL = str(CONFIG["lightningmaps"]["ws_url"])
    smtp = CONFIG["smtp"]; SMTP_ENABLED = bool(smtp["enabled"]); SMTP_SEND_STARTUP = bool(smtp["send_startup_email"])
    SMTP_SERVER = str(smtp["server"]); SMTP_PORT = int(smtp["port"])
    MAIL_FROM = str(smtp["mail_from"]); MAIL_TO = str(smtp["mail_to"])

    alert = CONFIG["alerts"]
    WARNING_RADIUS_KM = float(alert["warning_radius_km"]); CRITICAL_RADIUS_KM = float(alert["critical_radius_km"])
    WARNING_COOLDOWN = int(alert["warning_cooldown_seconds"]); CRITICAL_COOLDOWN = int(alert["critical_cooldown_seconds"])
    ALERT_MAX_STRIKE_AGE_SECONDS = int(alert["max_strike_age_seconds"])

    mp = CONFIG["map"]
    SAT_TILE_URL = str(mp["sat_tile_url"]); SNAPSHOT_ZOOM = int(mp["snapshot_zoom"])
    SNAPSHOT_WIDTH = int(mp["snapshot_width"]); SNAPSHOT_HEIGHT = int(mp["snapshot_height"]); TILE_SIZE = int(mp["tile_size"])

    geo = CONFIG["geocoding"]
    GEOCODING_ENABLED = bool(geo["enabled"]); GEOCODER_URL = str(geo["url"]); GEOCODER_USER_AGENT = str(geo["user_agent"])
    GEOCODER_TIMEOUT = float(geo["timeout_seconds"]); GEOCODER_MIN_INTERVAL = float(geo["min_interval_seconds"])
    GEOCODER_CACHE_DECIMALS = int(geo["cache_decimals"]); GEOCODER_BACKFILL_HISTORY = bool(geo["backfill_history_on_start"])
    GEOCODER_BACKFILL_BATCH_SIZE = int(geo["backfill_batch_size"])

    loc = CONFIG["localization"]
    DEFAULT_LANGUAGE = normalize_language(loc.get("default_language", "en"))
    EMAIL_LANGUAGE = normalize_language(loc.get("email_language", DEFAULT_LANGUAGE), DEFAULT_LANGUAGE)
    # Canonicalize legacy cz -> cs when settings are saved.
    loc["default_language"] = DEFAULT_LANGUAGE; loc["email_language"] = EMAIL_LANGUAGE

    intel = CONFIG["intelligence"]
    ANALYSIS_WINDOW_MINUTES = int(intel["analysis_window_minutes"]); TREND_SLICE_MINUTES = int(intel["trend_slice_minutes"])
    APPROACHING_DELTA_KM = float(intel["approaching_delta_km"]); ACTIVITY_INCREASE_RATIO = float(intel["activity_increase_ratio"])
    BURST_COUNT_25KM = int(intel["burst_count_25km_10min"]); SIGNIFICANT_CLOSER_KM = float(intel["significant_closer_km"])
    MIN_SMART_RESEND_SECONDS = int(intel["min_smart_resend_seconds"]); WS_STALE_SECONDS = int(intel["ws_stale_seconds"])
    GEOCODER_RETRY_ATTEMPTS = int(intel["geocoder_retry_attempts"]); GEOCODER_RETRY_BACKOFF_SECONDS = int(intel["geocoder_retry_backoff_seconds"])


# ============================================================
# RUNTIME STATE
# ============================================================

strikes = deque()
seen_keys = {}
state_lock = threading.Lock()

last_strike_time = None
last_strike_distance = None
last_warning_email = 0
last_critical_email = 0

ws_connected = False
last_ws_message_time = None
startup_time = time.time()
last_email_status = "not sent"

geocode_lock = threading.Lock()
last_geocode_request_monotonic = 0.0
geocode_queue = None
geocode_sequence = itertools.count()

last_alert_level = "NONE"
last_alert_distance = None
last_alert_time = 0.0
last_zabbix_ok = None
last_zabbix_time = None
last_zabbix_error = None
last_geocoder_ok = None
last_geocoder_time = None
last_geocoder_error = None

# Alert / Zabbix coalescing.  A burst of strikes produces one alert check
# (for the closest strike in the burst) and one immediate Zabbix push,
# instead of one blocking SMTP/geocode/tile round-trip per strike.
pending_alert = None
alert_event = None
zabbix_now_event = None
background_tasks = set()

# Satellite tiles are reused between snapshots (startup mail, alerts, web).
TILE_CACHE_MAX = 256
TILE_CACHE_TTL = 24 * 3600
tile_cache = OrderedDict()
tile_cache_lock = threading.Lock()


class GeocoderError(Exception):
    """Transport / HTTP failure talking to the reverse geocoder (retryable)."""


# Stored in strikes.locality when the geocoder answered but found no place
# (e.g. open water).  Prevents the backfill from asking again forever.
NO_LOCALITY = "—"


# ============================================================
# FLASK
# ============================================================

app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, "templates"),
    static_folder=os.path.join(BASE_DIR, "static"),
)


# ============================================================
# DATABASE
# ============================================================

def db_connect():
    con = sqlite3.connect(DB_PATH, timeout=15)
    con.row_factory = sqlite3.Row
    return con


def init_db():
    with db_connect() as con:
        # WAL lets the dashboard read while the collector writes.
        try:
            con.execute("PRAGMA journal_mode=WAL")
        except sqlite3.DatabaseError as exc:
            print("DB WAL WARNING:", repr(exc), flush=True)
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS strikes (
                strike_key TEXT PRIMARY KEY,
                ts REAL NOT NULL,
                lat REAL NOT NULL,
                lon REAL NOT NULL,
                distance_km REAL NOT NULL,
                locality TEXT
            )
            """
        )

        # Automatic migration for an existing lightning.db created by
        # an older version of the dashboard.
        columns = {row[1] for row in con.execute("PRAGMA table_info(strikes)")}
        if "locality" not in columns:
            con.execute("ALTER TABLE strikes ADD COLUMN locality TEXT")

        con.execute(
            """
            CREATE TABLE IF NOT EXISTS geocode_cache (
                cache_key TEXT PRIMARY KEY,
                lat REAL NOT NULL,
                lon REAL NOT NULL,
                locality TEXT NOT NULL,
                updated_ts REAL NOT NULL
            )
            """
        )
        con.execute("CREATE INDEX IF NOT EXISTS idx_strikes_ts ON strikes(ts)")
        con.commit()


def store_strike(strike_key, ts, lat, lon, dist, locality=None):
    try:
        with db_connect() as con:
            con.execute(
                "INSERT OR IGNORE INTO strikes("
                "strike_key, ts, lat, lon, distance_km, locality"
                ") VALUES (?, ?, ?, ?, ?, ?)",
                (strike_key, ts, lat, lon, dist, locality),
            )
            con.commit()
    except Exception as exc:
        print("DB STORE ERROR:", repr(exc), flush=True)


def update_strike_locality(strike_key, locality):
    if not locality:
        return
    try:
        with db_connect() as con:
            con.execute(
                "UPDATE strikes SET locality = ? WHERE strike_key = ?",
                (locality, strike_key),
            )
            con.commit()
    except Exception as exc:
        print("DB LOCALITY UPDATE ERROR:", repr(exc), flush=True)


def purge_old_history():
    cutoff = time.time() - HISTORY_RETENTION_DAYS * 86400
    try:
        with db_connect() as con:
            con.execute("DELETE FROM strikes WHERE ts < ?", (cutoff,))
            con.commit()
    except Exception as exc:
        print("DB PURGE ERROR:", repr(exc), flush=True)


def load_recent_state():
    global last_strike_time, last_strike_distance

    now = time.time()
    cutoff = now - WINDOW_SECONDS

    try:
        with db_connect() as con:
            recent = con.execute(
                "SELECT strike_key, ts, lat, lon, distance_km "
                "FROM strikes WHERE ts >= ? ORDER BY ts ASC",
                (cutoff,),
            ).fetchall()

            latest = con.execute(
                "SELECT ts, distance_km FROM strikes ORDER BY ts DESC LIMIT 1"
            ).fetchone()

        with state_lock:
            for row in recent:
                strikes.append(
                    (
                        float(row["ts"]),
                        float(row["lat"]),
                        float(row["lon"]),
                        float(row["distance_km"]),
                        row["strike_key"],
                    )
                )
                seen_keys[row["strike_key"]] = float(row["ts"])

            if latest:
                last_strike_time = float(latest["ts"])
                last_strike_distance = float(latest["distance_km"])

    except Exception as exc:
        print("DB LOAD ERROR:", repr(exc), flush=True)


# ============================================================
# GEOGRAPHY
# ============================================================

def distance_km(lat1, lon1, lat2, lon2):
    earth_radius = 6371.0088
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)

    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(p1) * math.cos(p2) * math.sin(dlon / 2) ** 2
    )
    return 2 * earth_radius * math.asin(math.sqrt(a))


def bounding_box(lat, lon, radius_km):
    radius_km *= 1.10
    dlat = radius_km / 111.32
    dlon = radius_km / (111.32 * math.cos(math.radians(lat)))
    return [lat + dlat, lon + dlon, lat - dlat, lon - dlon]


def latlon_to_world_pixel(lat, lon, zoom):
    lat = max(min(lat, 85.05112878), -85.05112878)
    scale = TILE_SIZE * (2 ** zoom)
    x = (lon + 180.0) / 360.0 * scale
    sin_lat = math.sin(math.radians(lat))
    y = (
        0.5
        - math.log((1 + sin_lat) / (1 - sin_lat)) / (4 * math.pi)
    ) * scale
    return x, y


def km_to_pixels(km, lat, zoom):
    meters_per_pixel = (
        156543.03392 * math.cos(math.radians(lat)) / (2 ** zoom)
    )
    return (km * 1000.0) / meters_per_pixel


# ============================================================
# REVERSE GEOCODING (COORDINATES -> LOCALITY)
# ============================================================

def geocode_cache_key(lat, lon):
    return f"{lat:.{GEOCODER_CACHE_DECIMALS}f},{lon:.{GEOCODER_CACHE_DECIMALS}f}"


def format_locality(address, display_name=None):
    primary = (
        address.get("city")
        or address.get("town")
        or address.get("village")
        or address.get("municipality")
        or address.get("hamlet")
        or address.get("suburb")
        or address.get("county")
    )
    region = address.get("state") or address.get("region")
    country = address.get("country")

    parts = []
    for value in (primary, region, country):
        if value and value not in parts:
            parts.append(value)

    if parts:
        return ", ".join(parts)

    if display_name:
        return ", ".join(part.strip() for part in display_name.split(",")[:3])

    return None


def _geocode_cache_get(cache_key):
    try:
        with db_connect() as con:
            row = con.execute(
                "SELECT locality FROM geocode_cache WHERE cache_key = ?",
                (cache_key,),
            ).fetchone()
        return row["locality"] if row else None
    except Exception as exc:
        print("GEOCODE CACHE READ ERROR:", repr(exc), flush=True)
        return None


def reverse_geocode_locality(lat, lon):
    """Return a locality name, NO_LOCALITY when the place has no name, or None
    when geocoding is disabled.  Raises GeocoderError on retryable failures
    (timeouts, HTTP 429/5xx, bad JSON)."""
    global last_geocode_request_monotonic

    if not GEOCODING_ENABLED:
        return None

    cache_key = geocode_cache_key(lat, lon)
    cached = _geocode_cache_get(cache_key)
    if cached:
        return cached

    # Serialize uncached calls and keep the public geocoder at a gentle rate.
    with geocode_lock:
        # Another thread may have populated the cache while we waited.
        cached = _geocode_cache_get(cache_key)
        if cached:
            return cached

        wait = GEOCODER_MIN_INTERVAL - (time.monotonic() - last_geocode_request_monotonic)
        if wait > 0:
            time.sleep(wait)

        try:
            response = requests.get(
                GEOCODER_URL,
                params={
                    "format": "jsonv2",
                    "lat": f"{lat:.6f}",
                    "lon": f"{lon:.6f}",
                    "zoom": 14,
                    "addressdetails": 1,
                },
                headers={"User-Agent": GEOCODER_USER_AGENT},
                timeout=GEOCODER_TIMEOUT,
            )
            response.raise_for_status()
            payload = response.json()
        except Exception as exc:
            raise GeocoderError(str(exc)) from exc
        finally:
            last_geocode_request_monotonic = time.monotonic()

        if not isinstance(payload, dict):
            raise GeocoderError("unexpected geocoder response")

        # Nominatim answers {"error": "Unable to geocode"} for open water etc.
        locality = None
        if not payload.get("error"):
            locality = format_locality(
                payload.get("address") or {},
                payload.get("display_name"),
            )
        locality = locality or NO_LOCALITY

        try:
            with db_connect() as con:
                con.execute(
                    "INSERT OR REPLACE INTO geocode_cache("
                    "cache_key, lat, lon, locality, updated_ts"
                    ") VALUES (?, ?, ?, ?, ?)",
                    (cache_key, lat, lon, locality, time.time()),
                )
                con.commit()
        except Exception as exc:
            print("GEOCODE CACHE WRITE ERROR:", repr(exc), flush=True)

        return locality


def locality_for_display(locality, unknown):
    return unknown if not locality or locality == NO_LOCALITY else locality


# ============================================================
# SATELLITE SNAPSHOT FOR EMAIL / WEB
# ============================================================


def load_snapshot_font(size=20, bold=False):
    """Load a TrueType font with Central-European glyph support.

    Raspberry Pi OS normally ships DejaVu Sans.  We also try common Noto and
    Liberation locations.  An optional map.font_path in config can override
    these without making the project depend on a particular install directory.
    """
    configured = str(CONFIG["map"].get("font_path", "")).strip()
    candidates = []
    if configured:
        candidates.append(configured if os.path.isabs(configured) else os.path.join(BASE_DIR, configured))

    if bold:
        candidates.extend([
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            "/Library/Fonts/Arial Bold.ttf",
            os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", "segoeuib.ttf"),
            os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", "arialbd.ttf"),
        ])
    else:
        candidates.extend([
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
            "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            "/Library/Fonts/Arial.ttf",
            os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", "segoeui.ttf"),
            os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", "arial.ttf"),
        ])

    for path in candidates:
        try:
            if path and os.path.isfile(path):
                return ImageFont.truetype(path, size=size)
        except Exception:
            pass

    # Pillow's built-in fallback is kept only as a last resort.
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def fit_snapshot_label(draw, text, font, max_width):
    """Trim a label only if it cannot fit in the available map width."""
    if draw.textbbox((0, 0), text, font=font)[2] <= max_width:
        return text
    ellipsis = "…"
    while text and draw.textbbox((0, 0), text + ellipsis, font=font)[2] > max_width:
        text = text[:-1]
    return text.rstrip() + ellipsis


def fetch_tile(z, x, y):
    n = 2 ** z
    x = x % n
    if y < 0 or y >= n:
        return None

    url = SAT_TILE_URL.format(z=z, x=x, y=y)
    now = time.time()
    with tile_cache_lock:
        hit = tile_cache.get(url)
        if hit and now - hit[0] < TILE_CACHE_TTL:
            tile_cache.move_to_end(url)
            return hit[1].copy()

    response = requests.get(
        url,
        timeout=8,
        headers={"User-Agent": f"lightning-monitor/{APP_VERSION}"},
    )
    response.raise_for_status()
    tile = Image.open(io.BytesIO(response.content)).convert("RGB")

    with tile_cache_lock:
        tile_cache[url] = (now, tile)
        tile_cache.move_to_end(url)
        while len(tile_cache) > TILE_CACHE_MAX:
            tile_cache.popitem(last=False)
    return tile.copy()


def alert_rings():
    """Rings drawn on the web map and PNG snapshot, derived from config."""
    rings = [
        (MAX_RADIUS_KM, "outer"),
        (50.0, "monitor"),
        (WARNING_RADIUS_KM, "warning"),
        (CRITICAL_RADIUS_KM, "critical"),
    ]
    out, seen = [], set()
    for radius, kind in rings:
        key = round(radius, 3)
        if radius <= 0 or radius > MAX_RADIUS_KM or key in seen:
            continue
        seen.add(key)
        out.append((radius, kind))
    return sorted(out, key=lambda r: -r[0])


def zone_for_distance(distance):
    if distance <= CRITICAL_RADIUS_KM:
        return "critical"
    if distance <= WARNING_RADIUS_KM:
        return "warning"
    if distance <= 50:
        return "monitor"
    return "regional"


def build_map_snapshot(strike_lat=None, strike_lon=None, strike_distance=None, strike_locality=None, language=None):
    zoom = SNAPSHOT_ZOOM
    width = SNAPSHOT_WIDTH
    height = SNAPSHOT_HEIGHT

    center_x, center_y = latlon_to_world_pixel(CENTER_LAT, CENTER_LON, zoom)
    left = center_x - width / 2
    top = center_y - height / 2
    right = center_x + width / 2
    bottom = center_y + height / 2

    tx0 = math.floor(left / TILE_SIZE)
    ty0 = math.floor(top / TILE_SIZE)
    tx1 = math.floor(right / TILE_SIZE)
    ty1 = math.floor(bottom / TILE_SIZE)

    canvas = Image.new("RGB", (width, height), (32, 39, 49))

    for ty in range(ty0, ty1 + 1):
        for tx in range(tx0, tx1 + 1):
            try:
                tile = fetch_tile(zoom, tx, ty)
                if tile is None:
                    continue
                px = int(tx * TILE_SIZE - left)
                py = int(ty * TILE_SIZE - top)
                canvas.paste(tile, (px, py))
            except Exception as exc:
                print(f"MAP TILE ERROR z={zoom} x={tx} y={ty}: {exc}", flush=True)

    draw = ImageDraw.Draw(canvas, "RGBA")

    # Alert rings around monitored location.
    cx = width / 2
    cy = height / 2
    ring_colors = {
        "outer": (255, 255, 255, 70),
        "monitor": (255, 203, 61, 100),
        "warning": (255, 153, 0, 150),
        "critical": (255, 61, 61, 190),
    }
    for radius_km, kind in alert_rings():
        r = km_to_pixels(radius_km, CENTER_LAT, zoom)
        draw.ellipse((cx - r, cy - r, cx + r, cy + r), outline=ring_colors[kind], width=3)

    # Other strikes from the live window give context (storm cell shape).
    dot_colors = {
        "critical": (255, 77, 90, 210),
        "warning": (255, 139, 56, 200),
        "monitor": (255, 189, 67, 180),
        "regional": (255, 255, 255, 150),
    }
    with state_lock:
        context = [(s[1], s[2], s[3]) for s in strikes]
    for c_lat, c_lon, c_dist in context[-400:]:
        px_world, py_world = latlon_to_world_pixel(c_lat, c_lon, zoom)
        px, py = px_world - left, py_world - top
        if -5 <= px <= width + 5 and -5 <= py <= height + 5:
            draw.ellipse((px - 3, py - 3, px + 3, py + 3), fill=dot_colors[zone_for_distance(c_dist)])

    # Monitored point.
    draw.ellipse((cx - 8, cy - 8, cx + 8, cy + 8), fill=(56, 189, 248, 255), outline=(255, 255, 255, 255), width=2)
    draw.line((cx - 14, cy, cx + 14, cy), fill=(255, 255, 255, 220), width=2)
    draw.line((cx, cy - 14, cx, cy + 14), fill=(255, 255, 255, 220), width=2)

    # Strike point.
    if strike_lat is not None and strike_lon is not None:
        sx_world, sy_world = latlon_to_world_pixel(strike_lat, strike_lon, zoom)
        sx = sx_world - left
        sy = sy_world - top
        draw.ellipse((sx - 12, sy - 12, sx + 12, sy + 12), fill=(255, 49, 49, 230), outline=(255, 255, 255, 255), width=3)
        draw.line((sx - 18, sy, sx + 18, sy), fill=(255, 255, 255, 230), width=3)
        draw.line((sx, sy - 18, sx, sy + 18), fill=(255, 255, 255, 230), width=3)

        lang = (language or DEFAULT_LANGUAGE).lower()
        strike_word = "Blesk" if normalize_language(lang) == "cs" else "Lightning"
        label = f"{strike_word} {strike_distance:.1f} km" if strike_distance is not None else strike_word
        if strike_locality and strike_locality != NO_LOCALITY:
            label += f" · {strike_locality}"

        # Use a real Unicode TrueType font so Czech/Slovak locality names
        # (Č, č, Š, š, Ž, ž, ě, ř, ů, etc.) render correctly in the PNG.
        label_font = load_snapshot_font(size=20, bold=True)
        box_left = 18
        box_right = width - 18
        box_bottom = height - 18
        box_top = height - 72
        text_x = box_left + 16
        text_y = box_top + 15
        max_text_width = box_right - text_x - 16
        label = fit_snapshot_label(draw, label, label_font, max_text_width)

        # Higher-opacity background + larger bold text for legibility over
        # detailed satellite imagery.  A subtle text stroke further separates
        # glyphs from the background without making the banner visually heavy.
        draw.rounded_rectangle(
            (box_left, box_top, box_right, box_bottom),
            radius=12,
            fill=(0, 0, 0, 220),
            outline=(255, 255, 255, 55),
            width=1,
        )
        draw.text(
            (text_x, text_y),
            label,
            font=label_font,
            fill=(255, 255, 255, 255),
            stroke_width=1,
            stroke_fill=(0, 0, 0, 255),
        )

    out = io.BytesIO()
    canvas.save(out, format="PNG", optimize=True)
    return out.getvalue()


# ============================================================
# CLEANUP IN-MEMORY WINDOW / DEDUPE
# ============================================================

def cleanup():
    cutoff = time.time() - WINDOW_SECONDS
    dedupe_cutoff = time.time() - max(WINDOW_SECONDS, 15 * 60)

    with state_lock:
        while strikes and strikes[0][0] < cutoff:
            strikes.popleft()

        old_keys = [key for key, ts in seen_keys.items() if ts < dedupe_cutoff]
        for key in old_keys:
            seen_keys.pop(key, None)


# ============================================================
# STORM INTELLIGENCE / HEALTH
# ============================================================

def _db_recent_strikes(window_minutes):
    cutoff = time.time() - max(1, int(window_minutes)) * 60
    with db_connect() as con:
        return con.execute(
            "SELECT ts, lat, lon, distance_km, locality FROM strikes "
            "WHERE ts >= ? ORDER BY ts ASC",
            (cutoff,),
        ).fetchall()


def calculate_storm_intelligence():
    """Summarize recent activity and whether the storm is moving closer."""
    now = time.time()
    window = max(ANALYSIS_WINDOW_MINUTES, TREND_SLICE_MINUTES * 2)
    try:
        rows = _db_recent_strikes(window)
    except Exception as exc:
        return {"error": str(exc), "trend": "unknown", "activity_trend": "unknown"}

    samples = [(float(r["ts"]), float(r["distance_km"])) for r in rows]
    recent_start = now - TREND_SLICE_MINUTES * 60
    previous_start = now - TREND_SLICE_MINUTES * 120
    recent = [d for ts, d in samples if ts >= recent_start]
    previous = [d for ts, d in samples if previous_start <= ts < recent_start]

    def closest(values):
        return min(values) if values else None

    recent_closest = closest(recent)
    previous_closest = closest(previous)
    delta = None
    trend = "stable"
    if recent_closest is not None and previous_closest is not None:
        delta = previous_closest - recent_closest
        if delta >= APPROACHING_DELTA_KM:
            trend = "approaching"
        elif delta <= -APPROACHING_DELTA_KM:
            trend = "receding"
    elif recent and not previous:
        trend = "new_activity"
    elif not recent and previous:
        trend = "quieting"
    elif not recent and not previous:
        trend = "quiet"

    recent25 = sum(d <= WARNING_RADIUS_KM for d in recent)
    previous25 = sum(d <= WARNING_RADIUS_KM for d in previous)
    if recent25 >= BURST_COUNT_25KM and recent25 >= max(1, previous25) * ACTIVITY_INCREASE_RATIO:
        activity_trend = "increasing"
    elif previous25 >= BURST_COUNT_25KM and recent25 * ACTIVITY_INCREASE_RATIO < previous25:
        activity_trend = "decreasing"
    elif recent25 or previous25:
        activity_trend = "steady"
    else:
        activity_trend = "quiet"

    recent10_rows = [(ts, d) for ts, d in samples if ts >= now - 600]
    distances10 = [d for _, d in recent10_rows]
    closest10 = min(distances10) if distances10 else None
    latest_ts = max((ts for ts, _ in samples), default=None)

    if closest10 is not None and closest10 <= CRITICAL_RADIUS_KM:
        risk = "critical"
    elif closest10 is not None and closest10 <= WARNING_RADIUS_KM:
        risk = "warning"
    elif closest10 is not None and closest10 <= 50:
        risk = "monitor"
    else:
        risk = "regional"

    return {
        "generated_at": now,
        "window_minutes": window,
        "trend_slice_minutes": TREND_SLICE_MINUTES,
        "trend": trend,
        "activity_trend": activity_trend,
        "risk": risk,
        "recent_closest_km": round(recent_closest, 2) if recent_closest is not None else None,
        "previous_closest_km": round(previous_closest, 2) if previous_closest is not None else None,
        "distance_change_km": round(delta, 2) if delta is not None else None,
        "strikes_25km_recent_slice": recent25,
        "strikes_25km_previous_slice": previous25,
        "strikes_5km_10min": sum(d <= 5 for d in distances10),
        "strikes_10km_10min": sum(d <= 10 for d in distances10),
        "strikes_25km_10min": sum(d <= 25 for d in distances10),
        "strikes_50km_10min": sum(d <= 50 for d in distances10),
        "strikes_100km_10min": sum(d <= 100 for d in distances10),
        "closest_10min_km": round(closest10, 2) if closest10 is not None else None,
        "last_strike_time": latest_ts,
    }


def get_health_status():
    now = time.time()
    ws_age = (now - last_ws_message_time) if last_ws_message_time else None
    ws_ok = bool(ws_connected and (ws_age is None or ws_age <= WS_STALE_SECONDS))
    if SMTP_ENABLED:
        smtp_ok = not str(last_email_status).lower().startswith("failed")
        smtp_status = last_email_status
    else:
        smtp_ok, smtp_status = None, "disabled"
    db_ok, db_error = True, None
    try:
        with db_connect() as con:
            con.execute("SELECT 1").fetchone()
    except Exception as exc:
        db_ok, db_error = False, str(exc)

    components = {
        "web": {"ok": True, "status": "online"},
        "database": {"ok": db_ok, "status": "ok" if db_ok else "error", "error": db_error},
        "websocket": {"ok": ws_ok, "status": "connected" if ws_connected else "disconnected", "last_message_age_sec": round(ws_age, 1) if ws_age is not None else None},
        "smtp": {"ok": smtp_ok, "status": smtp_status},
        "zabbix": (
            {"ok": last_zabbix_ok, "status": "ok" if last_zabbix_ok else ("error" if last_zabbix_ok is False else "unknown"), "last_check": last_zabbix_time, "error": last_zabbix_error}
            if ZABBIX_ENABLED else {"ok": None, "status": "disabled"}
        ),
        "geocoder": (
            {"ok": last_geocoder_ok, "status": "ok" if last_geocoder_ok else ("error" if last_geocoder_ok is False else "unknown"), "last_check": last_geocoder_time, "error": last_geocoder_error}
            if GEOCODING_ENABLED else {"ok": None, "status": "disabled"}
        ),
    }
    known = [v["ok"] for v in components.values() if v["ok"] is not None]
    overall = all(known) if known else True
    return {"ok": overall, "generated_at": now, "version": APP_VERSION, "components": components}

# ============================================================
# SMTP
# ============================================================

def send_email(subject, body, html_body=None, attachment_png=None):
    """Send a multipart plain-text + HTML email.

    When a PNG snapshot is provided it is embedded inline in the HTML as
    cid:lightning-map and is also attached as lightning_map.png so clients
    that block inline images can still open it manually.
    """
    global last_email_status

    if not SMTP_ENABLED:
        last_email_status = "disabled"
        print(f"EMAIL SKIPPED (smtp.enabled=false): {subject}", flush=True)
        return False

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = MAIL_FROM
    msg["To"] = MAIL_TO
    msg["Content-Language"] = "cs" if EMAIL_LANGUAGE == "cs" else "en"
    msg.set_content(body)

    if html_body:
        msg.add_alternative(html_body, subtype="html")

        if attachment_png:
            html_part = msg.get_payload()[-1]
            html_part.add_related(
                attachment_png,
                maintype="image",
                subtype="png",
                cid="<lightning-map>",
                filename="lightning_map_inline.png",
                disposition="inline",
            )

    if attachment_png:
        msg.add_attachment(
            attachment_png,
            maintype="image",
            subtype="png",
            filename="lightning_map.png",
        )

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=10) as smtp:
            smtp.send_message(msg)

        last_email_status = f"sent {time.strftime('%Y-%m-%d %H:%M:%S')}"
        print(f"EMAIL SENT: {subject}", flush=True)
        return True

    except Exception as exc:
        last_email_status = f"failed: {exc}"
        print("SMTP ERROR:", repr(exc), flush=True)
        return False


def _email_shell(header_title, header_subtitle, accent, content_html, footer_note, language="en"):
    """Build conservative table-based HTML that renders well in mail clients."""
    source_label = "Zdroj dat" if language == "cs" else "Data source"
    return f"""<!doctype html>
<html lang="{'cs' if language == 'cs' else 'en'}">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>{html.escape(header_title)}</title></head>
<body style="margin:0;padding:0;background:#eef2f6;font-family:Arial,Helvetica,sans-serif;color:#111827;">
<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background:#eef2f6;padding:24px 8px;"><tr><td align="center">
<table role="presentation" width="620" cellspacing="0" cellpadding="0" border="0" style="width:100%;max-width:620px;background:#ffffff;border-radius:14px;overflow:hidden;box-shadow:0 4px 18px rgba(0,0,0,.12);">
<tr><td style="background:{accent};color:#ffffff;padding:22px 26px;"><div style="font-size:23px;font-weight:700;line-height:1.25;">{html.escape(header_title)}</div><div style="font-size:14px;line-height:1.5;margin-top:7px;color:#ffffff;">{html.escape(header_subtitle)}</div></td></tr>
{content_html}
<tr><td style="background:#111827;color:#cbd5e1;padding:16px 26px;font-size:12px;line-height:18px;"><strong style="color:#ffffff;">Lightning Monitor</strong><br>{html.escape(footer_note)}<br>{source_label}: LightningMaps / Blitzortung</td></tr>
</table></td></tr></table></body></html>"""


def build_alert_html(level, distance, locality, lat, lon, readable_time, language=None, analysis=None):
    language = normalize_language(language or EMAIL_LANGUAGE, EMAIL_LANGUAGE)
    level = str(level).upper()
    analysis = analysis or calculate_storm_intelligence()
    if language == "cs":
        if level == "CRITICAL":
            accent, soft, title = "#dc2626", "#fff1f2", "⚡ KRITICKÁ VÝSTRAHA – BLESK"
            subtitle, threshold = "Blesk byl zaznamenán v kritické zóně.", CRITICAL_RADIUS_KM
        else:
            accent, soft, title = "#f59e0b", "#fffbeb", "⚡ VÝSTRAHA – BLESK"
            subtitle, threshold = "Blesk byl zaznamenán v blízkosti sledovaného místa.", WARNING_RADIUS_KM
        trend_names={"approaching":"PŘIBLIŽUJE SE","receding":"VZDÁLUJE SE","new_activity":"NOVÁ AKTIVITA","quieting":"SLÁBNE","quiet":"KLID","stable":"STABILNÍ"}
        activity_names={"increasing":"ROSTE","decreasing":"KLESÁ","steady":"STABILNÍ","quiet":"KLID"}
        labels = {"from":"od sledovaného místa","locality":"Lokalita","time":"Čas úderu","position":"Poloha úderu","point":"Sledovaný bod","zone":"Výstražná zóna","location":"Poloha blesku","attached":"Stejná mapa je také přiložena jako lightning_map.png.","footer":f"Hranice výstrahy: ≤ {threshold:.0f} km","unknown":"Neznámá lokalita","alt":"Satelitní mapa úderu blesku","trend":"Vývoj vzdálenosti","activity":"Aktivita","count":"Údery do 25 km / 10 min","closest":"Nejbližší za 10 min","change":"Změna vzdálenosti"}
    else:
        if level == "CRITICAL":
            accent, soft, title = "#dc2626", "#fff1f2", "⚡ LIGHTNING CRITICAL"
            subtitle, threshold = "Lightning detected inside the critical alert zone.", CRITICAL_RADIUS_KM
        else:
            accent, soft, title = "#f59e0b", "#fffbeb", "⚡ LIGHTNING WARNING"
            subtitle, threshold = "Lightning detected near the monitored location.", WARNING_RADIUS_KM
        trend_names={"approaching":"APPROACHING","receding":"MOVING AWAY","new_activity":"NEW ACTIVITY","quieting":"QUIETING","quiet":"QUIET","stable":"STABLE"}
        activity_names={"increasing":"INCREASING","decreasing":"DECREASING","steady":"STEADY","quiet":"QUIET"}
        labels = {"from":"from monitored location","locality":"Locality","time":"Strike time","position":"Strike position","point":"Monitored point","zone":"Alert zone","location":"Strike location","attached":"The same map is also attached as lightning_map.png.","footer":f"Alert threshold: ≤ {threshold:.0f} km","unknown":"Unknown locality","alt":"Lightning strike satellite map","trend":"Distance trend","activity":"Activity","count":"Strikes within 25 km / 10 min","closest":"Closest in 10 min","change":"Distance change"}
    locality_html=html.escape(locality or labels["unknown"]); readable_time_html=html.escape(readable_time)
    trend=trend_names.get(analysis.get("trend"), str(analysis.get("trend","—")).upper())
    activity=activity_names.get(analysis.get("activity_trend"), str(analysis.get("activity_trend","—")).upper())
    count25=analysis.get("strikes_25km_10min",0)
    closest10=analysis.get("closest_10min_km")
    change=analysis.get("distance_change_km")
    closest_text=f"{closest10:.1f} km" if closest10 is not None else "—"
    change_text=f"{change:+.1f} km" if change is not None else "—"
    content=f"""
<tr><td align="center" style="padding:28px 26px 22px;background:{soft};"><div style="font-size:50px;font-weight:800;line-height:1;color:{accent};">{distance:.1f} km</div><div style="font-size:15px;color:#374151;margin-top:8px;font-weight:600;">{labels['from']}</div></td></tr>
<tr><td style="padding:18px 26px 6px;"><table role="presentation" width="100%" cellspacing="8" cellpadding="0" border="0"><tr>
<td style="width:25%;background:#f8fafc;border:1px solid #e5e7eb;border-radius:9px;padding:12px;text-align:center;"><div style="font-size:11px;color:#64748b;font-weight:700;">{labels['trend']}</div><div style="font-size:14px;font-weight:800;color:#111827;margin-top:5px;">{trend}</div></td>
<td style="width:25%;background:#f8fafc;border:1px solid #e5e7eb;border-radius:9px;padding:12px;text-align:center;"><div style="font-size:11px;color:#64748b;font-weight:700;">{labels['activity']}</div><div style="font-size:14px;font-weight:800;color:#111827;margin-top:5px;">{activity}</div></td>
<td style="width:25%;background:#f8fafc;border:1px solid #e5e7eb;border-radius:9px;padding:12px;text-align:center;"><div style="font-size:11px;color:#64748b;font-weight:700;">{labels['count']}</div><div style="font-size:18px;font-weight:800;color:#111827;margin-top:3px;">{count25}</div></td>
<td style="width:25%;background:#f8fafc;border:1px solid #e5e7eb;border-radius:9px;padding:12px;text-align:center;"><div style="font-size:11px;color:#64748b;font-weight:700;">{labels['closest']}</div><div style="font-size:14px;font-weight:800;color:#111827;margin-top:5px;">{closest_text}</div></td>
</tr></table></td></tr>
<tr><td style="padding:16px 28px 18px;"><table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="font-size:14px;line-height:1.45;">
<tr><td style="padding:8px 0;width:36%;font-weight:700;color:#374151;border-bottom:1px solid #eef2f7;">{labels['locality']}</td><td style="padding:8px 0;border-bottom:1px solid #eef2f7;">{locality_html}</td></tr>
<tr><td style="padding:8px 0;font-weight:700;color:#374151;border-bottom:1px solid #eef2f7;">{labels['time']}</td><td style="padding:8px 0;border-bottom:1px solid #eef2f7;">{readable_time_html}</td></tr>
<tr><td style="padding:8px 0;font-weight:700;color:#374151;border-bottom:1px solid #eef2f7;">{labels['position']}</td><td style="padding:8px 0;border-bottom:1px solid #eef2f7;">{lat:.5f}, {lon:.5f}</td></tr>
<tr><td style="padding:8px 0;font-weight:700;color:#374151;border-bottom:1px solid #eef2f7;">{labels['change']}</td><td style="padding:8px 0;border-bottom:1px solid #eef2f7;">{change_text}</td></tr>
<tr><td style="padding:8px 0;font-weight:700;color:#374151;border-bottom:1px solid #eef2f7;">{labels['point']}</td><td style="padding:8px 0;border-bottom:1px solid #eef2f7;">{CENTER_LAT:.5f}, {CENTER_LON:.5f}</td></tr>
<tr><td style="padding:8px 0;font-weight:700;color:#374151;">{labels['zone']}</td><td style="padding:8px 0;">≤ {threshold:.0f} km</td></tr></table></td></tr>
<tr><td style="padding:0 26px 26px;"><div style="font-size:15px;font-weight:700;margin:4px 0 10px;color:#111827;">{labels['location']}</div><img src="cid:lightning-map" alt="{labels['alt']}" width="568" style="display:block;width:100%;max-width:568px;height:auto;border:1px solid #d1d5db;border-radius:10px;"><div style="font-size:11px;color:#6b7280;margin-top:8px;">{labels['attached']}</div></td></tr>"""
    return _email_shell(title,subtitle,accent,content,labels["footer"],language)

def build_startup_html(startup_time, language=None):
    language=normalize_language(language or EMAIL_LANGUAGE, EMAIL_LANGUAGE)
    if language=="cs":
        title="✓ MONITOR BLESKŮ JE ONLINE"; subtitle="Sběr dat, webový panel a e-mailová upozornění jsou spuštěny."; online="ONLINE"
        L={"check":"Úvodní kontrola e-mailu a vykreslení mapy","startup":"Čas spuštění","point":"Sledované místo","radius":"Sledovaný okruh","warning":"Výstražná zóna","critical":"Kritická zóna","dashboard":"Webový panel","relay":"SMTP server","area":"Sledovaná oblast","attached":"Mapa je vložena do zprávy a zároveň přiložena jako lightning_map.png.","footer":"Webový panel a živý sběr dat běží v jednom procesu Pythonu."}
    else:
        title="✓ LIGHTNING MONITOR ONLINE"; subtitle="Collector, dashboard and SMTP startup sequence has begun."; online="ONLINE"
        L={"check":"Startup SMTP and map-rendering check","startup":"Startup time","point":"Monitored point","radius":"Collection radius","warning":"Warning zone","critical":"Critical zone","dashboard":"Dashboard","relay":"SMTP relay","area":"Monitoring area","attached":"The same map is also attached as lightning_map.png.","footer":"Dashboard and live collection run in the same Python process."}
    content=f"""
<tr><td align="center" style="padding:26px;background:#ecfdf5;"><div style="font-size:38px;font-weight:800;color:#059669;line-height:1;">{online}</div><div style="font-size:14px;color:#4b5563;margin-top:8px;">{L['check']}</div></td></tr>
<tr><td style="padding:22px 28px 18px;"><table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="font-size:14px;line-height:1.45;">
<tr><td style="padding:8px 0;width:40%;font-weight:700;color:#374151;border-bottom:1px solid #eef2f7;">{L['startup']}</td><td style="padding:8px 0;border-bottom:1px solid #eef2f7;">{html.escape(startup_time)}</td></tr>
<tr><td style="padding:8px 0;font-weight:700;color:#374151;border-bottom:1px solid #eef2f7;">{L['point']}</td><td style="padding:8px 0;border-bottom:1px solid #eef2f7;">{CENTER_LAT:.5f}, {CENTER_LON:.5f}</td></tr>
<tr><td style="padding:8px 0;font-weight:700;color:#374151;border-bottom:1px solid #eef2f7;">{L['radius']}</td><td style="padding:8px 0;border-bottom:1px solid #eef2f7;">{MAX_RADIUS_KM:.0f} km</td></tr>
<tr><td style="padding:8px 0;font-weight:700;color:#374151;border-bottom:1px solid #eef2f7;">{L['warning']}</td><td style="padding:8px 0;border-bottom:1px solid #eef2f7;">≤ {WARNING_RADIUS_KM:.0f} km</td></tr>
<tr><td style="padding:8px 0;font-weight:700;color:#374151;border-bottom:1px solid #eef2f7;">{L['critical']}</td><td style="padding:8px 0;border-bottom:1px solid #eef2f7;">≤ {CRITICAL_RADIUS_KM:.0f} km</td></tr>
<tr><td style="padding:8px 0;font-weight:700;color:#374151;border-bottom:1px solid #eef2f7;">{L['dashboard']}</td><td style="padding:8px 0;border-bottom:1px solid #eef2f7;">Port {WEB_PORT}</td></tr>
<tr><td style="padding:8px 0;font-weight:700;color:#374151;border-bottom:1px solid #eef2f7;">Zabbix</td><td style="padding:8px 0;border-bottom:1px solid #eef2f7;">{html.escape(str(ZABBIX_SERVER))} / {html.escape(str(ZABBIX_HOST))}</td></tr>
<tr><td style="padding:8px 0;font-weight:700;color:#374151;">{L['relay']}</td><td style="padding:8px 0;">{html.escape(str(SMTP_SERVER))}:{SMTP_PORT}</td></tr></table></td></tr>
<tr><td style="padding:0 26px 26px;"><div style="font-size:15px;font-weight:700;margin:4px 0 10px;color:#111827;">{L['area']}</div><img src="cid:lightning-map" alt="Monitoring area satellite map" width="568" style="display:block;width:100%;max-width:568px;height:auto;border:1px solid #d1d5db;border-radius:10px;"><div style="font-size:11px;color:#6b7280;margin-top:8px;">{L['attached']}</div></td></tr>"""
    return _email_shell(title,subtitle,"#059669",content,L["footer"],language)


def send_startup_email():
    if not SMTP_ENABLED or not SMTP_SEND_STARTUP:
        print("Startup email skipped (disabled in config)", flush=True)
        return
    startup_time=time.strftime("%Y-%m-%d %H:%M:%S")
    if EMAIL_LANGUAGE=="cs":
        subject="Monitor blesků spuštěn"
        body=f"""Služba sledování blesků byla úspěšně spuštěna.\n\nČas spuštění:\n{startup_time}\n\nSledované místo:\n{CENTER_LAT}, {CENTER_LON}\n\nDashboard:\nhttp://<raspberry-pi-ip>:{WEB_PORT}/\n\nPoloměr sběru:\n{MAX_RADIUS_KM:.0f} km\n\nVýstražná zóna:\n<= {WARNING_RADIUS_KM:.0f} km\n\nKritická zóna:\n<= {CRITICAL_RADIUS_KM:.0f} km\n\nZabbix server:\n{ZABBIX_SERVER}\n\nZabbix host:\n{ZABBIX_HOST}\n\nSMTP server:\n{SMTP_SERVER}:{SMTP_PORT}\n\nZdroj blesků:\nLightningMaps / Blitzortung\n\nSatelitní mapa je vložena do HTML e-mailu a také přiložena jako lightning_map.png.\n"""
    else:
        subject="Lightning Monitor STARTED"
        body=f"""Lightning monitoring service has started successfully.\n\nStartup time:\n{startup_time}\n\nMonitored location:\n{CENTER_LAT}, {CENTER_LON}\n\nDashboard:\nhttp://<raspberry-pi-ip>:{WEB_PORT}/\n\nCollection radius:\n{MAX_RADIUS_KM:.0f} km\n\nWarning threshold:\n<= {WARNING_RADIUS_KM:.0f} km\n\nCritical threshold:\n<= {CRITICAL_RADIUS_KM:.0f} km\n\nZabbix server:\n{ZABBIX_SERVER}\n\nZabbix host:\n{ZABBIX_HOST}\n\nSMTP server:\n{SMTP_SERVER}:{SMTP_PORT}\n\nLightning source:\nLightningMaps / Blitzortung\n\nThe satellite snapshot is embedded in the HTML email and attached as lightning_map.png.\n"""
    print("Sending SMTP startup announcement...",flush=True)
    try: snapshot=build_map_snapshot(language=EMAIL_LANGUAGE)
    except Exception as exc: print("STARTUP MAP ERROR:",repr(exc),flush=True); snapshot=None
    html_body=build_startup_html(startup_time,EMAIL_LANGUAGE)
    if send_email(subject,body,html_body,snapshot): print("SMTP startup test SUCCESS",flush=True)
    else: print("SMTP startup test FAILED",flush=True)


def check_email_alert(distance, lat, lon, strike_time):
    """Smart alerting: escalation and meaningful approach bypass normal cooldown."""
    global last_warning_email, last_critical_email
    global last_alert_level, last_alert_distance, last_alert_time
    now = time.time()
    if not SMTP_ENABLED:
        return
    if now - strike_time > ALERT_MAX_STRIKE_AGE_SECONDS:
        return

    level = "CRITICAL" if distance <= CRITICAL_RADIUS_KM else "WARNING"
    cooldown = CRITICAL_COOLDOWN if level == "CRITICAL" else WARNING_COOLDOWN
    level_last = last_critical_email if level == "CRITICAL" else last_warning_email
    analysis = calculate_storm_intelligence()

    rank = {"NONE": 0, "WARNING": 1, "CRITICAL": 2}
    escalation = rank[level] > rank.get(last_alert_level, 0)
    significant_closer = (
        last_alert_distance is not None
        and distance <= last_alert_distance - SIGNIFICANT_CLOSER_KM
    )
    smart_change = (
        analysis.get("trend") == "approaching"
        or analysis.get("activity_trend") == "increasing"
    ) and now - last_alert_time >= MIN_SMART_RESEND_SECONDS
    cooldown_expired = now - level_last >= cooldown

    # Do not downgrade a recent CRITICAL alert to WARNING unless the warning
    # cooldown has naturally expired. Escalation to CRITICAL is immediate.
    recent_critical = last_alert_level == "CRITICAL" and now - last_alert_time < CRITICAL_COOLDOWN
    if level == "WARNING" and recent_critical and not cooldown_expired:
        return
    if not (escalation or significant_closer or smart_change or cooldown_expired):
        return

    readable_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(strike_time))
    unknown = "Neznámá lokalita" if EMAIL_LANGUAGE == "cs" else "Unknown locality"
    try:
        locality = locality_for_display(reverse_geocode_locality(lat, lon), unknown)
    except GeocoderError as exc:
        print("ALERT GEOCODE ERROR:", repr(exc), flush=True)
        locality = unknown
    try:
        snapshot = build_map_snapshot(lat, lon, distance, locality, EMAIL_LANGUAGE)
    except Exception as exc:
        print("ALERT MAP ERROR:", repr(exc), flush=True)
        snapshot = None

    trend = analysis.get("trend", "stable")
    activity = analysis.get("activity_trend", "steady")
    count25 = analysis.get("strikes_25km_10min", 0)
    closest10 = analysis.get("closest_10min_km")
    delta = analysis.get("distance_change_km")
    if EMAIL_LANGUAGE == "cs":
        trend_cs = {"approaching":"přibližuje se","receding":"vzdaluje se","new_activity":"nová aktivita","quieting":"slábne","quiet":"klid","stable":"stabilní"}.get(trend, trend)
        activity_cs = {"increasing":"roste","decreasing":"klesá","steady":"stabilní","quiet":"klid"}.get(activity, activity)
        subject = (f"KRITICKÁ VÝSTRAHA: blesk {distance:.1f} km" if level == "CRITICAL" else f"VÝSTRAHA: blesk {distance:.1f} km")
        body = f"""{level}\n\nVzdálenost: {distance:.1f} km\nLokalita: {locality}\nČas úderu: {readable_time}\nSouřadnice: {lat:.5f}, {lon:.5f}\n\nINTELIGENCE BOUŘKY\nVývoj vzdálenosti: {trend_cs}\nAktivita: {activity_cs}\nÚdery do 25 km / 10 min: {count25}\nNejbližší za 10 min: {closest10 if closest10 is not None else '—'} km\nZměna vzdálenosti: {delta if delta is not None else '—'} km\n\nZdroj: LightningMaps / Blitzortung\n"""
    else:
        subject = (f"LIGHTNING CRITICAL - {distance:.1f} km away" if level == "CRITICAL" else f"LIGHTNING WARNING - {distance:.1f} km away")
        body = f"""{level} LIGHTNING ALERT\n\nDistance: {distance:.1f} km\nLocality: {locality}\nStrike time: {readable_time}\nCoordinates: {lat:.5f}, {lon:.5f}\n\nSTORM INTELLIGENCE\nDistance trend: {trend}\nActivity: {activity}\nStrikes within 25 km / 10 min: {count25}\nClosest in 10 min: {closest10 if closest10 is not None else '—'} km\nDistance change: {delta if delta is not None else '—'} km\n\nSource: LightningMaps / Blitzortung\n"""

    if send_email(subject, body, build_alert_html(level, distance, locality, lat, lon, readable_time, EMAIL_LANGUAGE, analysis), snapshot):
        if level == "CRITICAL":
            last_critical_email = now
        else:
            last_warning_email = now
        last_alert_level = level
        last_alert_distance = distance
        last_alert_time = now


# ============================================================
# ZABBIX
# ============================================================

def calculate_metrics():
    cleanup()
    now = time.time()

    with state_lock:
        distances = [strike[3] for strike in strikes]
        latest_time = last_strike_time

    closest = min(distances) if distances else -1
    age = max(0, int(now - latest_time)) if latest_time is not None else 999999

    return {
        "lightning.closest.age_sec": age,
        "lightning.closest.distance_km": round(closest, 2),
        "lightning.strikes.5km.10min": sum(d <= 5 for d in distances),
        "lightning.strikes.10km.10min": sum(d <= 10 for d in distances),
        "lightning.strikes.25km.10min": sum(d <= 25 for d in distances),
        "lightning.strikes.50km.10min": sum(d <= 50 for d in distances),
        "lightning.strikes.100km.10min": sum(d <= 100 for d in distances),
    }


def send_to_zabbix():
    global last_zabbix_ok, last_zabbix_time, last_zabbix_error
    if not ZABBIX_ENABLED:
        return
    sender = shutil.which("zabbix_sender")
    if not sender:
        last_zabbix_time = time.time()
        if last_zabbix_ok is not False or last_zabbix_error != "zabbix_sender not found":
            print("ZABBIX: zabbix_sender not found in PATH (install zabbix-sender "
                  "or set zabbix.enabled=false)", flush=True)
        last_zabbix_ok = False
        last_zabbix_error = "zabbix_sender not found"
        return
    metrics = calculate_metrics()
    payload = "\n".join(
        f"{ZABBIX_HOST} {key} {value}" for key, value in metrics.items()
    ) + "\n"
    last_zabbix_time = time.time()
    try:
        result = subprocess.run(
            [sender, "-z", ZABBIX_SERVER, "-i", "-"],
            input=payload, text=True, capture_output=True, timeout=15,
        )
        output = (result.stdout or result.stderr or "").strip()
        if output:
            print(output, flush=True)
        last_zabbix_ok = result.returncode == 0
        last_zabbix_error = None if last_zabbix_ok else (output or f"return code {result.returncode}")
        if result.returncode != 0:
            print(f"ZABBIX ERROR: return code {result.returncode}", flush=True)
    except Exception as exc:
        last_zabbix_ok = False
        last_zabbix_error = str(exc)
        print("ZABBIX SENDER ERROR:", repr(exc), flush=True)


# ============================================================
# STRIKE PROCESSING
# ============================================================

def make_strike_key(stroke, timestamp, lat, lon):
    strike_id = stroke.get("id")
    src = stroke.get("src", "")
    if strike_id is not None:
        return f"{src}:{strike_id}:{int(timestamp * 1000)}"
    return f"fallback:{int(timestamp * 1000)}:{lat:.5f}:{lon:.5f}"


async def process_strike(stroke):
    global last_strike_time, last_strike_distance

    try:
        lat = float(stroke["lat"])
        lon = float(stroke["lon"])
        timestamp = float(stroke["time"])
        if timestamp > 10_000_000_000:
            timestamp /= 1000.0
    except (KeyError, ValueError, TypeError):
        return

    dist = distance_km(CENTER_LAT, CENTER_LON, lat, lon)
    if dist > MAX_RADIUS_KM:
        return

    strike_key = make_strike_key(stroke, timestamp, lat, lon)

    with state_lock:
        if strike_key in seen_keys:
            return
        seen_keys[strike_key] = timestamp
        strikes.append((timestamp, lat, lon, dist, strike_key))

        if last_strike_time is None or timestamp > last_strike_time:
            last_strike_time = timestamp
            last_strike_distance = dist

    store_strike(strike_key, timestamp, lat, lon, dist)

    if geocode_queue is not None:
        try:
            # Priority 0 = live strike. Historical backfill uses priority 1,
            # so a new strike is never stuck behind a large history backlog.
            geocode_queue.put_nowait(
                (0, next(geocode_sequence), strike_key, lat, lon)
            )
        except asyncio.QueueFull:
            print("GEOCODE QUEUE FULL - live locality deferred", flush=True)

    print(
        f"STRIKE: {dist:.1f} km lat={lat:.5f} lon={lon:.5f}",
        flush=True,
    )

    if dist <= WARNING_RADIUS_KM:
        queue_alert(dist, lat, lon, timestamp)
        if zabbix_now_event is not None:
            zabbix_now_event.set()


def queue_alert(dist, lat, lon, timestamp):
    """Remember the closest strike of the current burst for the alert worker."""
    global pending_alert
    if pending_alert is None or dist < pending_alert[0]:
        pending_alert = (dist, lat, lon, timestamp)
    if alert_event is not None:
        alert_event.set()


async def alert_loop():
    """Single alert worker: never blocks the WebSocket reader and never sends
    two e-mails for the same burst (cooldown is checked serially)."""
    global pending_alert
    while True:
        await alert_event.wait()
        alert_event.clear()
        item, pending_alert = pending_alert, None
        if item is None:
            continue
        try:
            await asyncio.to_thread(check_email_alert, *item)
        except Exception as exc:
            print("ALERT LOOP ERROR:", repr(exc), flush=True)


# ============================================================
# ASYNC LOOPS
# ============================================================

def _spawn(coro):
    """Keep a reference to fire-and-forget tasks so they are not GC'd."""
    task = asyncio.get_running_loop().create_task(coro)
    background_tasks.add(task)
    task.add_done_callback(background_tasks.discard)
    return task


async def _requeue_geocode_later(delay, item):
    # Runs as its own task: the geocoder consumer never sleeps on a retry and
    # never blocks on a full queue (which used to deadlock the only consumer).
    await asyncio.sleep(delay)
    await geocode_queue.put(item)


async def geocoder_loop():
    global last_geocoder_ok, last_geocoder_time, last_geocoder_error
    while True:
        item = await geocode_queue.get()
        if len(item) == 5:
            priority, _sequence, strike_key, lat, lon = item
            attempt = 0
        else:
            priority, _sequence, strike_key, lat, lon, attempt = item
        try:
            locality = await asyncio.to_thread(reverse_geocode_locality, lat, lon)
            if locality is None:  # geocoding disabled at runtime
                continue
            last_geocoder_time = time.time()
            last_geocoder_ok = True
            last_geocoder_error = None
            await asyncio.to_thread(update_strike_locality, strike_key, locality)
            source = "LIVE" if priority == 0 else "HISTORY"
            print(f"LOCALITY {source}: {lat:.5f},{lon:.5f} -> {locality}", flush=True)
        except Exception as exc:
            last_geocoder_time = time.time()
            last_geocoder_ok = False
            last_geocoder_error = str(exc)
            print("GEOCODER ERROR:", repr(exc), flush=True)
            if attempt + 1 < GEOCODER_RETRY_ATTEMPTS:
                delay = GEOCODER_RETRY_BACKOFF_SECONDS * (2 ** attempt)
                _spawn(_requeue_geocode_later(
                    delay, (priority, next(geocode_sequence), strike_key, lat, lon, attempt + 1)
                ))
            else:
                last_geocoder_error = f"retry limit reached: {exc}"
        finally:
            geocode_queue.task_done()


def get_missing_localities_batch(cursor=None):
    """Return unresolved historical rows using a stable (ts, strike_key) cursor."""
    cutoff = time.time() - HISTORY_RETENTION_DAYS * 86400
    with db_connect() as con:
        if cursor is None:
            rows = con.execute(
                "SELECT strike_key, ts, lat, lon FROM strikes "
                "WHERE ts >= ? AND (locality IS NULL OR TRIM(locality) = '') "
                "ORDER BY ts DESC, strike_key DESC LIMIT ?",
                (cutoff, GEOCODER_BACKFILL_BATCH_SIZE),
            ).fetchall()
        else:
            cursor_ts, cursor_key = cursor
            rows = con.execute(
                "SELECT strike_key, ts, lat, lon FROM strikes "
                "WHERE ts >= ? AND (locality IS NULL OR TRIM(locality) = '') "
                "AND (ts < ? OR (ts = ? AND strike_key < ?)) "
                "ORDER BY ts DESC, strike_key DESC LIMIT ?",
                (cutoff, cursor_ts, cursor_ts, cursor_key, GEOCODER_BACKFILL_BATCH_SIZE),
            ).fetchall()
    return rows


async def historical_geocode_backfill_loop(force=False):
    """Queue old DB rows with missing localities after startup.

    The queue is a PriorityQueue: live strikes have priority 0 while history
    has priority 1. That lets new alerts/localities jump ahead of backfill.
    """
    if not GEOCODING_ENABLED or not (GEOCODER_BACKFILL_HISTORY or force):
        return

    print("Historical locality backfill: scanning SQLite...", flush=True)
    cursor = None
    queued = 0

    while True:
        try:
            rows = await asyncio.to_thread(get_missing_localities_batch, cursor)
        except Exception as exc:
            print("HISTORICAL GEOCODE SCAN ERROR:", repr(exc), flush=True)
            return

        if not rows:
            break

        for row in rows:
            await geocode_queue.put(
                (
                    1,
                    next(geocode_sequence),
                    row["strike_key"],
                    float(row["lat"]),
                    float(row["lon"]),
                )
            )
            queued += 1

        cursor = (float(rows[-1]["ts"]), str(rows[-1]["strike_key"]))
        # Yield so the live WebSocket path can enqueue immediately.
        await asyncio.sleep(0)

    print(
        f"Historical locality backfill: queued {queued} unresolved strike(s)",
        flush=True,
    )

    if queued:
        await geocode_queue.join()
        print("Historical locality backfill: complete", flush=True)


async def sender_loop():
    """Periodic Zabbix push, plus an immediate push when a nearby strike
    arrives (coalesced so a burst triggers at most one extra send)."""
    while True:
        await asyncio.to_thread(send_to_zabbix)
        zabbix_now_event.clear()
        try:
            await asyncio.wait_for(zabbix_now_event.wait(), timeout=max(5, SEND_INTERVAL))
            await asyncio.sleep(1)  # let the rest of the burst arrive
        except asyncio.TimeoutError:
            pass


async def maintenance_loop():
    while True:
        await asyncio.sleep(3600)
        cleanup()
        await asyncio.to_thread(purge_old_history)
        # Pick up localities that were skipped (queue full, retries exhausted).
        if GEOCODING_ENABLED and geocode_queue is not None and geocode_queue.empty():
            _spawn(historical_geocode_backfill_loop(force=True))


def recompute_window_distances():
    """After the monitored point/radius changes, refresh the live window."""
    with state_lock:
        updated = []
        for ts, lat, lon, _dist, key in strikes:
            dist = distance_km(CENTER_LAT, CENTER_LON, lat, lon)
            if dist <= MAX_RADIUS_KM:
                updated.append((ts, lat, lon, dist, key))
        strikes.clear()
        strikes.extend(updated)


def build_subscription():
    bbox = bounding_box(CENTER_LAT, CENTER_LON, MAX_RADIUS_KM)
    return bbox, {
        "v": 24,
        "i": {},
        "s": False,
        "x": 0,
        "w": 0,
        "tx": 0,
        "tw": 1,
        "a": 4,
        "z": 8,
        "b": True,
        "h": "",
        "l": 1,
        "t": 1,
        "p": bbox,
        "r": "A",
    }


class ResubscribeNeeded(Exception):
    pass


async def websocket_loop():
    global ws_connected, last_ws_message_time

    reconnect_delay = 2

    while True:
        bbox, subscribe = build_subscription()
        url = WS_URL
        try:
            print(f"Connecting to {url}", flush=True)
            print("Bounding box:", [round(v, 4) for v in bbox], flush=True)

            async with websockets.connect(
                url,
                ping_interval=20,
                ping_timeout=20,
                open_timeout=20,
                close_timeout=5,
                max_size=4 * 1024 * 1024,
            ) as websocket:
                await websocket.send(json.dumps(subscribe, separators=(",", ":")))
                ws_connected = True
                connected_at = time.time()
                print("LightningMaps WebSocket CONNECTED", flush=True)
                reconnect_delay = 2

                while True:
                    try:
                        raw = await asyncio.wait_for(websocket.recv(), timeout=15)
                    except asyncio.TimeoutError:
                        raw = None

                    # Settings changed from the dashboard: resubscribe with the new area.
                    if WS_URL != url or build_subscription()[0] != bbox:
                        raise ResubscribeNeeded("monitoring area or feed URL changed")

                    if raw is None:
                        last = last_ws_message_time or connected_at
                        silent = time.time() - max(last, connected_at)
                        if silent > max(WS_STALE_SECONDS * 3, 300):
                            raise ResubscribeNeeded(f"no data for {int(silent)}s")
                        continue

                    last_ws_message_time = time.time()
                    try:
                        message = json.loads(raw)
                    except (json.JSONDecodeError, TypeError):
                        continue
                    if not isinstance(message, dict):
                        continue

                    batch = message.get("strokes") or []
                    if not batch:
                        continue

                    print(f"Received {len(batch)} strike(s)", flush=True)
                    for stroke in batch:
                        if isinstance(stroke, dict):
                            await process_strike(stroke)

        except asyncio.CancelledError:
            raise
        except ResubscribeNeeded as exc:
            ws_connected = False
            print(f"WEBSOCKET RESUBSCRIBE: {exc}", flush=True)
            recompute_window_distances()
            reconnect_delay = 2
            await asyncio.sleep(1)
        except Exception as exc:
            ws_connected = False
            print("WEBSOCKET ERROR:", repr(exc), flush=True)
            print(f"Retrying in {reconnect_delay}s", flush=True)
            await asyncio.sleep(reconnect_delay)
            reconnect_delay = min(reconnect_delay * 2, 60)
        finally:
            ws_connected = False


# ============================================================
# WEB API
# ============================================================

PASSWORD_MASK = "********"


def _admin_password():
    return str(CONFIG.get("web", {}).get("admin_password", "") or "")


def _is_admin(req):
    """HTTP Basic auth (any user name) when web.admin_password is set."""
    password = _admin_password()
    if not password:
        return True
    header = req.headers.get("Authorization", "")
    if not header.startswith("Basic "):
        return False
    try:
        decoded = base64.b64decode(header[6:]).decode("utf-8")
    except Exception:
        return False
    supplied = decoded.split(":", 1)[1] if ":" in decoded else decoded
    return hmac.compare_digest(supplied.encode("utf-8"), password.encode("utf-8"))


def _auth_required():
    response = jsonify({"ok": False, "error": "Authentication required"})
    response.status_code = 401
    response.headers["WWW-Authenticate"] = 'Basic realm="Lightning Monitor settings"'
    return response


def _is_language_only_update(update):
    return (
        isinstance(update, dict)
        and set(update) == {"localization"}
        and isinstance(update["localization"], dict)
        and set(update["localization"]) == {"default_language"}
    )


@app.after_request
def _security_headers(response):
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "same-origin")
    return response


@app.route("/")
def dashboard():
    return render_template(
        "dashboard.html",
        center_lat=CENTER_LAT,
        center_lon=CENTER_LON,
        max_radius=MAX_RADIUS_KM,
        warning_radius=WARNING_RADIUS_KM,
        critical_radius=CRITICAL_RADIUS_KM,
        default_language=DEFAULT_LANGUAGE,
        version=APP_VERSION,
    )


@app.route("/api/status")
def api_status():
    metrics = calculate_metrics()

    with state_lock:
        latest_time = last_strike_time
        latest_distance = last_strike_distance

    return jsonify(
        {
            "now": time.time(),
            "startup_time": startup_time,
            "ws_connected": ws_connected,
            "last_ws_message_time": last_ws_message_time,
            "last_email_status": last_email_status,
            "center": {"lat": CENTER_LAT, "lon": CENTER_LON},
            "warning_radius_km": WARNING_RADIUS_KM,
            "critical_radius_km": CRITICAL_RADIUS_KM,
            "max_radius_km": MAX_RADIUS_KM,
            "rings": [{"radius_km": r, "kind": k} for r, k in alert_rings()],
            "smtp_enabled": SMTP_ENABLED,
            "zabbix_enabled": ZABBIX_ENABLED,
            "geocoding_enabled": GEOCODING_ENABLED,
            "version": APP_VERSION,
            "latest_strike_time": latest_time,
            "latest_strike_distance_km": latest_distance,
            "metrics": metrics,
        }
    )


@app.route("/api/intelligence")
def api_intelligence():
    return jsonify(calculate_storm_intelligence())


@app.route("/api/health")
def api_health():
    health = get_health_status()
    return jsonify(health), (200 if health["ok"] else 503)


def _known_config_view(config, defaults):
    out = {}
    for key, default in defaults.items():
        value = config.get(key, default)
        if isinstance(default, dict) and isinstance(value, dict):
            out[key] = _known_config_view(value, default)
        else:
            out[key] = value
    return out


@app.route("/api/config", methods=["GET", "POST"])
def api_config():
    payload = request.get_json(silent=True) if request.method == "POST" else None
    update = payload.get("updates", payload) if isinstance(payload, dict) else None
    # Switching the dashboard language is harmless and must not prompt for a password.
    if not (request.method == "POST" and _is_language_only_update(update)) and not _is_admin(request):
        return _auth_required()

    if request.method == "GET":
        with CONFIG_LOCK:
            cfg = _known_config_view(CONFIG, DEFAULT_CONFIG)
        if cfg.get("web", {}).get("admin_password"):
            cfg["web"]["admin_password"] = PASSWORD_MASK
        return jsonify({
            "config": cfg,
            "config_path": CONFIG_PATH,
            "writable": bool(CONFIG.get("web", {}).get("allow_config_write", True)),
            "restart_allowed": bool(CONFIG.get("web", {}).get("allow_restart", True)),
            "restart_required_paths": sorted(RESTART_REQUIRED_PATHS),
        })

    if not bool(CONFIG.get("web", {}).get("allow_config_write", True)):
        return jsonify({"ok": False, "error": "Dashboard configuration writes are disabled"}), 403

    if not isinstance(update, dict):
        return jsonify({"ok": False, "error": "Expected a JSON object"}), 400
    web_update = update.get("web")
    if isinstance(web_update, dict) and web_update.get("admin_password") == PASSWORD_MASK:
        web_update.pop("admin_password")  # unchanged masked value

    try:
        with CONFIG_LOCK:
            changed = _merge_user_update(CONFIG, update, DEFAULT_CONFIG)
            _fill_missing(CONFIG, DEFAULT_CONFIG)
            apply_runtime_config()
            _write_config(CONFIG)
    except (ValueError, OSError) as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400

    restart = sorted(path for path in changed if path in RESTART_REQUIRED_PATHS)
    print("CONFIG UPDATED: " + (", ".join(changed) if changed else "no changes"), flush=True)
    if not _is_admin(request):
        # Unauthenticated language switch: confirm without exposing the config.
        return jsonify({"ok": True, "changed": changed, "restart_required": [],
                        "config": {"localization": {"default_language": DEFAULT_LANGUAGE}}})
    view = _known_config_view(CONFIG, DEFAULT_CONFIG)
    if view.get("web", {}).get("admin_password"):
        view["web"]["admin_password"] = PASSWORD_MASK
    return jsonify({
        "ok": True,
        "changed": changed,
        "restart_required": restart,
        "config": view,
    })


def _restart_process_after_response(delay=0.8):
    """Replace this process with a fresh copy of lightning.py after HTTP response flushes.

    This deliberately does not depend on systemd, sudo, the current working
    directory, or a fixed installation path. It restarts with the same Python
    interpreter and command-line arguments that launched the monitor.
    """
    time.sleep(delay)
    script = os.path.abspath(__file__)
    argv = [sys.executable, script, *sys.argv[1:]]
    env = dict(os.environ, LIGHTNING_RESTARTED="1")
    try:
        if os.environ.get("LIGHTNING_SUPERVISED"):
            # Running under "run.bat service" (Windows background task): its
            # loop restarts us immediately on exit code 75, so just exit.
            print("WEB RESTART: exiting for supervisor restart", flush=True)
            sys.stdout.flush(); sys.stderr.flush()
            os._exit(75)
        if os.name == "nt":
            # Windows has no real exec(): start a fresh copy and exit.  The new
            # process retries binding the port until this one has released it.
            print(f"WEB RESTART: spawn {sys.executable} {script}", flush=True)
            subprocess.Popen(argv, env=env, close_fds=True)
            os._exit(0)
        print(f"WEB RESTART: exec {sys.executable} {script}", flush=True)
        sys.stdout.flush(); sys.stderr.flush()
        os.execve(sys.executable, argv, env)
    except Exception as exc:
        print("WEB RESTART ERROR:", repr(exc), flush=True)


@app.route("/api/restart", methods=["POST"])
def api_restart():
    if not bool(CONFIG.get("web", {}).get("allow_restart", True)):
        return jsonify({"ok": False, "error": "Web restart is disabled"}), 403
    if not _is_admin(request):
        return _auth_required()

    # Start only after Flask has a chance to return this JSON to the browser.
    threading.Thread(target=_restart_process_after_response, daemon=True).start()
    print(f"WEB RESTART REQUESTED from {request.remote_addr or 'unknown'}", flush=True)
    return jsonify({
        "ok": True,
        "message": "Restart scheduled",
        "port": int(CONFIG.get("web", {}).get("port", WEB_PORT)),
        "host": str(CONFIG.get("web", {}).get("host", WEB_HOST)),
    })


@app.route("/api/strikes")
def api_strikes():
    try:
        minutes = int(request.args.get("minutes", "60"))
    except ValueError:
        minutes = 60
    minutes = max(1, min(minutes, HISTORY_RETENTION_DAYS * 24 * 60))

    try:
        limit = int(request.args.get("limit", "500"))
    except ValueError:
        limit = 500
    limit = max(1, min(limit, 5000))

    cutoff = time.time() - minutes * 60

    with db_connect() as con:
        rows = con.execute(
            "SELECT ts, lat, lon, distance_km, locality FROM strikes "
            "WHERE ts >= ? ORDER BY ts DESC LIMIT ?",
            (cutoff, limit),
        ).fetchall()

    return jsonify(
        [
            {
                "ts": float(row["ts"]),
                "lat": float(row["lat"]),
                "lon": float(row["lon"]),
                "distance_km": float(row["distance_km"]),
                "locality": row["locality"],
            }
            for row in rows
        ]
    )


@app.route("/api/timeline")
def api_timeline():
    """Strike counts per time bucket, split by zone, for the activity chart."""
    try:
        minutes = int(request.args.get("minutes", "60"))
    except ValueError:
        minutes = 60
    minutes = max(10, min(minutes, HISTORY_RETENTION_DAYS * 24 * 60))
    buckets = 60
    bucket_seconds = max(10, int(math.ceil(minutes * 60 / buckets)))
    now = time.time()
    end = math.ceil(now / bucket_seconds) * bucket_seconds
    start = end - buckets * bucket_seconds

    with db_connect() as con:
        rows = con.execute(
            "SELECT CAST((ts - ?) / ? AS INTEGER) AS b, "
            "SUM(distance_km <= ?) AS critical, "
            "SUM(distance_km > ? AND distance_km <= ?) AS warning, "
            "SUM(distance_km > ?) AS other "
            "FROM strikes WHERE ts >= ? GROUP BY b",
            (start, bucket_seconds, CRITICAL_RADIUS_KM, CRITICAL_RADIUS_KM,
             WARNING_RADIUS_KM, WARNING_RADIUS_KM, start),
        ).fetchall()

    series = [{"t": start + i * bucket_seconds, "critical": 0, "warning": 0, "other": 0}
              for i in range(buckets)]
    for row in rows:
        idx = row["b"]
        if idx is not None and 0 <= idx < buckets:
            series[idx]["critical"] = int(row["critical"] or 0)
            series[idx]["warning"] = int(row["warning"] or 0)
            series[idx]["other"] = int(row["other"] or 0)
    return jsonify({
        "bucket_seconds": bucket_seconds,
        "start": start,
        "end": end,
        "buckets": series,
    })


@app.route("/api/snapshot/latest.png")
def api_snapshot_latest():
    lang = normalize_language(request.args.get("lang", DEFAULT_LANGUAGE), DEFAULT_LANGUAGE)

    with db_connect() as con:
        row = con.execute(
            "SELECT lat, lon, distance_km, locality FROM strikes WHERE distance_km <= ? "
            "ORDER BY ts DESC LIMIT 1",
            (MAX_RADIUS_KM,),
        ).fetchone()

    try:
        if row:
            png = build_map_snapshot(
                float(row["lat"]),
                float(row["lon"]),
                float(row["distance_km"]),
                row["locality"],
                lang,
            )
        else:
            png = build_map_snapshot(language=lang)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500

    return send_file(io.BytesIO(png), mimetype="image/png", max_age=0)


# ============================================================
# WEB SERVER
# ============================================================

class DashboardServer:
    """Start the dashboard with an explicit socket bind.

    make_server() binds the listening socket in the main thread, so a bad
    address, occupied port, or permission problem is reported immediately
    instead of being hidden inside a background Flask thread.
    """

    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.server = make_server(host, port, app, threaded=True)
        self.thread = threading.Thread(
            target=self.server.serve_forever,
            name="lightning-dashboard",
            daemon=True,
        )

    def start(self):
        self.thread.start()

    def stop(self):
        self.server.shutdown()
        self.thread.join(timeout=5)


def start_web_server():
    # After a web restart the previous process may still hold the port for a
    # moment (always the case on Windows), so retry briefly in that case only.
    deadline = time.time() + (15 if os.environ.get("LIGHTNING_RESTARTED") else 0)
    while True:
        try:
            server = DashboardServer(WEB_HOST, WEB_PORT)
            break
        except (OSError, SystemExit) as exc:
            # Werkzeug reports "address already in use" by calling sys.exit()
            # itself instead of raising OSError, so both must be handled.
            if time.time() < deadline:
                time.sleep(0.5)
                continue
            reason = (
                "address already in use or not available "
                "(is another copy of the monitor running?)"
                if isinstance(exc, SystemExit) else str(exc)
            )
            raise SystemExit(
                f"Cannot bind dashboard to {WEB_HOST}:{WEB_PORT}: {reason}"
            ) from None

    server.start()

    # make_server() has already bound the socket at this point.  This is a
    # real readiness message, not merely a thread-start message.
    print(
        f"Dashboard listening on {WEB_HOST}:{WEB_PORT}",
        flush=True,
    )
    return server


# ============================================================
# MAIN
# ============================================================

async def main():
    global geocode_queue, alert_event, zabbix_now_event

    init_db()
    geocode_queue = asyncio.PriorityQueue(maxsize=GEOCODER_QUEUE_MAXSIZE)
    alert_event = asyncio.Event()
    zabbix_now_event = asyncio.Event()
    purge_old_history()
    load_recent_state()

    web_server = start_web_server()

    print("======================================", flush=True)
    print(f" Lightning Monitor {APP_VERSION}", flush=True)
    print(" LightningMaps -> Zabbix + Dashboard", flush=True)
    print("======================================", flush=True)
    print(f"Center: {CENTER_LAT}, {CENTER_LON}", flush=True)
    print(f"Collection radius: {MAX_RADIUS_KM} km", flush=True)
    print(f"Warning: {WARNING_RADIUS_KM} km", flush=True)
    print(f"Critical: {CRITICAL_RADIUS_KM} km", flush=True)
    print(f"Zabbix: {ZABBIX_SERVER} / {ZABBIX_HOST}" if ZABBIX_ENABLED else "Zabbix: disabled", flush=True)
    print(f"SMTP: {SMTP_SERVER}:{SMTP_PORT}" if SMTP_ENABLED else "SMTP: disabled", flush=True)
    if not _admin_password() and (CONFIG["web"].get("allow_config_write") or CONFIG["web"].get("allow_restart")):
        print("NOTE: settings/restart are open to anyone who can reach the dashboard; "
              "set web.admin_password to protect them.", flush=True)
    display_host = "<this-host>" if WEB_HOST in ("0.0.0.0", "::") else WEB_HOST
    print(f"Dashboard: http://{display_host}:{WEB_PORT}/", flush=True)
    print(f"SQLite: {DB_PATH}", flush=True)

    # Startup mail (tile download + SMTP) runs alongside collection instead of
    # delaying the first WebSocket connection.
    _spawn(asyncio.to_thread(send_startup_email))

    try:
        await asyncio.gather(
            websocket_loop(),
            sender_loop(),
            maintenance_loop(),
            geocoder_loop(),
            alert_loop(),
            historical_geocode_backfill_loop(),
        )
    finally:
        await asyncio.to_thread(web_server.stop)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nLightning monitor stopped.", flush=True)
