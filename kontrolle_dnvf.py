# -*- coding: utf-8 -*-
"""Abdeckungstest: Findet die Landkarte die Leute, die das Fach ausmachen?

Peter am 30.10.2026 zur DNVF-Gruppe der HochschullehrerInnen: „sind die alle
drin?" Die 52 Mitglieder sind der haerteste verfuegbare Pruefstein - wer in
Deutschland Versorgungsforschung betreibt, steht hier. Fehlt die Gruppe in der
Karte, taugt die Karte nicht.

Gemessen wird auf drei Ebenen, weil jede etwas anderes beantwortet:

  A) im gesamten DRKS          - ist die Person ueberhaupt im Register?
  B) im CC-BY-Teil             - duerfen wir sie zeigen?
  C) in der VF-Auswahl (710)   - hat unsere Heuristik sie gefunden?

Die Namen bleiben hier. In die veroeffentlichte Karte gehen nur Einrichtung
und Ort - diese Messung liest Personennamen aus dem Register, gibt sie aber
nicht weiter.

Gegenprobe eingebaut: erfundene Namen duerfen nicht treffen, und der
Nachname-allein-Treffer wird getrennt ausgewiesen, weil „Hoffmann" oder
„Schulz" sonst jede Menge Fremdtreffer liefert.

Aufruf:  py kontrolle_dnvf.py
"""
from __future__ import annotations

import collections
import json
import pathlib
import re
import sys
import zipfile

HIER = pathlib.Path(__file__).resolve().parent
DATEN = HIER / "daten"
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# DNVF, Gruppe der HochschullehrerInnen, Stand 30.10.2026 (52 Mitglieder).
# Nachname, Vorname, Ort laut DNVF-Seite.
GRUPPE = [
    ("Pfaff", "Holger", "Köln"), ("Ernstmann", "Nicole", "Bonn"),
    ("Altiner", "Attila", "Rostock"), ("Ansmann", "Lena", "Oldenburg"),
    ("Augustin", "Mattias", "Hamburg"), ("Büscher", "Andreas", "Osnabrück"),
    ("Busse", "Reinhard", "Berlin"), ("Dreinhöfer", "Karsten", "Berlin"),
    ("Farin-Glattacker", "Erik", "Freiburg"), ("Freitag", "Michael", "Oldenburg"),
    ("Geraedts", "Max", "Marburg"), ("Gerhardus", "Ansgar", "Bremen"),
    ("Grill", "Eva", "München"), ("Hämel", "Kerstin", "Bielefeld"),
    ("Hausen", "Anita", "München"), ("Herrmann", "Wolfram", "Berlin"),
    ("Hertrampf", "Katrin", "Kiel"), ("Holmberg", "Christine", "Brandenburg"),
    ("Hoffmann", "Falk", "Oldenburg"), ("Hoffmann", "Wolfgang", "Greifswald"),
    ("Icks", "Andrea", "Düsseldorf"), ("Karbach", "Ute", "Dortmund"),
    ("Klinkhammer-Schalke", "Monika", "Regensburg"),
    ("Köberlein-Neu", "Juliane", "Wuppertal"),
    ("Kolominsky-Rabas", "Peter", "Erlangen"),
    ("König", "Hans-Helmut", "Hamburg"), ("Krummenauer", "Frank", "Witten"),
    ("Kuske", "Silke", "Düsseldorf"), ("Langer", "Thorsten", "Lübeck"),
    ("Laux", "Gunter", "Heidelberg"), ("Lefering", "Rolf", "Witten"),
    ("Minden", "Kirsten", "Berlin"), ("Neugebauer", "Edmund", "Brandenburg"),
    ("Nienhaus", "Albert", "Hamburg"), ("Otte", "Ina", "Bochum"),
    ("Reuschenbach", "Bernd", "München"), ("Riedel-Heller", "Steffi", "Leipzig"),
    ("Schmailzl", "Kurt", "Brandenburg"), ("Schmitt", "Jochen", "Dresden"),
    ("Scholten", "Nadine", "Köln"), ("Schreyögg", "Jonas", "Hamburg"),
    ("Schulz", "Holger", "Hamburg"),
    ("Siebenhofer-Kroitzsch", "Andrea", "Frankfurt"),
    ("Stock", "Stephanie", "Köln"), ("Szecsenyi", "Joachim", "Heidelberg"),
    ("Vollmar", "Horst Christian", "Bochum"), ("Voltz", "Raymond", "Köln"),
    ("Wensing", "Michel", "Heidelberg"), ("Wolf-Ostermann", "Karin", "Bremen"),
    ("Möhler", "Ralph", "Düsseldorf"), ("Pieper", "Dawid", "Rüdersdorf"),
    ("van den Berg", "Neeltje", "Greifswald"),
]

