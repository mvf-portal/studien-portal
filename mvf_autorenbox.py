# -*- coding: utf-8 -*-
"""Autorenboxen aus den MVF-PDFs: Name, ORCID, Einrichtung, Ort, Kontakt.

WARUM AUS DEM PDF
-----------------
Die Affiliationen der MVF-Autor:innen stehen in keiner Schnittstelle.
Gemessen am 01.11.2026:

    Crossref            kein Affiliationsfeld gefuellt
    OpenAlex            5 von 80 Beitraegen mit Einrichtung
    Autorenprofil       1.340 Profile, alle ohne Inhaltstext
    Artikeltext         endet mit dem Fazit, keine Autorenbox
    abstract_text_de    401 von 1.528 gefuellt, also ebenso lueckenhaft

Im PDF stehen sie, am Ende, hinter dem Zitationshinweis.

ZWEI LAYOUTS, UND DAS IST DER GANZE WITZ
----------------------------------------
Mein erster Leser fand 4 Boxen in 20 PDFs, obwohl 7 eine ORCID tragen und
4 eine Korrespondenzadresse. Der Grund: Ich hatte an EINEM Beispiel
gebaut. Es gibt mindestens zwei Formen.

NEU (etwa ab 2023):

    Zitationshinweis
    Kostev, K., Kluge, S.: „...“ (MVF 05/26), S. 73-77. http://doi.org/...
    Prof. Dr. rer. med. habil. Karel Kostev MA  ORCID: 0000-0002-2124-7227
    ist Scientific Principal und Leiter des Epidemiologie-Teams bei IQVIA
    in Frankfurt. ... Kontakt: vorname.name@beispielfirma.example

ALT:

    Zitationshinweis
    Schwenke, C.: „...“ (03/21), S. 30-33. http://doi.org/...
    Anmerkungen
    Dr. Carsten Schwenke ist fuer ... taetig.
    Korrespondenzadresse
    Dr. Carsten Schwenke
    SCO:SSiS
    Karmeliterweg 42
    13465 Berlin
    Tel. +49 30 - 60409712
    carsten.schwenke@...

Die alte Form ist fuer unseren Zweck die BESSERE: Sie nennt die
Einrichtung als eigene Zeile und die Stadt ueber die Postleitzahl, statt
sie in einen Satz zu wickeln.

WELCHER BELEG GILT
------------------
Drei Belege, in dieser Reihenfolge:

  1. die Korrespondenzadresse  Einrichtung als Zeile, Ort aus der PLZ
  2. der Mailbereich           nachpruefbar, gehoert genau einem Haus
  3. der Fliesstext            nur ein Hinweis, nie allein tragend

Aus „ist Scientific Principal und Leiter des Epidemiologie-Teams bei
IQVIA in Frankfurt. ... Er lehrt am Universitaetsklinikum in Marburg"
die Affiliation zu raten, geht schief: der Satz nennt ein Team, ein
Haus, eine Stadt und eine zweite Einrichtung. Welche gilt, sagt er
nicht. beispielfirma.example sagt es.

⚠ WAS DIESES SKRIPT NICHT TUT
Es ordnet nichts einer ROR-Kennung zu. Das macht ein eigener Schritt.
Hier wird gelesen und offen gezaehlt, was nicht lesbar war.

  py -I mvf_autorenbox.py              liest, was fehlt
  py -I mvf_autorenbox.py --gegentest  prueft ohne Netz
  py -I mvf_autorenbox.py --nur 20     nur die neuesten 20
"""
import collections
import json
import pathlib
import re
import sys
import time
import urllib.request

HIER = pathlib.Path(__file__).parent
DATEN = HIER / "daten"
# Heruntergeladene Dateien sind fremdes Material und liegen in einem
# eigenen, sonst leeren Ordner, getrennt vom Code.
CACHE = HIER / "pdf-zwischenlager"
ZIEL = DATEN / "mvf_autorenbox.json"
UA = {"User-Agent": "Mozilla/5.0 (vf-landkarte; stegmaier@m-vf.de)"}

ZITAT = re.compile(r"Zitationshinweis|Citation\s*(?:hint|tips?)", re.I)
KORR = re.compile(r"Korrespondenzadresse|Kontaktadresse|"
                  r"Corresponding\s+author", re.I)
ORCID = re.compile(r"ORCID[:\s]*((?:\d{4}[\s‐-―-]?){3}\d{3}[\dXx])", re.I)
MAIL = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
PLZ = re.compile(r"^(?:D\s*-\s*)?(\d{5})\s+([A-ZÄÖÜ][\w .\-/()äöüß]{2,40})$")
STRASSE = re.compile(r"\d+\s*[a-zA-Z]?$")
TELEFON = re.compile(r"^(Tel|Fon|Telefon|Fax|Mobil)\b", re.I)
VERB = re.compile(r"^(ist|sind|war|waren|leitet|arbeitet|forscht|lehrt|"
                  r"studierte|promovierte|habilitierte|hat|haben|wurde|"
                  r"verantwortet|vertritt|is|are|was|works|leads|heads)\b", re.I)
GRAD = re.compile(r"^(Prof\.|PD\b|Priv\.|Dr\.|Dipl\.|Univ\.|M\.?Sc|MSc|MPH|"
                  r"MBA|MA\b|Mag\.|Ph\.?D|Dres\.)", re.I)
# Zeilen, die eine Marke sind und darum nie ein Name.
NIE_NAME = re.compile(r"^(Literatur|References|Keywords|Schlüsselwörter|"
                      r"Zusammenfassung|Abstract|Anmerkungen|Danksagung|"
                      r"Autorenerklärung|Interessenkonflikt|Zitationshinweis|"
                      r"Korrespondenzadresse|Kontaktadresse|Förderung|"
                      r"Acknowledge?ments?|Funding|Tel|Fax|Fon)\b", re.I)

