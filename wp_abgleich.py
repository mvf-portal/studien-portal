# -*- coding: utf-8 -*-
"""Autorenzuordnung: unser Bestand gegen WordPress, in beide Richtungen.

WAS DIESES SKRIPT ERSETZT
-------------------------
`wp_autorenluecke.py` zaehlte die Beitraege auf der gerenderten
Profilseite ueber die Heftangabe. Das war geeicht an zwei Faellen und
hat sie getroffen, aber es ist zu eng:

    Peter Stegmaier, Profilseite
      Abstract-Links auf der Seite        395
      davon von meinem Muster getroffen   385

68 Zeichenfolgen sehen aus wie eine Heftangabe und passen nicht:
„MVF 06/25 Supplement", „MVF 03723" (ein Tippfehler im Bestand), und
vor allem aeltere Beitraege, bei denen Heft und Titel in EINEM Textknoten
stehen: „MVF 02/08 Versorgungsforschung à la Barmer".

⚠ EINE EICHUNG AN ZWEI SAUBEREN FAELLEN BEWEIST NICHT, DASS EIN MUSTER
TRAEGT. Kathrin Pieloth (8) und Bertram Haeussler (14) hatten beide nur
neue Beitraege im klaren Format. Wer viele alte hat, wurde zu klein
gezaehlt - und erschien damit faelschlich als Luecke.

DIE QUELLE JETZT
----------------
`mvf-archiv-transfer/daten/wp_autorverknuepfung.json`: je Beitrag die
Profil-Slugs, von den Abstract-Seiten gelesen. 1.528 Beitraege, 2.570
Verknuepfungen.

⚠ AUCH DAS IST ZAEHLEN AM ERZEUGNIS, nur in der richtigen Richtung. Die
Schnittstelle liefert `author_id` nicht aus (Feldtyp
`searchable_post_type`, ACF gibt ihn nicht an REST weiter, 100 von 100
melden None). Am Beitrag gelesen gibt es aber keine Teaser-Liste, also
auch nicht das Problem, das die Profilseite hatte.

    py wp_abgleich.py
    py wp_abgleich.py --gegentest
"""
import collections
import json
import pathlib
import sys
import time

HIER = pathlib.Path(__file__).resolve().parent
DATEN = HIER / "daten"
FREMD = HIER.parent / "mvf-archiv-transfer" / "daten"


def lade(p, was):
    p = pathlib.Path(p)
    if not p.exists():
        raise SystemExit("ABBRUCH: %s fehlt (%s)" % (p, was))
    return json.loads(p.read_text(encoding="utf-8"))


