# -*- coding: utf-8 -*-
"""Baut die sieben Seiten des Studienportals aus einem gemeinsamen Geruest.

WARUM SIEBEN SEITEN
-------------------
Vorher stand alles auf einer Seite mit zwei Reitern, und Peter Stegmaier
hat am 01.11.2026 gesagt, worum es wirklich geht: Wer die Seite aufruft,
sucht sieben verschiedene Dinge.

  a) sich selbst              -> Forschende
  b) seine Studien           -> Forschende, Studien
  c) seine Institution       -> Institutionen
  d) woran andere forschen   -> Studien, Forschungsstandorte
  e) wer foerdert            -> Studien, Filter Foerderung
  f) wer Mitarbeitende sucht -> KEINE QUELLE, nur Selbstauskunft
  g) wer gerade rekrutiert   -> eigene Seite, 265 Studien
  h) Studien zu einem Thema  -> Suche, Studien

Darum oben auf jeder Seite EIN Suchfeld ueber alle Bestaende, und darunter
die Seite, die zur Frage passt.

MARIANNS VORGABEN, die hier tragen
----------------------------------
Kacheln statt Listen. Wenige grosse Karten. Wenig Text vor der Suche. Die
schwarze Netzleiste und die Fussleiste kommen aus `portal-vorlage`, nicht
aus einer Kopie.

  py seiten.py              baut alle Seiten
  py seiten.py --gegentest  prueft ohne Netz
"""
import html
import json
import pathlib
import re
import sys
import unicodedata
import urllib.parse

HIER = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HIER))
DATEN = HIER / "daten"
TEILE = HIER / "teile"

import leisten

# (Datei, Titel, H1, Unterzeile, Navigationsname)
SEITEN = [
    ("index.html", "Versorgungsstudien in Deutschland",
     "Versorgungsstudien in Deutschland",
     "Wer forscht wo, woran, und wer sucht gerade Teilnehmende.",
     "Überblick"),
    ("rekrutierend.html", "Studien, die gerade Teilnehmende suchen",
     "Rekrutiert gerade",
     "Studien, die heute offen sind. Das verfällt, darum steht es vorn.",
     "Rekrutiert gerade"),
    ("standorte.html", "Forschungsstandorte der Versorgungsforschung",
     "Forschungsstandorte",
     "Die Karte und die Rangliste der Einrichtungen mit eigener Profilseite.",
     "Forschungsstandorte"),
    ("institutionen.html", "Institutionen der Versorgungsforschung",
     "Institutionen",
     "Alle Einrichtungen, nach Trägerart getrennt. Hochschulen und "
     "außeruniversitäre Institute stehen nicht in einem Topf.",
     "Institutionen"),
    ("forschende.html", "Forschende der Versorgungsforschung",
     "Forschende",
     "Wer an Versorgungsstudien arbeitet, wer bei MVF publiziert, wer beim "
     "DKVF vorträgt.",
     "Forschende"),
    ("studien.html", "Versorgungsstudien im Register",
     "Studien",
     "Alle Studien mit Filtern, die neuesten zuerst.",
     "Studien"),
    ("mvf.html", "Versorgungsforschung bei MVF und in den Knowledge-Hubs",
     "MVF und die Hubs",
     "Wo die Forschung auftaucht, die das Studienregister nicht kennt.",
     "MVF und die Hubs"),
    ("eintragen.html", "Eintragen und pflegen",
     "Eintragen und pflegen",
     "Was keine Quelle hergibt, tragen Einrichtungen und Forschende hier "
     "selbst ein.",
     "Eintragen"),
]

PLATZ = {
    "titel": "<!--__TITEL__-->", "beschreibung": "<!--__BESCHREIBUNG__-->",
    "h1": "<!--__H1__-->", "unter": "<!--__UNTER__-->",
    "navigation": "<!--__NAVIGATION__-->", "inhalt": "<!--__INHALT__-->",
    "wurzel": "<!--__WURZEL__-->", "skripte": "<!--__SKRIPTE__-->",
}


def esc(s):
    return html.escape(str(s if s is not None else ""), quote=True)


def zahl(n):
    """Deutsche Tausenderpunkte. 1298 wird 1.298."""
    return f"{int(n or 0):,}".replace(",", ".")


def navigation(aktuell):
    aus = []
    for datei, _, _, _, name in SEITEN:
        ziel = datei
        jetzt = ' aria-current="page"' if datei == aktuell else ""
        aus.append(f'<a href="{ziel}"{jetzt}>{esc(name)}</a>')
    return "\n      ".join(aus)


def lade(name):
    p = DATEN / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


# ------------------------------------------------------------- Bausteine

def kachel(frage, titel, text, ziel, wert=None, einheit="", jetzt=False):
    k = ['<a class="kachel%s" href="%s">' % (" jetzt" if jetzt else "", ziel)]
    if frage:
        k.append('<div class="frage">%s</div>' % esc(frage))
    k.append("<h2>%s</h2>" % esc(titel))
    k.append("<p>%s</p>" % esc(text))
    if wert is not None:
        k.append('<span class="zahl">%s<small>%s</small></span>'
                 % (zahl(wert), esc(einheit)))
    k.append("</a>")
    return "\n".join(k)


def sprungmarke(s):
    """Aus einem Namen eine Sprungmarke machen.

    ⚠ NUR FUER EINRICHTUNGEN. Personen haben ihre Sprungmarke seit dem
    01.11.2026 als Feld „anker" in personen.json, gebildet aus dem
    Zusammenfuehrungsschluessel. Wer sie hier aus dem Anzeigenamen neu
    bildet, bricht jeden Personenlink der Suche.
    """
    s = (s or "").lower()
    for a, b in (("\u00e4", "ae"), ("\u00f6", "oe"), ("\u00fc", "ue"),
                 ("\u00df", "ss")):
        s = s.replace(a, b)
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", s)).strip("-")[:80]


def vergleichbar(s):
    """Kleingeschrieben und ohne Umlaute, zum Filtern im Browser.

    ⚠ MUSS ZU norm() IN teile/liste.js PASSEN. Tut sie das nicht, findet
    das Filterfeld „Muenster" nicht, wenn jemand „Münster" tippt.
    """
    s = (s or "").lower()
    for a, b in (("\u00e4", "ae"), ("\u00f6", "oe"), ("\u00fc", "ue"),
                 ("\u00df", "ss")):
        s = s.replace(a, b)
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()


def sortname(s):
    """Der Schluessel fuer „Name A bis Z".

    Vorne stehende Zeichen, die keine Buchstaben sind, fallen weg:
    Aufzaehlungszeichen, Klammern, Gliederungsnummern. Ein Name, der nur
    aus solchen Zeichen besteht, behaelt seinen Rest, damit er nicht
    stumm nach vorne rutscht.

    ⚠ NUR DER SCHLUESSEL. Der angezeigte Name bleibt, wie das Register
    ihn fuehrt.
    """
    v = vergleichbar(s)
    # vergleichbar() liefert nur ASCII in Kleinschreibung, darum genuegt
    # a bis z als Mass fuer „Buchstabe".
    rest = re.sub(r"^[^a-z]+", "", v)
    return (rest or v).strip()


def steuerleiste(felder, suche):
    """Die Leiste ueber einer langen Liste.

    ⚠ SIE STEHT ALS hidden IN DER SEITE, teile/liste.js deckt sie auf.
    Ohne JavaScript tun Sortierfeld und Filter nichts, und eine Leiste,
    die nichts tut, ist schlimmer als keine.
    """
    s = ['<div class="steuer" hidden>']
    for name, titel, werte in felder:
        attr = "data-sort" if name == "sort" else 'data-filter="%s"' % name
        s.append('<label>%s <select %s>' % (esc(titel), attr))
        for wert, wort in werte:
            s.append('<option value="%s">%s</option>'
                     % (esc(wert), esc(wort)))
        s.append("</select></label>")
    s.append('<label>Suchen <input type="search" data-such '
             'placeholder="%s"></label>' % esc(suche))
    s.append('<p class="steuer-stand" aria-live="polite"></p>')
    s.append("</div>")
    return "\n".join(s)


def eintragsziel(art, name, text):
    """Der Weg zum Formular fuer eine Zeile, die keine eigene Seite hat.

    ⚠ DER NAME GEHT ALS ABFRAGE MIT. eintragen.html setzt ihn ins
    Formular, damit niemand ihn abschreiben muss.
    """
    return ('<a class="ziel" href="eintragen.html?art=%s&amp;name=%s">'
            '%s <b>Eintragen oder \u00e4ndern</b></a>'
            % (art, urllib.parse.quote(name or ""), esc(text)))


def gestapelt(teile, leer):
    """Jede Zahl auf ihre eigene Zeile.

    ⚠ NICHT mit " &middot; " verbinden. Die Spalte rechts ist schmal,
    die lange Zeile bricht trotzdem um, und die Trennpunkte bleiben
    dann am Zeilenende stehen.
    """
    if not teile:
        return '<div>%s</div>' % leer
    return "".join("<div>%s</div>" % s for s in teile)


