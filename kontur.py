"""Holt EINMAL die Umrisslinie Deutschlands und legt sie als Pfad ab.

Quelle: Natural Earth, 1:50m, **Public Domain** - keine Namensnennung
noetig, keine Lizenzbedingung, die wir weitergeben muessten. Bezogen ueber
das Paket `world-atlas`, das die Natural-Earth-Daten als TopoJSON fuehrt.

  py kontur.py              holt und schreibt daten/kontur.json
  py kontur.py --gegentest  prueft die Entpackung ohne Netz

Warum ueberhaupt eine eigene Datei und keine Kartenbibliothek: Die
Landkarte ist eine EINZELNE HTML-Datei ohne Nachladen - keine Kachelserver,
keine fremden Aufrufe, kein Cookie. Das Versprechen der Knowledge-Hubs
lautet „keine Cookies“, und ein Kachelserver sieht jede Bewegung mit.
Darum: Umriss einmal holen, als Pfaddaten einbetten, fertig.

TopoJSON ist bewusst nicht in der Seite entpackt worden - das Entpacken
(Bogenketten, Delta-Kodierung, Quantisierung) passiert hier, einmal, und
auf der Seite stehen nur fertige Koordinaten.
"""
import json
import pathlib
import sys
import urllib.request

HIER = pathlib.Path(__file__).parent
DATEN = HIER / "daten"
QUELLE = "https://unpkg.com/world-atlas@2.0.2/countries-50m.json"
UA = {"User-Agent": "vf-landkarte/1.0 (mailto:stegmaier@m-vf.de)"}


def entpacken(topo, land="Germany"):
    """TopoJSON -> Liste von Ringen, jeder eine Liste von (lon, lat).

    TopoJSON speichert Linien EINMAL (als „arcs“) und setzt Flaechen daraus
    zusammen; ein negativer Index bedeutet „denselben Bogen rueckwaerts“,
    geschrieben als ~i, also -i-1. Die Punkte sind delta-kodiert und
    quantisiert - ohne transform waeren es rohe Gitterzahlen.
    """
    tr = topo.get("transform") or {}
    sx, sy = (tr.get("scale") or [1, 1])
    dx, dy = (tr.get("translate") or [0, 0])

    def bogen(i):
        rueckwaerts = i < 0
        if rueckwaerts:
            i = ~i
        punkte, x, y = [], 0, 0
        for p in topo["arcs"][i]:
            if tr:
                x += p[0]
                y += p[1]
                punkte.append((x * sx + dx, y * sy + dy))
            else:
                punkte.append((p[0], p[1]))
        return punkte[::-1] if rueckwaerts else punkte

    def kette(idx):
        punkte = []
        for i in idx:
            teil = bogen(i)
            # Der letzte Punkt eines Bogens ist der erste des naechsten.
            punkte.extend(teil[1:] if punkte else teil)
        return punkte

    geo = topo["objects"]["countries"]["geometries"]
    treffer = [g for g in geo if (g.get("properties") or {}).get("name") == land]
    if not treffer:
        raise RuntimeError(f"{land} nicht im Datensatz")
    g = treffer[0]
    ringe = []
    if g["type"] == "Polygon":
        ringe = [kette(r) for r in g["arcs"]]
    elif g["type"] == "MultiPolygon":
        for teil in g["arcs"]:
            ringe.extend(kette(r) for r in teil)
    else:
        raise RuntimeError(f"unerwarteter Typ {g['type']}")
    return ringe


def gegentest():
    """Prueft die Entpackung an einem kleinen, von Hand gerechneten Fall."""
    ok = True
    topo = {
        "transform": {"scale": [1.0, 1.0], "translate": [10.0, 50.0]},
        "arcs": [[[0, 0], [2, 0], [0, 2]],        # (10,50) (12,50) (12,52)
                 [[2, 2], [-2, 0], [0, -2]]],     # (12,52) (10,52) (10,50)
        "objects": {"countries": {"geometries": [
            {"type": "Polygon", "arcs": [[0, 1]],
             "properties": {"name": "Germany"}}]}},
    }
    r = entpacken(topo)
    soll = [(10.0, 50.0), (12.0, 50.0), (12.0, 52.0), (10.0, 52.0), (10.0, 50.0)]
    pruef = [
        ("ein Ring", len(r) == 1),
        ("Delta-Kodierung aufgeloest", r[0] == soll),
    ]
    # Rueckwaerts gelesener Bogen: ~0 = -1
    topo2 = json.loads(json.dumps(topo))
    topo2["objects"]["countries"]["geometries"][0]["arcs"] = [[-1]]
    r2 = entpacken(topo2)
    pruef.append(("negativer Index liest rueckwaerts",
                  r2[0] == [(12.0, 52.0), (12.0, 50.0), (10.0, 50.0)]))
    # Doppelpunkt an der Naht darf nicht zweimal auftauchen
    pruef.append(("Naht nicht doppelt",
                  r[0].count((12.0, 52.0)) == 1))
    for text, gut in pruef:
        ok = ok and gut
        print(f"  {'ok ' if gut else 'FEHLER'} {text}")
    print("\n" + ("Gegentest bestanden." if ok else "GEGENTEST GESCHEITERT."))
    return ok


def main():
    if "--gegentest" in sys.argv:
        return 0 if gegentest() else 1

    print(f"hole {QUELLE}")
    req = urllib.request.Request(QUELLE, headers=UA)
    with urllib.request.urlopen(req, timeout=120) as f:
        topo = json.loads(f.read().decode("utf-8"))
    ringe = entpacken(topo)
    punkte = sum(len(r) for r in ringe)
    lons = [p[0] for r in ringe for p in r]
    lats = [p[1] for r in ringe for p in r]
    print(f"  {len(ringe)} Ringe, {punkte} Punkte")
    print(f"  Laenge {min(lons):.2f}–{max(lons):.2f}, "
          f"Breite {min(lats):.2f}–{max(lats):.2f}")
    if not (5 < min(lons) < 7 and 14 < max(lons) < 16
            and 47 < min(lats) < 48 and 54 < max(lats) < 56):
        print("  WARNUNG: Die Ausdehnung passt nicht zu Deutschland.")
        return 1

    # Auf fuenf Nachkommastellen runden - das ist gut einen Meter und
    # halbiert die Datei. Mehr braucht ein Umriss auf 900 Pixeln nicht.
    ringe = [[[round(x, 5), round(y, 5)] for x, y in r] for r in ringe]
    ziel = DATEN / "kontur.json"
    ziel.write_text(json.dumps({
        "quelle": "Natural Earth 1:50m via world-atlas@2.0.2",
        "lizenz": "Public Domain (Natural Earth)",
        "geholt": "2026-11-01",
        "ringe": ringe,
    }, ensure_ascii=False), encoding="utf-8")
    print(f"-> daten/kontur.json ({ziel.stat().st_size / 1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
