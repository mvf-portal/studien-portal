# -*- coding: utf-8 -*-
"""Was macht das Fach Versorgungsforschung aus? Alles, was wir fuehren.

WARUM DIESE DATEI
-----------------
Peter am 02.11.2026: "Fuer das Fach Versorgungsforschung waere es wichtig,
eine einzige Seite zu haben, die moeglichst vieles gesamthaft darstellt,
was dieses Wissenschaftsfach ausmacht."

Bevor eine solche Seite gebaut wird, muss gezaehlt sein, was es ueberhaupt
zu zeigen gibt - aus allen Bestaenden, die wir fuehren, nicht nur aus
denen dieses Ordners.

⚠ KEINE ZAHL VON HAND. Jede Zahl der Dachseite kommt aus einer Datei, die
eine Kette gebaut hat. Eine abgeschriebene Zahl veraltet still, und genau
das ist auf mvf.html schon einmal passiert.

⚠ KEIN FELDNAME GERATEN. Der erste Entwurf suchte die Listen mit einer
Heuristik ("nimm die laengste Liste") und zaehlte vier Saeulen falsch:
0 rekrutierende Studien statt 265, 11 Einrichtungen statt 2.430,
0 Ausschreibungen statt 24. Ein Feld, das der Datensatz nicht fuehrt,
liest sich leer - und leer sieht aus wie eine Tatsache. Darum steht jeder
Zugriff unten ausgeschrieben, und `pflicht()` bricht ab, wenn er ins
Leere greift.

⚠ FEHLT EINE QUELLE, SAGT DIE ZEILE DAS. Sie wird nicht weggelassen.
Eine Dachseite, die eine Saeule verschweigt, weil ihre Datei gerade
fehlt, behauptet etwas ueber das Fach, das nicht stimmt.

    py fachbestand.py            zaehlen und daten/fachbestand.json schreiben
    py fachbestand.py --zeigen   nur zeigen, nichts schreiben
    py fachbestand.py --gegentest  beweisen, dass die Pruefung greift
"""
import json
import pathlib
import sys

HIER = pathlib.Path(__file__).resolve().parent
DATEN = HIER / "daten"
CLAUDE = HIER.parent
VF_HUB = CLAUDE / "versorgungsforschung-portal"
INNOFONDS = CLAUDE / "innofonds-portal"
THESIS = CLAUDE / "thesis-vorschau"


class Fehlt(Exception):
    """Eine Quelle oder ein Feld, mit dem gerechnet wurde, ist nicht da."""


def lade(p):
    p = pathlib.Path(p)
    if not p.exists():
        raise Fehlt("Datei fehlt: %s" % p.name)
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (ValueError, OSError) as e:
        raise Fehlt("unlesbar: %s (%s)" % (p.name, e))


def pflicht(d, *weg):
    """Einen Wert holen und abbrechen, wenn der Weg ins Leere fuehrt.

    ⚠ NICHT .get() MIT VORGABE. Eine Vorgabe macht aus einem falschen
    Feldnamen eine ploetzlich plausible Null.
    """
    x = d
    for w in weg:
        if isinstance(x, dict):
            if w not in x:
                raise Fehlt("Feld %r fehlt (Weg %s)" % (w, " -> ".join(
                    str(y) for y in weg)))
            x = x[w]
        elif isinstance(x, list) and isinstance(w, int):
            if w >= len(x):
                raise Fehlt("Element %d fehlt" % w)
            x = x[w]
        else:
            raise Fehlt("Weg %s passt nicht zum Aufbau" % " -> ".join(
                str(y) for y in weg))
    return x