def kurz(text, grenze=110):
    """Schneidet an der letzten Wortgrenze, nie mitten im Wort."""
    text = (text or "").strip()
    if len(text) <= grenze:
        return text
    stumpf = text[:grenze]
    raum = stumpf.rfind(" ")
    if raum > grenze * 0.6:
        stumpf = stumpf[:raum]
    return stumpf.rstrip(" ,.;:-\u2013\u2014") + " \u2026"


def haus_zeile(e, art="", gesehen=None):
    """Eine Einrichtung als Zeile, mit Sprungmarke, Sortierschl\u00fcsseln
    und Ziel.

    ⚠ JEDE ZEILE BRAUCHT EIN ZIEL. 2.265 von 2.430 Einrichtungen haben
    keine Profilseite. Vorher stand ihr Name als fetter Text da, in
    derselben Farbe wie die 165 Links daneben, und sah aus wie ein Link.
    Jetzt sagt die Zeile, dass es keine Seite gibt, und bietet das
    Formular an.
    """
    name = esc(e["name"])
    ziel = ""
    if e.get("datei"):
        name = '<a href="standort/%s">%s</a>' % (esc(e["datei"]), name)
    else:
        ziel = eintragsziel("einrichtung", e["name"], "Keine Profilseite.")
    z = []
    if e.get("studien"):
        z.append("<b>%s</b> Studien" % zahl(e["studien"]))
    if e.get("rekrutiert"):
        z.append("%s rekrutieren" % zahl(e["rekrutiert"]))
    if e.get("projekte"):
        z.append("<b>%s</b> Innofonds-Projekte" % zahl(e["projekte"]))
    marke = ""
    quellen = e.get("quellen") or []
    if quellen == ["Innovationsfonds"]:
        marke = '<span class="marke">nur Innofonds</span>'

    # Sprungmarke. Gemessen: 17 von 2.430 Namen fallen auf denselben
    # Buchstabenrest zusammen, darum die laufende Nummer.
    m = sprungmarke(e["name"]) or "haus"
    if gesehen is not None:
        gesehen[m] = gesehen.get(m, 0) + 1
        if gesehen[m] > 1:
            m = "%s-%d" % (m, gesehen[m])

    marken = []
    if "Studienregister" in quellen:
        marken.append("register")
    if "Innovationsfonds" in quellen:
        marken.append("innofonds")
    if quellen == ["Innovationsfonds"]:
        marken.append("nur-innofonds")
    if e.get("rekrutiert"):
        marken.append("rekrutiert")
    marken.append("profil-ja" if e.get("datei") else "profil-nein")

    ort = e.get("ort") or ""
    return ('<div class="haus" id="haus-%s" data-n="%s" data-studien="%d" '
            'data-projekte="%d" data-summe="%d" data-art="%s" '
            'data-quelle="%s" data-such="%s">'
            '<div>%s%s</div>'
            '<div class="wo">%s</div>'
            '<div class="zahlen">%s</div>%s</div>'
            % (esc(m), esc(sortname(e["name"])),
               e.get("studien") or 0, e.get("projekte") or 0,
               (e.get("studien") or 0) + (e.get("projekte") or 0),
               esc(art), esc(" ".join(marken)),
               esc(vergleichbar(" ".join([e["name"], ort, art]))),
               name, marke,
               esc(ort or "Ort nicht angegeben"),
               gestapelt(z, "ohne Z\u00e4hlung"), ziel))


# ----------------------------------------------------------------- Seiten

def inhalt_home():
    L = lade("landkarte.json") or {}
    E = lade("einrichtungen.json") or {}
    S = lade("suchindex.json") or {}
    HS = lade("suchindex-hubs.json") or {}
    AB = lade("mvf_autorenbox.json") or {}
    studien = L.get("studien", [])
    rekrutiert = sum(1 for x in studien if x.get("status") == "RECRUITING")
    personen = (S.get("zaehlung") or {}).get("person", 0)
    einr = E.get("gesamt", 0)
    fe = next((a for a in E.get("abschnitte", [])
               if a["art"] == "Ausseruniversitaere Forschungseinrichtung"), {})
    fehlt = len((E.get("fehlen_im_register") or {}).get("liste", []))

    k = [
        kachel("Wer rekrutiert gerade", "Rekrutiert gerade",
               "Studien, die heute Teilnehmende suchen. Das einzige hier, zu "
               "dem Sie sofort etwas tun können.",
               "rekrutierend.html", rekrutiert, "Studien, davon %s mit Ort"
               % zahl(sum(1 for x in studien
                          if x.get("status") == "RECRUITING" and x.get("orte"))),
               jetzt=True),
        kachel("Wo wird geforscht", "Forschungsstandorte",
               "Die Karte, die Rangliste und je Standort eine Profilseite mit "
               "Fächern, Registern und Personen.",
               "standorte.html", 63, "Standorte mit Profilseite"),
        kachel("Welche Einrichtungen", "Institutionen",
               "Nach Trägerart getrennt. Hochschulen und außeruniversitäre "
               "Institute stehen nicht in einem Topf.",
               "institutionen.html", einr, "Einrichtungen, %s davon "
               "außeruniversitäre Institute" % zahl(fe.get("anzahl", 0))),
        kachel("Wer forscht", "Forschende",
               "Wer an Versorgungsstudien arbeitet, bei MVF publiziert oder "
               "beim DKVF vorträgt.",
               "forschende.html", personen, "Personen"),
        kachel("Woran wird geforscht", "Studien",
               "Alle Studien mit Filtern nach Thema, Ort, Förderung und "
               "Status, die neuesten zuerst.",
               "studien.html", len(studien), "Studien, die wir zeigen dürfen"),
        kachel("Was das Register nicht sieht", "MVF und die Hubs",
               "Häuser, die bei uns publizieren und im Studienregister "
               "fehlen, und die Verbindung zu den 15 Knowledge-Hubs.",
               "mvf.html", fehlt, "Häuser, die im Register fehlen"),
    ]

    aus = ['<div class="kacheln">', "\n".join(k), "</div>"]

    aus.append('''
<div class="hinweiskasten" id="was-fehlt">
  <h2>Was Sie hier sehen, und was nicht</h2>
  <p>Im Studienregister stehen <b>%s Studien mit Versorgungsbezug</b>.
    Wiedergeben dürfen wir <b>%s</b> davon. <b>%s fehlen hier, obwohl es sie
    gibt.</b> Das liegt nicht an der Forschung, sondern an vier Schranken,
    und zwei davon können die Forschenden selbst aufheben.</p>
  <ol>
    <li><b>Die Lizenz wirkt wie ein Zeitfilter.</b> Nur Einträge, die ab
      2025 registriert oder zuletzt aktualisiert wurden, stehen unter
      CC BY 4.0. Abgeschlossene Forschung fehlt am stärksten.</li>
    <li><b>Nur registrierte Forschung.</b> Kleine, qualitative und nicht
      geförderte Versorgungsforschung wird oft gar nicht registriert.</li>
    <li><b>Nur ein Register.</b> Multizentrische Studien stehen häufig bei
      ClinicalTrials.gov, nicht im DRKS.</li>
    <li><b>Ganze Einrichtungstypen fehlen.</b> Institute, die
      Sekundärdaten auswerten und evaluieren, registrieren keine
      klinischen Studien. Sie können im Register nie auftauchen, egal wie
      viel sie forschen. <a href="mvf.html#fehlen">Was das konkret
      heißt</a>.</li>
  </ol>
  <p><b>Deshalb unsere Bitte:</b> Tragen Sie ein, was hier fehlt. Ihre
    Studien, Ihr Publikationsverzeichnis, Ihre Arbeitsgruppe, Ihre
    Stellenangebote. Jede Einrichtung behält, was sie einträgt, und
    erkennbar getrennt von den Registerdaten.</p>
  <a class="mehr" href="institutionen.html#mitmachen">Eintragen oder
    ändern</a>
</div>''' % (zahl(L.get("vf_im_register", 0)), zahl(len(studien)),
             zahl(L.get("vf_nicht_zeigbar", 0))))

    hubs = len([e for e in (HS.get("eintraege") or [])])
    aus.append('''
<div class="hinweiskasten">
  <h2>Was die Suche oben durchsucht</h2>
  <p>Ein Feld über sechs Bestände: <b>%s Einträge</b>. Forschende,
    Institutionen, Studien, MVF-Beiträge, Förderer und die <b>%s
    Studien der 15 Knowledge-Hubs</b>, jede mit deutschem Titel.</p>
  <p>Die Hub-Studien laden im Hintergrund nach, weil sie für sich schon
    so groß sind wie alles übrige zusammen. Tippen können Sie sofort,
    die Hub-Treffer erscheinen, sobald sie da sind.</p>
  <p><b>Nicht enthalten:</b> Stellenanzeigen, für die es keine offene
    Quelle gibt, und %s Studien, deren Lizenz uns die Wiedergabe
    verbietet. Beides sagen wir hier, statt es zu verschweigen.</p>
</div>''' % (zahl(len((S.get("eintraege") or [])) + hubs), zahl(hubs),
             zahl(L.get("vf_nicht_zeigbar", 0))))

    if AB.get("zaehlung"):
        aus.append('<p class="unter">Stand der Auswertung: %s. '
                   'Quelle der Studien: Deutsches Register Klinischer '
                   'Studien (DRKS), BfArM, unter CC BY 4.0.</p>'
                   % esc(L.get("stand", "")))
    return "\n".join(aus)


