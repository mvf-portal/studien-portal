# -*- coding: utf-8 -*-
"""Wie viele Beitraege zeigt ein Autorenprofil auf m-vf.de, und wie viele
schreibt Crossref derselben Person zu?

DER ANLASS (02.11.2026)
-----------------------
Peter: „https://www.monitor-versorgungsforschung.de/autoren/kathrin-
pieloth/ sie steht im Portal mit 39 Beitraegen, aber nicht auf ihrem
Profil."

Nachgemessen: Crossref fuehrt sie bei 39 Beitraegen als Autorin, ihre
Profilseite verlinkt 8 Hefte. Stichprobe ueber fuenf DOI, alle fuenf mit
ihr bei Crossref, alle fuenf ohne Zitationsangabe im CMS.

⚠ DIE PROFILSEITE IST NICHT DIE QUELLE. Sie zeigt, was in WordPress als
Autorenbeziehung gesetzt ist. Crossref zeigt, was beim DOI hinterlegt
wurde. Beides kann auseinanderlaufen, und bis heute hat niemand gemessen,
wie weit.

WAS DIESES SKRIPT TUT
---------------------
Fuer jedes Autorenprofil:
  1. die Zahl aus unserem Bestand (Crossref-Metadaten, mit den
     aufgeloesten Initialen)
  2. die Zahl auf der Profilseite, abgerufen und ausgezaehlt
  3. die Differenz, und welche DOI konkret fehlen

⚠ NICHT AM EINZELEINTRAG ENTSCHEIDEN. Eine Profilseite kann aus anderen
Gruenden kuerzer sein (Beitraege ohne DOI, andere Schreibweise des
Namens). Darum nennt die Ausgabe immer beide Zahlen und die fehlenden
DOI, nie nur „Luecke".

    py wp_autorenluecke.py --probe 25     25 Profile, zum Hinsehen
    py wp_autorenluecke.py                alle, dauert
    py wp_autorenluecke.py --gegentest    beweisen, dass das Zaehlen traegt

Ergebnis: daten/wp_autorenluecke.json
"""
import collections
import json
import pathlib
import re
import sys
import time
import urllib.error
import urllib.request

HIER = pathlib.Path(__file__).resolve().parent
DATEN = HIER / "daten"
BASIS = "https://www.monitor-versorgungsforschung.de"
UA = {"User-Agent": "MVF-Landkarte-Abgleich/1.0 (mailto:stegmaier@m-vf.de)"}

# Die Artikelliste der Profilseite. Oben stehen vier Teaser „Top
# Originalartikel", die NICHT zur Liste gehoeren - sie werden ueber die
# Heftangabe gezaehlt, die nur die Liste traegt.
HEFT = re.compile(r"^(MVF \d\d/\d\d|Ausgabe \d\d / \d{4})$")


def lade(name):
    p = DATEN / name
    if not p.exists():
        raise SystemExit("ABBRUCH: daten/%s fehlt" % name)
    return json.loads(p.read_text(encoding="utf-8"))


def hole(url, versuche=3):
    for i in range(versuche):
        try:
            with urllib.request.urlopen(
                    urllib.request.Request(url, headers=UA), timeout=30) as a:
                return a.getcode(), a.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            return e.code, ""
        except (urllib.error.URLError, OSError):
            if i == versuche - 1:
                return 0, ""
            time.sleep(2 * (i + 1))
    return 0, ""


def zaehle_profil(html):
    """Die Beitraege der Profilseite zaehlen.

    ⚠ UEBER DIE HEFTANGABE, NICHT UEBER DIE LINKS. Die vier Teaser oben
    („Top Originalartikel") sind auch Links auf Abstracts, gehoeren aber
    nicht zur Werkliste. Die Heftangabe steht nur an den Listeneintraegen.
    """
    ohne = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html, flags=re.S)
    stuecke = re.split(r"<[^>]+>", ohne)
    return sum(1 for s in stuecke if HEFT.match(s.strip()))


def unsere_dois(B, schluessel, teile_namen, personenschluessel):
    """Alle DOI, die wir dieser Person zuschreiben."""
    aus = []
    for doi, b in B.items():
        for a in (b.get("autoren") or []):
            nach, vor = teile_namen(a)
            if personenschluessel(nach, vor) == schluessel:
                aus.append(doi)
                break
    return aus