def saeulen():
    """Die Saeulen des Fachs. Jede zaehlt sich selbst, jede nennt ihre
    Quelle, und jede faengt ihr eigenes Fehlen ab."""
    aus = []

    def dazu(k, titel, gruppe, zaehler, einheit, quelle, wo, satz):
        try:
            zahl, neben = zaehler()
            fehlt = ""
        except Fehlt as e:
            zahl, neben, fehlt = 0, "", str(e)
        aus.append({"k": k, "titel": titel, "gruppe": gruppe, "zahl": zahl,
                    "neben": neben, "einheit": einheit, "quelle": quelle,
                    "wo": wo, "satz": satz, "fehlt": fehlt})

    # ------------------------------------------------ WAS GERADE LAEUFT
    def f_rekrutiert():
        L = lade(DATEN / "landkarte.json")
        n = 0
        for x in pflicht(L, "studien"):
            if pflicht(x, "status_de") == "rekrutiert":
                n += 1
        orte = sum(1 for x in pflicht(L, "studien")
                   if x.get("status_de") == "rekrutiert" and x.get("orte"))
        return n, "%d davon mit Ort" % orte

    dazu("rekrutiert", "Sucht gerade Teilnehmende", "laeuft", f_rekrutiert,
         "Studien", "DRKS", "rekrutierend.html",
         "Das Einzige hier, zu dem Sie heute etwas tun können. Es verfällt, "
         "darum steht es vorn.")

    def f_studien():
        # ⚠ vf_gesamt ist das ZEIGBARE, nicht das Gefundene. Gefunden
        # sind vf_im_register, und vf_nicht_zeigbar duerfen wir wegen
        # der CC-BY-Grenze des Registers nicht wiedergeben. Wer die
        # beiden verwechselt, schreibt "710 von 710".
        L = lade(DATEN / "landkarte.json")
        n = len(pflicht(L, "studien"))
        if n != pflicht(L, "vf_gesamt"):
            raise Fehlt("studien=%d passt nicht zu vf_gesamt=%d"
                        % (n, L["vf_gesamt"]))
        return n, ("von %s im Register, %s sperrt die Lizenz"
                   % (zahl(pflicht(L, "vf_im_register")),
                      zahl(pflicht(L, "vf_nicht_zeigbar"))))

    dazu("studien", "Registrierte Studien", "laeuft", f_studien, "Studien",
         "DRKS", "studien.html",
         "Was in Deutschland läuft oder gelaufen ist, mit Ort, Förderung "
         "und Status.")

    def f_innofonds():
        if not INNOFONDS.exists():
            raise Fehlt("Ordner innofonds-portal fehlt")
        n = sum(1 for p in (INNOFONDS / "projekt").glob("*/index.html"))
        if not n:
            raise Fehlt("keine Projektseiten in innofonds-portal/projekt")
        return n, "seit 2016"

    dazu("innofonds", "Innovationsfonds-Projekte", "laeuft", f_innofonds,
         "Projekte", "GBA-Projektdatenbank", "https://innofonds.m-vf.de/",
         "Das größte Förderprogramm des Fachs, mit Evaluationsberichten "
         "und dem, was aus den Vorhaben geworden ist.")

    # ------------------------------------------------ WAS VEROEFFENTLICHT IST
    def f_literatur():
        d = lade(VF_HUB / "studien-archiv.json")
        if not isinstance(d, list):
            raise Fehlt("studien-archiv.json ist keine Liste")
        return len(d), "jeden Morgen neue"

    dazu("literatur", "Neue Literatur", "publiziert", f_literatur, "Arbeiten",
         "PubMed, täglich", "https://wissen.m-vf.de/neue-studien.html",
         "Mit deutscher Zusammenfassung, Ergebnis und Übertragbarkeit auf "
         "Deutschland.")

    def f_mvf():
        M = lade(DATEN / "mvf_beitraege.json")
        return len(pflicht(M, "beitraege")), "seit 2008, alle mit DOI"

    dazu("mvf", "Beiträge in „Monitor Versorgungsforschung“", "publiziert",
         f_mvf, "Beiträge", "MVF", "mvf.html",
         "Die Fachzeitschrift des Fachs, begutachtet, offen zugänglich.")

    def f_hubs():
        H = lade(DATEN / "suchindex-hubs.json")
        return len(pflicht(H, "eintraege")), "aus 15 Themen-Hubs"

    dazu("hubs", "Studien der Knowledge-Hubs", "publiziert", f_hubs,
         "Arbeiten", "PubMed", "https://knowledge-hubs.de/",
         "Adipositas bis Kardiologie. Themen, die ein Studienregister "
         "nicht kennt. In der Suche oben enthalten.")

    def f_dkvf():
        D = lade(DATEN / "dkvf.json")
        return (len(pflicht(D, "abstracts")),
                "von %s Vortragenden" % zahl(len(pflicht(D, "personen"))))

    dazu("dkvf", "Abstracts des DKVF", "publiziert", f_dkvf, "Abstracts",
         "Deutscher Kongress für Versorgungsforschung", "forschende.html",
         "Was auf dem Jahreskongress des Fachs vorgetragen wurde.")

    # --------------------------------------------------------- WER FORSCHT
    def f_forschende():
        P = lade(DATEN / "personen.json")
        leute = pflicht(P, "personen")
        mit = sum(1 for p in leute.values() if p.get("profil"))
        return len(leute), "%s mit eigenem Profil" % zahl(mit)

    dazu("forschende", "Forschende", "wer", f_forschende, "Personen",
         "DRKS, MVF, DKVF, Autorenprofile", "forschende.html",
         "Wer an Versorgungsstudien arbeitet, bei MVF publiziert oder "
         "beim DKVF vorträgt.")

    def f_institutionen():
        E = lade(DATEN / "einrichtungen.json")
        return (pflicht(E, "gesamt"),
                "%s mit Profilseite" % zahl(pflicht(E, "mit_profil")))

    dazu("institutionen", "Institutionen", "wer", f_institutionen,
         "Einrichtungen", "DRKS und Partnernetz des Innovationsfonds",
         "institutionen.html",
         "Nach Trägerart getrennt. Hochschulen und außeruniversitäre "
         "Institute stehen nicht in einem Topf.")

    def f_foerderer():
        # ⚠ "foerderer" ist hier eine ZAHL, nicht die Liste. Die Liste
        # heisst "liste". Beide stehen nebeneinander, und len() auf der
        # Zahl bricht ab - was gut ist, denn ein stilles Zurueckfallen
        # haette 484 mit irgendetwas anderem verwechselt.
        F = lade(DATEN / "foerderer.json")
        n = pflicht(F, "foerderer")
        if n != len(pflicht(F, "liste")):
            raise Fehlt("foerderer=%d passt nicht zu liste=%d"
                        % (n, len(F["liste"])))
        return n, "aus %s Schreibweisen" % zahl(pflicht(F, "schreibweisen"))

    dazu("foerderer", "Förderer", "wer", f_foerderer, "Geldgeber", "DRKS",
         "studien.html", "Wer die Forschung bezahlt.")

    # ------------------------------------------------------- WAS KOMMT
    def f_ausschreibungen():
        A = lade(VF_HUB / "ausschreibungen.json")
        themen = pflicht(A, "themen")
        n = sum(pflicht(t, "anzahl") for t in themen)
        eigen = [pflicht(t, "anzahl") for t in themen
                 if t.get("slug") == "versorgungsforschung"]
        return n, "%d davon im Fach selbst" % (eigen[0] if eigen else 0)

    dazu("ausschreibungen", "Offene Ausschreibungen", "kommt",
         f_ausschreibungen, "Ausschreibungen", "Innovationsfonds, Bund, DFG, EU",
         "https://wissen.m-vf.de/ausschreibungen.html",
         "Wo es gerade Geld für Versorgungsforschung gibt.")

    def f_zulassungen():
        Z = lade(VF_HUB / "zulassungen.json")
        return len(pflicht(Z, "eintraege")), "fünf Stufen bis zur Erstattung"

    dazu("zulassungen", "Zulassungs- und DiGA-Radar", "kommt", f_zulassungen,
         "Verfahren", "GBA, BfArM, EMA",
         "https://wissen.m-vf.de/zulassungen.html",
         "Was auf dem Weg in die Versorgung ist, mit Zeitstrahl.")

    def f_thesis():
        d = lade(THESIS / "arbeiten.json")
        if not isinstance(d, list):
            raise Fehlt("arbeiten.json ist keine Liste")
        return len(d), "Vorschau, noch nicht öffentlich"

    dazu("thesis", "Abschlussarbeiten", "kommt", f_thesis, "Arbeiten", "DNVF",
         "https://mvf-portal.github.io/thesis-vorschau/",
         "Wer gerade in das Fach hineinwächst.")

    return aus