BEREICH_RAUSCHEN = {
    "gmail.com", "googlemail.com", "web.de", "gmx.de", "gmx.net", "gmx.com",
    "t-online.de", "outlook.com", "outlook.de", "hotmail.com", "hotmail.de",
    "yahoo.de", "yahoo.com", "icloud.com", "me.com", "mail.de", "posteo.de",
    "aol.com", "freenet.de", "online.de", "protonmail.com", "live.de",
    "mailbox.org", "arcor.de", "bluewin.ch", "gmx.at",
}


# --------------------------------------------------------------- Werkzeug

def entsilben(t):
    """Trennstriche am Zeilenende zusammenziehen.

    Im PDF steht „freibe\\n-\\nruflicher" und „geför\\n-\\ndert". Wer das
    nicht zusammenzieht, findet die Woerter nicht, nach denen er sucht.
    Ein Bindestrich MIT folgendem Grossbuchstaben bleibt stehen, denn
    „Nordrhein-\\nWestfalen" ist ein echter Bindestrich.

    ⚠ DREI Faelle, nicht zwei. Den dritten hat am 01.11.2026 die
    Crossref-Sitzung gefunden, und er traf diesen Code auch:

        Gesundheits-\\nwesen        -> Gesundheitswesen   zusammenziehen
        Nordrhein-\\nWestfalen      -> Nordrhein-Westfalen bleibt
        Versorgungs-\\nund ...      -> bleibt GANZ, Aufzaehlung

    Der dritte Fall sieht wie der erste aus, beide Seiten klein, ist aber
    das Gegenteil: „Versorgungs- und Gesundheitsforschung" ist eine
    Aufzaehlung mit haengendem Bindestrich. Zusammengezogen wurde daraus
    „Versorgungsund", gemessen an zwei echten Stellen im Bestand:
    „Forschungsinstitut fuer Gesundheitsund Systemgestaltung" und
    „Prozessund Strukturinnovationen".
    """
    t = (t or "").replace("\r", "")
    # Kein Zusammenziehen vor einem Bindewort: dort haengt der Strich.
    nach = r"(?=[a-zäöüß])(?!(?:und|oder|sowie|bzw|wie|beziehungsweise)\b)"
    t = re.sub(r"([a-zäöüß])[‐-―-]\s*\n\s*" + nach, r"\1", t)
    t = re.sub(r"([a-zäöüß])\s*\n[‐-―-]\s*\n\s*" + nach, r"\1", t)
    return t


def orcid_putzen(s):
    """Die Trennstriche im PDF sind oft Gedankenstriche, nicht Bindestriche."""
    z = re.sub(r"[^0-9Xx]", "", s or "")
    if len(z) != 16:
        return ""
    return "-".join(z[i:i + 4] for i in range(0, 16, 4)).upper()


def bereich(mail):
    """Der Mailbereich, wenn er etwas ueber die Einrichtung sagt."""
    if not mail or "@" not in mail:
        return ""
    b = mail.rsplit("@", 1)[1].lower().strip(".,;:)")
    return "" if b in BEREICH_RAUSCHEN else b


def zeilen_von(t):
    return [" ".join(z.split()) for z in t.split("\n") if z.strip()]


# ------------------------------------------------------- die zwei Layouts

def aus_korrespondenz(zl):
    """Layout ALT: der Block hinter „Korrespondenzadresse".

    ⚠ ER STEHT MEIST VOR DEM ZITATIONSHINWEIS, nicht dahinter. Gemessen
    an drei echten PDFs aus Heft 03/21: zweimal davor, einmal danach.
    Darum faehrt dieser Zweig ueber den GANZEN Text, nicht nur ueber den
    Schluss. Mein erster Leser schnitt am letzten Zitationshinweis und
    fand darum in 20 PDFs keine einzige Korrespondenzadresse, obwohl
    vier eine haben.

    Drei Gestalten, alle drei echt belegt:

      a) saeuberlich zeilenweise
         Dr. Carsten Schwenke / SCO:SSiS / Karmeliterweg 42 / 13465 Berlin
      b) Einrichtung mit Stadt in einer Zeile
         Dr. Klaus Piwernetz / medimaxx health management GmbH, Muenchen
      c) alles in EINER Zeile, Name und Haus durch Gedankenstrich getrennt
         Prof. Dr. Franz Porzsolt - Institute of Clinical Economics 89081 Ulm

    Die Postleitzahl ist die verlaesslichste Marke fuer den Ort. Sie wird
    aus der Zeile herausgeschnitten, damit sie nicht im Hausnamen landet.
    """
    raus = []
    for i, z in enumerate(zl):
        if not KORR.match(z):
            continue
        name, haus, ort, mail = "", [], "", ""
        for b in zl[i + 1:i + 14]:
            # ⚠ Die Mail steht NACH der Telefonzeile. Erst lesen, dann
            # abbrechen, sonst geht sie verloren: „Tel" steht in NIE_NAME
            # und beendete die Schleife eine Zeile zu frueh.
            m = MAIL.search(b)
            if m and not mail:
                mail = m.group(0)
            if TELEFON.match(b):
                continue
            if NIE_NAME.match(b) or KORR.match(b):
                break
            # Der Artikeltext beginnt mit der Marke „>>" oder laeuft als
            # langer Satz weiter. Beides beendet den Block.
            if b.startswith(">>") or (len(b) > 110 and name):
                break
            rest = MAIL.sub(" ", b)
            rest = re.sub(r"\b(e-?mail|email|mail|web|internet)\s*:?",
                          " ", rest, flags=re.I)
            # Postleitzahl samt Ort herausschneiden.
            p = re.search(r"(?:D\s*-\s*)?\b(\d{5})\s+"
                          r"([A-ZÄÖÜ][\wäöüß.\-/()]*"
                          r"(?:\s[A-ZÄÖÜ][\wäöüß.\-/()]*)?)", rest)
            if p:
                if not ort:
                    ort = p.group(2).strip(" .,;:")
                rest = rest[:p.start()] + " " + rest[p.end():]
            rest = " ".join(rest.split()).strip(" .,;:-–")
            if not rest:
                continue
            if not name:
                # Gestalt (c): Name und Haus in einer Zeile.
                teil = re.split(r"\s[–—-]\s", rest, maxsplit=1)
                name = teil[0].strip(" .,;:")
                if len(teil) > 1 and len(teil[1]) > 2:
                    haus.append(teil[1].strip(" .,;:"))
                continue
            # Eine Strasse mit Hausnummer ist kein Hausname.
            if STRASSE.search(rest) and len(rest) < 50:
                continue
            # Gestalt (b): „... GmbH, Muenchen" - der Ort steckt hinten.
            m2 = re.match(r"(.+),\s*([A-ZÄÖÜ][\wäöüß.\-]{2,24})$", rest)
            if m2 and not ort and len(m2.group(1)) > 6:
                ort = m2.group(2)
                rest = m2.group(1).strip()
            haus.append(rest.strip(" .,;:"))
        if name and len(name) > 3:
            raus.append({
                "name": name, "orcid": "",
                "haus_zeilen": haus[:3], "ort": ort,
                "mail": mail, "bereich": bereich(mail),
                "beleg": "Korrespondenzadresse", "text": "",
            })
    return raus


