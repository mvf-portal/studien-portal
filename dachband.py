# -*- coding: utf-8 -*-
"""Das Dach-Band fuer wissen.m-vf.de erzeugen und einsetzen.

Peter am 02.11.2026: „Auf der Startseite muss klar werden, dass 'Wissen'
mehr ist als nur ein hub von 15!"

    py dachband.py            erzeugen und in den Hub einsetzen
    py dachband.py --zeigen   nur erzeugen, nichts schreiben
    py dachband.py --pruefen  Standdatum und Marken pruefen
    py dachband.py --gegentest  beweisen, dass die Pruefungen greifen

WARUM FEST EINGEBAUT UND NICHT NACHGELADEN
------------------------------------------
Die Zahlen stammen aus daten/fachbestand.json, also aus einem ANDEREN
Projekt als dem Hub. Genau so eine Kette ueber Projektgrenzen hat am
02.11.2026 schon einmal Schaden angerichtet: personen.py liest die
Autorenprofile aus dem Arbeitsordner der Archiv-Sitzung, die Datei war
einen Moment nicht da, und 281 Menschen verloren still ihren Profillink.

⚠ EINE ZAHL, DIE STILL VERALTET, IST SCHLIMMER ALS EINE, DIE IHR ALTER
NENNT. Darum steht das Band fest in index.html, mit sichtbarem
Standdatum, und `--pruefen` meldet, wenn es zu alt wird.
"""
import datetime
import json
import pathlib
import re
import sys

HIER = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HIER))

import seiten                                             # noqa: E402

DATEN = HIER / "daten"
VORLAGE = HIER / "vorlage-dach-band.html"
HUB = HIER.parent / "versorgungsforschung-portal"
ZIEL = HUB / "index.html"
SCHNIPSEL = HUB / "teile-dach-band.html"

ANFANG = ("<!-- __DACH_BAND_ANFANG__  erzeugt von vf-landkarte/dachband.py"
          "  nicht von Hand aendern -->")
ENDE = "<!-- __DACH_BAND_ENDE__ -->"

# Die Stelle, vor der das Band stehen soll: direkt vor „Aktuell im Hub".
ANKER = '      <!-- Band „Aktuell im Hub'

# So alt darf der Stand werden, bevor die Pruefung meckert.
HOECHSTALTER_TAGE = 60

MONATE = ("Januar", "Februar", "März", "April", "Mai", "Juni", "Juli",
          "August", "September", "Oktober", "November", "Dezember")

# Je Gruppe: Ueberschrift, ein Satz, Ziel, und welche Saeulen hinein.
GRUPPEN = [
    ("laeuft", "Was gerade läuft",
     "Vorhaben, die noch nicht zu Ende sind.",
     "https://studien.m-vf.de/rekrutierend.html",
     ["rekrutiert", "studien", "innofonds"]),
    ("publiziert", "Was veröffentlicht ist",
     "Von der Arbeit von heute Morgen bis zum Jahrgang 2008.",
     "neue-studien.html",
     ["literatur", "mvf", "hubs", "dkvf"]),
    ("wer", "Wer es macht",
     "Menschen, Häuser und Geldgeber, und wie sie zusammenhängen.",
     "https://studien.m-vf.de/forschende.html",
     ["forschende", "institutionen", "foerderer"]),
    ("kommt", "Was als Nächstes kommt",
     "Geld, Zulassungen und der Nachwuchs.",
     "ausschreibungen.html",
     ["ausschreibungen", "zulassungen", "thesis"]),
]

# Kurze Beschriftung je Saeule. Die Titel aus fachbestand.json sind fuer
# eine eigene Seite gemacht und hier zu lang.
KURZ = {
    "rekrutiert": "Studien suchen Teilnehmende",
    "studien": "registrierte Studien",
    "innofonds": "Innovationsfonds-Projekte",
    "literatur": "neue Arbeiten, täglich",
    "mvf": "Beiträge in MVF",
    "hubs": "Studien der 15 Hubs",
    "dkvf": "Abstracts des DKVF",
    "forschende": "Forschende",
    "institutionen": "Institutionen",
    "foerderer": "Förderer",
    "ausschreibungen": "offene Ausschreibungen",
    "zulassungen": "Zulassungsverfahren",
    "thesis": "Abschlussarbeiten",
}


