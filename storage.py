"""
storage.py - SQLite Database Storage & Persistent Caching Layer
Provides ACID-safe persistent storage for:
1. Live DNS MX and Catch-All Verification Cache (eliminates redundant DNS lookups across app sessions)
2. Search Query History Logs (indexed, searchable, recallable)
3. Lead Archive & Backup Database
"""

import os
import sqlite3
import datetime
import threading

DB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "db")
DB_FILE = os.path.join(DB_DIR, "scraper_storage.db")

_DB_LOCK = threading.Lock()


def get_db_connection():
    """Establishes an SQLite connection with optimized WAL mode and timeout."""
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_FILE, timeout=10.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    # Enable Write-Ahead Logging for high-concurrency threading performance
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
    except Exception:
        pass
    return conn


def init_db():
    """Initializes the database schema if tables do not already exist."""
    with _DB_LOCK:
        conn = get_db_connection()
        try:
            with conn:
                # 1. MX & Catch-All Verification Cache Table
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS mx_cache (
                        domain TEXT PRIMARY KEY,
                        has_mx INTEGER NOT NULL,
                        is_catchall INTEGER NOT NULL,
                        mx_host TEXT DEFAULT '',
                        checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)
                conn.execute("CREATE INDEX IF NOT EXISTS idx_mx_domain ON mx_cache(domain);")

                # 2. Search Query History Table
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS search_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT NOT NULL,
                        engine TEXT NOT NULL,
                        query TEXT NOT NULL,
                        leads_count INTEGER DEFAULT 0,
                        search_type TEXT DEFAULT 'generalized'
                    );
                """)
                conn.execute("CREATE INDEX IF NOT EXISTS idx_history_timestamp ON search_history(timestamp DESC);")

                # Auto-migrate schema: ensure search_type column exists
                cursor = conn.cursor()
                cursor.execute("PRAGMA table_info(search_history);")
                columns = [row["name"] for row in cursor.fetchall()]
                if "search_type" not in columns:
                    cursor.execute("ALTER TABLE search_history ADD COLUMN search_type TEXT DEFAULT 'generalized';")

                # 3. Saved Leads Persistent Storage Table
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS saved_leads (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        full_name TEXT,
                        job_role TEXT,
                        organisation TEXT,
                        enriched_email TEXT,
                        deliverability_status TEXT,
                        domain TEXT,
                        phone TEXT,
                        profile_url TEXT,
                        saved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(profile_url, enriched_email)
                    );
                """)
                conn.execute("CREATE INDEX IF NOT EXISTS idx_leads_domain ON saved_leads(domain);")
        finally:
            conn.close()


# ---------------------------------------------------------------------------
# MX DNS & CATCH-ALL PERSISTENT CACHE
# ---------------------------------------------------------------------------
def get_cached_mx(domain: str) -> dict:
    """
    Retrieves cached MX and Catch-All resolution for a domain.
    Returns dict: {'has_mx': bool, 'is_catchall': bool, 'mx_host': str} or None.
    """
    if not domain:
        return None
    domain_clean = domain.strip().lower()

    with _DB_LOCK:
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT has_mx, is_catchall, mx_host FROM mx_cache WHERE domain = ?", (domain_clean,))
            row = cursor.fetchone()
            if row:
                return {
                    "has_mx": bool(row["has_mx"]),
                    "is_catchall": bool(row["is_catchall"]),
                    "mx_host": row["mx_host"] or ""
                }
            return None
        except Exception:
            return None
        finally:
            conn.close()


