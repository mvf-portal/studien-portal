# -*- coding: utf-8 -*-
"""Die Autorenseiten aus dem MVF-Archiv: Name, ORCID, Einrichtung, Artikel.

WARUM DIESE QUELLE UND NICHT DIE PDFS
-------------------------------------
Ich hatte einen Leser fuer die Autorenboxen in den Beitrags-PDFs gebaut.
Er funktioniert, aber er findet nur 64 Prozent dessen, was in den PDFs
ueberhaupt steht, und er musste vier verschiedene Layouts lernen.

Das Archiv auf archiv.monitor-versorgungsforschung.de haelt dasselbe
sauber ausgezeichnet. Eine Autorenseite sieht so aus:

    Albrecht, Dr. Martin
    Dr. Martin Albrecht  ORCID: 0000-0002-9919-7346
    ist am IGES Institut als Geschaeftsfuehrer und Leiter des Bereiches
    Gesundheitspolitik zustaendig fuer ...
    Artikel: „Leistungskonzentration in der stationaeren Versorgung"
    Artikel: "Bei Dekonzentration kommen Mindestmengen unter Druck"

Name, ORCID, Einrichtung UND die Artikelliste, also die Verbindung von
Person zu Beitrag. Rund 640 Seiten, erreichbar ueber die Blaetterung.

⚠ DIESES SKRIPT DEUTET NICHTS
Es holt und legt ab. Aus „ist am IGES Institut als Geschaeftsfuehrer"
die Einrichtung zu schneiden, ist eine eigene Aufgabe mit eigenem
Gegentest: Der Satz nennt oft mehrere Haeuser, frueheres und heutiges,
und welches gilt, sagt die Grammatik nicht zuverlaessig.

⚠ EIN EINGEFRORENES ABBILD
Das Archiv ist eine Plone-Seite, abgezogen als statische Dateien. Die
Blaetterungsadressen tragen darum Zufallsnamen wie `autoren8c63.html`.
Gesammelt wird deshalb ueber die Verweise, die jede Seite selbst nennt,
nicht ueber geratene Adressen.

  py mvf_autoren_archiv.py              holt alles
  py mvf_autoren_archiv.py --gegentest  prueft ohne Netz
"""
import collections
import html
import json
import pathlib
import re
import sys
import time
import urllib.parse
import urllib.request

HIER = pathlib.Path(__file__).parent
DATEN = HIER / "daten"
ZIEL = DATEN / "mvf_autoren_archiv.json"
BASIS = "https://archiv.monitor-versorgungsforschung.de/"
UA = {"User-Agent": "Mozilla/5.0 (vf-landkarte; stegmaier@m-vf.de)"}

ORCID = re.compile(r"ORCID[:\s]*((?:\d{4}[\s\u2010-\u2015-]?){3}\d{3}[\dXx])", re.I)
MAIL = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
# Die Artikelliste am Fuss der Seite.
ARTIKEL = re.compile(r"Artikel\s*:\s*[\u201e\u201c\"']([^\u201c\u201d\"']{6,180})")
# Alles ab hier gehoert zur Seitenleiste, nicht zur Person.
LEISTE = re.compile(r"Editorial\s+Herausgeber|Termine\b|Kommende Termine|"
                    r"Weiter\u2026|« \w+ \d{4} »|Autoren\s+\w+,")
DATUM = re.compile(r"\b\d\d\.\d\d\.\d{4}\s+\d\d:\d\d\b")


def hol(u):
    warte = 4
    for versuch in range(4):
        try:
            with urllib.request.urlopen(
                    urllib.request.Request(u, headers=UA), timeout=120) as f:
                return f.read().decode("utf-8", "replace")
        except Exception as e:
            if versuch == 3:
                return ""
            time.sleep(warte)
            warte *= 2
    return ""


def inhalt(s):
    """Nur den Inhaltsbereich, ohne Leisten und Kalender."""
    m = re.search(r'<div[^>]+id=["\']content["\'][^>]*>(.*?)'
                  r'(?:<div[^>]+id=["\']portal-footer|</body)', s, re.S | re.I)
    k = m.group(1) if m else s
    k = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", k, flags=re.S)
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", k)).split())


def orcid_putzen(s):
    z = re.sub(r"[^0-9Xx]", "", s or "")
    if len(z) != 16:
        return ""
    return "-".join(z[i:i + 4] for i in range(0, 16, 4)).upper()