def heute_lang(d=None):
    d = d or datetime.date.today()
    return "%d. %s %d" % (d.day, MONATE[d.month - 1], d.year)


def karten(B):
    nach_k = {x["k"]: x for x in B["saeulen"]}
    aus = ['<div class="mvf-dach-karten">']
    for _, titel, was, ziel, schluessel in GRUPPEN:
        zeilen = []
        for s in schluessel:
            x = nach_k.get(s)
            if not x or x.get("fehlt"):
                # ⚠ FEHLENDES WIRD NICHT WEGGELASSEN, sondern benannt.
                zeilen.append('<li><b>?</b><span>%s, Quelle fehlt</span></li>'
                              % seiten.esc(KURZ.get(s, s)))
                continue
            zeilen.append("<li><b>%s</b><span>%s</span></li>"
                          % (seiten.zahl(x["zahl"]),
                             seiten.esc(KURZ.get(s, x["titel"]))))
        aus.append(
            '<a class="mvf-dach-karte" href="%s"><h3>%s</h3>'
            '<p class="mvf-dach-was">%s</p><ul>%s</ul></a>'
            % (seiten.esc(ziel), seiten.esc(titel), seiten.esc(was),
               "".join(zeilen)))
    aus.append("</div>")
    return "\n    ".join(aus)


def bauen():
    B = json.loads((DATEN / "fachbestand.json").read_text(encoding="utf-8"))
    t = VORLAGE.read_text(encoding="utf-8")
    t = t.replace("{{KARTEN}}", karten(B))
    t = t.replace("{{STAND}}", heute_lang())
    t = t.replace("{{SUMME}}", seiten.zahl(B["gesamt"]))
    t = t.replace("{{QUELLEN}}", str(len(B["saeulen"])))
    offen = re.findall(r"\{\{[A-Z_]+\}\}", t)
    if offen:
        raise SystemExit("Platzhalter nicht gefuellt: %s" % ", ".join(offen))
    return ANFANG + "\n" + t.strip() + "\n" + ENDE


def einsetzen(band):
    """Einmal einfuegen, danach immer ersetzen. Nie zweimal einsetzen."""
    t = ZIEL.read_text(encoding="utf-8")
    if ANFANG in t:
        i, j = t.index(ANFANG), t.index(ENDE) + len(ENDE)
        neu = t[:i] + band + t[j:]
        wie = "ersetzt"
    else:
        if t.count(ANKER) != 1:
            raise SystemExit(
                "Anker fuer die Einfuegestelle nicht eindeutig (%d Treffer).\n"
                "  Gesucht: %r" % (t.count(ANKER), ANKER))
        neu = t.replace(ANKER, band + "\n\n" + ANKER, 1)
        wie = "neu eingesetzt"
    if neu.count(ANFANG) != 1 or neu.count(ENDE) != 1:
        raise SystemExit("Marken stehen doppelt, nichts geschrieben.")
    ZIEL.write_text(neu, encoding="utf-8")
    return wie, len(neu)


def stand_aus_datei():
    if not ZIEL.exists():
        return None
    # ⚠ NICHT AN DAS SATZZEICHEN DAHINTER BINDEN. Die erste Fassung
    # verlangte einen Punkt nach der Jahreszahl. Als die Fusszeile
    # umformuliert wurde und dort ein Komma stand, meldete die Pruefung
    # „kein lesbares Standdatum" - richtig gemeldet, aber aus dem
    # falschen Grund. Ein Wortende genuegt.
    m = re.search(r"Stand (\d{1,2})\. (\w+) (\d{4})\b",
                  ZIEL.read_text(encoding="utf-8"))
    if not m:
        return None
    try:
        return datetime.date(int(m.group(3)),
                             MONATE.index(m.group(2)) + 1, int(m.group(1)))
    except ValueError:
        return None


