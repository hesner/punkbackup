"""v1.8.10: the "Reportes" screen, phase 1 (PLAN.md section 27). compute_report reads
a destination's index read-only and never closes a run that's really in progress.

Run with: .venv\\Scripts\\python.exe -m pytest tests -v
"""
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gui.reports import compute_report, count_text, duration_text, month_name, run_line, size_text, summary_lines
from server.manifest_db import ManifestDB


def _dest(tmp_path):
    dest = tmp_path / "dest"
    db = ManifestDB(dest)
    rows = [
        ("IMG_1.HEIC", "2014-03-02T10:00:00", 2_000_000),
        ("IMG_2.JPG", "2014-03-20T10:00:00", 1_000_000),
        ("IMG_3.heic", "2014-07-01T10:00:00", 3_000_000),
        ("VID_1.MOV", "2025-12-31T23:00:00", 1_500_000_000),
        ("odd.bin", "2025-01-01T00:00:00", 10),
        ("NODATE.JPG", None, 500_000),
        ("EMPTYDATE.JPG", "", 500_000),
    ]
    for i, (name, taken, size) in enumerate(rows):
        db.record_file(name, f"{i:064x}", taken, str(dest / f"x{i}" / name), size)
    done = db.start_run("cable")
    db.bump_run(done, "files_new")
    db.finish_run(done)
    live = db.start_run()
    db.bump_run(live, "files_error")
    db.close()
    return dest, live


def test_totals_kinds_and_dates(tmp_path):
    dest, _ = _dest(tmp_path)
    r = compute_report(str(dest))
    assert r["state"] == "ok"
    assert r["files"] == 7 and r["bytes"] == 1_507_000_010
    assert r["kinds"]["photos"] == (5, 7_000_000)
    assert r["kinds"]["videos"] == (1, 1_500_000_000)
    assert r["kinds"]["other"] == (1, 10)
    assert r["undated"] == (2, 1_000_000)
    assert (r["oldest"], r["newest"]) == ("2014-03-02", "2025-12-31")
    assert r["free_bytes"] > 0


def test_timeline_by_year_and_month(tmp_path):
    dest, _ = _dest(tmp_path)
    r = compute_report(str(dest))
    assert r["years"] == [("2014", 3, 6_000_000), ("2025", 2, 1_500_000_010)]
    assert r["months"]["2014"] == [("03", 2, 3_000_000), ("07", 1, 3_000_000)]


def test_runs_newest_first_and_the_live_one_stays_open(tmp_path):
    dest, live = _dest(tmp_path)
    r = compute_report(str(dest))
    assert [run["state"] for run in r["runs"]] == ["running", "done"]
    assert r["runs"][0]["id"] == live and r["runs"][0]["errors"] == 1
    assert r["runs"][1]["source"] == "cable" and r["runs"][1]["new"] == 1
    # Read-only: the run in progress is still open afterwards (AGENTS.md lesson 16).
    conn = sqlite3.connect(dest / ".iphone_backup_index" / "index.sqlite")
    assert conn.execute("SELECT finished_at FROM runs WHERE id = ?", (live,)).fetchone()[0] is None
    conn.close()


def test_missing_and_empty_destinations(tmp_path):
    assert compute_report(str(tmp_path / "unplugged"))["state"] == "unreachable"
    assert compute_report("")["state"] == "unreachable"
    (tmp_path / "new").mkdir()
    assert compute_report(str(tmp_path / "new"))["state"] == "empty"


def test_a_broken_index_is_reported_not_raised(tmp_path):
    index = tmp_path / "d" / ".iphone_backup_index"
    index.mkdir(parents=True)
    (index / "index.sqlite").write_bytes(b"not a database at all" * 100)
    r = compute_report(str(tmp_path / "d"))
    assert r["state"] == "error" and r["error"]


def test_second_copy_states(tmp_path):
    dest, _ = _dest(tmp_path)
    assert compute_report(str(dest))["mirror"] is None
    assert compute_report(str(dest), str(tmp_path / "unplugged"))["mirror"] == {"state": "not_connected"}
    mirror = tmp_path / "mirror"
    m = ManifestDB(mirror)
    m.record_file("IMG_1.HEIC", "0" * 64, "2014-03-02T10:00:00", str(mirror / "a"), 1)
    m.close()
    assert compute_report(str(dest), str(mirror))["mirror"] == {"state": "behind", "files": 1, "missing": 6}


def test_summary_text_both_languages(tmp_path):
    dest, _ = _dest(tmp_path)
    r = compute_report(str(dest))
    es = summary_lines(r, "es")
    assert es[0] == "7 archivos, 1,5 GB"
    assert "Fotos: 5 (7 MB)" in es and "Videos: 1 (1,5 GB)" in es and "Otros: 1 (<1 MB)" in es
    assert "Fechas de captura: del 2014-03-02 al 2025-12-31" in es
    assert "Sin fecha de captura: 2 (1 MB)" in es
    assert "Segunda copia: no configurada" in es
    en = summary_lines(r, "en")
    assert en[0] == "7 files, 1.5 GB" and "Second copy: not set up" in en


def test_small_formatters():
    assert count_text(50369, "es") == "50.369" and count_text(50369, "en") == "50,369"
    assert duration_text(None, "es") == "—"
    assert duration_text(20, "es") == "menos de 1 min"
    assert duration_text(11.5 * 60, "en") == "12 min"
    assert duration_text(3 * 3600 + 5 * 60, "es") == "3 h 5 min"
    assert month_name("03", "es") == "mar" and month_name("12", "en") == "Dec"
    assert size_text(0, "es") == "0 MB" and size_text(1573, "es") == "<1 MB" and size_text(4_000_000, "en") == "4 MB"


def test_run_line_text():
    run = {"started_at": "2026-11-05T16:11:52+00:00", "source": "wifi", "seconds": 690, "new": 5, "errors": 0,
           "state": "done"}
    line = run_line(run, "es")
    assert "WiFi" in line and "12 min" in line and "5 nuevos, 0 con error" in line and line.endswith("terminada")
    assert run_line({**run, "source": "cable", "state": "open"}, "en").endswith("never closed")