def gegentest():
    print("GEGENTEST: zaehlt zaehle_profil() wirklich die Liste?")
    ok = True
    faelle = [
        ("<li>MVF 05/26</li><li>Ausgabe 03 / 2019</li>", 2, "zwei Hefte"),
        ("<p>Top Originalartikel</p><a href='/abstract/x'>Titel</a>", 0,
         "ein Teaser ohne Heftangabe zaehlt nicht"),
        ("<span>MVF 05/26 und Text</span>", 0,
         "Heftangabe im Fliesstext zaehlt nicht"),
        ("", 0, "leere Seite"),
    ]
    for html, soll, was in faelle:
        ist = zaehle_profil(html)
        gut = ist == soll
        ok = ok and gut
        print("   %s %-42s %d (erwartet %d)"
              % ("ok " if gut else "FEHLER", was, ist, soll))
    print("\n" + ("Gegentest bestanden." if ok else "GEGENTEST GESCHEITERT."))
    return 0 if ok else 1


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if "--gegentest" in sys.argv:
        return gegentest()

    grenze = None
    if "--probe" in sys.argv:
        i = sys.argv.index("--probe")
        grenze = int(sys.argv[i + 1]) if i + 1 < len(sys.argv) else 25

    sys.path.insert(0, str(HIER))
    from suchindex import teile_namen, personenschluessel
    from zuschnitt import REDAKTION

    P = lade("personen.json")["personen"]
    B = lade("mvf_beitraege.json")["beitraege"]

    # Nur wer ein Profil hat und bei uns mindestens einen Beitrag traegt.
    kandidaten = [(k, p) for k, p in sorted(P.items())
                  if p.get("profil") and (p.get("mvf") or 0) > 0
                  and k not in REDAKTION]
    print("Autorenprofile mit mindestens einem MVF-Beitrag: %d"
          % len(kandidaten))
    if grenze:
        kandidaten = kandidaten[:grenze]
        print("   Probe: die ersten %d" % len(kandidaten))
    print()

    zeilen, z = [], collections.Counter()
    for n, (k, p) in enumerate(kandidaten, 1):
        slug = (p["profil"].rstrip("/").rsplit("/", 1)[-1])
        code, html = hole("%s/autoren/%s/" % (BASIS, slug))
        if code != 200:
            z["nicht abrufbar"] += 1
            zeilen.append({"k": k, "slug": slug, "http": code,
                           "unsere": p.get("mvf"), "profil": None})
            print("   %4d/%d  %-32s HTTP %s" % (n, len(kandidaten),
                                                slug[:32], code))
            continue
        auf_profil = zaehle_profil(html)
        unsere = int(p.get("mvf") or 0)
        fehlt = max(0, unsere - auf_profil)
        z["geprueft"] += 1
        z["mit Luecke" if fehlt else "vollstaendig"] += 1
        z["fehlende Beitraege"] += fehlt
        zeilen.append({"k": k, "slug": slug, "http": 200, "name": p.get("name"),
                       "unsere": unsere, "profil": auf_profil, "fehlt": fehlt})
        if fehlt:
            print("   %4d/%d  %-32s Crossref %3d  Profil %3d  fehlen %3d"
                  % (n, len(kandidaten), slug[:32], unsere, auf_profil, fehlt))

    print()
    print("=" * 66)
    for a, b in z.most_common():
        print("   %-24s %6d" % (a, b))

    mit = [x for x in zeilen if x.get("fehlt")]
    if mit:
        print()
        print("Die zehn groessten Luecken:")
        for x in sorted(mit, key=lambda y: -y["fehlt"])[:10]:
            print("   %-34s %3d statt %3d, fehlen %3d"
                  % (x["slug"][:34], x["profil"], x["unsere"], x["fehlt"]))

    ziel = DATEN / "wp_autorenluecke.json"
    ziel.write_text(json.dumps(
        {"stand": time.strftime("%Y-%m-%d"),
         "hinweis": ("Crossref gegen die Autorenprofile von m-vf.de. "
                     "Gezaehlt wird auf der Profilseite ueber die "
                     "Heftangabe, nicht ueber die Links: Die vier Teaser "
                     "oben gehoeren nicht zur Werkliste."),
         "vollstaendig": bool(grenze is None),
         "zaehlung": dict(z), "profile": zeilen},
        ensure_ascii=False, indent=1), encoding="utf-8")
    print("\n-> %s" % ziel)
    return 0


if __name__ == "__main__":
    sys.exit(main())