def zahl(n):
    return f"{n:,}".replace(",", ".")


# ------------------------------------------------------------ Profilpflege

# ⚠ NICHT AUF WORTBESTANDTEILE PRUEFEN. Der erste Entwurf suchte unter
# anderem nach "stand" und fand "standort" - ein Ort wurde als Datum
# gelesen, und die Zaehlung meldete -1 statt 0. Darum ganze Feldnamen.
DATUMSFELDER = {"von", "bis", "jahr", "seit", "zeitraum", "stand",
                "einrichtung_von", "einrichtung_bis", "einrichtung_seit",
                "einrichtung_stand", "historie", "verlauf"}


def pflege():
    """Kann ein Mensch seinen Eintrag überhaupt richtig halten?

    Peter am 02.11.2026: „Die Menschen wechseln zwischen den
    Institutionen, das muss man nachhalten können."

    ⚠ WIE OFT GEWECHSELT WIRD, KÖNNEN WIR NICHT MESSEN, und das ist
    hier ausdrücklich vermerkt statt überspielt:

      * Die Autorenboxen tragen die Einrichtung nur als Maildomäne, und
        die ist um eine Position verschoben (Carsten Telschow bekommt im
        Datensatz die Adresse von Jonas Lohmüller). Eine verschobene
        Quelle beantwortet die Frage nicht.
      * Die DKVF-Abstracts haben zwei Jahrgänge. Von 99 Personen, die in
        beiden vorkommen, nennen 66 eine andere Zugehörigkeit - aber die
        Beispiele sind fast alle Schreib- und Sprachvarianten desselben
        Hauses („Universität Witten/Herdecke" gegen „Witten/Herdecke
        University"), nicht Wechsel. Zwei Jahre sind zu kurz für
        Karrieren.

    Messbar und entscheidend ist dafür etwas anderes: Keine einzige
    Einrichtungsangabe im ganzen Bestand trägt ein Datum. Die Frage „wo
    war diese Person 2017?" ist nicht falsch beantwortet, sie ist gar
    nicht stellbar.
    """
    P = pflicht(lade(DATEN / "personen.json"), "personen")
    felder = set()
    for p in P.values():
        felder |= set(p)
    datiert = sorted(f for f in felder if f in DATUMSFELDER)

    # ⚠ NACH PERSON ZAEHLEN, NICHT NACH NAMENSZEICHENKETTE. "Peter
    # Stegmaier" und "Dr. Peter Stegmaier" sind zwei Zeichenketten und
    # ein Mensch. Ueber Zeichenketten gezaehlt kamen 43 heraus, ueber
    # den Hausschluessel 31.
    sys.path.insert(0, str(HIER))
    from suchindex import personenschluessel, teile_namen

    M = pflicht(lade(DATEN / "mvf_beitraege.json"), "beitraege")
    jahre = {}
    for b in M.values():
        j = b.get("jahr")
        if not isinstance(j, int):
            continue
        for a in (b.get("autoren") or []):
            nach, vor = teile_namen(a)
            k = personenschluessel(nach, vor)
            if k:
                jahre.setdefault(k, set()).add(j)
    lang = sum(1 for v in jahre.values() if max(v) - min(v) >= 5)
    sehr = sum(1 for v in jahre.values() if max(v) - min(v) >= 10)

    return {
        "personen": len(P),
        "mit_einrichtung": sum(1 for p in P.values()
                               if (p.get("einrichtung") or "").strip()),
        "mit_datum": 0 if not datiert else -1,
        "mit_historie": 0,
        "datumsfelder": datiert,
        "spanne_5": lang,
        "spanne_10": sehr,
        "nicht_messbar": [
            "Wie oft gewechselt wird. Die Autorenbox trägt die "
            "Einrichtung nur als Maildomäne, und die ist um eine "
            "Position verschoben.",
            "Ob eine abweichende Zugehörigkeit ein Wechsel ist oder nur "
            "eine andere Schreibweise. Von 99 Personen in beiden "
            "DKVF-Jahrgängen nennen 66 eine andere Zugehörigkeit, die "
            "Beispiele sind fast alle Varianten desselben Hauses.",
        ],
    }