def zerlegen(t):
    """Eine Autorenseite in ihre Teile.

    Aufbau: „Nachname, Grade Vorname" + Datum + Uhrzeit, dann der
    Vorstellungstext, dann die Artikelliste, dann die Seitenleiste.
    """
    # Die Seitenleiste abschneiden, sonst landet der Kalender im Text.
    m = LEISTE.search(t)
    kopf = t[:m.start()] if m else t
    artikel = [html.unescape(a).strip() for a in ARTIKEL.findall(kopf)]
    # Vor dem ersten „Artikel:" steht die Person.
    i = kopf.find("Artikel:")
    person = kopf[:i] if i > 0 else kopf
    # Sortierform und Zeitstempel abtrennen.
    d = DATUM.search(person)
    sortname = person[:d.start()].strip(" ,;:") if d else ""
    text = person[d.end():].strip() if d else person.strip()
    oid = orcid_putzen((ORCID.search(text) or [None, ""])[1]
                       if ORCID.search(text) else "")
    text_ohne = ORCID.sub(" ", text)
    mm = MAIL.search(text_ohne)
    # Der Name wird am Satzbeginn wiederholt. Er endet, wo der Satz
    # beginnt: bei „ist", „war", „leitet".
    v = re.search(r"\b(ist|war|leitet|arbeitet|forscht|lehrt|hat|wurde|"
                  r"verantwortet|studierte|promovierte)\b", text_ohne)
    name = text_ohne[:v.start()].strip(" ,;:.") if v else ""
    satz = text_ohne[v.start():].strip() if v else text_ohne.strip()
    return {
        "sortname": " ".join(sortname.split()),
        "name": " ".join(name.split()),
        "orcid": oid,
        "mail": mm.group(0) if mm else "",
        "satz": " ".join(satz.split())[:1400],
        "artikel": artikel,
    }


def gegentest():
    ok = True
    print("ORCID putzen:")
    for roh, soll in (("0000-0002-9919-7346", "0000-0002-9919-7346"),
                      ("0000 0002 9919 734X", "0000-0002-9919-734X"),
                      ("0000-0002", "")):
        ist = orcid_putzen(roh)
        gut = ist == soll
        ok = ok and gut
        print(f"  {'ok ' if gut else 'FEHLER'} {roh!r:<24} -> {ist!r}")

    print("\nEine echte Autorenseite zerlegen:")
    echt = ("Albrecht, Dr. Martin 10.12.2010 10:45 Dr. Martin Albrecht "
            "ORCID: 0000-0002-9919-7346 ist am IGES Institut als "
            "Gesch\u00e4ftsf\u00fchrer und Leiter des Bereiches "
            "Gesundheitspolitik zust\u00e4ndig f\u00fcr die Bereiche "
            "Finanzierung, Wettbewerb und Effizienz im Gesundheitssystem. "
            "Voraus gingen wissenschaftliche T\u00e4tigkeiten beim "
            "Sachverst\u00e4ndigenrat. "
            "Artikel: \u201e Leistungskonzentration in der station\u00e4ren "
            "Versorgung \u201c Artikel: \"Bei Dekonzentration kommen "
            "Mindestmengen unter Druck\" Ausgabe 05 / 2021 "
            "Editorial Herausgeber Prof. Dr. Reinhold Roski "
            "Autoren Jungen, Thomas Danner, Dr. Martin "
            "Termine digitale Fachtagung 24.01.2023 10:00 "
            "\u00ab Dezember 2022 \u00bb Mo Di Mi Do Fr Sa So 1 2 3")
    e = zerlegen(echt)
    for was, gut in (
            ("Sortname", e["sortname"] == "Albrecht, Dr. Martin"),
            ("Name", e["name"] == "Dr. Martin Albrecht"),
            ("ORCID", e["orcid"] == "0000-0002-9919-7346"),
            ("Satz beginnt mit ist am IGES",
             e["satz"].startswith("ist am IGES Institut")),
            ("zwei Artikel", len(e["artikel"]) == 2),
            ("Artikeltitel geputzt",
             bool(e["artikel"]) and
             e["artikel"][0].strip() ==
             "Leistungskonzentration in der station\u00e4ren Versorgung"),
            ("Kalender bleibt draussen", "Dezember" not in e["satz"]),
            ("fremde Autoren bleiben draussen", "Jungen" not in e["satz"]),
            ("Herausgeber bleibt draussen", "Roski" not in e["satz"])):
        ok = ok and gut
        print(f"  {'ok ' if gut else 'FEHLER'} {was}")
    print("    ->", json.dumps({k: e[k] for k in
          ("sortname", "name", "orcid", "artikel")}, ensure_ascii=False)[:200])
    print("    satz:", e["satz"][:120])

    print("\nGEGENPROBE: eine Seite ohne ORCID und ohne Artikel:")
    e2 = zerlegen("Pfaff, Prof. Dr. Holger 26.10.2010 15:25 Prof. Dr. Holger "
                  "Pfaff ist seit 2009 Direktor des Instituts f\u00fcr "
                  "Medizinsoziologie. Termine AMNOG 26.01.2023 09:00")
    for was, gut in (("Name", e2["name"] == "Prof. Dr. Holger Pfaff"),
                     ("ORCID leer", e2["orcid"] == ""),
                     ("keine Artikel", e2["artikel"] == []),
                     ("Satz da", e2["satz"].startswith("ist seit 2009"))):
        ok = ok and gut
        print(f"  {'ok ' if gut else 'FEHLER'} {was}")

    print("\n" + ("Gegentest bestanden." if ok else "GEGENTEST GESCHEITERT."))
    return ok


