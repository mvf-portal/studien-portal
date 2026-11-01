# -*- coding: utf-8 -*-
"""Holt den DRKS-Gesamtexport nach daten/drks-export-JJJJ-MM-TT.zip.

Das DRKS hat keine API. Es gibt genau einen Weg an den Gesamtbestand:
`https://drks.de/search/en/download/all-json` liefert ein ZIP mit dem ganzen
Register als JSON (am 30.10.2026: 87,8 MB ZIP, 349 MB JSON, 22.737
Datensaetze). Der Download dauert mehrere Minuten.

**Das Abrufdatum ist keine Zierde, sondern Lizenzpflicht.** Die
Nutzungsbedingungen verlangen bei jeder Weitergabe die Quelle „DRKS" UND das
Datum, an dem die Daten geholt wurden. Es steckt deshalb im Dateinamen, und
`bauen.py` liest es von dort in die Seite. Wer die Datei umbenennt, bricht
diese Kette.

Nur Eintraege ab 2025 (registriert oder aktualisiert) stehen unter CC BY 4.0;
den Filter setzt `bauen.py`, nicht dieses Skript - hier wird der Bestand
vollstaendig abgelegt, damit auch Messungen moeglich sind, die nicht
veroeffentlicht werden.

Aufruf:
    py holen.py              # holt, wenn der heutige Stand noch fehlt
    py holen.py --erzwingen  # holt auch dann, wenn er schon da ist
    py holen.py --pruefen    # prueft nur, was da ist
"""
from __future__ import annotations

import argparse
import datetime
import json
import pathlib
import sys
import urllib.request
import zipfile

HIER = pathlib.Path(__file__).resolve().parent
DATEN = HIER / "daten"
QUELLE = "https://drks.de/search/en/download/all-json"
KENNUNG = ("mvf-vf-landkarte (Monitor Versorgungsforschung, "
           "stegmaier@m-vf.de)")
MINDEST_MB = 50          # darunter ist es keine Vollauslieferung

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def vorhandene() -> list[pathlib.Path]:
    return sorted(DATEN.glob("drks-export-*.zip"))


def pruefe(p: pathlib.Path) -> tuple[bool, str]:
    """Ist das eine brauchbare Vollauslieferung? Gibt (ok, Befund) zurueck."""
    mb = p.stat().st_size / 1e6
    if mb < MINDEST_MB:
        return False, f"nur {mb:.1f} MB - zu klein fuer den Gesamtbestand"
    try:
        z = zipfile.ZipFile(p)
    except zipfile.BadZipFile:
        return False, "kein lesbares ZIP (meist eine Fehlerseite statt der Datei)"
    namen = [n for n in z.namelist() if n.startswith("DRKS") and n.endswith(".json")]
    if not namen:
        return False, f"keine DRKS-JSON im Archiv, enthalten: {z.namelist()}"
    try:
        d = json.loads(z.read(namen[0]).decode("utf-8"))
    except Exception as e:
        return False, f"JSON nicht lesbar: {e}"
    if not isinstance(d, list) or not d:
        return False, "JSON ist keine nichtleere Liste"
    if "drksId" not in d[0]:
        return False, "Datensaetze ohne drksId - Format hat sich geaendert"
    return True, (f"{mb:.1f} MB, {len(d)} Datensaetze, "
                  f"Archivdatei {namen[0]}")


def hole(ziel: pathlib.Path) -> None:
    print(f"lade {QUELLE}")
    print("  (mehrere Minuten, rund 88 MB)")
    teil = ziel.with_suffix(".teil")
    anfrage = urllib.request.Request(QUELLE, headers={"User-Agent": KENNUNG})
    with urllib.request.urlopen(anfrage, timeout=900) as r, open(teil, "wb") as f:
        gesamt = 0
        while True:
            brocken = r.read(1 << 20)
            if not brocken:
                break
            f.write(brocken)
            gesamt += len(brocken)
            print(f"\r  {gesamt/1e6:7.1f} MB", end="")
            sys.stdout.flush()
    print()
    ok, befund = pruefe(teil)
    if not ok:
        teil.unlink(missing_ok=True)
        raise SystemExit(f"FEHLER: Download unbrauchbar - {befund}")
    teil.replace(ziel)
    print(f"  geprueft: {befund}")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--erzwingen", action="store_true",
                   help="auch holen, wenn der heutige Stand schon da ist")
    p.add_argument("--pruefen", action="store_true",
                   help="nur pruefen, was in daten/ liegt")
    a = p.parse_args()

    DATEN.mkdir(exist_ok=True)

    if a.pruefen:
        da = vorhandene()
        if not da:
            print("kein Export in daten/")
            return 1
        for f in da:
            ok, befund = pruefe(f)
            print(f"{'ok  ' if ok else 'FEHL'} {f.name}: {befund}")
        return 0

    heute = datetime.date.today().isoformat()
    ziel = DATEN / f"drks-export-{heute}.zip"

    if ziel.exists() and not a.erzwingen:
        ok, befund = pruefe(ziel)
        if ok:
            print(f"{ziel.name} ist schon da ({befund})")
            print("  --erzwingen laedt trotzdem neu")
            return 0
        print(f"{ziel.name} ist unbrauchbar ({befund}) - wird neu geholt")

    hole(ziel)
    print(f"\ngeschrieben: {ziel}")

    alt = [f for f in vorhandene() if f != ziel]
    if alt:
        print(f"\naeltere Staende in daten/ ({len(alt)}): "
              f"{', '.join(f.name for f in alt)}")
        print("  bleiben liegen - ein frueherer Stand ist der Beleg fuer eine "
              "frueher veroeffentlichte Fassung.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
