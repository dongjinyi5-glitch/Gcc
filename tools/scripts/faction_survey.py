"""Survey the 33 characters and report the real colour make-up of each faction.

Why this exists
---------------
``SPEC`` in ``style_metrics.py`` was calibrated on Vinnie alone. Applying it to
a zombie would fail or, worse, pass while producing a normal-looking man. The
three factions do not share a palette: a gangster wears a suit, a zombie wears
rags over decayed flesh, a rat is fur. Inventing separate ranges without data
would just move the guess somewhere else, so this script measures the original
composite of every character first.

It reports, per faction:
  * pigment shares (what the art actually is)
  * luminance / chroma spread (how much tonal room the restyle has)
  * ink coverage (how much of the figure is already dark)

Output: validation/FACTION_SURVEY.json + a readable table on stdout.

CLI
---
    python faction_survey.py
"""
import json
import os
import sys

import numpy as np

import factions
from ggc_assets import PROJECT
from style_metrics import PIGMENTS, measure

CHARS_DIR = os.path.join(PROJECT, "extracted", "characters")
OUT = os.path.join(PROJECT, "validation", "FACTION_SURVEY.json")

ORDER = list(factions.FACTIONS)


def main():
    paths = sorted(p for p in os.listdir(CHARS_DIR) if p.endswith(".png"))
    rows = []
    for p in paths:
        name = os.path.splitext(p)[0]
        m = measure(os.path.join(CHARS_DIR, p))
        if m.get("empty") or "error" in m:
            print(f"  skip {p}: {m.get('error', 'empty')}")
            continue
        m["name"] = name
        m["faction"] = factions.faction_of(name)
        rows.append(m)

    unclassified = [r["name"] for r in rows if r["faction"] == "未归类"]
    if unclassified:
        print(f"!! unclassified: {unclassified}", file=sys.stderr)

    report = {"total": len(rows), "factions": {}}
    for f in ORDER + (["未归类"] if unclassified else []):
        sub = [r for r in rows if r["faction"] == f]
        if not sub:
            continue
        pig = {}
        for k in list(PIGMENTS) + ["未归类"]:
            vals = [r["pigment"].get(k, 0.0) for r in sub]
            pig[k] = round(float(np.mean(vals)), 3)
        chroma = [r for r in sub if r["pigment"].get("未归类", 0) < 0.95]
        entry = {
            "count": len(sub),
            "members": sorted(r["name"] for r in sub),
            "pigment_mean": pig,
            "ink_w_mean": round(float(np.mean([r["ink_w_mean"] for r in sub])), 2),
            "ink_cv": round(float(np.mean([r["ink_cv"] for r in sub])), 3),
            "ink_ratio": round(float(np.mean([r["ink_ratio"] for r in sub])), 3),
            "paper_ratio": round(float(np.mean([r["paper_ratio"] for r in sub])), 3),
            "saturation": round(float(np.mean([r["saturation"] for r in chroma])), 3),
            "texture_std": round(float(np.mean([r["texture_std"] for r in sub])), 2),
            "ink_levels": round(float(np.mean([r["ink_levels"] for r in sub])), 1),
            "alpha_cov": round(float(np.mean([r["alpha_cov"] for r in sub])), 3),
            "per_char": [
                {"name": r["name"], "ink_ratio": r["ink_ratio"],
                 "saturation": r["saturation"], "ink_w_mean": r["ink_w_mean"],
                 "pigment": r["pigment"]}
                for r in sorted(sub, key=lambda x: x["name"])
            ],
        }
        report["factions"][f] = entry

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)

    # ------------------------------------------------------------- print it
    hdr = f"{'faction':<6} {'n':>2} {'石青':>6} {'石绿':>6} {'朱红':>6} " \
          f"{'赭石':>6} {'藤黄':>6} {'花青':>6} {'未归':>6} " \
          f"{'墨率':>5} {'留白':>5} {'饱和':>5} {'肌理':>5}"
    print(hdr)
    print("-" * len(hdr))
    for f, e in report["factions"].items():
        p = e["pigment_mean"]
        print(f"{f:<6} {e['count']:>2} "
              f"{p['石青']:>6.3f} {p['石绿']:>6.3f} {p['朱红']:>6.3f} "
              f"{p['赭石']:>6.3f} {p['藤黄']:>6.3f} {p['花青']:>6.3f} "
              f"{p['未归类']:>6.3f} "
              f"{e['ink_ratio']:>5.3f} {e['paper_ratio']:>5.3f} "
              f"{e['saturation']:>5.3f} {e['texture_std']:>5.2f}")

    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
