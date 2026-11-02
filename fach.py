# -*- coding: utf-8 -*-
"""Die Dachseite des Fachs bauen: fach.html

ENTWURF vom 02.11.2026, nicht veroeffentlicht. Peter: "Bau bitte eine
Testseite, die mir zeigt, wie das aussehen koennte. Fuer das Fach
Versorgungsforschung waere es wichtig, eine einzige Seite zu haben, die
moeglichst vieles gesamthaft darstellt, was dieses Wissenschaftsfach
ausmacht."

WIE SIE GEBAUT WIRD
-------------------
    py fachbestand.py     zaehlt alle Saeulen -> daten/fachbestand.json
    py fach.py            setzt sie in vorlage-fach.html ein -> fach.html

⚠ CODE UND TEXT GEHOEREN NICHT IN PYTHON-ZEICHENKETTEN. Der feste Text
steht in `vorlage-fach.html`, die Kacheln baut `seiten.kachel`, das
Geruest kommt aus `teile/geruest.html`. Hier steht nur das Einsetzen.

⚠ KEINE ZAHL VON HAND. Jede Zahl kommt aus daten/fachbestand.json. Steht
eine Zahl in der Vorlage, ist das ein Fehler, und `--gegentest` sucht
danach.
"""
import json
import pathlib
import re
import sys

HIER = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HIER))

import leisten                                            # noqa: E402
import seiten                                             # noqa: E402

DATEN = HIER / "daten"
TEILE = HIER / "teile"
ZIEL = HIER / "fach.html"
VORLAGE = HIER / "_vorlage-fach.html"

TITEL = "Versorgungsforschung: das Fach auf einer Seite"
H1 = "Versorgungsforschung"
UNTER = ("Was gerade läuft, was veröffentlicht ist, wer es macht und was "
         "als Nächstes kommt. Alles aus einer Hand und mit Quelle.")

# Die Navigation dieses Entwurfs. Vier Fragen statt Rubriknamen - das ist
# eine Behauptung ueber Nutzerfuehrung, und die Seite sagt das auch.
NAVI = [
    ("#laeuft", "Was läuft"),
    ("#publiziert", "Was veröffentlicht ist"),
    ("#wer", "Wer es macht"),
    ("#kommt", "Was kommt"),
    ("#pflege", "Profil pflegen"),
    ("index.html", "← zur Landkarte"),
]


def gruppenblock(B):
    """Die vier Gruppen mit ihren Kacheln."""
    aus = []
    saeulen = B["saeulen"]
    for g in B["gruppen"]:
        teil = [x for x in saeulen if x["gruppe"] == g["k"]]
        if not teil:
            continue
        aus.append('<section class="gruppe" id="%s">' % seiten.esc(g["k"]))
        aus.append("<h2>%s</h2>" % seiten.esc(g["titel"]))
        aus.append('<p class="was lesebreite">%s</p>' % seiten.esc(g["was"]))
        aus.append('<div class="kacheln">')
        for x in teil:
            if x["fehlt"]:
                # ⚠ EINE FEHLENDE QUELLE WIRD GEZEIGT, NICHT VERSCHWIEGEN.
                aus.append(
                    '<div class="kachel fehlt"><div class="frage">%s</div>'
                    "<h2>%s</h2><p>Diese Säule fehlt gerade: %s</p></div>"
                    % (seiten.esc(x["quelle"]), seiten.esc(x["titel"]),
                       seiten.esc(x["fehlt"])))
                continue
            # ⚠ DAS NEBENBEI GEHOERT UNTER DIE ZAHL, NICHT HINTER DEN
            # SATZ. Angehaengt las es sich als abgebrochener Nachsatz:
            # "...was aus den Vorhaben geworden ist. seit 2016."
            klein = x["einheit"]
            if x["neben"]:
                klein += ", " + x["neben"]
            aus.append(seiten.kachel(
                x["quelle"], x["titel"], x["satz"],
                x["wo"] or "#", x["zahl"], klein,
                jetzt=(x["k"] == "rekrutiert")))
        aus.append("</div></section>")
    return "\n".join(aus)