def set_cached_mx(domain: str, has_mx: bool, is_catchall: bool, mx_host: str = ""):
    """Stores or updates the MX and Catch-All status of a domain in the SQLite cache."""
    if not domain:
        return
    domain_clean = domain.strip().lower()

    with _DB_LOCK:
        conn = get_db_connection()
        try:
            with conn:
                conn.execute("""
                    INSERT INTO mx_cache (domain, has_mx, is_catchall, mx_host, checked_at)
                    VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(domain) DO UPDATE SET
                        has_mx = excluded.has_mx,
                        is_catchall = excluded.is_catchall,
                        mx_host = excluded.mx_host,
                        checked_at = CURRENT_TIMESTAMP;
                """, (domain_clean, 1 if has_mx else 0, 1 if is_catchall else 0, str(mx_host or "")))
        except Exception:
            pass
        finally:
            conn.close()


# ---------------------------------------------------------------------------
# SEARCH HISTORY LOGGING
# ---------------------------------------------------------------------------
def log_search_query(engine: str, query: str, leads_count: int = 0, search_type: str = "generalized"):
    """Logs a search query execution with timestamp, engine, query, leads count, and search type."""
    if not query or not query.strip():
        return
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    st = str(search_type or "generalized").lower().strip()
    if st not in ["targeted", "generalized"]:
        st = "targeted" if "site:" in query.lower() else "generalized"

    with _DB_LOCK:
        conn = get_db_connection()
        try:
            with conn:
                conn.execute("""
                    INSERT INTO search_history (timestamp, engine, query, leads_count, search_type)
                    VALUES (?, ?, ?, ?, ?);
                """, (ts, str(engine), str(query).strip(), int(leads_count), st))
        except Exception:
            pass
        finally:
            conn.close()


def get_search_history(limit: int = 250) -> list:
    """Retrieves the most recent search queries ordered by timestamp descending."""
    with _DB_LOCK:
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT timestamp, engine, query, leads_count, COALESCE(search_type, 'generalized') as search_type
                FROM search_history
                ORDER BY id DESC
                LIMIT ?;
            """, (limit,))
            rows = cursor.fetchall()
            return [dict(r) for r in rows]
        except Exception:
            return []
        finally:
            conn.close()


def clear_search_history():
    """Clears all records from the search query history."""
    with _DB_LOCK:
        conn = get_db_connection()
        try:
            with conn:
                conn.execute("DELETE FROM search_history;")
        except Exception:
            pass
        finally:
            conn.close()


# ---------------------------------------------------------------------------
# SAVED LEADS STORAGE
# ---------------------------------------------------------------------------
def save_lead(lead_dict: dict) -> bool:
    """Saves a lead to the persistent SQLite storage."""
    if not lead_dict:
        return False
    with _DB_LOCK:
        conn = get_db_connection()
        try:
            with conn:
                conn.execute("""
                    INSERT OR REPLACE INTO saved_leads (
                        full_name, job_role, organisation, enriched_email,
                        deliverability_status, domain, phone, profile_url, saved_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP);
                """, (
                    lead_dict.get("full_name", ""),
                    lead_dict.get("job_role", ""),
                    lead_dict.get("organisation", ""),
                    lead_dict.get("enriched_email", ""),
                    lead_dict.get("deliverability_status", ""),
                    lead_dict.get("domain", ""),
                    lead_dict.get("phone", ""),
                    lead_dict.get("profile_url", "")
                ))
            return True
        except Exception:
            return False
        finally:
            conn.close()


def get_stats() -> dict:
    """Returns storage metrics (total cached MX domains, logged queries, saved leads)."""
    with _DB_LOCK:
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) as count FROM mx_cache;")
            mx_count = cursor.fetchone()["count"]

            cursor.execute("SELECT COUNT(*) as count FROM search_history;")
            hist_count = cursor.fetchone()["count"]

            cursor.execute("SELECT COUNT(*) as count FROM saved_leads;")
            leads_count = cursor.fetchone()["count"]

            return {
                "cached_mx_domains": mx_count,
                "logged_searches": hist_count,
                "saved_leads": leads_count,
                "db_path": DB_FILE
            }
        except Exception:
            return {"cached_mx_domains": 0, "logged_searches": 0, "saved_leads": 0, "db_path": DB_FILE}
        finally:
            conn.close()


# Automatically initialize schema on first import
init_db()