def aus_orcid(zl):
    """Layout NEU: die Namenszeile mit ORCID, darunter der Satz."""
    raus = []
    for i, z in enumerate(zl):
        m = ORCID.search(z)
        if not m:
            continue
        name = ORCID.sub("", z).strip(" .,;:–-")
        # Steht die ORCID allein in der Zeile, ist der Name darueber.
        if len(name) < 4 and i > 0 and not NIE_NAME.match(zl[i - 1]):
            name = zl[i - 1].strip(" .,;:")
        satz = []
        for b in zl[i + 1:i + 12]:
            if ORCID.search(b) or NIE_NAME.match(b) or KORR.match(b):
                break
            satz.append(b)
        txt = " ".join(satz)
        mm = MAIL.search(txt) or MAIL.search(z)
        mail = mm.group(0) if mm else ""
        if len(name) > 3:
            raus.append({
                "name": name, "orcid": orcid_putzen(m.group(1)),
                "haus_zeilen": [], "ort": "",
                "mail": mail, "bereich": bereich(mail),
                "beleg": "ORCID-Box", "text": txt[:700],
            })
    return raus


def aus_satz(zl):
    """Letzter Ausweg: Namenszeile, darunter ein Satz, der mit Verb beginnt."""
    raus = []
    for i, z in enumerate(zl[:-1]):
        if NIE_NAME.match(z) or ORCID.search(z) or len(z) > 120:
            continue
        namig = bool(GRAD.match(z)) or (z[:1].isupper() and not VERB.match(z)
                                        and len(z.split()) <= 8)
        if not (namig and VERB.match(zl[i + 1])):
            continue
        satz = []
        for b in zl[i + 1:i + 12]:
            if NIE_NAME.match(b) or KORR.match(b) or ORCID.search(b):
                break
            satz.append(b)
        txt = " ".join(satz)
        m = MAIL.search(txt)
        mail = m.group(0) if m else ""
        raus.append({
            "name": z.strip(" .,;:"), "orcid": "",
            "haus_zeilen": [], "ort": "",
            "mail": mail, "bereich": bereich(mail),
            "beleg": "Fliesstext", "text": txt[:700],
        })
    return raus


def zusammen(a, b):
    """Zwei Funde zur selben Person vereinen, der bessere Beleg sticht."""
    RANG = {"Korrespondenzadresse": 0, "ORCID-Box": 1, "Fliesstext": 2}
    if RANG[b["beleg"]] < RANG[a["beleg"]]:
        a, b = b, a
    for f in ("orcid", "ort", "mail", "bereich", "text"):
        if not a.get(f) and b.get(f):
            a[f] = b[f]
    if not a["haus_zeilen"] and b["haus_zeilen"]:
        a["haus_zeilen"] = b["haus_zeilen"]
    return a


def nachname(name):
    """Zum Zusammenfuehren: das laengste Wort ohne Grad und Punkt."""
    w = [x.strip(" .,;:") for x in re.sub(r"\(.*?\)", " ", name or "").split()]
    w = [x for x in w if len(x) > 2 and not GRAD.match(x + " ") and "." not in x]
    return (max(w, key=len).lower() if w else (name or "").lower())


VON = re.compile(r"^von\s*:\s*(.+)$", re.I)
NUMMER = re.compile(r"^(\d{1,2})\s*[:.]\s*(.+)$")
KONTAKT = re.compile(r"^Kontakt(?:\s+zu[rm]?\s+\w+)?\s*:?\s*(.*)$", re.I)
# „Name | Einrichtung" - der Senkrechtstrich trennt beides sauber.
STRICH = re.compile(r"^(.{3,70}?)\s*[|│]\s*(.{2,90})$")
NUR_ZAHL = re.compile(r"^\d{1,3}$")
# Die Fusszeile jedes MVF-PDF. Sie darf nie als Angabe durchgehen.
FUSSZEILE = re.compile(r"Monitor Versorgungsforschung\s+\d\d/\d{4}|"
                       r"This article was published under the license", re.I)


def _mail_und_rest(z):
    m = MAIL.search(z)
    mail = m.group(0) if m else ""
    rest = MAIL.sub(" ", z)
    rest = re.sub(r"\b(e-?mail|email|mail)\s*:?", " ", rest, flags=re.I)
    return mail, " ".join(rest.split()).strip(" .,;:|–-")