def pflegeblock(P):
    """Die Messung zur Profilpflege als Tabelle."""
    zeilen = [
        ("Personen in der Landkarte", P["personen"], ""),
        ("davon mit irgendeiner Einrichtung", P["mit_einrichtung"], ""),
        ("davon mit einer <b>datierten</b> Einrichtung", P["mit_datum"],
         "hart"),
        ("davon mit einer <b>Historie</b> früherer Häuser",
         P["mit_historie"], "hart"),
        ("publizieren bei uns über 5 Jahre oder mehr", P["spanne_5"], ""),
        ("publizieren bei uns über 10 Jahre oder mehr", P["spanne_10"], ""),
    ]
    aus = ['<table class="messung"><tbody>']
    for titel, wert, art in zeilen:
        aus.append('<tr class="%s"><th scope="row">%s</th><td>%s</td></tr>'
                   % (art, titel, seiten.zahl(wert)))
    aus.append("</tbody></table>")
    return "\n".join(aus)


def bauen():
    B = json.loads((DATEN / "fachbestand.json").read_text(encoding="utf-8"))
    vorlage = VORLAGE.read_text(encoding="utf-8")

    inhalt = vorlage.replace("{{GRUPPEN}}", gruppenblock(B))
    inhalt = inhalt.replace("{{PFLEGE}}", pflegeblock(B["pflege"]))
    inhalt = inhalt.replace("{{UNMESSBAR}}", "\n".join(
        "    <li>%s</li>" % seiten.esc(x)
        for x in B["pflege"]["nicht_messbar"]))

    offen = re.findall(r"\{\{[A-Z_]+\}\}", inhalt)
    if offen:
        raise SystemExit("Platzhalter nicht gefuellt: %s" % ", ".join(offen))

    geruest = (TEILE / "_geruest.html").read_text(encoding="utf-8")
    netz, fuss = leisten.beide()
    navi = "\n      ".join(
        '<a href="%s">%s</a>' % (z, seiten.esc(n)) for z, n in NAVI)

    s = geruest
    s = s.replace(seiten.PLATZ["titel"], seiten.esc(TITEL))
    s = s.replace(seiten.PLATZ["beschreibung"], seiten.esc(UNTER))
    s = s.replace(seiten.PLATZ["h1"], seiten.esc(H1))
    s = s.replace(seiten.PLATZ["unter"], seiten.esc(UNTER))
    s = s.replace(seiten.PLATZ["navigation"], navi)
    s = s.replace(seiten.PLATZ["inhalt"], inhalt)
    s = s.replace(seiten.PLATZ["wurzel"], "")
    s = s.replace(seiten.PLATZ["skripte"], "")
    # ⚠ NICHT VERLINKT IST NICHT UNSICHTBAR. GitHub Pages liefert jede
    # Datei des Repos aus, und studien.m-vf.de ist live. Am 02.11.2026
    # gemessen: standort-vorlage.html gab HTTP 200 mit {{DNVF}} im
    # Klartext, obwohl niemand sie verlinkt hatte. Diese Seite geht als
    # Vorschau bewusst mit hinaus, aber nicht in die Suchmaschinen.
    s = s.replace("</head>",
                  '<meta name="robots" content="noindex, nofollow">\n'
                  "</head>", 1)

    # ⚠ EIGENE STILDATEI, NUR HIER. Der Entwurf darf an den
    # veroeffentlichten Seiten nichts aendern, also haengt sein Stil nicht
    # in stil-zusatz.css, sondern wird hier in den Kopf gesetzt.
    MARKE = '<link rel="stylesheet" href="teile/stil-zusatz.css">'
    if MARKE not in s:
        raise SystemExit("Stil-Anker im Geruest nicht gefunden")
    s = s.replace(
        MARKE, MARKE + '\n<link rel="stylesheet" href="teile/stil-fach.css">')

    # Die Augenbraue des Geruests nennt die Landkarte. Dieser Entwurf
    # steht eine Ebene hoeher, also nennt sie hier das Fach.
    # ⚠ IM QUELLTEXT STEHT SIE GEMISCHT. Die Grossschreibung macht das
    # CSS (text-transform). Wer nach der Fassung sucht, die im Browser
    # steht, findet nichts.
    AUGE = "Knowledge-Hubs &middot; Versorgungsstudien"
    if AUGE not in s:
        raise SystemExit("Augenbraue im Geruest nicht gefunden")
    s = s.replace(AUGE, "Knowledge-Hubs &middot; das Fach")

    s = leisten.einsetzen(s, netz, fuss)
    s = seiten.stempel(s)
    ZIEL.write_text(s, encoding="utf-8")
    return B, len(s)


