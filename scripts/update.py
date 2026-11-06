#!/usr/bin/env python3
"""Tarik data FRED, hitung status & analisa bond market vs risk assets.

Hanya memakai library standar Python (3.10+). Tanpa API key: memakai endpoint CSV publik FRED.

Output:
  data/history.csv   - gabungan semua seri (harian)
  data/latest.json   - ringkasan terbaru
  docs/data.json     - sumber data untuk dashboard GitHub Pages
"""
import argparse
import csv
import io
import json
import os
import statistics
import sys
import time
import urllib.request
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# id FRED -> (label, satuan)
SERIES = {
    "DGS10": ("Yield US Treasury 10Y", "%"),
    "DGS2": ("Yield US Treasury 2Y", "%"),
    "T10Y2Y": ("Selisih 10Y-2Y", "%"),
    "BAMLH0A0HYM2": ("HY credit spread (OAS)", "%"),
    "BAMLC0A0CM": ("IG credit spread (OAS)", "%"),
    "SP500": ("S&P 500", "pts"),
    "VIXCLS": ("VIX", "pts"),
    "CBBTCUSD": ("Bitcoin (Coinbase)", "USD"),
}
URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}"
KEEP_DAYS = 365 * 5
SPARK_POINTS = 120


def load_config():
    with open(os.path.join(ROOT, "config.json"), encoding="utf-8") as fh:
        return json.load(fh)


def fetch(sid, fixtures=None):
    """Kembalikan list (tanggal 'YYYY-MM-DD', nilai float) tanpa nilai kosong."""
    if fixtures:
        with open(os.path.join(fixtures, sid + ".csv"), encoding="utf-8") as fh:
            text = fh.read()
    else:
        last_err = None
        for attempt in range(3):
            try:
                req = urllib.request.Request(
                    URL.format(sid=sid), headers={"User-Agent": "bond-terminal/1.0"}
                )
                with urllib.request.urlopen(req, timeout=30) as resp:
                    text = resp.read().decode("utf-8")
                break
            except Exception as exc:  # noqa: BLE001
                last_err = exc
                time.sleep(2 * (attempt + 1))
        else:
            raise RuntimeError(f"Gagal mengambil {sid}: {last_err}")
    rows = []
    reader = csv.reader(io.StringIO(text))
    next(reader, None)  # header
    for row in reader:
        if len(row) < 2 or row[1].strip() in ("", "."):
            continue
        try:
            rows.append((row[0].strip(), float(row[1])))
        except ValueError:
            continue
    return rows


def trim(rows):
    if not rows:
        return rows
    cutoff = datetime.fromisoformat(rows[-1][0]).toordinal() - KEEP_DAYS
    return [r for r in rows if datetime.fromisoformat(r[0]).toordinal() >= cutoff]


def delta(rows, n):
    """Perubahan nilai terakhir vs n observasi sebelumnya (None bila data kurang)."""
    if len(rows) <= n:
        return None
    return rows[-1][1] - rows[-1 - n][1]


def pct(rows, n):
    if len(rows) <= n or rows[-1 - n][1] == 0:
        return None
    return (rows[-1][1] / rows[-1 - n][1] - 1) * 100


def corr_yield_vs_spx(y10, spx, window=60):
    """Korelasi perubahan harian yield 10Y dengan return harian S&P 500."""
    ys = {d: v for d, v in y10}
    sp = dict(spx)
    dates = sorted(set(ys) & set(sp))[-(window + 1):]
    dy, dr = [], []
    for a, b in zip(dates, dates[1:]):
        dy.append(ys[b] - ys[a])
        dr.append(sp[b] / sp[a] - 1)
    if len(dy) < 20 or len(set(dy)) < 2 or len(set(dr)) < 2:
        return None
    return statistics.correlation(dy, dr)


def fmt(x, nd=2, sign=False):
    if x is None:
        return "n/a"
    if round(x, nd) == 0:
        x = 0.0  # hindari tampilan "-0.00"
    return f"{x:+.{nd}f}" if sign else f"{x:.{nd}f}"


