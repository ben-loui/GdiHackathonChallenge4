"""Resumable and failure-aware synchronization of public FIM Portal resources.

No location parameter. Every list item is checkpointed, even if its detail
fetch fails. Individual failures are retained for a later retry and never
count toward a genuinely complete catalog snapshot.
"""
from __future__ import annotations

import json
import sqlite3
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Callable

from .catalog import AuthorityTaxonomy, clean, first, normalize_record
from .fim_import import call_fim, extract_items, keys_for_detail

SOURCES = ("service-profiles", "leika", "landesredaktion", "pvog")
PAGE_SIZE = 200
RETRY_COOLDOWN = timedelta(minutes=30)


class RequestPacer:
    """Throttle *starts* of FIM detail commands across multiple workers.

    Underlying CLI retries can cause extra HTTP requests. Keep max_rps
    conservative because the public FIM Portal applies per-IP rate limits.
    """

    def __init__(self, max_rps: float | None):
        self._interval = (1.0 / max_rps) if max_rps else 0.0
        self._lock = threading.Lock()
        self._next_start = 0.0

    def wait(self) -> None:
        if not self._interval:
            return
        with self._lock:
            now = time.monotonic()
            wait_for = max(0.0, self._next_start - now)
            self._next_start = max(now, self._next_start) + self._interval
        if wait_for:
            time.sleep(wait_for)


def stamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def connect_db(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=10000")
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS records (
          record_key TEXT PRIMARY KEY,
          source TEXT NOT NULL,
          document TEXT NOT NULL,
          imported_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS sync_progress (
          source TEXT PRIMARY KEY,
          next_offset INTEGER NOT NULL DEFAULT 0,
          finished INTEGER NOT NULL DEFAULT 0,
          last_error TEXT,
          last_update TEXT
        );
        CREATE INDEX IF NOT EXISTS records_by_source ON records(source);
        CREATE TABLE IF NOT EXISTS failed_details (
          record_key TEXT PRIMARY KEY,
          source TEXT NOT NULL,
          item_json TEXT NOT NULL,
          last_error TEXT NOT NULL,
          attempts INTEGER NOT NULL DEFAULT 1,
          last_attempt TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS failed_details_by_source ON failed_details(source);
    """)
    return conn


def get_progress(conn: sqlite3.Connection, source: str) -> tuple[int, bool]:
    row = conn.execute("SELECT next_offset, finished FROM sync_progress WHERE source=?", (source,)).fetchone()
    return (int(row[0]), bool(row[1])) if row else (0, False)


def set_progress(conn: sqlite3.Connection, source: str, offset: int, *, complete: bool = False,
                 error: str | None = None) -> None:
    conn.execute("""INSERT INTO sync_progress(source,next_offset,finished,last_error,last_update)
                    VALUES(?,?,?,?,?) ON CONFLICT(source) DO UPDATE SET
                    next_offset=excluded.next_offset, finished=excluded.finished,
                    last_error=excluded.last_error, last_update=excluded.last_update""",
                 (source, offset, 1 if complete else 0, error, stamp()))
    conn.commit()


def profile_identity(item: dict) -> str:
    value = first(item, ("leistungsschluessel", "leistungsschlüssel", "service_key", "leika_id", "id"))
    return clean(value)


def detail_identity(item: dict, source: str) -> tuple[str, tuple[str, ...]]:
    if source == "service-profiles":
        key = profile_identity(item)
        if not key:
            raise RuntimeError(f"Leistungssteckbrief ohne ID: {str(item)[:240]}")
        return f"profile:{key}", ("service-profiles", "get", key)
    identity = keys_for_detail(item, source)
    if not identity:
        raise RuntimeError(f"Stammtext ohne Detailidentifikator: {str(item)[:240]}")
    return f"text:{':'.join(identity)}", ("service-texts", "get", *identity)


def write_record(conn: sqlite3.Connection, taxonomy: AuthorityTaxonomy, source: str,
                 item: dict, key: str, detail: dict | None) -> bool:
    payload = dict(detail or {})
    for k, v in item.items():
        payload.setdefault(k, v)
    doc = normalize_record(payload, taxonomy, origin=f"fim:{source}")
    if doc is None:
        if detail is not None:
            raise RuntimeError(f"FIM-Detail ohne Titel/Identifikator: {key}")
        return False
    doc["id"] = key
    doc["fim_source_key"] = key
    doc["original_source"] = source
    doc["retrieval_status"] = "detail" if detail is not None else "summary_only"
    if detail is None:
        # List response may omit the authoritative field. Do not claim a verified mapping.
        doc["behoerdenkategorien"] = []
        doc["zustaendige_stelle_original"] = []
        doc["mapping_status"] = "detail_abruf_fehlgeschlagen"
    conn.execute("INSERT OR REPLACE INTO records(record_key,source,document,imported_at) VALUES(?,?,?,?)",
                 (key, source, json.dumps(doc, ensure_ascii=False), stamp()))
    return True


def register_failure(conn: sqlite3.Connection, key: str, source: str, item: dict, error: Exception) -> None:
    conn.execute("""INSERT INTO failed_details(record_key,source,item_json,last_error,attempts,last_attempt)
                    VALUES(?,?,?,?,1,?) ON CONFLICT(record_key) DO UPDATE SET
                    item_json=excluded.item_json, last_error=excluded.last_error,
                    attempts=failed_details.attempts+1, last_attempt=excluded.last_attempt""",
                 (key, source, json.dumps(item, ensure_ascii=False), str(error)[-1000:], stamp()))


def retry_failed_details(conn: sqlite3.Connection, taxonomy: AuthorityTaxonomy, *,
                         executable: str, log: Callable[[str], None],
                         force: bool = False) -> int:
    recovered = 0
    rows = conn.execute("SELECT record_key,source,item_json,last_attempt FROM failed_details ORDER BY last_attempt").fetchall()
    for key, source, item_json, last_attempt in rows:
        try:
            recent = datetime.fromisoformat(last_attempt)
        except (ValueError, TypeError):
            recent = datetime.min.replace(tzinfo=timezone.utc)
        if not force and datetime.now(timezone.utc) - recent < RETRY_COOLDOWN:
            continue
        item = json.loads(item_json)
        try:
            actual_key, args = detail_identity(item, source)
            if actual_key != key:
                raise RuntimeError("FIM-Identifikator hat sich geändert")
            detail = call_fim(*args, executable=executable)
            write_record(conn, taxonomy, source, item, key, detail)
        except (RuntimeError, ValueError, KeyError, TypeError) as exc:
            register_failure(conn, key, source, item, exc)
            conn.commit()
            log(f"[{source}] Detail weiterhin nicht abrufbar ({key}): {str(exc)[:220]}")
        else:
            conn.execute("DELETE FROM failed_details WHERE record_key=?", (key,))
            conn.commit()
            recovered += 1
            log(f"[{source}] Nachträglich geladen: {key}")
    return recovered


def sync_catalog(db_path: Path, taxonomy: AuthorityTaxonomy, *, sources: tuple[str, ...] = SOURCES,
                 max_records: int | None = None, pause: float = 0.05,
                 executable: str = "fim-portal", force_retry: bool = False,
                 workers: int = 1, max_rps: float | None = None,
                 printer: Callable[[str], None] | None = None) -> dict:
    """Page all sources, retaining failures and completing other records.

    Completion means no missing details. `max_records` is for testing only.
    Existing SQLite checkpoints (including the user's offset 319) are kept.
    """
    if max_records is not None and max_records < 1:
        raise ValueError("max_records muss > 0 sein")
    if not 1 <= workers <= 12:
        raise ValueError("workers muss zwischen 1 und 12 liegen")
    if max_rps is not None and not 0 < max_rps <= 100:
        raise ValueError("max_rps muss > 0 und <= 100 sein")
    if any(x not in SOURCES for x in sources):
        raise ValueError(f"Unbekannte FIM-Quelle. Erlaubt: {SOURCES}")
    log = printer or (lambda m: print(m, file=sys.stderr, flush=True))
    conn = connect_db(db_path)
    processed = 0
    pacer = RequestPacer(max_rps)
    try:
        # Only failures from previous launches are eligible here.
        retry_failed_details(conn, taxonomy, executable=executable, log=log, force=force_retry)
        for source in sources:
            offset, finished = get_progress(conn, source)
            if finished:
                log(f"[{source}] Katalogseiten bereits durchblättert ({offset} Einträge)")
                continue
            log(f"[{source}] Synchronisation ab Offset {offset}")
            while True:
                start = (offset // PAGE_SIZE) * PAGE_SIZE
                remaining_in_page = offset - start
                if source == "service-profiles":
                    args = ("service-profiles", "search", "--limit", str(PAGE_SIZE), "--offset", str(start))
                else:
                    args = ("service-texts", "search", "--source", source, "--limit", str(PAGE_SIZE), "--offset", str(start))
                try:
                    response = call_fim(*args, executable=executable)
                except RuntimeError as exc:
                    set_progress(conn, source, offset, error=f"Suchseite: {exc}"[:1000])
                    raise RuntimeError(f"FIM-Suchseite fehlgeschlagen ({source}, Offset {offset}): {exc}") from exc
                items = extract_items(response)
                total = response.get("total_count", response.get("total"))
                if len(items) < remaining_in_page:
                    raise RuntimeError(f"Pagination geändert: {source}, offset={offset}, page={len(items)}")
                if not items or remaining_in_page >= len(items):
                    if not items or (total is not None and offset >= int(total)) or len(items) < PAGE_SIZE:
                        set_progress(conn, source, offset, complete=True)
                        log(f"[{source}] Ende erreicht (Offset {offset}, API total={total})")
                        break
                # Fetch only a small ordered window concurrently. The main thread
                # remains the *only* SQLite writer and checkpoints every item.
                # A crash/restart can repeat in-flight requests, but not prior
                # committed records. Bounded windows allow Ctrl+C to stop swiftly.
                pending = items[remaining_in_page:]

                def fetch_one(item: dict) -> tuple[str | None, dict | None, Exception | None]:
                    try:
                        key, detail_args = detail_identity(item, source)
                    except (ValueError, TypeError, RuntimeError) as exc:
                        return None, None, exc
                    try:
                        pacer.wait()
                        return key, call_fim(*detail_args, executable=executable), None
                    except (RuntimeError, ValueError, KeyError, TypeError) as exc:
                        return key, None, exc

                # Use at most 2*workers outstanding calls; do not create 200
                # futures that would keep running after a keyboard interrupt.
                batch_size = max(1, workers * 2)
                with ThreadPoolExecutor(max_workers=workers) as pool:
                    for start_idx in range(0, len(pending), batch_size):
                        batch = pending[start_idx:start_idx + batch_size]
                        for item, (key, detail, error) in zip(batch, pool.map(fetch_one, batch)):
                            if key is None:
                                key = f"missing-id:{source}:{offset}"
                                assert error is not None
                                register_failure(conn, key, source, item, error)
                                log(f"[{source}] Kein Detail-Schlüssel bei Offset {offset}: {str(error)[:200]}")
                            elif error is not None:
                                register_failure(conn, key, source, item, error)
                                write_record(conn, taxonomy, source, item, key, None)
                                log(f"[{source}] Detail übersprungen, späterer Retry ({key}): {str(error)[:220]}")
                            else:
                                # Keep normalization and SQLite writes single-threaded.
                                try:
                                    write_record(conn, taxonomy, source, item, key, detail)
                                    conn.execute("DELETE FROM failed_details WHERE record_key=?", (key,))
                                except (RuntimeError, ValueError, KeyError, TypeError) as exc:
                                    register_failure(conn, key, source, item, exc)
                                    write_record(conn, taxonomy, source, item, key, None)
                                    log(f"[{source}] Ungültiges Detail, späterer Retry ({key}): {str(exc)[:220]}")
                            offset += 1
                            set_progress(conn, source, offset)
                            processed += 1
                            if processed % 50 == 0:
                                log(f"[{source}] {offset} durchblättert, {processed} in diesem Lauf")
                            if max_records is not None and processed >= max_records:
                                log("Test-Limit erreicht: KEINE Quelle als vollständig markiert")
                                return sync_status(conn)
                            if pause:
                                time.sleep(pause)
                if len(items) < PAGE_SIZE:
                    set_progress(conn, source, offset, complete=True)
                    log(f"[{source}] letzte Seite durchblättert ({offset} Einträge)")
                    break
        return sync_status(conn)
    finally:
        conn.close()


def sync_status(conn_or_path: sqlite3.Connection | Path) -> dict:
    own = isinstance(conn_or_path, Path)
    conn = connect_db(conn_or_path) if own else conn_or_path
    try:
        counts = conn.execute("SELECT COUNT(*), SUM(CASE WHEN json_array_length(json_extract(document,'$.behoerdenkategorien'))>0 THEN 1 ELSE 0 END) FROM records").fetchone()
        progress = {row[0]: {"processed": row[1], "finished": bool(row[2]), "error": row[3]}
                    for row in conn.execute("SELECT source,next_offset,finished,last_error FROM sync_progress")}
        failures = conn.execute("SELECT source, COUNT(*) FROM failed_details GROUP BY source").fetchall()
        missing = sum(count for _, count in failures)
        return {"total_records": counts[0] or 0, "with_authority": counts[1] or 0,
                "unmapped": (counts[0] or 0) - (counts[1] or 0),
                "missing_details": missing, "missing_details_by_source": dict(failures),
                "sources": progress,
                "all_sources_complete": all(progress.get(x, {}).get("finished", False) for x in SOURCES) and missing == 0}
    finally:
        if own:
            conn.close()


def export_jsonl(db_path: Path, output: Path) -> int:
    conn = connect_db(db_path)
    try:
        output.parent.mkdir(parents=True, exist_ok=True)
        partial = output.with_suffix(output.suffix + ".tmp")
        with partial.open("w", encoding="utf-8") as stream:
            count = 0
            for (body,) in conn.execute("SELECT document FROM records ORDER BY source, record_key"):
                stream.write(body + "\n")
                count += 1
        partial.replace(output)
        return count
    finally:
        conn.close()