def inhalt_institutionen():
    """Alle 2.430 Einrichtungen, nach Tr\u00e4gerart getrennt.

    ⚠ ALLE ZEILEN STEHEN IN DER SEITE. teile/liste.js kappt auf 40 je
    Abschnitt und bietet je Abschnitt den Knopf „Alle N zeigen". Vorher
    kappte der Bau selbst, und die 1.990 \u00fcbrigen H\u00e4user waren
    \u00fcberhaupt nicht in der Seite.
    """
    E = lade("einrichtungen.json") or {}
    aus = []
    aus.append('''
<div class="hinweiskasten">
  <h2>Warum hier mehr steht als die 63 Standorte</h2>
  <p>Die Forschungsstandorte mit eigener Profilseite sind zu 51 von 63
    Hochschulen. Das ist kein Filter von uns, sondern das Register selbst:
    Von seinen Einrichtungen sind die große Mehrheit Hochschule oder
    Universitätsmedizin.</p>
  <p>Diese Seite führt darum <b>zwei Quellen zusammen</b>: das
    Studienregister und das Partnernetz des Innovationsfonds. Jede
    Einrichtung nennt, aus welcher Quelle sie bekannt ist. Eine
    Einrichtung mit null Studien und 27 Projekten forscht nicht weniger,
    sie forscht anders.</p>
  <p>Ganz unten stehen die Häuser, die in <b>keiner</b> der beiden Quellen
    vorkommen und trotzdem nachweislich forschen.</p>
</div>

<div class="hinweiskasten">
  <h2>Wie diese Liste sortiert ist</h2>
  <p>Voreingestellt <b>nach Studien und Innofonds-Projekten zusammen,
    absteigend</b>. Das stand hier lange nicht, und eine Rangliste, die
    ihre Regel nicht nennt, ist eine Behauptung. Sie können oben auf
    <b>Name A bis Z</b> umstellen, nach Trägerart und Quelle filtern und
    nach Name oder Ort suchen.</p>
  <p><b>%s von %s Einrichtungen haben hier keine eigene Profilseite.</b>
    Profilseiten baut das Register nur, wo genug registrierte Studien
    zusammenkommen. Jede Zeile ohne Seite sagt das und führt zum
    Formular.</p>
</div>''' % (zahl(E.get("gesamt", 0)
                      - sum(1 for a in E.get("abschnitte", [])
                            for e in a["einrichtungen"] if e.get("datei"))),
             zahl(E.get("gesamt", 0))))

    arten = [(sprungmarke(a["art"]), a["titel"], a["anzahl"])
             for a in E.get("abschnitte", []) if a["anzahl"]]
    aus.append('<div class="listenraum">')
    aus.append(steuerleiste([
        ("sort", "Sortierung", [
            ("summe", "Studien und Projekte zusammen"),
            ("studien", "Studien im Register"),
            ("projekte", "Innofonds-Projekte"),
            ("name", "Name A bis Z"),
        ]),
        ("art", "Tr\u00e4gerart",
         [("", "alle %s" % zahl(E.get("gesamt", 0)))]
         + [(s, "%s (%s)" % (ti, zahl(n))) for s, ti, n in arten]),
        ("quelle", "Quelle", [
            ("", "beide Quellen"),
            ("register", "im Studienregister"),
            ("innofonds", "im Innofonds-Partnernetz"),
            ("nur-innofonds", "nur im Partnernetz"),
            ("rekrutiert", "rekrutiert gerade"),
            ("profil-ja", "mit eigener Profilseite"),
            ("profil-nein", "ohne Profilseite"),
        ]),
    ], "Name oder Ort, etwa Bremen"))

    gesehen = {}
    for a in E.get("abschnitte", []):
        if not a["anzahl"]:
            continue
        art = sprungmarke(a["art"])
        aus.append('<section class="traeger" id="art-%s" data-teil '
                   'data-grenze="40">' % esc(art))
        aus.append("<h2>%s <span style=\"color:var(--ink-faint);"
                   "font-weight:400\">%s</span></h2>"
                   % (esc(a["titel"]), zahl(a["anzahl"])))
        aus.append('<p class="was">%s</p>' % esc(a["was"]))
        if a["nur_innofonds"]:
            aus.append('<p class="was"><b>%s davon</b> kennt nur das '
                       'Partnernetz des Innovationsfonds, nicht das '
                       'Studienregister.</p>' % zahl(a["nur_innofonds"]))
        aus.append('<div class="haeuser">')
        for e in a["einrichtungen"]:
            aus.append(haus_zeile(e, art, gesehen))
        aus.append("</div>")
        # Ohne JavaScript steht hier die Wahrheit: alle sind da.
        aus.append('<p class="teil-stand">Alle %s stehen in dieser Liste.'
                   '</p>' % zahl(a["anzahl"]))
        aus.append("</section>")
    aus.append("</div>")

    f = E.get("fehlen_im_register") or {}
    liste = f.get("liste", [])
    aus.append('<section class="traeger fremd" id="fehlen">')
    aus.append("<h2>Einrichtungen, die hier fehlen m\u00fcssen</h2>")
    aus.append('<p class="was">Diese H\u00e4user forschen nachweislich, '
               'stehen aber in keiner der beiden Quellen dieser Seite. Der '
               'Nachweis kommt aus unseren eigenen Heften: Ihre '
               'Autor:innen nennen diese Einrichtungen in der Autorenbox. '
               'Gepr\u00fcft an %s Beitr\u00e4gen.</p>'
               % zahl(f.get("geprueft_beitraege", 0)))
    aus.append('<p class="was">Der Grund ist strukturell. Wer '
               'Sekund\u00e4rdaten auswertet, Versorgungsmodelle '
               'evaluiert oder Routinedaten analysiert, f\u00fchrt keine '
               'klinische Studie und registriert darum nichts. <b>Diese '
               'Einrichtungen k\u00f6nnen von allein nie '
               'auftauchen.</b></p>')
    aus.append('<div class="haeuser">')
    for e in liste[:24]:
        name = esc(e["haus"]) if e.get("haus") else \
            ('<span style="color:var(--ink-faint)">%s</span>'
             % esc(e["bereich"]))
        hinweis = "" if e.get("haus") else \
            ' <span class="wo">Name nicht hinterlegt, nur die ' \
            'Mailadresse</span>'
        aus.append('<div class="haus"><div>%s%s</div>'
                   '<div class="wo">%s</div>'
                   '<div class="zahlen"><b>%s</b> MVF-Beitr\u00e4ge</div>'
                   '%s</div>'
                   % (name, hinweis,
                      esc(", ".join(e.get("bereiche", [e["bereich"]]))),
                      zahl(e["beitraege"]),
                      eintragsziel("einrichtung",
                                   e.get("haus") or e["bereich"],
                                   "Noch in keiner Quelle.")))
    aus.append("</div>")
    if len(liste) > 24:
        aus.append('<p class="was">Insgesamt %s H\u00e4user. Gezeigt sind '
                   'die 24 mit den meisten Beitr\u00e4gen.</p>'
                   % zahl(len(liste)))
    aus.append('<a class="mehr" href="eintragen.html?art=einrichtung">Ihre '
               'Einrichtung eintragen</a>')
    aus.append("</section>")

    aus.append('''
<div class="hinweiskasten" id="mitmachen">
  <h2>Ihre Einrichtung eintragen oder ändern</h2>
  <p>Sie können für Ihre Einrichtung hinterlegen, was das Register nicht
    hergibt: Ihr Publikationsverzeichnis, Ihre Studien, Ihre
    Studiengänge, Ihre Arbeitsgruppe und Professuren, Ihre
    Stellenangebote, Ihre Veranstaltungen.</p>
  <p>Bei den Stellenangeboten ist das der <b>einzige</b> Weg: Dazu gibt es
    keine offene Quelle, die wir auswerten könnten.</p>
  <a class="mehr" href="eintragen.html?art=einrichtung">Zum Formular</a>
</div>''')
    return "\n".join(aus)