def gegentest():
    """Steht wirklich keine Zahl von Hand in der Vorlage?"""
    print("GEGENTEST")
    ok = True
    roh = VORLAGE.read_text(encoding="utf-8")

    # ⚠ ENGE REGEL. Die erste Fassung nahm "jede Zahl ab drei Stellen" und
    # meldete das Datum 02.11.2026, die Jahreszahlen 2014 und 2017 und die
    # Lizenz CC BY 4.0 - vier Fehlalarme, null Funde. Eine Pruefung, die
    # man wegsieht, prueft nichts.
    #
    # Eine Bestandszahl sieht so aus: 5.395 oder 710. Also entweder
    # deutsche Tausendergruppe oder genau drei Ziffern fuer sich.
    MUSTER = r"\b\d{1,3}\.\d{3}\b|(?<![\d.])\d{3}(?![\d.])"

    def zahlen(t):
        return [m.group(0) for m in re.finditer(MUSTER, t)]

    treffer = zahlen(roh)
    if treffer:
        ok = False
        print("  FEHLER Bestandszahl in der Vorlage:", ", ".join(treffer[:6]))
    else:
        print("  ok  keine Bestandszahl steht von Hand in der Vorlage")

    # Gegenprobe zur Gegenprobe, in beide Richtungen.
    if zahlen(roh + " 5.395 ") and zahlen(roh + " 710 "):
        print("  ok  eine eingeschmuggelte Zahl wuerde auffallen")
    else:
        ok = False
        print("  FEHLER die Pruefung findet nicht einmal eine echte Zahl")
    falsch = zahlen("Stand 02.11.2026, seit 2014, CC BY 4.0, 15. Kongress")
    if falsch:
        ok = False
        print("  FEHLER Datum oder Lizenz gelten als Bestandszahl:", falsch)
    else:
        print("  ok  Datum, Jahr und Lizenz loesen keinen Fehlalarm aus")

    B = json.loads((DATEN / "fachbestand.json").read_text(encoding="utf-8"))
    leer = [x["titel"] for x in B["saeulen"] if x["fehlt"]]
    print("  %s %d Säulen ohne Quelle%s"
          % ("ok " if not leer else "   ", len(leer),
             (": " + ", ".join(leer)) if leer else ""))
    print("\n" + ("Gegentest bestanden." if ok else "GEGENTEST GESCHEITERT."))
    return 0 if ok else 1


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if "--gegentest" in sys.argv:
        return gegentest()
    B, n = bauen()
    print("fach.html gebaut, %s Zeichen" % seiten.zahl(n))
    print("  %d Säulen, %s Einträge, %d Quellen fehlen"
          % (len(B["saeulen"]), seiten.zahl(B["gesamt"]),
             B["fehlende_quellen"]))
    print("  ENTWURF - nicht verlinkt, nicht veröffentlicht")
    return 0


if __name__ == "__main__":
    sys.exit(main())
