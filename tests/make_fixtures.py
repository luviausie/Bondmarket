#!/usr/bin/env python3
"""Buat data SINTETIS untuk uji offline. Bukan data pasar nyata.

Pemakaian:
  python tests/make_fixtures.py /tmp/fx
  python scripts/update.py --fixtures /tmp/fx
(lalu hapus data/ dan docs/data.json hasil uji sebelum commit)
"""
import math
import os
import random
import sys
from datetime import date, timedelta

out = sys.argv[1] if len(sys.argv) > 1 else "fixtures"
os.makedirs(out, exist_ok=True)
random.seed(7)

days = []
d = date(2025, 1, 1)
while len(days) < 520:
    if d.weekday() < 5:
        days.append(d)
    d += timedelta(days=1)


def walk(start, step, floor=None, drift=0.0, jump_at=None, jump=0.0):
    v, vals = start, []
    for i, _ in enumerate(days):
        v += random.gauss(drift, step)
        if jump_at is not None and i == jump_at:
            v += jump
        if floor is not None:
            v = max(floor, v)
        vals.append(v)
    return vals


series = {
    "DGS10": walk(4.2, 0.04, 1.0, 0.0012),
    "DGS2": walk(3.8, 0.04, 0.5, 0.0004),
    "BAMLH0A0HYM2": walk(3.0, 0.03, 2.0, 0.0, jump_at=len(days) - 4, jump=0.35),
    "BAMLC0A0CM": walk(0.9, 0.01, 0.5),
    "SP500": [5000 * math.exp(0.0004 * i + 0.01 * math.sin(i / 20)) for i in range(len(days))],
    "VIXCLS": walk(16, 0.6, 9),
    "CBBTCUSD": walk(60000, 900, 10000, 20),
}
series["T10Y2Y"] = [a - b for a, b in zip(series["DGS10"], series["DGS2"])]

for sid, vals in series.items():
    with open(os.path.join(out, sid + ".csv"), "w", encoding="utf-8") as fh:
        fh.write(f"observation_date,{sid}\n")
        for i, (dt_, v) in enumerate(zip(days, vals)):
            fh.write(f"{dt_.isoformat()},{'.' if i % 97 == 5 else round(v, 4)}\n")
print("fixtures ditulis ke", out)