def _namen_aus(z):
    """Eine Zeile mit einem oder mehreren Namen zerlegen.

    „Madeleine Barlozek MBA" -> ein Name.
    „Anna Mueller 1, Bernd Schmidt 2" -> zwei Namen, Fussnoten getrennt.
    """
    z = re.sub(r"\s*–\s*", " - ", z)
    raus = []
    for teil in re.split(r"\s*(?:,|\bund\b|&)\s*", z):
        teil = teil.strip(" .,;:")
        if not teil or len(teil) < 4:
            continue
        # Nachgestellte Fussnotenzahlen abtrennen.
        fn = re.findall(r"(\d{1,2})\s*$", teil)
        kern = re.sub(r"[\d\s,]+$", "", teil).strip(" .,;:")
        # Eine Zeile mit Zahlen und ohne Buchstaben ist kein Name.
        if len(kern) < 4 or not re.search(r"[A-Za-zÄÖÜäöüß]{3}", kern):
            continue
        raus.append({"name": kern, "fussnoten": fn})
    return raus


def anker_von(zl):
    """FORM 1: die Zeile „von: ...", dazu die Fussnoten darunter."""
    raus = []
    for i, z in enumerate(zl):
        m = VON.match(z)
        if not m:
            continue
        kopf = m.group(1).strip()
        # Der Name kann in der naechsten Zeile weitergehen.
        if len(kopf) < 60 and i + 1 < len(zl):
            nx = zl[i + 1]
            if (not NUR_ZAHL.match(nx) and not ORCID.search(nx)
                    and not NUMMER.match(nx) and not FUSSZEILE.search(nx)
                    and nx[:1].isupper() and len(nx) < 70
                    and not VERB.match(nx)):
                kopf += ", " + nx
        # ⚠ Die hochgestellte Fussnotenzahl wird beim Auslesen des PDF zu
        # einer EIGENEN ZEILE. Wer nur am Namen nach Ziffern sucht, findet
        # sie nie, und die Affiliation bleibt liegen. Gemessen an 05/26.
        lose = []
        for nx in zl[i + 1:i + 5]:
            if NUR_ZAHL.match(nx):
                lose.append(nx.strip())
            elif ORCID.search(nx) or not nx.strip():
                continue
            else:
                break
        for n in _namen_aus(kopf):
            raus.append({
                "name": n["name"], "orcid": "", "haus_zeilen": [], "ort": "",
                "mail": "", "bereich": "", "beleg": "von-Zeile",
                "text": "",
                "fussnoten": n["fussnoten"] or lose, "zeile": i,
            })
    return raus


def anker_nummern(zl):
    """Die numerierten Affiliationen: „1: Beraterin ... bei Danone"."""
    tab = {}
    for z in zl:
        m = NUMMER.match(z)
        if not m or FUSSZEILE.search(z):
            continue
        txt = m.group(2).strip()
        # Eine Literaturstelle ist keine Affiliation: sie nennt ein Jahr
        # und eine Zeitschrift, und sie ist lang.
        if re.search(r"\b(19|20)\d\d\b", txt) and len(txt) > 70:
            continue
        if len(txt) < 6 or len(txt) > 200:
            continue
        tab.setdefault(m.group(1), txt)
    return tab


def anker_kontakt(zl):
    """FORM 1 und 2: der Kontaktblock, mit Senkrechtstrich oder ohne."""
    raus = []
    for i, z in enumerate(zl):
        m = KONTAKT.match(z)
        if not m:
            continue
        name, haus, mail = "", [], ""
        kandidaten = ([m.group(1)] if m.group(1).strip() else []) \
            + zl[i + 1:i + 5]
        for b in kandidaten:
            if FUSSZEILE.search(b) or NIE_NAME.match(b):
                break
            mm, rest = _mail_und_rest(b)
            if mm and not mail:
                mail = mm
            if not rest:
                continue
            s = STRICH.match(rest)
            if s:
                if not name:
                    name = s.group(1).strip(" .,;:")
                haus.append(s.group(2).strip(" .,;:"))
                continue
            if not name and not VERB.match(rest) and len(rest) < 80:
                name = rest.strip(" .,;:")
        if name and len(name) > 3:
            raus.append({
                "name": name, "orcid": "", "haus_zeilen": haus[:2], "ort": "",
                "mail": mail, "bereich": bereich(mail), "beleg": "Kontaktblock",
                "text": "", "fussnoten": [], "zeile": i,
            })
    return raus


def anker_orcid(zl):
    """Alle ORCID, mit ihrer Zeilennummer. KEIN Anker, nur ein Merkmal.

    ⚠ Im Spaltensatz reisst die ORCID aus dem Zusammenhang. Gemessen an
    Heft 05/26: dreimal stand sie mitten im Fliesstext, 300 Zeichen vom
    Namen entfernt. Wer sie als Anker nimmt, erfindet Autor:innen.
    """
    raus = []
    for i, z in enumerate(zl):
        m = ORCID.search(z)
        if not m:
            continue
        oid = orcid_putzen(m.group(1))
        if not oid:
            continue
        # Der Name steht in derselben Zeile oder bis zu drei darueber.
        name = ORCID.sub("", z).strip(" .,;:–-")
        if len(name) < 4:
            name = ""
            for k in range(i - 1, max(-1, i - 4), -1):
                k_z = zl[k]
                if (NUR_ZAHL.match(k_z) or FUSSZEILE.search(k_z)
                        or ORCID.search(k_z)):
                    continue
                v = VON.match(k_z)
                kern = (v.group(1) if v else k_z).strip()
                if (len(kern) > 4 and len(kern) < 80 and kern[:1].isupper()
                        and not VERB.match(kern) and not NIE_NAME.match(kern)):
                    name = re.sub(r"[\d\s,]+$", "", kern).strip(" .,;:")
                    break
        raus.append({"orcid": oid, "name": name, "zeile": i})
    return raus


def _fuss_anhaengen(person, nummern):
    """Die numerierte Affiliation an die Person mit dieser Fussnote."""
    for fn in person.get("fussnoten") or []:
        txt = nummern.get(fn)
        if txt and txt not in person["haus_zeilen"]:
            person["haus_zeilen"].append(txt)
    return person