# Gegenprobe: diese darf die Messung NICHT finden.
ERFUNDEN = [
    ("Flunkerhuber", "Xaver", "Hintertupfingen"),
    ("Wolkenkuckucks", "Adelheid", "Wolkenheim"),
    ("Pfaffenhofer", "Holger", "Köln"),     # aehnelt Pfaff, ist aber ein anderer
]


def norm(s: str) -> str:
    s = (s or "").lower()
    return (s.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue")
             .replace("ß", "ss").strip())


def personen(x: dict) -> list[tuple[str, str, str]]:
    """Alle (Nachname, Vorname, Ort) eines Datensatzes."""
    raus = []
    for k in (x.get("trialContacts") or []):
        c = k.get("contact") or {}
        if c.get("lastName"):
            raus.append((norm(c.get("lastName")), norm(c.get("firstName") or ""),
                         norm(c.get("city") or "")))
    for v in ((x.get("ethicsCommittee") or {}).get("ethicVotes") or []):
        c = v.get("contact") or {}
        if c.get("lastName"):
            raus.append((norm(c.get("lastName")), norm(c.get("firstName") or ""),
                         norm(c.get("city") or "")))
    return raus


def messe(menge: list[dict], liste, etikett: str) -> dict:
    """Wie viele der Liste kommen in dieser Datensatzmenge vor?"""
    streng = collections.Counter()     # Nachname UND Ort
    locker = collections.Counter()     # Nachname allein
    for x in menge:
        p = personen(x)
        if not p:
            continue
        nachnamen = {n for n, _, _ in p}
        namen_ort = {(n, o) for n, _, o in p}
        for nach, vor, ort in liste:
            nn, oo = norm(nach), norm(ort)
            if nn in nachnamen:
                locker[(nach, ort)] += 1
                if any(nn == a and oo and oo in b for a, b in namen_ort):
                    streng[(nach, ort)] += 1
    print(f"\n{etikett}  ({len(menge)} Datensaetze)")
    print(f"  mit Nachname UND Ort gefunden : {len(streng)} von {len(liste)}")
    print(f"  nur ueber den Nachnamen       : {len(locker)} von {len(liste)}"
          f"   (unsicher, Namensvettern)")
    return {"streng": streng, "locker": locker}


def main() -> int:
    quelle = sorted(DATEN.glob("drks-export-*.zip"))[-1]
    z = zipfile.ZipFile(quelle)
    name = [n for n in z.namelist() if n.startswith("DRKS") and n.endswith(".json")][0]
    roh = json.loads(z.read(name).decode("utf-8"))

    def jahr(v):
        return str(v)[:4] if v else "0"
    ccby = [x for x in roh
            if jahr(x.get("lastUpdate")) >= "2025" or jahr(x.get("registrationDrks")) >= "2025"]

    lk = json.loads((DATEN / "landkarte.json").read_text(encoding="utf-8"))
    vf_ids = {s["id"] for s in lk["studien"]}
    vf = [x for x in roh if x.get("drksId") in vf_ids]

    print(f"Quelle: {quelle.name}")
    print(f"DNVF-Gruppe der HochschullehrerInnen: {len(GRUPPE)} Mitglieder")

    a = messe(roh, GRUPPE, "A) Gesamtes DRKS")
    b = messe(ccby, GRUPPE, "B) CC-BY-Teil (das, was wir zeigen duerfen)")
    c = messe(vf, GRUPPE, "C) VF-Auswahl der Landkarte")

    print("\nGegenprobe (darf NICHT treffen):")
    g = messe(roh, ERFUNDEN, "   erfundene Namen im gesamten DRKS")
    print("   Gegenprobe bestanden." if not g["streng"]
          else f"   GEGENPROBE FEHLGESCHLAGEN: {dict(g['streng'])}")

    print("\nWer in der VF-Auswahl steht (Nachname und Ort, mit Studienzahl):")
    for (nach, ort), n in c["streng"].most_common():
        print(f"   {n:>3}  {nach}, {ort}")

    fehlend = [f"{n} ({o})" for n, _, o in GRUPPE if (n, o) not in c["streng"]]
    print(f"\nIn der VF-Auswahl NICHT gefunden: {len(fehlend)} von {len(GRUPPE)}")
    for f in fehlend:
        print(f"   {f}")

    nur_ausserhalb = [f"{n} ({o})" for n, _, o in GRUPPE
                      if (n, o) in a["streng"] and (n, o) not in b["streng"]]
    print(f"\nIm Register vorhanden, aber durch die Lizenzgrenze verloren: "
          f"{len(nur_ausserhalb)}")
    for f in nur_ausserhalb:
        print(f"   {f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
