#!/usr/bin/env python3
"""Readability lint for KiCad schematics (.kicad_sch).

Checks things ERC does not: whether a human can read the drawing.
Usage: python sch_lint.py sheet1.kicad_sch [sheet2.kicad_sch ...] [--json]
Exit code 1 if any ERROR-level finding.

Checks
  E off-grid        symbol/wire/label/junction not on the 50 mil (1.27 mm) grid
  E diagonal-wire   wire not horizontal or vertical
  E label-on-pin    label that touches no wire (stacked directly on a pin)
  W label-near      two local labels with the same net closer than 25 mm
                    (should be a wire)
  W label-heavy     more labels than wires on the sheet
  E power-orient    power symbol rotated/mirrored (supplies up, grounds down)
  W four-way        four or more wire ends meeting at one point
  E unannotated     reference designator with '?'
  W no-footprint    placed symbol without footprint (excluding power/flags)
  W title-block     missing title / rev / date / company
"""
import json
import math
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sexpr  # noqa: E402

GRID = 1.27
TOL = 0.01
NEAR_MM = 25.0


def on_grid(v):
    r = v / GRID
    return abs(r - round(r)) * GRID < TOL


def prop(sym, name):
    for p in sexpr.children(sym, "property"):
        if len(p) > 2 and p[1] == name:
            return p[2]
    return None


def point_on_seg(p, a, b):
    (px, py), (ax, ay), (bx, by) = p, a, b
    if abs(ax - bx) < TOL:  # vertical
        return abs(px - ax) < TOL and min(ay, by) - TOL <= py <= max(ay, by) + TOL
    if abs(ay - by) < TOL:  # horizontal
        return abs(py - ay) < TOL and min(ax, bx) - TOL <= px <= max(ax, bx) + TOL
    # diagonal: distance to line
    d = abs((by - ay) * px - (bx - ax) * py + bx * ay - by * ax) / math.hypot(bx - ax, by - ay)
    return d < TOL and min(ax, bx) - TOL <= px <= max(ax, bx) + TOL


def lint(path):
    root = sexpr.load(path)
    f = []

    def add(level, code, msg, xy=None):
        loc = f" @({xy[0]:.2f},{xy[1]:.2f})" if xy else ""
        f.append({"file": os.path.basename(path), "level": level, "code": code,
                  "msg": msg + loc})

    # wires
    wires = []
    for w in sexpr.children(root, "wire"):
        pts = sexpr.child(w, "pts")
        xy = [(float(p[1]), float(p[2])) for p in sexpr.children(pts, "xy")]
        if len(xy) == 2:
            wires.append(tuple(xy))
    buses = []
    for b in sexpr.children(root, "bus"):
        pts = sexpr.child(b, "pts")
        xy = [(float(p[1]), float(p[2])) for p in sexpr.children(pts, "xy")]
        if len(xy) == 2:
            buses.append(tuple(xy))

    ends = defaultdict(int)
    for a, b in wires:
        for p in (a, b):
            if not (on_grid(p[0]) and on_grid(p[1])):
                add("E", "off-grid", "wire end off grid", p)
            ends[(round(p[0], 2), round(p[1], 2))] += 1
        if abs(a[0] - b[0]) > TOL and abs(a[1] - b[1]) > TOL:
            add("E", "diagonal-wire", "diagonal wire", a)
    for p, n in ends.items():
        if n >= 4:
            add("W", "four-way", f"{n} wire ends meet (use two T-junctions)", p)

    # labels
    local = defaultdict(list)
    n_labels = 0
    for tag in ("label", "hierarchical_label", "global_label"):
        for lab in sexpr.children(root, tag):
            n_labels += 1
            name = lab[1] if len(lab) > 1 and isinstance(lab[1], str) else "?"
            a = sexpr.at(lab)
            if not a:
                continue
            p = (a[0], a[1])
            if not (on_grid(p[0]) and on_grid(p[1])):
                add("E", "off-grid", f"{tag} '{name}' off grid", p)
            touches = any(point_on_seg(p, s, e) for s, e in wires + buses)
            if not touches:
                add("E", "label-on-pin",
                    f"{tag} '{name}' touches no wire — draw a short wire stub "
                    "(or a wire to the part if it is local)", p)
            if tag == "label":
                local[name].append(p)
    for name, pts in local.items():
        for i in range(len(pts)):
            for j in range(i + 1, len(pts)):
                d = math.dist(pts[i], pts[j])
                if d < NEAR_MM:
                    add("W", "label-near",
                        f"label '{name}' repeated {d:.1f} mm apart — use a wire", pts[i])
    n_wires = len(wires)
    if n_labels > n_wires and n_labels > 5:
        add("W", "label-heavy",
            f"{n_labels} labels vs {n_wires} wires — topology is hidden in labels")

    # junctions
    for j in sexpr.children(root, "junction"):
        a = sexpr.at(j)
        if a and not (on_grid(a[0]) and on_grid(a[1])):
            add("E", "off-grid", "junction off grid", a[:2])

    # symbols
    refs_seen = defaultdict(int)
    for s in sexpr.children(root, "symbol"):
        lib = sexpr.child(s, "lib_id")
        lib_id = lib[1] if lib else ""
        a = sexpr.at(s) or (0, 0, 0)
        ref = prop(s, "Reference") or "?"
        if not (on_grid(a[0]) and on_grid(a[1])):
            add("E", "off-grid", f"symbol {ref} ({lib_id}) off grid", a[:2])
        mirror = sexpr.child(s, "mirror")
        if lib_id.startswith("power:"):
            if (a[2] % 360) != 0 or mirror:
                add("E", "power-orient",
                    f"power symbol {lib_id} rotated {a[2]:.0f}° "
                    f"{'mirrored ' if mirror else ''}— supplies point up, grounds down", a[:2])
            continue
        if "?" in ref:
            add("E", "unannotated", f"{ref} ({lib_id}) not annotated", a[:2])
        refs_seen[ref] += 1
        fp = prop(s, "Footprint")
        if not fp and not ref.startswith("#"):
            add("W", "no-footprint", f"{ref} has no footprint", a[:2])

    # title block
    tb = sexpr.child(root, "title_block")
    have = {c[0] for c in tb[1:] if isinstance(c, list)} if tb else set()
    for need in ("title", "rev", "date", "company"):
        if need not in have:
            add("W", "title-block", f"title block missing '{need}'")

    stats = {"file": os.path.basename(path), "wires": n_wires, "labels": n_labels,
             "symbols": len(sexpr.children(root, "symbol"))}
    return f, stats


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    as_json = "--json" in sys.argv
    if not args:
        print(__doc__)
        sys.exit(2)
    all_f, all_s = [], []
    for p in args:
        f, s = lint(p)
        all_f += f
        all_s.append(s)
    if as_json:
        print(json.dumps({"findings": all_f, "stats": all_s}, indent=2))
    else:
        for s in all_s:
            print(f"[{s['file']}] symbols={s['symbols']} wires={s['wires']} labels={s['labels']}")
        for x in all_f:
            print(f"{x['level']} {x['code']:<14} {x['file']}: {x['msg']}")
        e = sum(1 for x in all_f if x["level"] == "E")
        w = len(all_f) - e
        print(f"\n{e} error(s), {w} warning(s)")
    sys.exit(1 if any(x["level"] == "E" for x in all_f) else 0)


if __name__ == "__main__":
    main()
