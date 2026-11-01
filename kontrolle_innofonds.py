# -*- coding: utf-8 -*-
"""Ergaenzt die Innovationsfonds-Projektdatenbank die Landkarte - oder doppelt sie?

Offene Frage aus MANUAL.md. Der Innovationsfonds ist der groesste Geldgeber
der deutschen Versorgungsforschung; wenn seine Vorhaben ohnehin im DRKS
stehen, braucht die Landkarte ihn nicht als zweite Quelle. Stehen sie dort
nicht, ist er eine Pflichtquelle.

Gemessen wird ueber das **Akronym**, weil der Innovationsfonds seine Vorhaben
danach benennt und das DRKS ein eigenes Akronymfeld fuehrt. Zusaetzlich ueber
den Titel, falls kein Akronym vergeben wurde.

Die Akronyme kommen aus den Projektseiten des Innofonds-Portals
(`innofonds-portal/projekt/<akronym>/`) - das ist die veroeffentlichte
Auslieferung, nicht die Produktions-SQLite. Die gehoert ihrer eigenen Sitzung.

Gegenprobe: erfundene Akronyme duerfen nicht treffen, und sehr kurze Akronyme
werden getrennt ausgewiesen, weil "ACD" oder "ACC" sonst zufaellig treffen.

Aufruf:  py kontrolle_innofonds.py
"""
from __future__ import annotations

import json
import pathlib
import re
import sys
import zipfile

HIER = pathlib.Path(__file__).resolve().parent
DATEN = HIER / "daten"
PORTAL = HIER.parent / "innofonds-portal" / "projekt"
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ERFUNDEN = ["FLUNKERIA", "WOLKENKUCKUCK", "ZZZTESTXYZ"]
KURZ = 4          # Akronyme kuerzer als das gelten als unsicher


def projekte() -> dict[str, str]:
    """Akronym -> Titel aus den Projektseiten des Portals."""
    raus: dict[str, str] = {}
    for ordner in sorted(PORTAL.iterdir()):
        if not ordner.is_dir():
            continue
        idx = ordner / "index.html"
        titel = ""
        if idx.exists():
            m = re.search(r"<title>([^<]*)", idx.read_text(encoding="utf-8",
                                                           errors="replace"))
            if m:
                titel = m.group(1).split("·")[0].strip()
        raus[ordner.name] = titel
    return raus


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def main() -> int:
    quelle = sorted(DATEN.glob("drks-export-*.zip"))[-1]
    z = zipfile.ZipFile(quelle)
    name = [n for n in z.namelist() if n.startswith("DRKS") and n.endswith(".json")][0]
    roh = json.loads(z.read(name).decode("utf-8"))

    # Akronyme und Titel aller DRKS-Datensaetze einsammeln
    drks_akr: dict[str, list[str]] = {}
    drks_titel: list[tuple[str, str]] = []
    for x in roh:
        for b in (x.get("trialDescriptions") or []):
            a = norm(b.get("acronym"))
            if a:
                drks_akr.setdefault(a, []).append(x.get("drksId"))
            t = (b.get("title") or "").lower()
            if t:
                drks_titel.append((t, x.get("drksId")))

    proj = projekte()
    print(f"Quelle DRKS : {quelle.name} ({len(roh)} Datensaetze, "
          f"{len(drks_akr)} verschiedene Akronyme)")
    print(f"Innofonds   : {len(proj)} Vorhaben aus {PORTAL.name}/")

    treffer_akr, treffer_titel, unsicher, ohne = {}, {}, {}, []
    for akr, titel in proj.items():
        a = norm(akr)
        if a in drks_akr:
            ziel = unsicher if len(a) < KURZ else treffer_akr
            ziel[akr] = drks_akr[a]
            continue
        # Titelweg: der Innofonds-Titel muss im DRKS-Titel vorkommen
        t = (titel or "").lower()
        if len(t) > 25:
            fund = [i for dt, i in drks_titel if t[:40] in dt]
            if fund:
                treffer_titel[akr] = fund
                continue
        ohne.append(akr)

    n = len(proj)
    print(f"\n  ueber das Akronym im DRKS gefunden : {len(treffer_akr):>4}  "
          f"({len(treffer_akr)/n*100:.1f} %)")
    print(f"  nur ueber den Titel gefunden       : {len(treffer_titel):>4}  "
          f"({len(treffer_titel)/n*100:.1f} %)")
    print(f"  Akronym kuerzer als {KURZ} Zeichen (unsicher): {len(unsicher):>4}")
    print(f"  im DRKS NICHT gefunden             : {len(ohne):>4}  "
          f"({len(ohne)/n*100:.1f} %)")

    gef = len(treffer_akr) + len(treffer_titel)
    print(f"\n  Deckung gesamt (ohne die unsicheren): {gef} von {n} "
          f"= {gef/n*100:.1f} %")

    print("\nGegenprobe (duerfen NICHT treffen):")
    for e in ERFUNDEN:
        print(f"   {e:<16}{'TREFFER - FEHLER' if norm(e) in drks_akr else 'kein Treffer  ok'}")

    print("\nBeispiele gefundener Vorhaben (Akronym -> DRKS):")
    for akr, ids in list(treffer_akr.items())[:12]:
        print(f"   {akr:<22}{', '.join(ids[:2])}")

    print("\nBeispiele NICHT gefundener Vorhaben:")
    for akr in ohne[:12]:
        print(f"   {akr:<22}{(proj[akr] or '')[:58]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
