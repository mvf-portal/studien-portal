# -*- coding: utf-8 -*-
"""Welche Beitraege genau fehlen auf welchem Autorenprofil?

`wp_autorenluecke.py` zaehlt und findet 72 Profile mit einer Luecke.
Zum Nachtragen in WordPress reicht eine Zahl nicht: Es muss dastehen,
WELCHER Beitrag fehlt.

WIE ZUGEORDNET WIRD
-------------------
Die Profilseite verlinkt Abstracts als /abstract/<slug>/. Unser Bestand
kennt zu jedem DOI die Adresse (mvf_artikel.json, Feld `link`). Ueber
diese Adresse laesst sich sagen, welcher unserer DOI auf der Seite steht
und welcher nicht.

⚠ DIE LUECKE GEHT IN BEIDE RICHTUNGEN. Bei Peter Stegmaier zeigt das
Profil 385 Beitraege, Crossref kennt 326. Die Differenz sind
redaktionelle Stuecke ohne DOI. „Fehlt auf dem Profil" heisst also
nicht „das Profil ist unvollstaendig", sondern nur: Dieser DOI ist dort
nicht verlinkt. Beides wird getrennt ausgewiesen.

⚠ EIN DOI OHNE ADRESSE IM CMS KANN NICHT FEHLEN. Wo mvf_artikel.json
keinen Link kennt, gibt es in WordPress keinen Beitrag, auf den man
verlinken koennte. Das ist eine andere Luecke und wird getrennt
gezaehlt, nicht untergemischt.

    py wp_luecken_benennen.py
    py wp_luecken_benennen.py --gegentest

Ergebnis: daten/wp_luecken_benannt.json und eine Liste zum Mitlesen.
"""
import collections
import json
import pathlib
import re
import sys
import time

HIER = pathlib.Path(__file__).resolve().parent
DATEN = HIER / "daten"


def lade(name):
    p = DATEN / name
    if not p.exists():
        raise SystemExit("ABBRUCH: daten/%s fehlt" % name)
    return json.loads(p.read_text(encoding="utf-8"))


def pfad(url):
    """Aus einer Adresse den Teil, der die Seite benennt."""
    m = re.search(r"/(abstract|artikel)/([^/?#]+)", url or "")
    return m.group(2).lower() if m else ""


def gegentest():
    print("GEGENTEST: trennt pfad() die Adresse richtig?")
    ok = True
    faelle = [
        ("https://www.monitor-versorgungsforschung.de/abstract/rheuma-x/",
         "rheuma-x"),
        ("/abstract/Rheuma-X", "rheuma-x"),
        ("https://www.monitor-versorgungsforschung.de/autoren/wer/", ""),
        ("", ""),
    ]
    for url, soll in faelle:
        ist = pfad(url)
        gut = ist == soll
        ok = ok and gut
        print("   %s %-54s -> %r" % ("ok " if gut else "FEHLER",
                                     url[:54], ist))
    print("\n" + ("Gegentest bestanden." if ok else "GEGENTEST GESCHEITERT."))
    return 0 if ok else 1


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if "--gegentest" in sys.argv:
        return gegentest()

    sys.path.insert(0, str(HIER))
    from suchindex import teile_namen, personenschluessel
    from wp_autorenluecke import hole

    L = lade("wp_autorenluecke.json")
    B = lade("mvf_beitraege.json")["beitraege"]
    A = lade("mvf_artikel.json")["artikel"]
    P = lade("personen.json")["personen"]

    # DOI -> Adresse im CMS
    adresse = {}
    for v in A.values():
        d = (v.get("doi") or "").lower()
        if d and v.get("link"):
            adresse[d] = v["link"]

    # Person -> ihre DOI
    #
    # ⚠ DIESELBE ZUORDNUNG WIE DAS PORTAL, SONST VERGLEICHT MAN ZWEI
    # VERSCHIEDENE DINGE. Die erste Fassung hier bildete den Schluessel
    # selbst aus den Rohnennungen und liess damit die aufgeloesten
    # Initialen weg: Fuer Matthias Kalder kamen 2 DOI heraus, waehrend
    # personen.json 5 fuehrt. Die Folge waren 3 benennbare Luecken statt
    # der wirklichen Zahl.
    #
    # personen() aus suchindex.py ist die Stelle, die auch die
    # Initialen aufloest. Sie liefert je Person die Liste ihrer DOI.
    from suchindex import personen as suchindex_personen
    ihre = {k: list(v.get("mvf") or [])
            for k, v in suchindex_personen().items()}

    betroffen = [x for x in L["profile"] if x.get("fehlt")]
    print("Profile mit Luecke: %d" % len(betroffen))
    print()

    aus, z = [], collections.Counter()
    for x in betroffen:
        k, slug = x["k"], x["slug"]
        code, html = hole(
            "https://www.monitor-versorgungsforschung.de/autoren/%s/" % slug)
        if code != 200:
            z["Profil nicht abrufbar"] += 1
            continue
        drauf = {pfad(u) for u in re.findall(r'href="([^"]+)"', html)}
        drauf.discard("")

        fehlend, ohne_seite = [], []
        for doi in sorted(set(ihre.get(k, []))):
            u = adresse.get(doi.lower())
            if not u:
                ohne_seite.append(doi)
            elif pfad(u) not in drauf:
                fehlend.append({"doi": doi, "adresse": u,
                                "titel": (B[doi].get("titel") or "")[:90],
                                "jahr": B[doi].get("jahr")})
        z["Profile geprueft"] += 1
        z["fehlende Verknuepfungen"] += len(fehlend)
        z["DOI ohne Seite im CMS"] += len(ohne_seite)
        if fehlend:
            z["Profile mit benennbarer Luecke"] += 1
        aus.append({"schluessel": k, "slug": slug,
                    "name": P.get(k, {}).get("name"),
                    "profil_zeigt": x.get("profil"),
                    "crossref": x.get("unsere"),
                    "fehlende_verknuepfungen": fehlend,
                    "doi_ohne_seite": ohne_seite})
        if fehlend:
            print("   %-32s %d nachzutragen" % (slug[:32], len(fehlend)))
            for f in fehlend[:2]:
                print("        %s  %s  %s"
                      % (f["doi"], f["jahr"], f["titel"][:52]))

    print()
    print("=" * 66)
    for a, b in z.most_common():
        print("   %-32s %5d" % (a, b))

    ziel = DATEN / "wp_luecken_benannt.json"
    ziel.write_text(json.dumps(
        {"stand": time.strftime("%Y-%m-%d"),
         "hinweis": ("Je Autorenprofil die DOI, die unser Bestand der "
                     "Person zuschreibt und die auf der Profilseite NICHT "
                     "verlinkt sind. 'doi_ohne_seite' ist eine andere "
                     "Luecke: Dazu gibt es in WordPress keinen Beitrag."),
         "zaehlung": dict(z), "profile": aus},
        ensure_ascii=False, indent=1), encoding="utf-8")
    print("\n-> %s" % ziel)
    return 0


if __name__ == "__main__":
    sys.exit(main())