def boxen(text):
    """Alle Autorenangaben eines Beitrags, aus vier unabhaengigen Ankern.

    Die Reihenfolge der Belege, vom belastbarsten zum schwaechsten:

      1. Korrespondenzadresse  Haus als eigene Zeile, Ort aus der PLZ
      2. Kontaktblock          Haus hinter dem Senkrechtstrich, plus Mail
      3. ORCID-Box             Name und ORCID in einer Zeile
      4. von-Zeile             Name, Haus nur ueber die Fussnote
      5. Fliesstext            letzter Ausweg, traegt nie allein

    ⚠ Die ORCID ist KEIN Anker. Im Spaltensatz steht sie mitten im
    Fliesstext. Sie wird nachtraeglich zugeordnet, und nur dann, wenn ein
    Name dazu passt oder der Beitrag genau eine Person hat.
    """
    t = entsilben(text)
    if not t.strip():
        return []
    ganz = zeilen_von(t)
    treffer = list(ZITAT.finditer(t))
    ab = treffer[-1].end() if treffer else int(len(t) * 0.8)
    schluss = zeilen_von(t[ab:])

    # Die Korrespondenzadresse steht meist VOR dem Zitationshinweis, die
    # ORCID-Box dahinter. Darum zwei verschiedene Ausschnitte.
    funde = (aus_korrespondenz(ganz) + anker_kontakt(ganz)
             + aus_orcid(schluss) + anker_von(ganz))
    nummern = anker_nummern(ganz)

    RANG = {"Korrespondenzadresse": 0, "Kontaktblock": 1, "ORCID-Box": 2,
            "von-Zeile": 3, "Fliesstext": 4}

    tabelle = {}
    for f in funde:
        f.setdefault("fussnoten", [])
        f.setdefault("zeile", 0)
        k = nachname(f["name"])
        if not k or len(k) < 3:
            continue
        if k in tabelle:
            a, b = tabelle[k], f
            if RANG[b["beleg"]] < RANG[a["beleg"]]:
                a, b = b, a
            for feld in ("orcid", "ort", "mail", "bereich", "text"):
                if not a.get(feld) and b.get(feld):
                    a[feld] = b[feld]
            for h in b.get("haus_zeilen") or []:
                if h not in a["haus_zeilen"]:
                    a["haus_zeilen"].append(h)
            a["fussnoten"] = sorted(set(a["fussnoten"]) | set(b["fussnoten"]))
            # Der laengere Name traegt mehr (Grade, zweiter Vorname).
            if len(b["name"]) > len(a["name"]):
                a["name"] = b["name"]
            tabelle[k] = a
        else:
            tabelle[k] = f

    if not tabelle:
        for f in aus_satz(schluss):
            f.setdefault("fussnoten", [])
            k = nachname(f["name"])
            if k and len(k) >= 3 and k not in tabelle:
                tabelle[k] = f

    leute = list(tabelle.values())

    # Die ORCID nachtraeglich zuordnen.
    for o in anker_orcid(ganz):
        k = nachname(o["name"]) if o["name"] else ""
        if k and k in tabelle and not tabelle[k]["orcid"]:
            tabelle[k]["orcid"] = o["orcid"]
        elif len(leute) == 1 and not leute[0]["orcid"]:
            # Genau eine Person im Beitrag: die ORCID kann nur ihr gehoeren.
            leute[0]["orcid"] = o["orcid"]
        elif not k:
            continue

    for p in leute:
        _fuss_anhaengen(p, nummern)
        if not p.get("bereich") and p.get("mail"):
            p["bereich"] = bereich(p["mail"])
        p.pop("fussnoten", None)
        p.pop("zeile", None)
    return leute


# --------------------------------------------------------------- Holen

def hol_pdf(url, ziel):
    if ziel.exists() and ziel.stat().st_size > 2000:
        return True
    warte = 4
    for versuch in range(4):
        try:
            with urllib.request.urlopen(
                    urllib.request.Request(url, headers=UA), timeout=180) as f:
                b = f.read()
            if len(b) < 2000:
                return False
            ziel.write_bytes(b)
            return True
        except Exception:
            if versuch == 3:
                return False
            time.sleep(warte)
            warte *= 2
    return False


def pdf_text(p):
    try:
        import pypdf
        r = pypdf.PdfReader(str(p))
    except ImportError:
        try:
            import PyPDF2 as pypdf
            r = pypdf.PdfReader(str(p))
        except ImportError:
            return None
    except Exception:
        return ""
    try:
        return "\n".join((s.extract_text() or "") for s in r.pages)
    except Exception:
        return ""


# ------------------------------------------------------------- Gegentest

NEU = (
    "Diese Studie zeigt, dass die Teilnahme am Check-up 35 ...\n"
    "Autorenerklärung\n"
    "Karel Kostev und Sabine Kluge sind Mitarbeiter von IQVIA.\n"
    "Zitationshinweis\n"
    "Kostev, K., Kluge, S.: „Untersuchung ...“ (MVF 05/26), S. 73–77.\n"
    "Prof. Dr. rer. med. habil. Karel Kostev MA  ORCID: 0000-0002-2124-7227\n"
    "ist Scientific Principal und Leiter des Epidemiologie-Teams bei IQVIA\n"
    "in Frankfurt. Er hat Soziologie studiert. Kontakt: vorname.name@beispielfirma.example\n"
    "Dr. Sabine Kluge  ORCID: 0000-0003-1111-2222\n"
    "ist Epidemiologin bei IQVIA in Frankfurt. Kontakt: s.name@beispielfirma.example\n")

