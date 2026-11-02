# -*- coding: utf-8 -*-
"""Fachgebiete der MVF-Beitraege bei OpenAlex.

WARUM NUR DAS FACHGEBIET
------------------------
Der erste Lauf am 01.11.2026 hat die eigentliche Hoffnung widerlegt: Von
80 beantworteten Beitraegen trugen 80 ein Fachgebiet, aber nur 5 eine
Einrichtung. OpenAlex kennt unsere Beitraege thematisch, nicht aber, wer
sie wo geschrieben hat. Die Standortzuordnung muss also aus unserem
eigenen Bestand kommen. Geholt wird daher nur, was OpenAlex wirklich
hergibt: Fachgebiet, Feld, Thema und Zitationen.

⚠ OPENALEX ANTWORTET BEI DROSSELUNG MIT 401, NICHT MIT 429
Der erste Lauf lief ab Block 600 in die Drosselung und lieferte nur 80
von 936. Darum hier: 25 DOIs je Frage, eine Sekunde Pause, und bei einem
Fehlschlag warten mit Verdopplung bis 120 Sekunden. Der Lauf dauert
dadurch ueber eine halbe Stunde und ist dafuer vollstaendig.

Der Lauf ist WIEDERAUFNEHMBAR: Was schon in der Zieldatei steht, wird
nicht neu gefragt. Ein abgebrochener Lauf kostet also nichts.

  py mvf_fach.py              holt, was fehlt
  py mvf_fach.py --gegentest  prueft ohne Netz
"""
import json
import pathlib
import sys
import time
import urllib.request

HIER = pathlib.Path(__file__).parent
DATEN = HIER / "daten"
ZIEL = DATEN / "mvf_openalex.json"
UA = {"User-Agent": "vf-landkarte/1.0 (mailto:stegmaier@m-vf.de)"}
SEL = ("doi,type,publication_year,primary_topic,authorships,cited_by_count")
BLOCK = 25


def frage(dois):
    """Ein Block. Gibt die Antwort oder None, wenn OpenAlex zumacht."""
    u = ("https://api.openalex.org/works?per-page=50&select=" + SEL
         + "&mailto=stegmaier@m-vf.de&filter=doi:" + "|".join(dois))
    warte = 5
    for versuch in range(6):
        try:
            with urllib.request.urlopen(
                    urllib.request.Request(u, headers=UA), timeout=120) as f:
                return json.loads(f.read())
        except Exception as e:
            # 401 heisst hier nicht „nicht erlaubt", sondern „zu schnell".
            if versuch == 5:
                print(f"     aufgegeben nach 6 Versuchen ({e})")
                return None
            time.sleep(warte)
            warte = min(warte * 2, 120)
    return None


def auspacken(w):
    pt = w.get("primary_topic") or {}
    rors = []
    for a in (w.get("authorships") or []):
        rors += [i.get("ror") for i in (a.get("institutions") or [])
                 if i.get("ror")]
    return {
        "typ": w.get("type"), "jahr": w.get("publication_year"),
        "fach": (pt.get("subfield") or {}).get("display_name"),
        "feld": (pt.get("field") or {}).get("display_name"),
        "thema": pt.get("display_name"),
        "rors": sorted(set(rors)),
        "zitiert": w.get("cited_by_count"),
    }


def gegentest():
    ok = True
    print("Auspacken eines Datensatzes:")
    w = {"doi": "https://doi.org/10.24945/x", "type": "journal-article",
         "publication_year": 2025, "cited_by_count": 3,
         "primary_topic": {"display_name": "Health Policy",
                           "subfield": {"display_name": "Health Policy"},
                           "field": {"display_name": "Medicine"}},
         "authorships": [{"institutions": [{"ror": "https://ror.org/a"},
                                           {"ror": None}]},
                         {"institutions": []}]}
    e = auspacken(w)
    for feld, soll in (("fach", "Health Policy"), ("feld", "Medicine"),
                       ("jahr", 2025), ("zitiert", 3),
                       ("rors", ["https://ror.org/a"])):
        gut = e[feld] == soll
        ok = ok and gut
        print(f"  {'ok ' if gut else 'FEHLER'} {feld:<9} {e[feld]!r}")

    print("\nOhne primary_topic faellt nichts um:")
    e = auspacken({"doi": "x", "authorships": []})
    gut = e["fach"] is None and e["rors"] == []
    ok = ok and gut
    print(f"  {'ok ' if gut else 'FEHLER'} fach={e['fach']!r} rors={e['rors']!r}")

    print("\n" + ("Gegentest bestanden." if ok else "GEGENTEST GESCHEITERT."))
    return ok


def main():
    if "--gegentest" in sys.argv:
        return 0 if gegentest() else 1

    B = json.loads((DATEN / "mvf_beitraege.json").read_text(encoding="utf-8"))
    alle = sorted(B["beitraege"])
    habe = {}
    if ZIEL.exists():
        habe = json.loads(ZIEL.read_text(encoding="utf-8")).get("arbeiten", {})
    offen = [d for d in alle if d not in habe]
    print(f"Beitraege {len(alle)} | schon da {len(habe)} | offen {len(offen)}")
    if not offen:
        print("nichts zu tun")
        return 0

    for i in range(0, len(offen), BLOCK):
        teil = offen[i:i + BLOCK]
        d = frage(teil)
        if d:
            for w in d.get("results", []):
                doi = (w.get("doi") or "").replace("https://doi.org/", "").lower()
                if doi:
                    habe[doi] = auspacken(w)
        # Nach JEDEM Block schreiben, damit ein Abbruch nichts kostet.
        ZIEL.write_text(json.dumps({
            "stand": time.strftime("%Y-%m-%d"),
            "hinweis": ("Nur Fachgebiet und Zitationen. Einrichtungen fuehrt "
                        "OpenAlex zu MVF-Beitraegen so gut wie nicht, "
                        "gemessen 5 von 80 im ersten Lauf."),
            "angefragt": len(alle), "gefunden": len(habe), "arbeiten": habe,
        }, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"  {i + len(teil):4d} von {len(offen)} gefragt | "
              f"insgesamt gefunden {len(habe)}")
        time.sleep(1.0)

    mit_fach = sum(1 for v in habe.values() if v.get("fach"))
    mit_ror = sum(1 for v in habe.values() if v.get("rors"))
    print(f"\ngefunden {len(habe)} von {len(alle)} | mit Fach {mit_fach} | "
          f"mit Einrichtung {mit_ror}")
    print(f"-> daten/mvf_openalex.json")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