GRUPPEN = [
    ("laeuft", "Was gerade läuft",
     "Vorhaben, die noch nicht zu Ende sind. Hier ändert sich etwas, "
     "solange Sie zusehen."),
    ("publiziert", "Was veröffentlicht ist",
     "Das Wissen des Fachs, von der Arbeit von heute Morgen bis zum "
     "Jahrgang 2008."),
    ("wer", "Wer es macht",
     "Menschen, Häuser und Geldgeber, und wie sie zusammenhängen."),
    ("kommt", "Was als Nächstes kommt",
     "Geld, Zulassungen und der Nachwuchs. Alles drei entscheidet, "
     "was das Fach in fünf Jahren ist."),
]


def gegentest():
    """Greift pflicht() wirklich, oder nickt sie alles durch?"""
    print("GEGENTEST: eine Pruefung, die nie fehlschlaegt, prueft nichts")
    ok = True
    for weg, titel in (
            (("studien_", ), "falscher Feldname"),
            (("studien", 99999), "Element ausserhalb"),
            (("stand", "x"), "Weg passt nicht zum Aufbau")):
        try:
            pflicht(lade(DATEN / "landkarte.json"), *weg)
        except Fehlt as e:
            print("  ok  %-26s -> %s" % (titel, e))
            continue
        except Exception as e:
            print("  FEHLER %-23s -> falsche Ausnahme: %r" % (titel, e))
            ok = False
            continue
        print("  FEHLER %-23s -> durchgewunken" % titel)
        ok = False
    try:
        n = pflicht(lade(DATEN / "landkarte.json"), "studien")
        print("  ok  richtiger Weg traegt      -> %d Studien" % len(n))
    except Fehlt as e:
        print("  FEHLER richtiger Weg bricht ab -> %s" % e)
        ok = False
    print("\n" + ("Gegentest bestanden." if ok else "GEGENTEST GESCHEITERT."))
    return 0 if ok else 1


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if "--gegentest" in sys.argv:
        return gegentest()

    s = saeulen()
    print("Die Säulen des Fachs Versorgungsforschung")
    print("=" * 70)
    for g, titel, _ in GRUPPEN:
        print("\n%s" % titel.upper())
        for x in s:
            if x["gruppe"] != g:
                continue
            if x["fehlt"]:
                print("   %-40s FEHLT: %s" % (x["titel"][:40], x["fehlt"]))
            else:
                print("   %-40s %9s  %s"
                      % (x["titel"][:40], zahl(x["zahl"]), x["neben"]))
    fehlen = sum(1 for x in s if x["fehlt"])
    gesamt = sum(x["zahl"] for x in s if not x["fehlt"])
    print("\n" + "=" * 70)
    print("  %d Säulen, %s Einträge zusammen, %d Quelle(n) fehlen"
          % (len(s) - fehlen, zahl(gesamt), fehlen))

    if "--zeigen" in sys.argv:
        return 0
    pf = pflege()
    print("\nProfilpflege")
    print("   Personen                   %7s" % zahl(pf["personen"]))
    print("   mit irgendeiner Einrichtung%7s" % zahl(pf["mit_einrichtung"]))
    print("   mit DATIERTER Einrichtung  %7s" % zahl(pf["mit_datum"]))
    print("   mit einer HISTORIE         %7s" % zahl(pf["mit_historie"]))
    print("   Datumsfelder im Datensatz  %7s"
          % (", ".join(pf["datumsfelder"]) or "KEINES"))
    print("   publizieren über 5 Jahre   %7s" % zahl(pf["spanne_5"]))
    print("   publizieren über 10 Jahre  %7s" % zahl(pf["spanne_10"]))

    ziel = DATEN / "fachbestand.json"
    ziel.write_text(json.dumps(
        {"saeulen": s, "gruppen": [{"k": a, "titel": b, "was": c}
                                   for a, b, c in GRUPPEN],
         "pflege": pf,
         "fehlende_quellen": fehlen, "gesamt": gesamt},
        ensure_ascii=False, indent=1), encoding="utf-8")
    print("\n-> %s" % ziel)
    return 0


if __name__ == "__main__":
    sys.exit(main())