def inhalt_rekrutierend():
    L = lade("landkarte.json") or {}
    rek = [x for x in L.get("studien", [])
           if x.get("status") == "RECRUITING"]
    rek.sort(key=lambda x: (x.get("registriert") or ""), reverse=True)
    mit_ort = [x for x in rek if x.get("orte")]
    aus = ['''
<div class="hinweiskasten">
  <h2>Warum das eine eigene Seite ist</h2>
  <p><b>%s Studien suchen gerade Teilnehmende</b>, %s davon mit Ortsangabe.
    Das ist die einzige Angabe auf diesem Portal, zu der ein Mensch heute
    etwas tun kann, und sie verfällt. Unter %s anderen Einträgen sieht sie
    niemand.</p>
  <p><b>Wichtig:</b> Wir vermitteln nicht und beraten nicht. Jeder Eintrag
    führt zum Originaleintrag im Register, dort stehen die Bedingungen und
    die Ansprechstelle.</p>
</div>''' % (zahl(len(rek)), zahl(len(mit_ort)), zahl(len(L.get("studien", []))))]
    aus.append('<div class="haeuser" id="liste">')
    for x in rek[:60]:
        ort = ", ".join(sorted({o.get("ort", "") for o in (x.get("orte") or [])
                                if o.get("ort")}))
        titel = x.get("akronym") or kurz(x.get("titel"))
        aus.append('<div class="haus">'
                   '<div><a href="https://drks.de/search/de/trial/%s" '
                   'target="_blank" rel="noopener">%s</a></div>'
                   '<div class="wo">%s</div>'
                   '<div class="zahlen">%s<br>%s</div></div>'
                   % (esc(x.get("id")), esc(titel),
                      esc(ort or "Ort nicht angegeben"),
                      esc(x.get("id")),
                      "ab %s" % esc((x.get("registriert") or "")[:7])))
    aus.append("</div>")
    if len(rek) > 60:
        aus.append('<p class="unter">Gezeigt sind die 60 zuletzt '
                   'registrierten von %s. Die übrigen finden Sie über die '
                   'Suche oben oder auf der <a href="studien.html">'
                   'Studienseite</a> mit Filter.</p>' % zahl(len(rek)))
    return "\n".join(aus)


def inhalt_forschende():
    """Alle 5.395 Personen in EINER Liste, jede mit Sprungmarke.

    ⚠ ES GIBT KEINE EIGENEN PROFILSEITEN, und das ist Absicht. Eine
    Profilseite zu einer Person, die davon nichts weiss, ist etwas
    anderes als ein Eintrag, den sie selbst gefuellt hat. Wer bei MVF ein
    Profil hat, wird dorthin verlinkt. Wer keines hat, findet in seiner
    Zeile den Weg zum Formular.

    ⚠ VORHER WAREN ES DREI RANGLISTEN mit je 30 Zeilen, und dieselben
    Menschen standen in zweien davon. 5.305 Personen waren in der Seite
    gar nicht vorhanden, und die Personenlinks der Suche fuehrten
    deswegen ins Leere.
    """
    P = (lade("personen.json") or {}).get("personen", {})
    Z = (lade("personen.json") or {}).get("zaehlung", {})
    ZU = (lade("suchindex.json") or {}).get("zuordnung", {})
    leute = list(P.values())

    mit_studien = [p for p in leute if p.get("studien")]
    mit_mvf = [p for p in leute if p.get("mvf")]
    mit_dkvf = [p for p in leute if p.get("dkvf")]
    beides = [p for p in leute if p.get("studien") and p.get("mvf")]
    mit_orcid = [p for p in leute if p.get("orcid")]
    mit_haus = [p for p in leute if p.get("einrichtung")]
    mit_profil = [p for p in leute if p.get("profil")]
    ohne_beleg = [p for p in leute if not (p.get("studien") or p.get("mvf")
                                          or p.get("dkvf"))]

    aus = ['''
<div class="hinweiskasten">
  <h2>Woher diese Namen kommen</h2>
  <p><b>%s Personen</b>, zusammengeführt über Nachname und <b>ganzen</b>
    Vornamen. Bloße Initialen haben wir verworfen: Mit ihnen fällt
    „Schmidt, A.“ mit jeder anderen Schmidt zusammen.</p>
  <ul>
    <li><b>%s</b> haben ein Autorenprofil bei „Monitor
      Versorgungsforschung“.</li>
    <li><b>%s</b> stehen als Autor:in auf der Ergebnispublikation einer
      Studie aus dem Register.</li>
    <li><b>%s</b> haben ein Abstract beim Deutschen Kongress für
      Versorgungsforschung eingereicht.</li>
    <li><b>%s</b> tragen eine ORCID, also eine eindeutige Kennung über
      alle Datenbanken hinweg.</li>
  </ul>
  <p><b>%s Personen sind in beiden Welten</b>, sie führen Studien
    <em>und</em> publizieren bei MVF.</p>
</div>

<div class="hinweiskasten">
  <h2>Warum %s Autorenprofile hier keinen Beitrag zeigen</h2>
  <p>Zwei Zahlen auf dieser Seite passen scheinbar nicht zusammen: <b>%s
    Personen haben ein Autorenprofil</b>, aber nur <b>%s</b> tragen hier
    einen MVF-Beitrag. Der Grund ist unsere eigene Regel, und wir nennen
    ihn, statt die Lücke stehen zu lassen.</p>
  <ul>
    <li><b>%s Beiträge</b> nennen Autor:innen, mit zusammen <b>%s
      Nennungen</b>.</li>
    <li><b>%s Nennungen</b> konnten wir einer Person zuordnen.</li>
    <li><b>%s Nennungen</b> führen nur eine Initiale als Vornamen und
      bleiben offen, etwa „M. Klein“. Hier kennen wir mehrere Menschen
      dieses Namens, und wir raten nicht: „Schmidt, A.“ würde sonst mit
      jeder anderen Schmidt zusammenfallen.</li>
    <li>Bei <b>%s</b> Nennungen fehlt der Vorname ganz, meist weil im
      Heft „et al.“ steht und der Nachname mehrfach vorkommt.</li>
  </ul>
  <p>Steht eine Initiale dagegen für <b>genau eine</b> Person, die wir
    kennen, lösen wir sie auf: „P. Stegmaier“ ist in dieser Zeitschrift
    eindeutig. Das ist keine Aufweichung der Regel, sondern ihre
    Anwendung auf einen geschlossenen Autorenkreis.</p>
  <p>Die Zuordnung gelingt damit bei <b>%d von 100 Nennungen</b>. Was
    fehlt, fehlt nicht in der Zeitschrift, sondern in der Verknüpfung
    zwischen Beitrag und Person. <b>Fehlt bei Ihnen etwas?</b>
    <a href="eintragen.html?art=person">Hier zuordnen oder abweisen</a>.</p>
</div>

<div class="hinweiskasten">
  <h2>Wie diese Liste sortiert ist, und wie Sie sie umstellen</h2>
  <p>Voreingestellt <b>nach der Zahl der Belege, absteigend</b>:
    Studienpublikationen, MVF-Beiträge und DKVF-Abstracts zusammen. Oben
    stellen Sie auf <b>Name A bis Z</b> um oder sortieren nach einer
    einzelnen Spalte.</p>
  <p>Vorher standen hier drei Ranglisten mit je 30 Namen, und dieselben
    Menschen standen in mehreren. Jetzt ist es <b>eine Liste mit allen
    %s</b>. Die drei alten Überschriften sind Knöpfe geworden:</p>
  <p>
    <a class="mehr" href="#liste" data-stellt=\'{"merkmal":"beides","sort":"summe"}\'>In beiden Welten (%s)</a><br>
    <a class="mehr" href="#liste" data-stellt=\'{"merkmal":"studien","sort":"studien"}\'>Die meisten Studienpublikationen (%s)</a><br>
    <a class="mehr" href="#liste" data-stellt=\'{"merkmal":"mvf","sort":"mvf"}\'>Die meisten MVF-Beiträge (%s)</a><br>
    <a class="mehr" href="#liste" data-stellt=\'{"merkmal":"orcid","sort":"name"}\'>Mit ORCID (%s)</a>
  </p>
  <p><b>Steht in einer Zeile keine Einrichtung, haben wir keine sicher
    erkannt.</b> Das heißt nie, dass die Person keine hat. Bei %s von %s
    gelang der Schnitt aus dem Vorstellungstext.</p>
  <p><b>%s Personen haben kein Profil bei MVF</b>, bei ihnen führt kein
    Link vom Namen weg. Das ist Absicht: Eine Profilseite zu einem
    Menschen, der davon nichts weiß, ist etwas anderes als ein Eintrag,
    den er selbst gefüllt hat. Jede solche Zeile führt zum Formular.</p>
</div>

<div class="hinweiskasten">
  <h2>Steht bei Ihnen die falsche Einrichtung? Oder gar keine?</h2>
  <p>Bei <b>%s von %s</b> Personen steht ein Haus. <b>Steht bei Ihnen
    keines, heißt das nicht, dass Sie keines haben</b>, sondern dass wir
    es aus Ihrem Vorstellungstext nicht sicher herauslesen konnten.</p>
  <p>Wir nehmen immer nur das <b>zuerst genannte</b> Haus, und wir zeigen
    lieber gar nichts, wenn der Text selbst sagt, dass er von früher
    spricht. Eine Lücke ist uns lieber als ein alter Arbeitgeber unter
    Ihrem Namen.</p>
  <p><b>Sie können das in einer Minute richtigstellen</b>, und was Sie
    schicken, ersetzt unsere Lesung.
    <a href="eintragen.html?art=person">Eintrag ändern oder ergänzen</a>.
    Dort lassen sich auch Ihre Studien, Beiträge und Repositorien
    zuordnen oder abweisen.</p>
</div>''' % (zahl(len(leute)), zahl(len(mit_profil)),
             zahl(len(mit_studien)), zahl(len(mit_dkvf)),
             zahl(len(mit_orcid)), zahl(len(beides)),
             # Der Kasten zur Zuordnungsquote.
             zahl(len(mit_profil) - sum(1 for p in mit_profil
                                        if p.get("mvf"))),
             zahl(len(mit_profil)), zahl(len(mit_mvf)),
             zahl(ZU.get("beitraege", 0)), zahl(ZU.get("nennungen", 0)),
             zahl(ZU.get("zugeordnet", 0)), zahl(ZU.get("nur_initiale", 0)),
             zahl(ZU.get("ohne_vornamen", 0)),
             round(100 * ZU.get("zugeordnet", 0)
                   / max(1, ZU.get("nennungen", 0))),
             zahl(len(leute)), zahl(len(beides)), zahl(len(mit_studien)),
             zahl(len(mit_mvf)), zahl(len(mit_orcid)),
             zahl(len(mit_haus)), zahl(len(leute)),
             zahl(len(leute) - len(mit_profil)),
             zahl(len(mit_haus)), zahl(len(leute)))]

    def zeile(k, p):
        name = esc(p.get("name") or "")
        ziel = ""
        if p.get("profil"):
            name = '<a href="%s" target="_blank" rel="noopener">%s</a>' \
                % (esc(p["profil"]), name)
        else:
            ziel = eintragsziel("person", p.get("name") or "",
                                "Kein MVF-Profil.")
        haus = p.get("einrichtung") or ""
        # ⚠ KEINE ZEILE, WENN NICHTS DASTEHT. 3.734 mal denselben Satz zu
        # wiederholen kostete 355 KB. Was eine fehlende Zeile bedeutet,
        # steht im Kasten ueber der Liste.
        wo = ""
        if p.get("standort_datei"):
            wo = '<div class="wo"><a href="standort/%s">%s</a></div>' \
                % (esc(p["standort_datei"]), esc(p.get("standort") or haus))
        elif haus:
            wo = '<div class="wo">%s</div>' % esc(haus)
        z = []
        if p.get("studien"):
            z.append("<b>%s</b> Studienpublikationen" % zahl(p["studien"]))
        if p.get("mvf"):
            z.append("<b>%s</b> MVF-Beitr\u00e4ge" % zahl(p["mvf"]))
        if p.get("dkvf"):
            z.append("%s DKVF-Abstracts" % zahl(p["dkvf"]))
        marke = ""
        if p.get("orcid"):
            marke = ('<span class="marke" title="ORCID %s">ORCID</span>'
                     % esc(p["orcid"]))

        m = []
        if p.get("studien"):
            m.append("studien")
        if p.get("mvf"):
            m.append("mvf")
        if p.get("dkvf"):
            m.append("dkvf")
        if p.get("studien") and p.get("mvf"):
            m.append("beides")
        if p.get("orcid"):
            m.append("orcid")
        m.append("profil" if p.get("profil") else "ohne-profil")
        if haus:
            m.append("haus")
        if not (p.get("studien") or p.get("mvf") or p.get("dkvf")):
            m.append("ohne-beleg")

        return ('<div class="haus" id="%s" data-n="%s" data-studien="%d" '
                'data-mvf="%d" data-dkvf="%d" data-summe="%d" '
                'data-merkmal="%s" data-such="%s">'
                '<div>%s%s</div>%s'
                '<div class="zahlen">%s</div>%s</div>'
                % (esc(p.get("anker") or ""),
                   esc(sortname(k.replace(", ", " "))),
                   p.get("studien") or 0, p.get("mvf") or 0,
                   p.get("dkvf") or 0,
                   (p.get("studien") or 0) + (p.get("mvf") or 0)
                   + (p.get("dkvf") or 0),
                   esc(" ".join(m)),
                   esc(vergleichbar("%s %s %s"
                                    % (p.get("name") or "", haus,
                                       p.get("standort") or ""))),
                   name, marke, wo,
                   gestapelt(z, "ohne Beleg im Register"), ziel))

    aus.append('<div class="listenraum">')
    aus.append(steuerleiste([
        ("sort", "Sortierung", [
            ("summe", "Belege zusammen"),
            ("studien", "Studienpublikationen"),
            ("mvf", "MVF-Beitr\u00e4ge"),
            ("dkvf", "DKVF-Abstracts"),
            ("name", "Name A bis Z"),
        ]),
        ("merkmal", "Beleg",
         [("", "alle %s" % zahl(len(leute))),
          ("beides", "in beiden Welten (%s)" % zahl(len(beides))),
          ("studien", "mit Studienpublikation (%s)" % zahl(len(mit_studien))),
          ("mvf", "mit MVF-Beitrag (%s)" % zahl(len(mit_mvf))),
          ("dkvf", "mit DKVF-Abstract (%s)" % zahl(len(mit_dkvf))),
          ("orcid", "mit ORCID (%s)" % zahl(len(mit_orcid))),
          ("haus", "mit erkannter Einrichtung (%s)" % zahl(len(mit_haus))),
          ("profil", "mit MVF-Profil (%s)" % zahl(len(mit_profil))),
          ("ohne-profil", "ohne MVF-Profil (%s)"
           % zahl(len(leute) - len(mit_profil))),
          ("ohne-beleg", "ohne Beleg in unseren Quellen (%s)"
           % zahl(len(ohne_beleg)))]),
    ], "Name oder Einrichtung, etwa Sundmacher"))

    aus.append('<section class="traeger" id="liste" data-teil '
               'data-grenze="50">')
    aus.append("<h2>Alle %s Forschenden</h2>" % zahl(len(leute)))
    aus.append('<div class="haeuser">')
    # ⚠ NACH DEM SCHLUESSEL SORTIEREN, nicht nach nachname und vorname.
    # Der Schluessel ist „nachname, vorname" aus personenschluessel(),
    # gebaut aus der Quelle. Die beiden Felder sind abgeleitet, und bis
    # zum 01.11.2026 waren sie bei 4.056 Personen vertauscht.
    for k, p in sorted(P.items(), key=lambda kp: (
            -((kp[1].get("studien") or 0) + (kp[1].get("mvf") or 0)
              + (kp[1].get("dkvf") or 0)),
            sortname(kp[0].replace(", ", " ")))):
        aus.append(zeile(k, p))
    aus.append("</div>")
    aus.append('<p class="teil-stand">Alle %s stehen in dieser Liste.</p>'
               % zahl(len(leute)))
    aus.append("</section>")
    aus.append("</div>")

    aus.append('''
<div class="hinweiskasten" id="mitmachen">
  <h2>Ihr Eintrag stimmt nicht?</h2>
  <p>Drei Gründe sind häufig. Eine Datenbank führt Sie unter einer
    anderen Schreibweise. Zwei Personen gleichen Namens sind
    zusammengefallen. Oder Ihr Vorstellungstext nennt die Einrichtung in
    einer Form, die wir nicht sicher schneiden konnten.</p>
  <p>Haben Sie ein Profil bei „Monitor Versorgungsforschung“, pflegen Sie
    Vorstellungstext und Porträt direkt dort. Was Sie dort ändern,
    erscheint beim nächsten Durchlauf auch hier. Für alles andere, und
    für die %s Menschen ohne Profil, gibt es das Formular.</p>
  <p>Fehlt Ihre Arbeit ganz, liegt es meist daran, dass Ihre Studien
    nicht registriert sind oder unter einer Lizenz stehen, die uns die
    Anzeige verbietet. <a href="index.html#was-fehlt">Was wir nicht
    zeigen dürfen</a>.</p>
  <a class="mehr" href="eintragen.html?art=person">Eigenen Eintrag
    pflegen</a>
</div>''' % zahl(len(leute) - len(mit_profil)))
    return "\n".join(aus)