def alle_seiten():
    """Alle Autorenseiten einsammeln, ueber die Blaetterung.

    Gefolgt wird nur den Verweisen, die die Seiten selbst nennen. Adressen
    zu raten geht hier nicht: Das Abbild traegt Zufallsnamen.
    """
    offen = ["autoren.html"]
    gesehen, autoren = set(), set()
    while offen:
        p = offen.pop(0)
        if p in gesehen:
            continue
        gesehen.add(p)
        s = hol(urllib.parse.urljoin(BASIS, p))
        if not s:
            continue
        for l in re.findall(r'href=["\']([^"\']+)["\']', s):
            if re.match(r"autoren/[^/]+\.html$", l):
                autoren.add(l)
            elif re.match(r"autoren[0-9a-f]*\.html\?b_start", l):
                l = html.unescape(l)
                if l not in gesehen:
                    offen.append(l)
        print(f"  Uebersicht {len(gesehen):3d} | Autorenseiten "
              f"{len(autoren):4d} | offen {len(offen)}")
        time.sleep(0.2)
    return sorted(autoren)


def main():
    if "--gegentest" in sys.argv:
        return 0 if gegentest() else 1

    print("Autorenseiten einsammeln...")
    pfade = alle_seiten()
    print(f"\ngefunden: {len(pfade)} Autorenseiten")

    habe = {}
    if ZIEL.exists():
        habe = json.loads(ZIEL.read_text(encoding="utf-8")).get("autoren", {})

    zaehl = collections.Counter()
    for k, p in enumerate(pfade, 1):
        if p in habe:
            zaehl["uebersprungen"] += 1
            continue
        s = hol(urllib.parse.urljoin(BASIS, p))
        if not s:
            zaehl["nicht_ladbar"] += 1
            continue
        e = zerlegen(inhalt(s))
        e["pfad"] = p
        habe[p] = e
        zaehl["gelesen"] += 1
        if e["orcid"]:
            zaehl["mit_orcid"] += 1
        if e["mail"]:
            zaehl["mit_mail"] += 1
        if e["artikel"]:
            zaehl["mit_artikeln"] += 1
            zaehl["artikel_gesamt"] += len(e["artikel"])
        if e["satz"]:
            zaehl["mit_satz"] += 1
        if k % 40 == 0 or k == len(pfade):
            ZIEL.write_text(json.dumps({
                "stand": time.strftime("%Y-%m-%d"),
                "quelle": BASIS + "autoren.html",
                "hinweis": ("Name, ORCID, Vorstellungssatz und Artikelliste. "
                            "Die Einrichtung steckt im Satz und wird hier "
                            "NICHT herausgeschnitten, das ist ein eigener "
                            "Schritt."),
                "zaehlung": dict(zaehl), "autoren": habe,
            }, ensure_ascii=False, indent=1), encoding="utf-8")
            print(f"  {k:4d}/{len(pfade)} | gelesen {zaehl['gelesen']} | "
                  f"ORCID {zaehl['mit_orcid']} | Artikel "
                  f"{zaehl['artikel_gesamt']}")
        time.sleep(0.2)

    ZIEL.write_text(json.dumps({
        "stand": time.strftime("%Y-%m-%d"),
        "quelle": BASIS + "autoren.html",
        "hinweis": ("Name, ORCID, Vorstellungssatz und Artikelliste. Die "
                    "Einrichtung steckt im Satz und wird hier NICHT "
                    "herausgeschnitten, das ist ein eigener Schritt."),
        "zaehlung": dict(zaehl), "autoren": habe,
    }, ensure_ascii=False, indent=1), encoding="utf-8")

    print()
    for was in ("gelesen", "mit_orcid", "mit_mail", "mit_satz",
                "mit_artikeln", "artikel_gesamt", "nicht_ladbar",
                "uebersprungen"):
        print(f"  {was:<18} {zaehl[was]:5d}")
    print(f"\n-> daten/mvf_autoren_archiv.json")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
