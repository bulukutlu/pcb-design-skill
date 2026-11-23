#!/usr/bin/env python3
"""Routing-loop metrics from a kicad-cli DRC report and (optionally) the board file.

Usage:
  kicad-cli pcb drc --format json --schematic-parity -o drc.json board.kicad_pcb
  python drc_summary.py drc.json [board.kicad_pcb] [--json]

Prints: violations by type/severity, unconnected count, parity issues, and from the
board: vias, vias per routed net, track length per layer, top nets by via count.
Exit code 1 if errors or unconnected items remain.
"""
import json
import math
import os
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sexpr  # noqa: E402


def drc(path):
    d = json.load(open(path, encoding="utf-8"))
    v = d.get("violations", [])
    by = Counter((x.get("severity", "?"), x.get("type", "?")) for x in v)
    return {
        "violations_total": len(v),
        "errors": sum(n for (s, _), n in by.items() if s == "error"),
        "by_type": {f"{s}:{t}": n for (s, t), n in by.most_common()},
        "unconnected": len(d.get("unconnected_items", [])),
        "parity": len(d.get("schematic_parity", [])),
    }


def board(path):
    root = sexpr.load(path)
    names = {}
    for n in sexpr.children(root, "net"):
        if len(n) >= 3:
            names[n[1]] = n[2]

    def netname(node):
        n = sexpr.child(node, "net")
        if not n or len(n) < 2:
            return ""
        return names.get(n[1], n[1])

    length = defaultdict(float)
    nets_routed = set()
    for s in sexpr.children(root, "segment"):
        st, en = sexpr.child(s, "start"), sexpr.child(s, "end")
        lay = sexpr.child(s, "layer")
        L = math.dist((float(st[1]), float(st[2])), (float(en[1]), float(en[2])))
        length[lay[1] if lay else "?"] += L
        nets_routed.add(netname(s))
    vias = Counter()
    for v in sexpr.children(root, "via"):
        vias[netname(v)] += 1
    n_v = sum(vias.values())
    routed = max(len(nets_routed - {""}), 1)
    return {
        "vias": n_v,
        "routed_nets": routed,
        "vias_per_routed_net": round(n_v / routed, 2),
        "track_length_mm": {k: round(x, 1) for k, x in sorted(length.items())},
        "top_via_nets": vias.most_common(10),
    }


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        print(__doc__)
        sys.exit(2)
    out = {"drc": drc(args[0])}
    if len(args) > 1:
        out["board"] = board(args[1])
    if "--json" in sys.argv:
        print(json.dumps(out, indent=2))
    else:
        d = out["drc"]
        print(f"DRC: {d['violations_total']} violations ({d['errors']} errors), "
              f"{d['unconnected']} unconnected, {d['parity']} parity issues")
        for k, n in d["by_type"].items():
            print(f"  {n:4d}  {k}")
        if "board" in out:
            b = out["board"]
            print(f"Board: {b['vias']} vias, {b['routed_nets']} routed nets, "
                  f"{b['vias_per_routed_net']} vias/net")
            for lay, L in b["track_length_mm"].items():
                print(f"  {lay:<10} {L:9.1f} mm")
            print("  most vias:", ", ".join(f"{n}={c}" for n, c in b["top_via_nets"]))
    d = out["drc"]
    sys.exit(1 if d["errors"] or d["unconnected"] else 0)


if __name__ == "__main__":
    main()
