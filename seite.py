# -*- coding: utf-8 -*-
"""Setzt Daten und die gemeinsamen Leisten in die Vorlage, schreibt landkarte.html.

Vorlage und Code sind getrennt: `vorlage.html` enthaelt HTML, CSS und
JavaScript, dieses Skript nur das Einsetzen. Grund ist die Hausregel, Code
nicht in Python-Zeichenketten zu halten - ein maskiertes n wird dort zum
echten Umbruch und zerlegt still das Skript.

**Die Leisten kommen aus `portal-vorlage`, nicht aus einer Kopie.** Die
schwarze Netzleiste mit allen 15 Hubs und die dunkle Fussleiste sind die
gepflegten Quellen der Reihe (Entwurf Mariann Stegmaier, 07.10.2026); wer sie
dort aendert, baut diese Seite neu und hat sie auch hier. Die beiden Logos
werden als data:-URI eingebettet, weil ein Artifact Bilder von fremden Hosts
nicht laedt.

Aufruf:  py seite.py
"""
from __future__ import annotations

import json
import pathlib
import sys

HIER = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HIER))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import leisten

PLATZ_DATEN = "/*__DATEN__*/"


def main() -> int:
    vorlage = (HIER / "_vorlage.html").read_text(encoding="utf-8")
    daten = json.loads((HIER / "daten" / "landkarte.json").read_text(encoding="utf-8"))

    # Das Standortverzeichnis traegt die Verbindung zur anderen Haelfte: Es
    # nennt je Profilseite alle Schreibweisen, unter denen der Standort im
    # Register auftaucht. Darueber verlinkt jede Studienkarte ihre
    # Einrichtung. Fehlt es, bleibt die Karte bedienbar, aber unverbunden.
    p_orte = HIER / "daten" / "standorte.json"
    if p_orte.exists():
        daten["standorte"] = json.loads(p_orte.read_text(encoding="utf-8"))
        n_orte = len(daten["standorte"]["standorte"])
    else:
        print("  HINWEIS: daten/standorte.json fehlt - erst `py standorte.py` "
              "laufen lassen, sonst bleibt der Reiter Standorte leer")
        daten["standorte"] = {"standorte": []}
        n_orte = 0

    # Die Umrisslinie fuer die Karte. Sie wird MITGELIEFERT, nicht nachgeladen:
    # ein Kachelserver saehe jede Bewegung der Lesenden. Fehlt die Datei,
    # bleibt die Karte aus und die Liste steht allein.
    p_kontur = HIER / "daten" / "kontur.json"
    if p_kontur.exists():
        k = json.loads(p_kontur.read_text(encoding="utf-8"))
        daten["kontur"] = k["ringe"]
        print(f"  Umriss: {len(k['ringe'])} Ringe, "
              f"{sum(len(r) for r in k['ringe'])} Punkte ({k['lizenz']})")
    else:
        print("  HINWEIS: daten/kontur.json fehlt - keine Karte. "
              "Erst `py kontur.py` laufen lassen.")
        daten["kontur"] = []

    for s in daten["studien"]:
        if s.get("kurz") and len(s["kurz"]) > 260:
            s["kurz"] = s["kurz"][:260].rsplit(" ", 1)[0] + " …"
        # Die auslösenden Begriffe bleiben, auf drei gekürzt. Eine
        # Punktzahl ohne Grund ist eine Behauptung; mit Grund ist sie
        # nachprüfbar.
        s["vf_begriffe"] = (s.get("vf_begriffe") or [])[:3]

    if PLATZ_DATEN not in vorlage:
        print(f"FEHLER: Platzhalter {PLATZ_DATEN} fehlt in vorlage.html")
        return 1

    netz, fuss = leisten.beide()

    # `</script>` im Datenstrom wuerde den JSON-Block vorzeitig schliessen.
    roh = json.dumps(daten, ensure_ascii=False).replace("</", "<\\/")
    # Derselbe leere Endpunkt wie auf den Profilseiten. Solange er leer
    # ist, sagt das Mitmach-Formular das ehrlich und sendet nichts.
    from standorte import ENDPUNKT
    seite = (leisten.einsetzen(vorlage, netz, fuss)
             .replace(PLATZ_DATEN, roh)
             .replace("{{ENDPUNKT}}", ENDPUNKT))

    # index.html, damit GitHub Pages die Seite unter studien.m-vf.de/
    # ausliefert. landkarte.html bleibt als Name bestehen, weil die
    # Profilseiten darauf verweisen - beide zeigen dasselbe.
    ziel = HIER / "index.html"
    ziel.write_text(seite, encoding="utf-8")
    print(f"{len(daten['studien'])} Studien, {n_orte} Standorte, "
          f"Stand {daten['stand']}")
    print(f"  Netzleiste {len(netz)//1024} KB, Fussleiste {len(fuss)//1024} KB, "
          f"Logos eingebettet")
    # Zweitname fuer die Verweise aus den Profilseiten.
    (HIER / "landkarte.html").write_text(
        ziel.read_text(encoding="utf-8"), encoding="utf-8")
    print(f"geschrieben: {ziel}  ({ziel.stat().st_size/1e6:.2f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