ALT = (
    "Angesichts neuer Studieninformationen soll das IQWiG ...\n"
    "Zitationshinweis\n"
    "Schwenke, C.: „Implikation von Datenschnit-\nten und Zensierung“ "
    "in: „Monitor Versorgungsforschung“ (03/21),\nS. 30-33.\n"
    "Anmerkungen\n"
    "Dr. Carsten Schwenke ist für pharmazeutische Unternehmen als freibe\n"
    "-\nruflicher Statistiker tätig.\n"
    "Korrespondenzadresse\n"
    "Dr. Carsten Schwenke\n"
    "SCO:SSiS\n"
    "Karmeliterweg 42\n"
    "13465 Berlin\n"
    "Tel. +49 30 - 60409712\n"
    "vorname.name@statistik.example\n")


# Gestalt (c), echt aus Heft 03/21: alles in einer Zeile, Name und Haus
# durch Gedankenstrich getrennt, Postleitzahl hinten dran. Und der Block
# steht VOR dem Zitationshinweis.
EINZEILIG = (
    "Korrespondenzadresse\n"
    "Prof. Dr. Franz Porzsolt – Institute of Clinical Economics (ICE) e.V. "
    "89081 Ulm\n"
    "eMail: vorname.name@institut.example\n"
    ">> Wissenschaftliche Untersuchungen belegen, dass der Gesundheits"
    "zustand von Menschen aus sozial benachteiligten Wohnvierteln "
    "schlechter ist.\n"
    "Zitationshinweis\n"
    "Porzsolt, F.: „Ein Titel“ (03/21), S. 20-25.\n")

# Gestalt (b), echt aus Heft 03/21: Einrichtung und Stadt in einer Zeile,
# darunter die Strasse, darunter die Postleitzahl.
MIT_KOMMA = (
    "Korrespondenzadresse\n"
    "Dr. med. Dr. rer. nat. Klaus Piwernetz\n"
    "medimaxx health management GmbH, München\n"
    "Brienner Str. 55\n"
    "80333 München\n"
    "E-Mail: info@beratung.example\n"
    "Zitationshinweis\n"
    "Piwernetz, K.: „Gesundheitssystem neu denken“ (03/21), S. 26-29.\n")


# Form 1, echt aus Heft 05/26. Der Name steht in der von-Zeile, das Haus
# zweimal: einmal als numerierte Fussnote, einmal im Kontaktblock hinter
# dem Senkrechtstrich. Die ORCID steht zwei Zeilen vom Namen entfernt,
# dazwischen die blosse Fussnotenzahl.
FORM_EINS = (
    "nicht nur das gewuenschte Ergebnis - sie gestaltet die Spielregeln "
    "so, dass rationales Eigeninteresse zu diesem Ergebnis fuehrt. <<\n"
    "von: Madeleine Barlozek MBA\n"
    "1\n"
    "ORCID 0009-0005-6731-1561\n"
    "1: Beraterin und Senior Market Access Manager bei Danone\n"
    "Kontakt zur Autorin:\n"
    "Madeleine Barlozek MBA | Barlozek Consulting\n"
    "info@beratung2.example\n"
    "Monitor Versorgungsforschung 05/2026 / This article was published "
    "under the license CC BY 4.0\n")