def pruefen():
    print("Das Dach-Band auf wissen.m-vf.de")
    ok = True
    t = ZIEL.read_text(encoding="utf-8") if ZIEL.exists() else ""
    for marke, name in ((ANFANG, "Anfangsmarke"), (ENDE, "Endmarke")):
        n = t.count(marke)
        gut = n == 1
        ok = ok and gut
        print("   %s %-14s %dmal" % ("ok " if gut else "FEHLER", name, n))
    # ⚠ AUCH DIE BLOSSEN NAMEN ZAEHLEN, nicht nur die ganzen Marken.
    # Am 02.11.2026 standen sie zweimal in index.html, weil der
    # Erklaertext der Vorlage sie ausschrieb. Gerettet hat nur, dass die
    # ganze Marke laenger ist als der Name. Das ist kein Verlass.
    for name in ("__DACH_BAND_ANFANG__", "__DACH_BAND_ENDE__"):
        n = t.count(name)
        gut = n == 1
        ok = ok and gut
        print("   %s Name %-22s %dmal (muss 1 sein)"
              % ("ok " if gut else "FEHLER", name, n))

    d = stand_aus_datei()
    if not d:
        ok = False
        print("   FEHLER kein lesbares Standdatum im Band")
    else:
        alt = (datetime.date.today() - d).days
        gut = alt <= HOECHSTALTER_TAGE
        ok = ok and gut
        print("   %s Stand %s, %d Tage alt (Grenze %d)"
              % ("ok " if gut else "FEHLER", heute_lang(d), alt,
                 HOECHSTALTER_TAGE))
        if not gut:
            print("      -> py dachband.py neu laufen lassen")
    print("\n" + ("Band bestanden." if ok else "BAND GESCHEITERT."))
    return 0 if ok else 1


def gegentest():
    """Greifen die Pruefungen, oder nicken sie alles durch?"""
    print("GEGENTEST")
    ok = True
    heute = datetime.date.today()
    alt = heute - datetime.timedelta(days=HOECHSTALTER_TAGE + 1)
    frisch = heute - datetime.timedelta(days=1)
    for d, soll in ((alt, False), (frisch, True)):
        tage = (heute - d).days
        ist = tage <= HOECHSTALTER_TAGE
        gut = ist is soll
        ok = ok and gut
        print("   %s %d Tage alt gilt als %s"
              % ("ok " if gut else "FEHLER", tage,
                 "frisch" if ist else "veraltet"))
    # Und: Faellt ein fehlendes Datum auf?
    m = re.search(r"Stand (\d{1,2})\. (\w+) (\d{4})\.", "ohne Datum")
    gut = m is None
    ok = ok and gut
    print("   %s ein Text ohne Standdatum wird erkannt"
          % ("ok " if gut else "FEHLER"))
    print("\n" + ("Gegentest bestanden." if ok else "GEGENTEST GESCHEITERT."))
    return 0 if ok else 1


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if "--gegentest" in sys.argv:
        return gegentest()
    if "--pruefen" in sys.argv:
        return pruefen()
    band = bauen()
    if "--zeigen" in sys.argv:
        print(band)
        return 0
    if not HUB.exists():
        raise SystemExit("Hub-Ordner fehlt: %s" % HUB)
    SCHNIPSEL.write_text(band + "\n", encoding="utf-8")
    wie, n = einsetzen(band)
    print("-> %s: Band %s, Datei jetzt %s Zeichen"
          % (ZIEL.name, wie, seiten.zahl(n)))
    print("-> %s geschrieben (nur zum Nachlesen)" % SCHNIPSEL.name)
    print("   Stand %s" % heute_lang())
    return 0


if __name__ == "__main__":
    sys.exit(main())