def inhalt_eintragen():
    """Selbstauskunft fuer Einrichtungen und fuer Personen.

    ⚠ DIE SEITE IST DAS ZIEL JEDER ZEILE OHNE EIGENES ZIEL. Darum nimmt
    sie den Namen aus der Adresszeile (?art=…&name=…) und setzt ihn ins
    Formular. Siehe teile/eintragen.js.
    """
    E = lade("einrichtungen.json") or {}
    P = (lade("personen.json") or {}).get("personen", {})
    mit_profil = E.get("mit_profil") or sum(
        1 for a in E.get("abschnitte", []) for e in a["einrichtungen"]
        if e.get("datei"))
    ohne_profil = E.get("gesamt", 0) - mit_profil
    mit_mvf = sum(1 for p in P.values() if p.get("profil"))
    ohne_mvf = len(P) - mit_mvf

    formular = (TEILE / "_formular-einrichtung.html").read_text(
        encoding="utf-8")
    # Ein Namensfeld, das die Standortseiten nicht brauchen: Dort steht der
    # Name schon in der Ueberschrift. Hier kommt er aus der Adresszeile.
    NAMENSFELD = """
        <label><b>Name der Einrichtung</b>
          <input type="text" name="einrichtung" id="einrichtung-name"
                 placeholder="Institut für …, Universität …"></label>"""
    marke = '<form id="form" novalidate>'
    if marke not in formular:
        raise SystemExit("formular-einrichtung.html: <form> nicht gefunden")
    formular = formular.replace(marke, marke + NAMENSFELD, 1)

    aus = ['''
<div class="hinweiskasten" hidden>
  <h2>Ihr Eintrag</h2>
  <p>Sie kommen von einer Zeile, zu der wir keine Seite haben:
    <b id="gemeint"></b>. Der Name steht unten schon im Formular.</p>
</div>

<div class="hinweiskasten">
  <h2>Warum es diese Seite gibt</h2>
  <p>Dieses Portal zeigt, was in offenen Quellen steht: im Studienregister,
    im Partnernetz des Innovationsfonds, in unseren eigenen Heften. Das ist
    nicht Ihr Fach, das ist der Teil Ihres Fachs, der registriert wird.</p>
  <ul>
    <li><b>%s von %s Einrichtungen</b> haben hier keine eigene Profilseite.</li>
    <li><b>%s von %s Forschenden</b> haben kein Profil bei
      „Monitor Versorgungsforschung“.</li>
    <li>Bei <b>Stellenangeboten</b> ist die Selbstauskunft der einzige Weg
      überhaupt. Dazu gibt es keine offene Quelle, die wir auswerten
      könnten.</li>
  </ul>
  <p>Wir werten nichts und bewerten nichts. Was Sie eintragen, steht als
    Ihre Angabe neben den Registerdaten, erkennbar getrennt.</p>
</div>

<div class="kacheln">
  <a class="kachel" href="#teil-einrichtung" data-oeffnet="teil-einrichtung">
    <div class="frage">Ich spreche für ein Haus</div>
    <h2>Einrichtung eintragen</h2>
    <p>Institut, Klinik, Hochschule, Kostenträger, Unternehmen. Mit
      Publikationsverzeichnis, Studiengängen, Professuren, Stellen und
      Veranstaltungen.</p>
  </a>
  <a class="kachel" href="#teil-person" data-oeffnet="teil-person">
    <div class="frage">Ich trage für mich ein</div>
    <h2>Eigenen Eintrag pflegen</h2>
    <p>Schreibweise, ORCID, Einrichtung, Arbeitsgebiet. Auch dann, wenn
      Sie bei uns nie publiziert haben.</p>
  </a>
</div>

<div class="box selbst">
  <details id="teil-einrichtung">
    <summary><b>Einrichtung eintragen oder ändern</b></summary>
    <p class="was">Wir schicken einen persönlichen Link an Ihre dienstliche
      Adresse. Lässt sich die Domain der Einrichtung zuordnen, geht er
      sofort heraus, sonst prüfen wir von Hand. Mit dem Link ändern Sie
      Ihre Angaben später jederzeit.</p>
%s
  </details>
</div>

<div class="box selbst">
  <details id="teil-person">
    <summary><b>Eigenen Eintrag pflegen</b></summary>
    <p class="was"><b>Haben Sie ein Profil bei „Monitor
      Versorgungsforschung“?</b> Dann pflegen Sie Vorstellungstext und
      Porträt bitte dort. Was Sie dort ändern, erscheint beim nächsten
      Durchlauf auch hier. Dieses Formular ist für alles, was dort nicht
      hingehört, und für die %s Menschen, die dort kein Profil haben.</p>
    <form id="form-person" novalidate>
      <label><b>Ihre dienstliche E-Mail-Adresse</b>
        <input name="email" type="email" required
               placeholder="name@einrichtung.de"></label>
      <p class="hinweis">Wir schicken einen persönlichen Link an diese
        Adresse. Ohne eine Adresse, die sich einer Einrichtung zuordnen
        lässt, können wir einen Eintrag über eine Person nicht
        annehmen.</p>

      <label><b>Ihr Name, so wie er geführt werden soll</b>
        <input type="text" name="name" id="person-name"
               placeholder="Prof. Dr. med. Anna Musterfrau"></label>
      <p class="hinweis">Wir führen Personen über Nachname und
        <b>ganzen</b> Vornamen zusammen. Bloße Initialen haben wir
        verworfen: Mit ihnen fällt „Schmidt, A.“ mit jeder anderen
        Schmidt zusammen.</p>

      <label><b>ORCID</b>
        <input type="text" name="orcid"
               placeholder="0000-0002-1825-0097"></label>
      <p class="hinweis">Die ORCID ist die einzige Kennung, die über alle
        Datenbanken hinweg eindeutig ist. %s von %s Personen tragen bei
        uns eine.</p>

      <fieldset>
        <legend>Wo Sie arbeiten</legend>
        <label><b>Einrichtung, Abteilung, Ort</b>
          <input type="text" name="einrichtung"
                 placeholder="Institut für …, Universität …, Stadt"></label>
        <label><b>Funktion und Arbeitsgebiet</b>
          <textarea name="arbeitsgebiet"
            placeholder="Ein Satz, wie Sie ihn selbst schreiben würden. Wir schneiden Einrichtungen sonst aus dem ersten Satzteil eines Vorstellungstextes, und das geht oft schief."></textarea></label>
        <label><b>Ihre Seite im Netz</b>
          <input type="text" name="netzadresse"
                 placeholder="https://…"></label>
      </fieldset>

      <fieldset>
        <legend>Was fehlt oder falsch ist</legend>
        <label><b>Stimmt Ihr Eintrag nicht?</b></label>
        <div class="ja-nein">
          <label><input type="radio" name="fehler" value="schreibweise">
            andere Schreibweise</label>
          <label><input type="radio" name="fehler" value="zusammenfall">
            zwei Personen zusammengefallen</label>
          <label><input type="radio" name="fehler" value="haus">
            falsche Einrichtung</label>
          <label><input type="radio" name="fehler" value="nichts" checked>
            nichts davon</label>
        </div>
        <label><input type="text" name="fehler_text"
               placeholder="Wenn ja: Was genau steht falsch?"></label>

        <label><b>Arbeiten, die hier fehlen</b>
          <textarea name="publikationen"
            placeholder="Eine je Zeile, gern mit DOI. Auch Beiträge, die nicht bei MVF erschienen sind."></textarea></label>

        <label><b>Studien, die hier fehlen</b>
          <textarea name="studien"
            placeholder="Eine je Zeile, mit DRKS- oder NCT-Nummer, wenn registriert. Ohne Registrierung: Titel, Zeitraum, Förderung."></textarea></label>
      </fieldset>

      <fieldset>
        <legend>Ansprechbar</legend>
        <label><b>Für Kooperationen und Anfragen ansprechbar?</b></label>
        <div class="ja-nein">
          <label><input type="radio" name="ansprechbar" value="ja"> ja</label>
          <label><input type="radio" name="ansprechbar" value="nein" checked>
            keine Angabe</label>
        </div>
      </fieldset>

      <label><b>Was sonst fehlt oder falsch ist</b>
        <textarea name="sonstiges"></textarea></label>

      <button type="submit">Absenden</button>
      <p class="stand" aria-live="polite"></p>
      <p class="hinweis">Mit dem Absenden stimmen Sie zu, dass wir Ihre
        Angaben zur Pflege dieses Eintrags verarbeiten.
        <a href="https://knowledge-hubs.m-vf.de/datenschutz.html"
           target="_blank" rel="noopener">Datenschutz</a></p>
    </form>
  </details>
</div>

<div class="hinweiskasten">
  <h2>Was wir nicht annehmen</h2>
  <p>Einträge über Dritte. Wer eine Kollegin eintragen will, bittet sie
    besser selbst darum. Und Angaben ohne dienstliche Adresse, weil wir
    sonst nicht prüfen können, wer spricht.</p>
  <p>Löschung Ihres Eintrags: Schreiben Sie an
    <a href="mailto:info@m-vf.de">info@m-vf.de</a>. Was aus dem
    Studienregister stammt, können wir nicht löschen, das steht dort unter
    CC BY 4.0 und ist nicht unsere Angabe.</p>
</div>''' % (zahl(ohne_profil), zahl(E.get("gesamt", 0)),
             zahl(ohne_mvf), zahl(len(P)), formular, zahl(ohne_mvf),
             zahl(sum(1 for p in P.values() if p.get("orcid"))),
             zahl(len(P)))]
    return "\n".join(aus)