def gegentest():
    print("GEGENTEST")
    ok = True
    V = lade(FREMD / "wp_autorverknuepfung.json", "Verknuepfungen")
    b = V["beitraege"]
    n = len(b)
    gut = n == 1528
    ok = ok and gut
    print("   %s 1.528 Beitraege gelesen (%d)" % ("ok " if gut else "FEHLER", n))

    # ⚠ DIE FALLE, VOR DER DIE ANDERE SITZUNG GEWARNT HAT.
    alle = collections.Counter()
    for x in b:
        for s in (x.get("author_slug") or []):
            alle[s] += 1
    schlimm = [s for s in alle if "autorenunterlagen" in s or s in
               ("autoren", "autorinnen", "autorenhinweise")]
    gut = not schlimm
    ok = ok and gut
    print("   %s kein Sammel-Slug als Person (%s)"
          % ("ok " if gut else "FEHLER", schlimm or "keiner"))

    # Keine Verknuepfung darf auf einen Slug zeigen, den es nicht gibt.
    W = lade(FREMD / "wp_autoren.json", "Autorenprofile")["autoren"]
    fremd = sorted(s for s in alle if s not in W)
    gut = not fremd
    ok = ok and gut
    print("   %s jeder Slug hat ein Profil (%d fremde%s)"
          % ("ok " if gut else "FEHLER", len(fremd),
             ": " + ", ".join(fremd[:3]) if fremd else ""))
    print("\n" + ("Gegentest bestanden." if ok else "GEGENTEST GESCHEITERT."))
    return 0 if ok else 1


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if "--gegentest" in sys.argv:
        return gegentest()

    sys.path.insert(0, str(HIER))
    from suchindex import personen as suchindex_personen
    from zuschnitt import REDAKTION

    V = lade(FREMD / "wp_autorverknuepfung.json", "Verknuepfungen")
    A = lade(DATEN / "mvf_artikel.json", "Artikel")["artikel"]
    P = lade(DATEN / "personen.json", "Personen")["personen"]

    # Beitrags-Slug -> DOI, und DOI -> Beitrags-Slug
    doi_von = {}
    for v in A.values():
        if v.get("doi") and v.get("slug"):
            doi_von[v["slug"]] = v["doi"].lower()
    if not doi_von:   # mvf_artikel.json fuehrt den Slug nur im Link
        for v in A.values():
            u = v.get("link") or ""
            s = u.rstrip("/").rsplit("/", 1)[-1] if "/abstract/" in u else ""
            if s and v.get("doi"):
                doi_von[s] = v["doi"].lower()

    # WordPress: Profil-Slug -> Menge der Beitrags-Slugs
    wp = collections.defaultdict(set)
    for x in V["beitraege"]:
        for s in (x.get("author_slug") or []):
            wp[s].add(x["slug"])

    # Wir: Personenschluessel -> Menge der Beitrags-Slugs (ueber DOI)
    slug_von_doi = {d: s for s, d in doi_von.items()}
    unser = {}
    for k, v in suchindex_personen().items():
        unser[k] = {slug_von_doi[d.lower()] for d in (v.get("mvf") or [])
                    if d.lower() in slug_von_doi}

    print("Autorenzuordnung, beide Richtungen")
    print("=" * 68)
    z = collections.Counter()
    zeilen = []
    for k, p in sorted(P.items()):
        if k in REDAKTION or not p.get("profil"):
            continue
        slug = p["profil"].rstrip("/").rsplit("/", 1)[-1]
        ihre = wp.get(slug, set())
        meine = unser.get(k, set())
        z["Profile geprueft"] += 1
        fehlt_in_wp = sorted(meine - ihre)      # wir kennen, WP verknuepft nicht
        fehlt_bei_uns = sorted(ihre - meine)    # WP verknuepft, wir kennen nicht
        if fehlt_in_wp:
            z["Profile, denen WordPress etwas fehlt"] += 1
            z["fehlende Verknuepfungen in WordPress"] += len(fehlt_in_wp)
        if fehlt_bei_uns:
            z["Profile, denen UNS etwas fehlt"] += 1
            z["Beitraege, die wir nicht zuordnen"] += len(fehlt_bei_uns)
        if not fehlt_in_wp and not fehlt_bei_uns:
            z["deckungsgleich"] += 1
        if fehlt_in_wp or fehlt_bei_uns:
            zeilen.append({"schluessel": k, "slug": slug,
                           "name": p.get("name"),
                           "wp": len(ihre), "wir": len(meine),
                           "fehlt_in_wordpress": fehlt_in_wp,
                           "fehlt_bei_uns": fehlt_bei_uns})

    for a, b in z.most_common():
        print("   %-38s %5d" % (a, b))

    print("\nDie zehn groessten Luecken bei UNS (Beitraege ohne DOI):")
    for x in sorted(zeilen, key=lambda y: -len(y["fehlt_bei_uns"]))[:10]:
        if not x["fehlt_bei_uns"]:
            break
        print("   %-34s WP %3d, wir %3d, uns fehlen %3d"
              % (x["slug"][:34], x["wp"], x["wir"], len(x["fehlt_bei_uns"])))

    print("\nDie zehn groessten Luecken in WORDPRESS:")
    for x in sorted(zeilen, key=lambda y: -len(y["fehlt_in_wordpress"]))[:10]:
        if not x["fehlt_in_wordpress"]:
            break
        print("   %-34s WP %3d, wir %3d, dort fehlen %3d"
              % (x["slug"][:34], x["wp"], x["wir"],
                 len(x["fehlt_in_wordpress"])))

    ziel = DATEN / "wp_abgleich.json"
    ziel.write_text(json.dumps(
        {"stand": time.strftime("%Y-%m-%d"),
         "hinweis": ("Unsere Zuordnung (Crossref ueber DOI, mit "
                     "aufgeloesten Initialen) gegen die Verknuepfungen in "
                     "WordPress. 'fehlt_in_wordpress': wir kennen den "
                     "Beitrag, dort ist die Person nicht verknuepft. "
                     "'fehlt_bei_uns': dort verknuepft, bei uns nicht - "
                     "fast immer ein Beitrag ohne DOI."),
         "zaehlung": dict(z), "profile": zeilen},
        ensure_ascii=False, indent=1), encoding="utf-8")
    print("\n-> %s" % ziel)
    return 0


if __name__ == "__main__":
    sys.exit(main())