def gegentest():
    ok = True

    print("Trennstriche zusammenziehen, drei Faelle:")
    for roh, drin in (("freibe\n-\nruflicher", "freiberuflicher"),
                      ("geför-\ndert", "gefördert"),
                      ("Gesundheits-\nwesen", "Gesundheitswesen"),
                      # Echter Bindestrich, bleibt.
                      ("Nordrhein-\nWestfalen", "Nordrhein-"),
                      ("Case-\nManagement", "Case-"),
                      # Aufzaehlung mit haengendem Strich, bleibt GANZ.
                      ("Versorgungs-\nund Gesundheitsforschung",
                       "Versorgungs-"),
                      ("Prozess-\nund Strukturinnovationen", "Prozess-"),
                      ("Arznei-\nmittel-\nund Heilmittel", "Arzneimittel-")):
        ist = entsilben(roh).replace("\n", " ")
        gut = drin in ist
        ok = ok and gut
        print(f"  {'ok ' if gut else 'FEHLER'} {roh!r:<34} -> {ist!r}")

    print("\nGEGENPROBE: Woerter, die zu Recht auf 'und' enden, bleiben:")
    for roh, drin in (("Hinter-\ngrund", "Hintergrund"),
                      ("Aerzte-\nverbund", "Aerzteverbund"),
                      ("auf-\ngrund", "aufgrund")):
        ist = entsilben(roh).replace("\n", " ")
        gut = drin in ist
        ok = ok and gut
        print(f"  {'ok ' if gut else 'FEHLER'} {roh!r:<26} -> {ist!r}")

    print("\nORCID putzen:")
    for roh, soll in (("0000-0002-2124-7227", "0000-0002-2124-7227"),
                      ("0000–0002–2124–7227", "0000-0002-2124-7227"),
                      ("0000 0002 2124 722X", "0000-0002-2124-722X"),
                      ("0000-0002-2124", "")):
        ist = orcid_putzen(roh)
        gut = ist == soll
        ok = ok and gut
        print(f"  {'ok ' if gut else 'FEHLER'} {roh!r:<26} -> {ist!r}")

    print("\nMailbereich:")
    for m, soll in (("vorname.name@beispielfirma.example", "beispielfirma.example"),
                    ("a.b@hochschule.example", "hochschule.example"),
                    ("beispiel@gmail.com", ""), ("x@web.de", ""), ("", "")):
        ist = bereich(m)
        gut = ist == soll
        ok = ok and gut
        print(f"  {'ok ' if gut else 'FEHLER'} {m!r:<26} -> {ist!r}")

    print("\nLayout NEU, ORCID-Box:")
    b = boxen(NEU)
    for was, gut in (
            ("zwei Personen", len(b) == 2),
            ("ORCID der ersten",
             bool(b) and b[0]["orcid"] == "0000-0002-2124-7227"),
            ("Mail der ersten",
             bool(b) and b[0]["mail"] == "vorname.name@beispielfirma.example"),
            ("Bereich beispielfirma.example", bool(b) and b[0]["bereich"] == "beispielfirma.example"),
            ("Beleg benannt", bool(b) and b[0]["beleg"] == "ORCID-Box"),
            ("Fazit bleibt draussen",
             all("Diese Studie" not in x["text"] for x in b))):
        ok = ok and gut
        print(f"  {'ok ' if gut else 'FEHLER'} {was}")
    if len(b) != 2:
        print("    gefunden:", [x["name"] for x in b])

    print("\nLayout ALT, Korrespondenzadresse:")
    b = boxen(ALT)
    e = b[0] if b else {}
    for was, gut in (
            ("eine Person", len(b) == 1),
            ("Name", e.get("name", "").endswith("Carsten Schwenke")),
            ("Einrichtung als Zeile", e.get("haus_zeilen") == ["SCO:SSiS"]),
            ("Ort aus der PLZ", e.get("ort") == "Berlin"),
            ("Strasse NICHT als Einrichtung",
             all("Karmeliterweg" not in h for h in e.get("haus_zeilen", []))),
            ("Mail", e.get("mail") == "vorname.name@statistik.example"),
            ("Beleg benannt", e.get("beleg") == "Korrespondenzadresse")):
        ok = ok and gut
        print(f"  {'ok ' if gut else 'FEHLER'} {was}")
    if b:
        print("    ->", json.dumps({k: e[k] for k in
              ("name", "haus_zeilen", "ort", "mail", "beleg")},
              ensure_ascii=False))

    print("\nGestalt (c), alles in einer Zeile, Block VOR dem Zitationshinweis:")
    b = boxen(EINZEILIG)
    e = b[0] if b else {}
    for was, gut in (
            ("eine Person", len(b) == 1),
            ("Name ohne das Haus", e.get("name") == "Prof. Dr. Franz Porzsolt"),
            ("Haus erkannt",
             any("Institute of Clinical Economics" in h
                 for h in e.get("haus_zeilen", []))),
            ("Ort aus der PLZ", e.get("ort") == "Ulm"),
            ("PLZ nicht im Hausnamen",
             all("89081" not in h for h in e.get("haus_zeilen", []))),
            ("Mail", e.get("mail") == "vorname.name@institut.example"),
            ("Artikeltext bleibt draussen",
             all("Wissenschaftliche" not in h
                 for h in e.get("haus_zeilen", [])))):
        ok = ok and gut
        print(f"  {'ok ' if gut else 'FEHLER'} {was}")
    if b:
        print("    ->", json.dumps({k: e[k] for k in
              ("name", "haus_zeilen", "ort", "mail")}, ensure_ascii=False))

    print("\nGestalt (b), Einrichtung und Stadt in einer Zeile:")
    b = boxen(MIT_KOMMA)
    e = b[0] if b else {}
    for was, gut in (
            ("eine Person", len(b) == 1),
            ("Name", e.get("name", "").endswith("Klaus Piwernetz")),
            ("Haus ohne die Stadt",
             e.get("haus_zeilen", [""])[0] ==
             "medimaxx health management GmbH"),
            ("Ort", e.get("ort") == "München"),
            ("Strasse NICHT als Haus",
             all("Brienner" not in h for h in e.get("haus_zeilen", []))),
            ("Mail", e.get("mail") == "info@beratung.example")):
        ok = ok and gut
        print(f"  {'ok ' if gut else 'FEHLER'} {was}")
    if b:
        print("    ->", json.dumps({k: e[k] for k in
              ("name", "haus_zeilen", "ort", "mail")}, ensure_ascii=False))

    print("\nForm 1, heute ueblich: von-Zeile, Fussnote, Kontaktblock:")
    b = boxen(FORM_EINS)
    e = b[0] if b else {}
    for was, gut in (
            ("eine Person", len(b) == 1),
            ("Name", e.get("name") == "Madeleine Barlozek MBA"),
            ("Haus aus dem Kontaktblock",
             "Barlozek Consulting" in e.get("haus_zeilen", [])),
            ("Haus aus der Fussnote",
             any("Danone" in h for h in e.get("haus_zeilen", []))),
            ("ORCID zugeordnet", e.get("orcid") == "0009-0005-6731-1561"),
            ("Mail", e.get("mail") == "info@beratung2.example"),
            ("Fusszeile bleibt draussen",
             all("Monitor Versorgungsforschung" not in h
                 for h in e.get("haus_zeilen", [])))):
        ok = ok and gut
        print(f"  {'ok ' if gut else 'FEHLER'} {was}")
    if b:
        print("    ->", json.dumps({k: e[k] for k in
              ("name", "orcid", "haus_zeilen", "mail", "beleg")},
              ensure_ascii=False))

    print("\nGEGENPROBE: eine freie ORCID im Fliesstext erfindet niemanden:")
    frei = boxen(
        "von: Anna Mueller\n"
        "1\n"
        "1: Institut fuer Versorgungsforschung, Bremen\n"
        "Ein langer Absatz Fliesstext, der weiterlaeuft und laeuft.\n"
        "ORCID 0000-0002-6999-474X\n"
        "43\n"
        "Monitor Versorgungsforschung 05/2026 / This article was published "
        "under the license CC BY 4.0\n"
        "Kommentar\n")
    namen = [x["name"] for x in frei]
    gut = namen == ["Anna Mueller"] and frei[0]["orcid"] == "0000-0002-6999-474X"
    ok = ok and gut
    print(f"  {'ok ' if gut else 'FEHLER'} nur die eine Person, ORCID "
          f"zugeordnet: {namen} / "
          f"{frei[0]['orcid'] if frei else ''}")

    print("\nGEGENPROBE: Text ohne jede Box darf nichts liefern:")
    leer = boxen("Ein Fliesstext ueber die Versorgung. Er endet hier.\n"
                 "Literatur\n1. Mueller A. Irgendwas. 2020.\n")
    gut = len(leer) == 0
    ok = ok and gut
    print(f"  {'ok ' if gut else 'FEHLER'} nichts gefunden: {[x['name'] for x in leer]}")

    print("\nGEGENPROBE: eine Literaturliste ist keine Autorenbox:")
    lit = boxen("Zitationshinweis\nMueller: Titel (01/20)\n"
                "Literatur\nMueller A, Schmidt B. Eine Arbeit. Lancet 2020.\n"
                "Schulze C. Noch eine. BMJ 2019.\n")
    gut = len(lit) == 0
    ok = ok and gut
    print(f"  {'ok ' if gut else 'FEHLER'} nichts gefunden: {[x['name'] for x in lit]}")

    print("\n" + ("Gegentest bestanden." if ok else "GEGENTEST GESCHEITERT."))
    return ok