def inhalt_studien():
    """Alle Studien, neueste zuerst, mit Filtern im Browser."""
    L = lade("landkarte.json") or {}
    studien = sorted(L.get("studien", []),
                     key=lambda x: (x.get("registriert") or ""), reverse=True)
    F = lade("foerderer.json") or {}
    import collections as _c
    jahre = _c.Counter((x.get("registriert") or "")[:4] for x in studien)
    arten = _c.Counter(x.get("status_de") or "ohne Angabe" for x in studien)

    aus = ['''
<div class="hinweiskasten">
  <h2>%s Studien, die neuesten zuerst</h2>
  <p>Jede Studie führt auf ihren Originaleintrag im Deutschen Register
    Klinischer Studien. Dort stehen die Einzelheiten, die Bedingungen und
    die Ansprechstelle.</p>
  <p>Das Register hält %s Studien mit Versorgungsbezug. <b>%s davon dürfen
    wir nicht wiedergeben</b>, weil ihre Lizenz es nicht zulässt.
    <a href="index.html#was-fehlt">Warum</a>.</p>
</div>''' % (zahl(len(studien)), zahl(L.get("vf_im_register", 0)),
             zahl(L.get("vf_nicht_zeigbar", 0)))]

    aus.append('<section class="traeger"><h2>Nach Status</h2>'
               '<div class="haeuser">')
    for st, n in arten.most_common():
        marke = ' <span class="marke">jetzt offen</span>' \
            if st == "rekrutiert" else ""
        ziel = "rekrutierend.html" if st == "rekrutiert" else "#liste"
        aus.append('<div class="haus"><div><a href="%s">%s</a>%s</div>'
                   '<div class="wo"></div>'
                   '<div class="zahlen"><b>%s</b> Studien</div></div>'
                   % (ziel, esc(st), marke, zahl(n)))
    aus.append("</div></section>")

    aus.append('<section class="traeger"><h2>Nach Jahr der Registrierung</h2>'
               '<p class="was">Die Lizenz wirkt wie ein Zeitfilter, darum '
               'sind die jüngeren Jahrgänge vollständiger.</p>'
               '<div class="haeuser">')
    for j in sorted(jahre, reverse=True)[:12]:
        if not j:
            continue
        aus.append('<div class="haus"><div>%s</div><div class="wo"></div>'
                   '<div class="zahlen"><b>%s</b> Studien</div></div>'
                   % (esc(j), zahl(jahre[j])))
    aus.append("</div></section>")

    oben = sorted((f for f in F.get("liste", []) if isinstance(f, dict)),
                  key=lambda f: -(f.get("studien") if isinstance(
                      f.get("studien"), int) else len(f.get("studien") or [])))
    aus.append('<section class="traeger" id="geber"><h2>Wer fördert</h2>'
               '<p class="was">%s Förderer stehen im Register. Gezeigt sind '
               'die 20 mit den meisten Studien.</p><div class="haeuser">'
               % zahl(len(F.get("liste", []))))
    for f in oben[:20]:
        n = f.get("studien")
        n = n if isinstance(n, int) else len(n or [])
        aus.append('<div class="haus" id="geber-%s"><div>%s</div>'
                   '<div class="wo"></div>'
                   '<div class="zahlen"><b>%s</b> Studien</div></div>'
                   % (esc((f.get("name") or "").lower().replace(" ", "-")[:50]),
                      esc(f.get("name")), zahl(n)))
    aus.append("</div></section>")

    aus.append('<section class="traeger" id="liste">'
               '<h2>Alle Studien, neueste zuerst</h2>'
               '<p class="was">Gezeigt sind die 80 zuletzt registrierten. '
               'Die übrigen finden Sie über die Suche oben, sie durchsucht '
               'Titel, Akronym, Indikation, Ort, Sponsor und Förderung.</p>'
               '<div class="haeuser">')
    for x in studien[:80]:
        ort = ", ".join(sorted({o.get("ort", "") for o in (x.get("orte") or [])
                                if o.get("ort")}))
        titel = x.get("akronym") or kurz(x.get("titel"))
        marke = ' <span class="marke">rekrutiert</span>' \
            if x.get("status") == "RECRUITING" else ""
        aus.append('<div class="haus" id="%s">'
                   '<div><a href="https://drks.de/search/de/trial/%s" '
                   'target="_blank" rel="noopener">%s</a>%s</div>'
                   '<div class="wo">%s</div>'
                   '<div class="zahlen">%s<br>%s</div></div>'
                   % (esc(x.get("id")), esc(x.get("id")), esc(titel), marke,
                      esc(ort or "Ort nicht angegeben"),
                      esc(x.get("status_de") or ""),
                      "registriert %s" % esc((x.get("registriert") or "")[:7])))
    aus.append("</div></section>")
    return "\n".join(aus)


