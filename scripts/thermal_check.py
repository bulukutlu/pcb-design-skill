#!/usr/bin/env python3
"""Junction-temperature check and cooling decision.

Usage:
  python thermal_check.py parts.json [--ta 40] [--margin 20]
  python thermal_check.py --part U5 --p 1.2 --theta-ja 45 --tj-max 125 [--ta 40]

parts.json: [{"ref": "U5", "p_w": 1.2, "theta_ja": 45, "tj_max": 125,
              "board_factor": 1.3}, ...]
  board_factor scales datasheet theta_JA (JEDEC 2s2p) to the real board:
  ~1.0 for a large 4-layer board with solid planes, 1.3-2.0 for small/2-layer boards.
Optional per part: "theta_jc" and "theta_sa" (heatsink) and "theta_cs" (interface).

Decision per part:
  OK passive      Tj <= Tj_max - margin with board copper only
  ADD COPPER      fails, but would pass with board_factor 1.0 (more copper/vias)
  HEATSINK        needs a heatsink (theta_jc given: required theta_SA printed)
  FORCED AIR      even a typical heatsink is not enough -> airflow or redesign
"""
import argparse
import json


def check(p, ta, margin):
    tj_lim = p["tj_max"] - margin
    bf = p.get("board_factor", 1.3)
    th = p["theta_ja"] * bf
    tj = ta + p["p_w"] * th
    res = {"ref": p["ref"], "p_w": p["p_w"], "theta_ja_eff": round(th, 1),
           "tj": round(tj, 1), "tj_limit": tj_lim}
    if tj <= tj_lim:
        res["decision"] = "OK passive"
    elif ta + p["p_w"] * p["theta_ja"] <= tj_lim:
        res["decision"] = "ADD COPPER / THERMAL VIAS"
    else:
        need_total = (tj_lim - ta) / p["p_w"] if p["p_w"] > 0 else float("inf")
        if "theta_jc" in p:
            sa = need_total - p["theta_jc"] - p.get("theta_cs", 0.5)
            res["required_theta_sa"] = round(sa, 1)
            res["decision"] = "HEATSINK" if sa > 2 else "FORCED AIR / REDESIGN"
        else:
            res["required_theta_ja"] = round(need_total, 1)
            res["decision"] = "HEATSINK or FORCED AIR (give theta_jc to size)"
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("file", nargs="?")
    ap.add_argument("--ta", type=float, default=40.0, help="max ambient °C (desk ~40)")
    ap.add_argument("--margin", type=float, default=20.0)
    ap.add_argument("--part"), ap.add_argument("--p", type=float)
    ap.add_argument("--theta-ja", type=float), ap.add_argument("--tj-max", type=float, default=125)
    ap.add_argument("--board-factor", type=float, default=1.3)
    a = ap.parse_args()
    if a.file:
        parts = json.load(open(a.file))
    elif a.part:
        parts = [{"ref": a.part, "p_w": a.p, "theta_ja": a.theta_ja,
                  "tj_max": a.tj_max, "board_factor": a.board_factor}]
    else:
        ap.print_help()
        return
    print(f"Ta = {a.ta} °C, margin = {a.margin} °C")
    print(f"{'ref':<8}{'P[W]':>6}{'θJA,eff':>9}{'Tj':>8}{'limit':>7}  decision")
    for p in parts:
        r = check(p, a.ta, a.margin)
        extra = ""
        if "required_theta_sa" in r:
            extra = f" (θSA ≤ {r['required_theta_sa']} K/W)"
        elif "required_theta_ja" in r:
            extra = f" (θJA ≤ {r['required_theta_ja']} K/W)"
        print(f"{r['ref']:<8}{r['p_w']:>6.2f}{r['theta_ja_eff']:>9.1f}{r['tj']:>8.1f}"
              f"{r['tj_limit']:>7.0f}  {r['decision']}{extra}")


if __name__ == "__main__":
    main()
