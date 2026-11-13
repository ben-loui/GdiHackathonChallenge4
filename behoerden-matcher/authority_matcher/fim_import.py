"""Optionaler FIM-Stammtext-Import über dokumentierten `fim-portal` CLI.

Die Bibliothek kommuniziert beim Import über die FIM-API; Queries laufen offline.
Das Importformat ist bewusst fehlertolerant, damit Änderungen transparent
auftauchen, statt eine angeblich vollständige Datenlage vorzutäuschen.
"""
from __future__ import annotations
import json
import subprocess
import sys
import time
from pathlib import Path

from .catalog import AuthorityTaxonomy, clean, first_shallow, normalize_record


def call_fim(*args: str, executable: str = "fim-portal") -> dict:
    """Call the public API with a long timeout and retries for transient failures.

    Keep the original HTTP/network error message, even if the CLI fails with
    an empty last log line. A 404 (exit 4) is not retried.
    """
    cmd = [executable, "--timeout", "60000", "--max-retries", "4", *args]
    for attempt in range(3):
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=105)
        except FileNotFoundError as exc:
            raise RuntimeError("'fim-portal' fehlt. Siehe README: npm install -g @maschinenlesbar.org/fim-portal-cli") from exc
        except subprocess.TimeoutExpired as exc:
            err = f"FIM-CLI Timeout bei {' '.join(args[:2])}, nach 105 Sekunden"
            code = 1
        else:
            code = proc.returncode
            err = (proc.stderr or proc.stdout or "(keine Fehlermeldung vom FIM-Client)").strip()[-1000:]
            if not code:
                try:
                    value = json.loads(proc.stdout)
                except json.JSONDecodeError as exc:
                    raise RuntimeError("Ungültige JSON-Antwort vom FIM-CLI") from exc
                if not isinstance(value, dict):
                    raise RuntimeError("Unerwartetes FIM-API-Format: JSON-Objekt erwartet")
                return value
        if code == 4:
            raise RuntimeError(f"FIM-Datensatz nicht vorhanden (404, CLI-Code 4): {err}")
        if attempt < 2:
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"FIM API CLI-Fehler ({code}), nach 3 Versuchen: {err}")


def extract_items(payload: dict) -> list[dict]:
    for name in ("items", "results", "data", "entries", "service_texts"):
        value = payload.get(name)
        if isinstance(value, list):
            return [x for x in value if isinstance(x, dict)]
    raise RuntimeError(f"FIM-Antwort ohne Ergebnisliste, Schluessel: {list(payload)[:10]}")


def keys_for_detail(item: dict, source: str) -> tuple[str, str, str] | None:
    red = first_shallow(item, ("redaktion_id", "redaktionId", "redaktion"))
    lid = first_shallow(item, ("leistung_id", "leistungId", "id"))
    src = first_shallow(item, ("source", "quelle")) or source
    if isinstance(red, (str, int)) and isinstance(lid, (str, int)) and str(red) and str(lid):
        return str(red), str(lid), str(src)
    return None


def collect_fim(path: Path, taxonomy: AuthorityTaxonomy, *, limit: int = 300,
                source: str = "leika", executable: str = "fim-portal") -> dict:
    if source not in ("leika", "landesredaktion"):
        raise ValueError("Nur FIM-Stammtexte (leika oder landesredaktion) sind für Variante A erlaubt")
    path.parent.mkdir(parents=True, exist_ok=True)
    stats = {"queried": 0, "normalized": 0, "categorized": 0, "missing_detail_id": 0,
             "missing_mapping": 0, "source": source}
    # Temporäre Datei verhindert irreführenden teilweisen Datenstand nach API-Fehler.
    partial = path.with_suffix(path.suffix + ".tmp")
    try:
        with partial.open("w", encoding="utf-8") as fh:
            offset, page_size = 0, min(200, max(1, limit))
            while stats["queried"] < limit:
                response = call_fim("service-texts", "search", "--source", source,
                                    "--limit", str(page_size), "--offset", str(offset),
                                    executable=executable)
                items = extract_items(response)
                if not items:
                    break
                for item in items:
                    if stats["queried"] >= limit:
                        break
                    stats["queried"] += 1
                    identity = keys_for_detail(item, source)
                    if not identity:
                        stats["missing_detail_id"] += 1
                        continue
                    # Details sind nötig: Die Suchtreffer enthalten nicht sicher das
                    # Zuständigkeitsfeld. Nicht die Freigabestelle als Ersatz benutzen!
                    detail = call_fim("service-texts", "get", *identity, executable=executable)
                    normalized = normalize_record(detail, taxonomy, origin=f"fim:{source}")
                    if not normalized:
                        stats["missing_mapping"] += 1
                        continue
                    normalized["fim_source_key"] = ":".join(identity)
                    fh.write(json.dumps(normalized, ensure_ascii=False) + "\n")
                    stats["normalized"] += 1
                    if normalized["behoerdenkategorien"]:
                        stats["categorized"] += 1
                    else:
                        stats["missing_mapping"] += 1
                offset += len(items)
                if len(items) < page_size:
                    break
        partial.replace(path)
    except Exception:
        partial.unlink(missing_ok=True)
        raise
    return stats