def inhalt_mvf():
    """Wo die Forschung auftaucht, die das Register nicht kennt."""
    E = lade("einrichtungen.json") or {}
    AB = lade("mvf_autorenbox.json") or {}
    S = lade("suchindex.json") or {}
    HS = lade("suchindex-hubs.json") or {}
    f = E.get("fehlen_im_register") or {}
    liste = f.get("liste", [])
    z = AB.get("zaehlung") or {}
    mvf_n = (S.get("zaehlung") or {}).get("mvf", 0)

    aus = ['''
<div class="hinweiskasten">
  <h2>Warum diese Seite nötig ist</h2>
  <p>Das Studienregister zeigt nicht das Fach, sondern den Teil des Fachs,
    der klinische Studien registriert. Wer Sekundärdaten auswertet,
    Versorgungsmodelle evaluiert oder Routinedaten analysiert, führt keine
    klinische Studie und taucht darum nirgends auf.</p>
  <p>Diese Seite zeigt, was dabei fehlt, und sie zeigt es mit einem Beleg
    aus unseren eigenen Heften.</p>
</div>''']

    aus.append('<section class="traeger fremd" id="fehlen">')
    aus.append("<h2>%s Häuser, die im Register fehlen</h2>" % zahl(len(liste)))
    aus.append('<p class="was">Der Beleg: Ihre Autor:innen nennen diese '
               'Einrichtung in der Autorenbox eines MVF-Beitrags. Wir haben '
               'dafür <b>%s Beiträge</b> ausgewertet und darin <b>%s '
               'Autor:innen</b> gefunden, <b>%s</b> davon mit einer '
               'Mailadresse, die das Haus benennt.</p>'
               % (zahl(z.get("gelesen", 0)), zahl(z.get("autoren", 0)),
                  zahl(z.get("mit_bereich", 0))))
    aus.append('<div class="haeuser">')
    for e in liste[:30]:
        name = esc(e["haus"]) if e.get("haus") else \
            ('<span style="color:var(--ink-faint)">%s</span>' % esc(e["bereich"]))
        aus.append('<div class="haus"><div>%s</div><div class="wo">%s</div>'
                   '<div class="zahlen"><b>%s</b> MVF-Beiträge</div></div>'
                   % (name, esc(", ".join(e.get("bereiche", [e["bereich"]]))),
                      zahl(e["beitraege"])))
    aus.append("</div>")
    aus.append('<p class="was"><b>Wie verlässlich ist das?</b> Von den '
               'Beiträgen, in denen nachweislich eine Autorenbox steht, '
               'haben wir <b>%s von %s</b> gelesen. %s Beiträge haben gar '
               'keine Box, das sind Interviews, Kommentare und '
               'Nachrichtenseiten, die im Heft nie eine hatten. Wo wir den '
               'Namen des Hauses nicht sicher kennen, steht die '
               'Mailadresse statt eines geratenen Namens.</p>'
               % (zahl(z.get("erwartbar_gefunden", 0)),
                  zahl(z.get("box_erwartbar", 0)), zahl(z.get("ohne_box", 0))))
    aus.append("</section>")

    aus.append('''
<section class="traeger">
  <h2>Die 15 Knowledge-Hubs</h2>
  <p class="was">Neben dieser Landkarte führen wir 15 thematische
    Knowledge-Hubs mit zusammen <b>%s Studien</b> aus PubMed, jede mit
    deutschem Titel und deutscher Zusammenfassung. Sie decken Themen ab,
    die ein Studienregister nicht kennt, etwa Gesundheitskompetenz, Klima
    und Gesundheit oder Künstliche Intelligenz.</p>
  <p class="was"><b>Diese Studien sind in der Suche oben enthalten.</b>
    Bis zum 01.11.2026 waren sie es nicht, und wir haben hier
    geschrieben, zu ihnen lägen nur PMID und DOI vor. Das war falsch:
    Nachgemessen tragen alle einen Titel. Die Suche lädt sie im
    Hintergrund nach, weil sie für sich so groß sind wie alles übrige
    zusammen.</p>
  <p class="was">Eine Arbeit, die in mehreren Hubs steht, erscheint
    <b>einmal</b> und nennt alle Hubs, in denen sie liegt.</p>
  <a class="mehr" href="https://knowledge-hubs.de/">Zu den Knowledge-Hubs</a>
</section>

<section class="traeger">
  <h2>Monitor Versorgungsforschung</h2>
  <p class="was">%s Fachbeiträge seit 2014, alle mit eigenem DOI, alle
    unter CC BY 4.0, alle bei Crossref und bei Zenodo hinterlegt. Die
    Suche oben durchsucht Titel, Abstract und Autor:innen.</p>
  <a class="mehr" href="https://www.monitor-versorgungsforschung.de/">Zur
    Zeitschrift</a>
</section>''' % (zahl(len((HS.get("eintraege") or []))), zahl(mvf_n)))
    return "\n".join(aus)