# ------------------------------------------------------------------ Lauf

def main():
    if "--gegentest" in sys.argv:
        return 0 if gegentest() else 1

    grenze = None
    if "--nur" in sys.argv:
        grenze = int(sys.argv[sys.argv.index("--nur") + 1])
    neu_lesen = "--neu" in sys.argv

    A = json.loads((DATEN / "mvf_artikel.json").read_text(encoding="utf-8"))
    liste = [a for a in A["artikel"].values() if a["doi"] and a["pdf"]]
    # ⚠ NICHT nach dem DOI sortieren: dort steht das Heft VOR dem Jahr,
    # „06.21" kaeme damit vor „03.26". Jahr und Heft getrennt nehmen.
    liste.sort(key=lambda a: (a["jahr"], a["heft"]), reverse=True)
    if grenze:
        liste = liste[:grenze]

    CACHE.mkdir(exist_ok=True)
    habe = {}
    if ZIEL.exists() and not neu_lesen:
        habe = json.loads(ZIEL.read_text(encoding="utf-8")).get("beitraege", {})

    zaehl = collections.Counter()

    def schreiben():
        ZIEL.write_text(json.dumps({
            "stand": time.strftime("%Y-%m-%d"),
            "hinweis": ("Autorenboxen aus den Beitrags-PDFs. Drei Belege, in "
                        "dieser Reihenfolge: Korrespondenzadresse, dann "
                        "Mailbereich, dann Fliesstext. Der Fliesstext allein "
                        "traegt nicht."),
            "zaehlung": dict(zaehl), "beitraege": habe,
        }, ensure_ascii=False, indent=1), encoding="utf-8")

    for k, a in enumerate(liste, 1):
        doi = a["doi"]
        if doi in habe and not neu_lesen:
            zaehl["uebersprungen"] += 1
            continue
        datei = CACHE / (re.sub(r"[^0-9a-z]", "_", doi) + ".pdf")
        if not hol_pdf(a["pdf"], datei):
            habe[doi] = {"titel": a["titel"], "jahr": a["jahr"],
                         "fehler": "PDF nicht ladbar", "autoren": []}
            zaehl["pdf_fehlt"] += 1
            continue
        t = pdf_text(datei)
        if t is None:
            print("KEIN PDF-LESER. Bitte `py -m pip install pypdf`.")
            return 2
        bs = boxen(t)
        habe[doi] = {
            "titel": a["titel"], "heft": a["heft"], "jahr": a["jahr"],
            "rubrik": a["rubrik"], "zeichen": len(t), "autoren": bs,
        }
        zaehl["gelesen"] += 1
        # Was im PDF ueberhaupt zu holen WAERE. Ohne diesen Zaehler ist
        # keine Quote zu beurteilen.
        tt = entsilben(t)
        if ORCID.search(tt) or KORR.search(tt):
            zaehl["box_erwartbar"] += 1
            if bs:
                zaehl["erwartbar_gefunden"] += 1
        if bs:
            zaehl["mit_box"] += 1
            zaehl["autoren"] += len(bs)
            zaehl["mit_orcid"] += sum(1 for x in bs if x["orcid"])
            zaehl["mit_bereich"] += sum(1 for x in bs if x["bereich"])
            zaehl["mit_haus"] += sum(1 for x in bs if x["haus_zeilen"])
            for x in bs:
                zaehl["beleg_" + x["beleg"]] += 1
        else:
            zaehl["ohne_box"] += 1

        if k % 25 == 0 or k == len(liste):
            schreiben()
            print(f"  {k:4d}/{len(liste)} | gelesen {zaehl['gelesen']} | "
                  f"Box {zaehl['mit_box']} | erwartbar {zaehl['box_erwartbar']} "
                  f"davon gefunden {zaehl['erwartbar_gefunden']} | "
                  f"ORCID {zaehl['mit_orcid']}")
        time.sleep(0.2)

    schreiben()
    print()
    for was in ("gelesen", "mit_box", "ohne_box", "box_erwartbar",
                "erwartbar_gefunden", "pdf_fehlt", "autoren", "mit_orcid",
                "mit_bereich", "mit_haus", "uebersprungen"):
        print(f"  {was:<20} {zaehl[was]:5d}")
    for was in sorted(z for z in zaehl if z.startswith("beleg_")):
        print(f"  {was:<20} {zaehl[was]:5d}")
    if zaehl["box_erwartbar"]:
        q = 100 * zaehl["erwartbar_gefunden"] / zaehl["box_erwartbar"]
        print(f"\n  Von den PDFs, die eine Box haben MUESSEN, gefunden: {q:.0f} %")
    oben = collections.Counter()
    for b in habe.values():
        for x in (b.get("autoren") or []):
            if x.get("bereich"):
                oben[x["bereich"]] += 1
    print("\n  haeufigste Mailbereiche:")
    for b, n in oben.most_common(20):
        print(f"    {b:<36} {n:4d}")
    print(f"\n-> daten/mvf_autorenbox.json")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