def analyse(data, cfg):
    t = cfg["thresholds"]
    hy = data.get("BAMLH0A0HYM2", [])
    y10 = data.get("DGS10", [])
    curve = data.get("T10Y2Y", [])
    spx = data.get("SP500", [])
    vix = data.get("VIXCLS", [])
    btc = data.get("CBBTCUSD", [])

    out = {"status": "N/A", "quadrant": "N/A", "curve_state": "N/A", "analysis": []}
    notes = out["analysis"]

    # --- status spread (sinyal cepat) ---
    if hy:
        lvl = hy[-1][1]
        d5 = delta(hy, 5)
        d20 = delta(hy, 20)
        status = "TENANG"
        if lvl >= t["hy_level_waspada"] or (d5 is not None and d5 >= t["hy_chg5_waspada"]):
            status = "WASPADA"
        if lvl >= t["hy_level_bahaya"] or (d5 is not None and d5 >= t["hy_chg5_bahaya"]):
            status = "BAHAYA"
        out["status"] = status
        notes.append(
            f"HY spread {fmt(lvl)}% (5 hari {fmt(d5, 2, True)} poin, 20 hari {fmt(d20, 2, True)} poin) -> status {status}."
        )
    else:
        d20 = None

    # --- kuadran yield x spread ---
    if y10 and hy:
        dy20 = delta(y10, 20)
        yield_up = dy20 is not None and dy20 >= t["yield_up_20d"]
        wide = out["status"] in ("WASPADA", "BAHAYA") or (
            d20 is not None and d20 >= t["hy_chg20_widening"]
        )
        names = {
            (True, False): "Optimisme pertumbuhan (yield naik, spread tipis)",
            (True, True): "Ketakutan stagflasi (yield naik, spread melebar)",
            (False, False): "Goldilocks (yield turun/datar, spread tipis)",
            (False, True): "Ketakutan resesi (yield turun/datar, spread melebar)",
        }
        out["quadrant"] = names[(yield_up, wide)]
        impact = {
            (True, False): "Yield naik karena pertumbuhan kuat; bisa berjalan bersama saham naik, tapi pantau kecepatan kenaikan.",
            (True, True): "Kombinasi paling berbahaya untuk aset berisiko: biaya uang naik sementara rasa takut kredit ikut naik.",
            (False, False): "Umumnya mendukung aset berisiko.",
            (False, True): "Pasar mencari aman; aset berisiko cenderung tertekan.",
        }
        notes.append(f"Kuadran: {out['quadrant']}. {impact[(yield_up, wide)]}")
        notes.append(f"Yield 10Y {fmt(y10[-1][1])}% (20 hari {fmt(dy20, 2, True)} poin).")

    # --- bentuk kurva (sinyal lambat) ---
    if curve:
        c = curve[-1][1]
        if c < 0:
            state = "Inversi"
        elif c < t["curve_flat"]:
            state = "Datar"
        else:
            state = "Normal"
        out["curve_state"] = state
        line = f"Kurva 10Y-2Y {fmt(c)}% ({state})."
        recent = [v for _, v in curve[-252:]]
        if recent and min(recent) < 0 <= c:
            line += " Baru keluar dari inversi dalam setahun terakhir; secara historis fase ini sering dekat dengan perlambatan."
        notes.append(line)

    # --- aset berisiko ---
    if spx:
        p20 = pct(spx, 20)
        hi = max(v for _, v in spx[-252:])
        dd = (spx[-1][1] / hi - 1) * 100
        notes.append(f"S&P 500: 20 hari {fmt(p20, 1, True)}%, {fmt(dd, 1)}% dari puncak 52 minggu.")
    if vix:
        v = vix[-1][1]
        tag = "tinggi" if v >= 25 else "sedang" if v >= 18 else "rendah"
        notes.append(f"VIX {fmt(v, 1)} ({tag}).")
    if btc:
        notes.append(f"Bitcoin: 20 hari {fmt(pct(btc, 20), 1, True)}%.")
    if y10 and spx:
        rho = corr_yield_vs_spx(y10, spx)
        if rho is not None:
            rel = (
                "yield naik cenderung bersamaan dengan saham turun"
                if rho < -0.2
                else "yield naik cenderung bersamaan dengan saham naik"
                if rho > 0.2
                else "hubungan yield-saham lemah"
            )
            notes.append(f"Korelasi 60 hari (perubahan yield 10Y vs return S&P 500): {fmt(rho)} -> {rel}.")

    # --- divergensi spread vs ekuitas ---
    if out["status"] in ("WASPADA", "BAHAYA") and spx:
        hi = max(v for _, v in spx[-252:])
        if spx[-1][1] >= hi * 0.98:
            notes.append(
                "Divergensi: spread memburuk tetapi S&P 500 masih dekat puncak. Secara historis spread sering memberi sinyal lebih dulu."
            )
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fixtures", help="folder berisi <SERIES>.csv untuk uji offline")
    args = ap.parse_args()
    cfg = load_config()

    data, errors = {}, []
    for sid in SERIES:
        try:
            data[sid] = trim(fetch(sid, args.fixtures))
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{sid}: {exc}")
            print("WARN", sid, exc, file=sys.stderr)
    if not data:
        print("Tidak ada data yang berhasil diambil; berhenti.", file=sys.stderr)
        return 1

    # history.csv (outer join per tanggal)
    all_dates = sorted({d for rows in data.values() for d, _ in rows})
    lookup = {sid: dict(rows) for sid, rows in data.items()}
    os.makedirs(os.path.join(ROOT, "data"), exist_ok=True)
    os.makedirs(os.path.join(ROOT, "docs"), exist_ok=True)
    with open(os.path.join(ROOT, "data", "history.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["date"] + list(data))
        for d in all_dates:
            w.writerow([d] + [lookup[s].get(d, "") for s in data])

    result = analyse(data, cfg)
    indicators = {}
    for sid, rows in data.items():
        if not rows:
            continue
        label, unit = SERIES[sid]
        indicators[sid] = {
            "label": label,
            "unit": unit,
            "date": rows[-1][0],
            "value": rows[-1][1],
            "d5": delta(rows, 5),
            "d20": delta(rows, 20),
            "pct20": pct(rows, 20) if sid in ("SP500", "CBBTCUSD") else None,
        }
    payload = {
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"),
        "status": result["status"],
        "quadrant": result["quadrant"],
        "curve_state": result["curve_state"],
        "analysis": result["analysis"],
        "indicators": indicators,
        "spark": {sid: [v for _, v in rows[-SPARK_POINTS:]] for sid, rows in data.items()},
        "thresholds": cfg["thresholds"],
        "errors": errors,
    }
    for path in (os.path.join(ROOT, "data", "latest.json"), os.path.join(ROOT, "docs", "data.json")):
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=1)
    print(f"OK: status={result['status']} | {result['quadrant']} | kurva={result['curve_state']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