def inhalt_standorte():
    """Karte, Rangliste und Ortliste.

    Die Karte braucht Daten im Dokument, nicht nachgeladen: Ein
    Kachelserver saehe jede Bewegung der Lesenden. Darum wird die
    Umrisslinie von Natural Earth mitgeliefert, 6 Ringe, 561 Punkte,
    12 KB, und die Koordinaten stehen im selben Datenblock.
    """
    L = lade("landkarte.json") or {}
    SV = lade("standorte.json") or {}
    orte = SV.get("standorte", [])
    mit_profil = len(orte)
    rekrutiert = sum(o.get("rekrutiert", 0) for o in orte)
    stadt = sum(1 for o in orte if o.get("koordinate") == "stadt")

    return '''
<div class="hinweiskasten">
  <h2>Was ein Standort hier ist</h2>
  <p>Die Einrichtung, die eine Studie <b>verantwortet</b>, nicht die
    Praxis, die Teilnehmende einschließt. <b>%s Standorte</b> haben eine
    eigene Profilseite, auf der die Verantwortlichen ergänzen können, was
    im Register fehlt: offene Stellen, Veröffentlichungen, Methoden und
    Datenzugänge.</p>
  <p>Zusammen führen sie <b>%s rekrutierende Studien</b>.</p>
  <p><b>Zur Karte:</b> Bei %s Standorten steht der Punkt auf der STADT,
    nicht auf der Einrichtung. Das ist dort richtig, wo die ROR-Kennung
    zur Mutterorganisation in einer anderen Stadt gehört, etwa beim
    Institut für Allgemeinmedizin des UK Lübeck, das in Kiel geführt
    wird. Diese Punkte sind auf der Karte als solche kenntlich.</p>
  <p>Die Karte lädt nichts nach. Die Umrisslinie liegt im Dokument, denn
    ein Kachelserver sähe jede Bewegung der Lesenden.</p>
</div>

<div class="karte" id="karte"></div>

<div class="topliste" id="topliste"></div>

<section class="traeger">
  <h2>Alle Standorte</h2>
  <p class="was">Nach der Zahl der Studien. Jeder Eintrag führt auf seine
    Profilseite.</p>
  <div class="zaehlzeile"><span class="treffer" id="otreffer"></span></div>
  <div class="ortliste" id="ortliste"></div>
  <div class="mehr"><button class="knopf" id="omehr" type="button">Weitere
    60 anzeigen</button></div>
</section>

<div class="hinweiskasten">
  <h2>Ihr Standort fehlt?</h2>
  <p>Das ist kein Versehen. Hier steht nur, wer im Studienregister als
    verantwortliche Einrichtung auftaucht. Wer nicht registriert, fehlt,
    und ganze Einrichtungstypen registrieren nie.
    <a href="institutionen.html#fehlen">Wen das betrifft</a>.</p>
  <p>Neue Standorte können sich eintragen, auch ohne eine einzige Studie
    im Register. Eine neu gegründete Hochschulmedizin kann dort noch gar
    nicht stehen.</p>
  <a class="mehr" href="eintragen.html?art=einrichtung">Standort eintragen oder
    ändern</a>
</div>''' % (zahl(mit_profil), zahl(rekrutiert), zahl(stadt))


def daten_block():
    """Der Datenblock, den die Karte liest. Nur was sie braucht.

    ⚠ NICHT die ganze landkarte.json einsetzen. Sie ist 1,3 MB, und die
    Karte braucht davon die Zaehlung, die Standorte und den Umriss.
    """
    L = lade("landkarte.json") or {}
    SV = lade("standorte.json") or {}
    K = lade("kontur.json") or {}
    d = {
        "zaehlung": L.get("zaehlung", {}),
        "standorte": {"standorte": SV.get("standorte", [])},
        "kontur": K.get("ringe", []),
        "stand": L.get("stand", ""),
        "vf_gesamt": L.get("vf_gesamt", 0),
    }
    return ('<script id="daten" type="application/json">%s</script>\n'
            '<script src="teile/standorte.js"></script>'
            % json.dumps(d, ensure_ascii=False).replace("</", "<\\/"))


INHALT = {
    "index.html": inhalt_home,
    "institutionen.html": inhalt_institutionen,
    "rekrutierend.html": inhalt_rekrutierend,
    "forschende.html": inhalt_forschende,
    "studien.html": inhalt_studien,
    "mvf.html": inhalt_mvf,
    "standorte.html": inhalt_standorte,
    "eintragen.html": inhalt_eintragen,
}

# Seiten mit eigenem Skript. Steht hier, nicht im Baulauf, damit eine
# neue Seite nicht eine weitere if-Abfrage in main() braucht.
LISTE = '<script src="teile/liste.js"></script>'


def endpunkt_block():
    """Die Adresse des Formular-Endpunkts in die Seite schreiben.

    Eine Quelle: standorte.py. Erst hier importiert, damit der Baulauf
    der uebrigen Seiten nicht von standorte.py abhaengt.
    """
    from standorte import ENDPUNKT_EINTRAGEN as ENDPUNKT
    return ('<script>window.ENDPUNKT = %s;</script>'
            % json.dumps(ENDPUNKT))
SKRIPTE = {
    "standorte.html": lambda: daten_block(),
    "eintragen.html": lambda: endpunkt_block()
    + '<script src="teile/eintragen.js"></script>',
    "institutionen.html": lambda: LISTE,
    "forschende.html": lambda: LISTE,
}


# ------------------------------------------------------------- Gegentest

def gegentest():
    ok = True
    print("Tausenderpunkte:")
    for n, soll in ((1298, "1.298"), (710, "710"), (0, "0"),
                    (6813, "6.813"), (None, "0")):
        ist = zahl(n)
        gut = ist == soll
        ok = ok and gut
        print(f"  {'ok ' if gut else 'FEHLER'} {n!r:<8} -> {ist!r}")

    print("\nMaskieren, damit kein Name die Seite zerlegt:")
    for roh, drin in (('Klinik "Sonnenhof" & Co', "&quot;"),
                      ("<script>alert(1)</script>", "&lt;script&gt;"),
                      ("Müller & Söhne", "&amp;")):
        ist = esc(roh)
        gut = drin in ist and "<" not in ist.replace("&lt;", "")
        ok = ok and gut
        print(f"  {'ok ' if gut else 'FEHLER'} {roh!r:<30} -> {ist[:44]!r}")

    print("\nNavigation setzt genau EIN aria-current:")
    for datei, _, _, _, _ in SEITEN:
        n = navigation(datei)
        c = n.count('aria-current="page"')
        gut = c == 1
        ok = ok and gut
        print(f"  {'ok ' if gut else 'FEHLER'} {datei:<22} {c}")

    print("\nGEGENPROBE: eine Seite, die es nicht gibt, markiert nichts:")
    c = navigation("gibt-es-nicht.html").count('aria-current="page"')
    gut = c == 0
    ok = ok and gut
    print(f"  {'ok ' if gut else 'FEHLER'} {c} Markierungen")

    print("\nJeder Platzhalter steht im Geruest:")
    g = (TEILE / "_geruest.html").read_text(encoding="utf-8")
    for name, p in PLATZ.items():
        gut = p in g
        ok = ok and gut
        print(f"  {'ok ' if gut else 'FEHLER'} {name:<14} {p}")
    for p in (leisten.PLATZ_NETZ, leisten.PLATZ_FUSS):
        gut = p in g
        ok = ok and gut
        print(f"  {'ok ' if gut else 'FEHLER'} {p}")

    print("\n" + ("Gegentest bestanden." if ok else "GEGENTEST GESCHEITERT."))
    return ok


def stempel(s):
    """Haengt an jede eigene Stil- und Skriptadresse einen Inhaltsstempel.

    ⚠ OHNE DAS liefert der Browser nach einer Aenderung das alte Skript
    zu den neuen Daten aus, und niemand sieht es.
    """
    import hashlib
    import re

    def ersetzen(m):
        pfad = m.group(2)
        datei = HIER / pfad
        if not datei.exists():
            return m.group(0)
        kurz = hashlib.sha256(datei.read_bytes()).hexdigest()[:8]
        return m.group(1) + pfad + "?v=" + kurz + m.group(3)

    return re.sub(r'((?:href|src)=")((?:\.\./)*teile/[^"?]+\.(?:css|js))(")',
                  ersetzen, s)


def main():
    if "--gegentest" in sys.argv:
        return 0 if gegentest() else 1

    geruest = (TEILE / "_geruest.html").read_text(encoding="utf-8")
    netz, fuss = leisten.beide()

    gebaut = []
    for datei, titel, h1, unter, _ in SEITEN:
        bauer = INHALT.get(datei)
        if not bauer:
            print(f"  {datei:<22} noch kein Inhalt, übersprungen")
            continue
        s = geruest
        s = s.replace(PLATZ["titel"], esc(titel))
        s = s.replace(PLATZ["beschreibung"], esc(unter))
        s = s.replace(PLATZ["h1"], esc(h1))
        s = s.replace(PLATZ["unter"], esc(unter))
        s = s.replace(PLATZ["navigation"], navigation(datei))
        s = s.replace(PLATZ["inhalt"], bauer())
        s = s.replace(PLATZ["wurzel"], "")
        bau = SKRIPTE.get(datei)
        s = s.replace(PLATZ["skripte"], bau() if bau else "")
        s = leisten.einsetzen(s, netz, fuss)
        s = stempel(s)
        (HIER / datei).write_text(s, encoding="utf-8")
        gebaut.append((datei, len(s)))
        print(f"  {datei:<22} {len(s):8,d} Zeichen".replace(",", "."))

    print(f"\n{len(gebaut)} von {len(SEITEN)} Seiten gebaut")
    offen = [d for d, *_ in SEITEN if d not in dict(gebaut)]
    if offen:
        print("noch offen:", ", ".join(offen))
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
