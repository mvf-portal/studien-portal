# -*- coding: utf-8 -*-
"""Personen der Versorgungsforschung, mit Einrichtung und Belegen.

WOHER DIE DATEN KOMMEN, und eine Korrektur an mir selbst
--------------------------------------------------------
Ich hatte am 01.11.2026 gemessen und gemeldet: „1.340 Autorenprofile auf
m-vf.de, ALLE ohne Inhaltstext." Das war falsch, und der Fehler war
meiner. Die Schnittstelle /wp-json/wp/v2/autoren liefert tatsaechlich
`acf: []` und kein Feld `content`, weil das Plugin die Felder nicht als
show_in_rest anmeldet. Die AUSGELIEFERTE SEITE traegt den Text aber sehr
wohl. Ich hatte nur die ersten 900 Zeichen angesehen, und darin stand die
Navigation.

Die Sitzung „Archiv ins neue MVF-WordPress" hat das nachgemessen:

    1.340 Profile, davon 1.136 mit Vorstellungstext
    361 mit ORCID   (gegen 44 im alten Archiv)
    1.340 mit Portraet

Das ist die beste Personenquelle, die wir haben. Besser als das Archiv
(603 Profile, 44 ORCID), besser als meine Autorenboxen aus den PDFs (810
Mailbereiche, aber nur dort, wo ein Beitrag eine Box hat).

VIER QUELLEN, jede fuer etwas anderes
-------------------------------------
    wp_autoren.json       Person -> Einrichtung, ORCID, Portraet
    mvf_autorenbox.json   Beitrag -> Person, also die Zuordnung je Artikel
    doi_bezug.json        Studie -> Person, ueber die Ergebnispublikation
    archiv_interviews     84 Paare Person/Einrichtung VON HAND gepflegt

Die vierte ist die genaueste und darum die Eichlatte: An ihr laesst sich
messen, wie gut der automatische Schnitt wirklich ist.

DIE FALLE IM SATZ
-----------------
Ein Vorstellungssatz nennt oft MEHRERE Haeuser, und die spaeteren sind
Vergangenheit:

    „ist wiss. Mitarbeiterin der Charite-Universitaetsmedizin im
     Arbeitsbereich Notfallmedizin. Vorher war sie ..."
    „ist dualer Masterstudent bei Airbus. Davor absolvierte er ein
     duales Bachelorstudium bei Hewlett Packard ..."

Geschnitten wird darum NUR im ersten Satzteil, und der endet am ersten
Punkt oder an einem Rueckblickwort. Wer das nicht tut, haengt Menschen an
ihren vorletzten Arbeitgeber.

  py personen.py              baut daten/personen.json
  py personen.py --gegentest  prueft ohne Netz
  py personen.py --eichen     misst gegen die 84 handgepflegten Paare
"""
import collections
import json
import pathlib
import re
import sys
import time
import unicodedata

HIER = pathlib.Path(__file__).parent
DATEN = HIER / "daten"
# Nur LESEN. Der Ordner gehoert der Sitzung „Archiv ins neue MVF-WordPress".
FREMD = HIER.parent / "mvf-archiv-transfer" / "daten"

sys.path.insert(0, str(HIER))
from einrichtungen import ist_bruchstueck, art_aus_regel   # noqa: E402
from repositorien import kopfwort                          # noqa: E402

# Rechtsformen und Einrichtungsarten, als Teilzeichenketten.
#
# ⚠ BEWUSST OHNE REGULAEREN AUSDRUCK. Ich habe das Muster hier zweimal
# zerstoert: einmal wurde aus dem Wortgrenzenzeichen das Steuerzeichen
# 0x08, einmal frass ein Heredoc die Backslashes. Eine Pruefung auf
# Teilzeichenketten leistet dasselbe und kann nicht kaputtgehen.
RECHTSFORMEN = (
    "gmbh", "mbh", "ggmbh", " ag", "-ag", " se", " kg", "gbr",
    "e.v", "e. v", "institut", "stiftung", "verband", "verein",
    "klinik", "hochschule", "universit", "akademie", "zentrum",
)


def traegt_rechtsform(name):
    """Traegt der Name eine Rechtsform oder eine Einrichtungsart?

    Nur fuer EINWORTNAMEN gebraucht. „aQua-Instituts" ja, „Arzneimittel"
    nein, „Versorgungsqualitaet" nein.
    """
    k = (name or "").lower()
    return any(r in k for r in RECHTSFORMEN)

# Woerter, ab denen der Satz von der Vergangenheit spricht. Alles danach
# ist nicht mehr die heutige Affiliation.
RUECKBLICK = re.compile(
    r"\b(vorher|davor|zuvor|frueher|früher|bis\s+\d{4}|von\s+\d{4}"
    r"|zuletzt\s+war|ehemals|bis\s+zu[rm]|nach\s+dem\s+studium"
    # ⚠ „Zur Zeit der Artikelerstellung" steht im Heft auch als
    # „Artkelerstellung" (Tippfehler) und als „Zur Zeit des Interviews".
    # Ein fester Wortlaut greift darum nicht, es muss das MUSTER sein.
    # Ohne diese Fassung schneidet der Leser „Artikelerstellung" als
    # Einrichtung, gemessen an fuenf der 84 Eichpaare.
    # Der echte Wortlaut im Heft ist „zum ZEITPUNKT der Artikelerstellung",
    # nicht „zur Zeit der". Mit dem falschen Wortlaut schnitt der Leser
    # „Artikelerstellung" als Einrichtung, bei fuenf der 84 Eichpaare.
    r"|aktuell\s*:|zu[rm]\s+zeit(?:punkt)?\s+(?:der|des)\s+\w+)\b", re.I)

# ⚠ EIN SATZ IM IMPERFEKT SAGT NICHTS UEBER HEUTE. „War zum Zeitpunkt der
# Artikelerstellung bayerischer Gesundheitsminister" ist eine Angabe von
# damals. Fuer eine Landkarte von heute ist NICHTS die richtige Antwort,
# nicht die Angabe von damals. Diese Saetze werden gezaehlt, nicht
# geschnitten.
VERGANGEN = re.compile(r"^\s*war\b", re.I)

# Die Praepositionen, hinter denen eine Einrichtung steht. Reihenfolge
# egal, genommen wird der ERSTE Treffer im ersten Satzteil.
VORSATZ = re.compile(
    r"\b(?:bei\s+de[rnm]|bei|an\s+de[rnm]|am|beim|in\s+de[rnm]"
    r"|de[srnm]|im)\s+"
    # ⚠ „aQua-Institut" beginnt KLEIN. Ein kleiner Anfangsbuchstabe ist
    # erlaubt, wenn unmittelbar ein grosser folgt. Sonst faellt jedes
    # Haus dieser Schreibweise durch: aQua, iGES, eHealth, inav.
    r"(?P<name>(?:(?:[A-ZÄÖÜ]|[a-zäöü](?=[A-ZÄÖÜ]))[\wÄÖÜäöüß.&\-]*"
    r"(?:\s+(?:für|und|der|des|die|zur|zum|am|in|von|van|de|e\.\s?V\.|gGmbH"
    r"|GmbH|AG|SE|KG|mbH|e\.V\.)\b)?"
    r"(?:\s+[A-ZÄÖÜ][\wÄÖÜäöüß.&\-]*)*)"
    r"(?:\s*\([A-ZÄÖÜ][\w\-]{1,12}\))?)")

# Rollen und Gremien. Sie stehen hinter derselben Praeposition wie ein
# Haus: „Vorsitzender DES VORSTANDES der DAK-Gesundheit". Ohne diese
# Sperre gewinnt die Rolle, und das Haus eine Fundstelle weiter verliert.
ROLLE = {
    "vorstand", "vorstandes", "vorstands", "vorsitzender", "vorsitzende",
    "geschaeftsfuehrer", "geschaeftsfuehrung", "leiter", "leiterin",
    "leitung", "direktor", "direktorin", "abteilung", "abteilungsleiter",
    "referat", "referent", "referentin", "sprecher", "sprecherin",
    "beirat", "beirats", "aufsichtsrat", "praesident", "praesidentin",
    "dekan", "dekanin", "lehrstuhls", "lehrstuhl", "arbeitsgruppe",
    "projektleiter", "projektleitung", "koordinator", "koordinatorin",
    "mitglied", "mitglieds", "teams", "team", "fachbereichs", "fachbereich",
    "bereichs", "bereich", "ressorts", "ressort", "stabsstelle",
}

# Staedte und Allgemeinwoerter. ⚠ Sie sperren nur, wenn sie den GANZEN
# Namen ausmachen. „Berlin-Chemie AG" ist eine Firma, nicht die Stadt,
# und wer auf das erste Wort sperrt, verliert sie.
KEIN_HAUS = {
    "januar", "februar", "maerz", "april", "mai", "juni", "juli", "august",
    "september", "oktober", "november", "dezember", "bereich", "bereiche",
    "schwerpunkt", "schwerpunkte", "thema", "themen", "rahmen", "auftrag",
    "mittelpunkt", "vordergrund", "jahr", "jahre", "alter", "folgenden",
    "ersten", "zweiten", "dritten", "deutschland", "berlin", "muenchen",
    "koeln", "hamburg", "europa", "bund", "laendern", "praxis", "klinik",
    "krankenhaus", "medizin", "pflege", "forschung", "versorgung",
    "gesundheitswesen", "wissenschaft", "studium", "promotion", "lehre",
}


def norm(s):
    s = (s or "").lower()
    for a, b in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")):
        s = s.replace(a, b)
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return " ".join(s.replace("-", " ").split())


# Der bekannte Einrichtungsbestand, einmal geladen. Register plus
# Innofonds-Partnernetz, zusammen rund 2.400 Namen.
BEKANNT = set()


def _bekannt_laden():
    if BEKANNT:
        return BEKANNT
    E = lade(DATEN / "einrichtungen.json") or {}
    for a in E.get("abschnitte", []):
        for e in a.get("einrichtungen", []):
            BEKANNT.add(norm(e["name"]))
    return BEKANNT


def ankername(k):
    """Die Sprungmarke zu einer Person auf forschende.html.

    Der Schluessel ist „nachname, vorname", der Anker „nachname-vorname".

    ⚠ DIESE REGEL DARF SICH NICHT AENDERN. Die Anker stehen als Adresse in
    suchindex.json und in Lesezeichen. Wer hier etwas verbessert, macht
    jeden bisherigen Personenlink unbrauchbar.

    ⚠ NICHT am Bindestrich zerlegen, um zurueckzurechnen. „Niepraschk-von
    Dollen, Lena" wird „niepraschk-von-dollen-lena", und daraus laesst sich
    der Schluessel nicht wiedergewinnen.
    """
    return (k or "").replace(", ", "-").replace(" ", "-")


def lade(p):
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


# Soviel Autorenprofile hat die Quelle am 02.11.2026. Faellt sie deutlich
# darunter, stimmt etwas nicht.
WP_ERWARTET = 1340
WP_UNTERGRENZE = int(WP_ERWARTET * 0.9)


def pruefe_wordpress(WP):
    """Abbrechen, wenn die Autorenprofile fehlen oder eingebrochen sind.

    ⚠ DIESE QUELLE LIEGT IM ARBEITSORDNER EINER ANDEREN SITZUNG
    (mvf-archiv-transfer/daten/wp_autoren.json). Wer dort gerade baut,
    kann sie kurzzeitig wegnehmen oder halb schreiben.

    Am 02.11.2026 ist genau das passiert, mitten in einem Baulauf.
    `lade(...) or {}` machte daraus still ein leeres Verzeichnis, die
    Kette lief durch, und 281 Menschen verloren ihren Profillink. Auf
    der veroeffentlichten Seite stand bei ihnen "Kein MVF-Profil",
    obwohl sie eines haben. Niemand hat es beim Bauen gemerkt, weil
    nichts gemeldet wurde.

    ⚠ EIN STILL FEHLENDER EINGANG IST SCHLIMMER ALS EIN ABBRUCH. Eine
    Seite, die weniger weiss als gestern, sieht aus wie eine Seite.
    """
    n = len(((WP or {}).get("autoren")) or {})
    if n >= WP_UNTERGRENZE:
        return n
    raise SystemExit(
        "ABBRUCH: nur %d Autorenprofile gelesen, erwartet sind rund %d.\n"
        "  Quelle: %s\n"
        "  Sie liegt im Arbeitsordner der Sitzung mvf-archiv-transfer.\n"
        "  Laeuft dort gerade ein Bau, spaeter erneut versuchen.\n"
        "  Ohne sie verlieren rund 1.300 Menschen ihren Profillink, und\n"
        "  die Seite behauptet dann 'Kein MVF-Profil'."
        % (n, WP_ERWARTET, FREMD / "wp_autoren.json"))


def erster_teil(satz):
    """Nur bis zum ersten Punkt oder Rueckblickwort.

    ⚠ OHNE DIESE GRENZE haengt der Schnitt Menschen an ihren vorletzten
    Arbeitgeber. „ist dualer Masterstudent bei Airbus. Davor absolvierte
    er ein duales Bachelorstudium bei Hewlett Packard" wuerde sonst beide
    liefern, und die zweite Nennung ist Vergangenheit.
    """
    s = " ".join((satz or "").split())
    m = RUECKBLICK.search(s)
    if m:
        s = s[:m.start()]
    # Der erste Punkt, aber nicht der in „Dr." oder „e. V." oder „z. B."
    for m in re.finditer(r"\.(\s+)", s):
        vor = s[max(0, m.start() - 5):m.start() + 1]
        if re.search(r"\b(Dr|Prof|rer|nat|med|phil|pol|oec|jur|habil|Dipl"
                     r"|Univ|PD|MSc|BSc|MA|MBA|ca|bzw|z|B|u|a|e|V|ggf"
                     r"|St|Nr|Abb)\.$", vor):
            continue
        return s[:m.start()]
    return s


def einrichtung_aus_satz(satz):
    """Die heutige Einrichtung, oder nichts.

    Gibt (name, grund). Ist der Name leer, sagt der Grund, warum. Leer
    heisst „nicht sicher erkannt", nie „hat keine".
    """
    if VERGANGEN.match(satz or ""):
        return "", "Satz spricht von damals, nicht von heute"
    teil = erster_teil(satz)
    if not teil:
        return "", "kein Satz"
    for m in VORSATZ.finditer(teil):
        roh = " ".join(m.group("name").split()).strip(" .,;:")
        if len(roh) < 4:
            continue
        # ⚠ EINE ROLLE WIRD ABGESCHNITTEN, NICHT VERWORFEN. Der Treffer
        # „Vorstandes der DAK-Gesundheit" enthaelt das Haus bereits. Wer
        # ihn verwirft, verliert es, denn die Suche laeuft hinter dem
        # ganzen Treffer weiter und sieht „der DAK-Gesundheit" nie.
        teile = roh.split()
        while teile and norm(teile[0]) in ROLLE:
            teile = teile[1:]
            while teile and norm(teile[0]) in {"der", "des", "dem", "den",
                                               "die", "das", "von", "fuer",
                                               "für", "im", "in", "am"}:
                teile = teile[1:]
        roh = " ".join(teile).strip(" .,;:")
        if len(roh) < 4:
            continue
        worte = norm(roh).split()
        kopf = worte[0] if worte else ""
        # Ein Allgemeinwort oder eine Stadt sperrt nur, wenn sie der
        # GANZE Name ist. Sonst faellt „Berlin-Chemie AG" durch.
        if set(worte) <= KEIN_HAUS:
            continue
        # Der geprueffte Waechter: Ein Abteilungsname ohne Haus taugt nicht.
        if ist_bruchstueck(roh):
            continue
        # ⚠ DER KOPFWORT-WAECHTER. Ohne ihn kommen das blosse
        # „Universitaet" und „Wissenschaftlichen Institut" als
        # Einrichtungen durch. Wer kein unterscheidendes Wort hat, ist
        # keine Einrichtung, sondern eine Gattung.
        if not kopfwort(roh):
            continue
        # Ein EINWORTNAME nur, wenn er bekannt ist oder eine Rechtsform
        # traegt. „Charite" steht im Register und kommt durch,
        # „Versorgungsqualitaet" und „Arzneimittel" nicht.
        if len(roh.split()) == 1:
            if not (traegt_rechtsform(roh) or norm(roh) in BEKANNT):
                continue
        return roh, "Vorsatz im ersten Satzteil"
    return "", "kein Haus hinter einer Praeposition im ersten Satzteil"


# ------------------------------------------------------------------ Bau

def bauen():
    _bekannt_laden()
    WP = lade(FREMD / "wp_autoren.json") or {}
    pruefe_wordpress(WP)
    IV = lade(FREMD / "archiv_interviews.json") or {}
    AB = lade(DATEN / "mvf_autorenbox.json") or {}
    SI = lade(DATEN / "suchindex.json") or {}
    SV = lade(DATEN / "standorte.json") or {}

    # Schreibweise -> Standort, fuer die Verbindung Person zu Profilseite.
    profil = {}
    for s in SV.get("standorte", []):
        for w in [s["name"]] + (s.get("schreibweisen") or []):
            profil[norm(w)] = s

    leute = {}

    def schluessel(nach, vor):
        # ⚠ DIESELBE REGEL WIE IN suchindex.py, NICHT EINE ZWEITE.
        # Hier stand eine eigene Fassung, und sie kannte die
        # Punkt-Regel nicht: Nach der Berichtigung dort blieb "Ch.
        # Giulini" hier trotzdem eine eigene Person. Zwei Stellen, die
        # dasselbe entscheiden sollen, driften auseinander.
        sys.path.insert(0, str(HIER))
        from suchindex import personenschluessel
        return personenschluessel(nach, vor)

    zaehl = collections.Counter()
    for v in (WP.get("autoren") or {}).values():
        k = schluessel(v.get("nachname"), v.get("vorname"))
        if not k:
            zaehl["ohne_brauchbaren_namen"] += 1
            continue
        haus, grund = einrichtung_aus_satz(v.get("satz"))
        st = profil.get(norm(haus)) if haus else None
        leute[k] = {
            "name": v.get("name"), "nachname": v.get("nachname"),
            "vorname": v.get("vorname"), "orcid": v.get("orcid") or "",
            "einrichtung": haus, "einrichtung_grund": grund,
            "art": art_aus_regel(haus) if haus else None,
            "standort": st["name"] if st else "",
            "standort_datei": st.get("datei") if st else "",
            "portraet": bool(v.get("portraet")),
            "profil": "https://www.monitor-versorgungsforschung.de/autoren/%s/"
                      % v.get("slug", ""),
            "mvf": 0, "studien": 0, "dkvf": 0, "quellen": ["WordPress"],
        }
        zaehl["aus_wordpress"] += 1
        if haus:
            zaehl["mit_einrichtung"] += 1
        if st:
            zaehl["mit_standort"] += 1
        if v.get("orcid"):
            zaehl["mit_orcid"] += 1

    # Die 84 handgepflegten Paare STECHEN jeden automatischen Schnitt.
    for e in (IV.get("interviews") or []):
        k = schluessel(e.get("nachname"), e.get("vorname"))
        if not k or not e.get("einrichtung"):
            continue
        p = leute.setdefault(k, {
            "name": e.get("name"), "nachname": e.get("nachname"),
            "vorname": e.get("vorname"), "orcid": "", "portraet": False,
            "profil": "", "mvf": 0, "studien": 0, "dkvf": 0, "quellen": [],
        })
        p["einrichtung"] = e["einrichtung"]
        p["einrichtung_grund"] = "Interviewtabelle, von Hand gepflegt"
        p["art"] = art_aus_regel(e["einrichtung"])
        st = profil.get(norm(e["einrichtung"]))
        p["standort"] = st["name"] if st else p.get("standort", "")
        p["standort_datei"] = st.get("datei") if st else p.get("standort_datei", "")
        if "Interviewtabelle" not in p["quellen"]:
            p["quellen"].append("Interviewtabelle")
        zaehl["aus_interviewtabelle"] += 1

    # Die Belege aus dem Suchindex anhaengen: Studien, MVF, DKVF.
    for e in (SI.get("eintraege") or []):
        if e["t"] != "person":
            continue
        # ⚠ NICHT aus der Ankeradresse zurueckrechnen. Der Schluessel steht
        # seit 01.11.2026 als Feld „k" im Index. Wer am Bindestrich trennt,
        # zerlegt „Niepraschk-von Dollen" falsch.
        k = e.get("k")
        if not k:
            continue
        z = e["z"] or {}
        if k not in leute:
            # Menschen ohne WordPress-Profil: Sie forschen, aber sie haben
            # bei uns nie publiziert. Frueher fielen sie hier heraus, und
            # darum zeigten alle Personenlinks der Suche ins Leere.
            # ⚠ rpartition GIBT (DAVOR, TRENNER, DANACH). Der
            # Nachname steht HINTEN. Bis zum 01.11.2026 stand hier
            # „nach, _, vor", und 4.056 Personen trugen den Vornamen als
            # Nachnamen. Gemessen gegen den Schluessel, der richtig ist.
            vor, _, nach = (e["n"] or "").rpartition(" ")
            leute[k] = {
                "name": e["n"], "nachname": nach or e["n"], "vorname": vor,
                "orcid": "", "portraet": False, "profil": "",
                "mvf": 0, "studien": 0, "dkvf": 0, "quellen": [],
            }
            zaehl["ohne_wordpress_profil"] += 1
            for h in (z.get("haeuser") or []):
                leute[k]["einrichtung"] = h
                leute[k]["einrichtung_grund"] = \
                    "ROR-Kennung der Publikation"
                break
        leute[k]["mvf"] = z.get("mvf", 0)
        leute[k]["studien"] = z.get("studien", 0)
        leute[k]["dkvf"] = z.get("dkvf", 0)
        zaehl["mit_belegen"] += 1

    # Die ORCID aus den Autorenboxen ergaenzen, wo WordPress keine hat.
    for b in (AB.get("beitraege") or {}).values():
        for a in (b.get("autoren") or []):
            if not a.get("orcid"):
                continue
            t = (a.get("name") or "").replace(",", " ").split()
            if len(t) < 2:
                continue
            k = schluessel(t[-1], t[0] if len(t[0]) > 2 else
                           (t[1] if len(t) > 2 else t[0]))
            if k and k in leute and not leute[k]["orcid"]:
                leute[k]["orcid"] = a["orcid"]
                zaehl["orcid_aus_pdf"] += 1

    # ⚠ ERST HIER, nachdem alle Quellen zusammengefuehrt sind. In der
    # Belegschleife bekamen nur die 4.615 mit Beleg einen Anker, und die
    # uebrigen 779 waren von der Seite aus nicht erreichbar.
    for k in leute:
        leute[k]["anker"] = ankername(k)

    raus = {
        "stand": time.strftime("%Y-%m-%d"),
        "quellen": {
            "wp_autoren.json": "ausgelieferte Profilseiten auf m-vf.de",
            "archiv_interviews.json": "84 von Hand gepflegte Paare",
            "mvf_autorenbox.json": "Autorenboxen aus den Beitrags-PDFs",
            "suchindex.json": "Belege aus Studien, MVF und DKVF",
        },
        "hinweis": ("Die Einrichtung ist aus dem Vorstellungssatz "
                    "geschnitten, NUR aus dem ersten Satzteil. Leer heisst "
                    "„nicht sicher erkannt“, nie „hat keine“."),
        "zaehlung": dict(zaehl),
        "personen": leute,
    }
    # ⚠ REDAKTION IST KEINE FORSCHUNG. Drei Menschen fuellen seit Jahren
    # jedes Heft mit Nachrichten, Interviews und Editorials und standen
    # damit ganz oben in einer Liste, die nach Forschungsbelegen sortiert.
    # Die Regel und die Begruendung stehen in zuschnitt.py, nicht hier.
    sys.path.insert(0, str(HIER))
    from zuschnitt import REDAKTION, EINRICHTUNG_VON_HAND

    # ⚠ HANDKORREKTUR STICHT DEN AUTOMATISCHEN SCHNITT. Begruendung je
    # Fall in zuschnitt.py. Gesetzt wird erst hier, damit die Zaehlung
    # oben misst, was die Regel von allein schafft.
    von_hand = 0
    for k, haus in EINRICHTUNG_VON_HAND.items():
        if k in leute:
            leute[k]["einrichtung"] = haus
            leute[k]["einrichtung_grund"] = "von Hand gesetzt, siehe zuschnitt.py"
            leute[k]["art"] = art_aus_regel(haus)
            von_hand += 1
        else:
            print("  HINWEIS: %r steht in EINRICHTUNG_VON_HAND, aber nicht "
                  "im Bestand" % k)
    # ⚠ NICHT NUR zaehl, SONDERN AUCH DIE AUSGABE. Das Verzeichnis
    # mit "zaehlung" wird weiter oben gebaut, ein spaeteres zaehl[...]
    # kaeme dort nie an - die Zahl stand als None in der Datei.
    zaehl["einrichtung_von_hand"] = von_hand
    raus["zaehlung"]["einrichtung_von_hand"] = von_hand

    weg = [k for k in leute if k in REDAKTION]
    for k in weg:
        del leute[k]
    zaehl["redaktion_ausgeblendet"] = len(weg)
    if weg:
        print("  ausgeblendet, weil Redaktion: %s" % ", ".join(sorted(weg)))

    ziel = DATEN / "personen.json"
    ziel.write_text(json.dumps(raus, ensure_ascii=False, indent=1),
                    encoding="utf-8")
    return raus, ziel


# ------------------------------------------------------------ Gegentest

PROBEN = [
    # (Satz, erwartete Einrichtung)
    ("ist am IGES Institut als Geschäftsführer und Leiter des Bereiches "
     "Gesundheitspolitik zuständig.", "IGES Institut"),
    ("ist seit 2017 Geschäftsführer des aQua-Instituts. Er hat als wiss. "
     "Mitarbeiter des aQua-Instituts von 1996 bis 2004 gearbeitet.",
     "aQua-Instituts"),
    ("ist Produktgruppenleiter Diabetes bei der Berlin-Chemie AG und "
     "verfügt über mehr als 25 Jahre Pharmaerfahrung.", "Berlin-Chemie AG"),
    ("ist Studentin der Gesundheitsökonomie im sechsten Semester an der "
     "Hochschule Fresenius in Idstein.", "Hochschule Fresenius"),
    ("entwickelt und begleitet als Mitarbeiterin der AOK Nordost im "
     "Unternehmensbereich Versorgungsmanagement Selektivverträge.",
     "AOK Nordost"),
    ("ist Vorsitzender des Vorstandes der DAK-Gesundheit. Er verantwortet "
     "bei der DAK-Gesundheit die Bereiche Strategie.", "DAK-Gesundheit"),
]

# Diese duerfen NICHTS liefern. Das ist die Gegenprobe.
LEER = [
    "studierte Erziehungswissenschaften sowie Medizinwissenschaften und "
    "promovierte.",
    "ist Facharzt für Innere Medizin, Endokrinologie und Diabetologie.",
    "arbeitet seit vielen Jahren im Bereich der Versorgungsforschung.",
    "",
]


def gegentest():
    _bekannt_laden()
    ok = True
    print("Der erste Satzteil endet am Rueckblick, nicht am Grad:")
    for roh, soll in (
            ("ist Masterstudent bei Airbus. Davor war er bei HP.",
             "ist Masterstudent bei Airbus"),
            # Der Schlusspunkt bleibt stehen, weil ihm kein Leerzeichen
            # folgt. Das stoert nicht, der Schnitt kommt davor.
            ("ist Dr. rer. nat. und arbeitet bei der AOK.",
             "ist Dr. rer. nat. und arbeitet bei der AOK."),
            ("ist bei X. Vorher bei Y.", "ist bei X"),
            ("leitet das Institut seit 2019", "leitet das Institut seit 2019"),
            ("ist bei A tätig, von 2010 bis 2015 bei B", "ist bei A tätig,")):
        ist = erster_teil(roh)
        gut = ist.strip() == soll.strip()
        ok = ok and gut
        print(f"  {'ok ' if gut else 'FEHLER'} {ist!r}")

    print("\nEinrichtung aus dem Satz:")
    for satz, soll in PROBEN:
        ist, grund = einrichtung_aus_satz(satz)
        gut = ist == soll
        ok = ok and gut
        print(f"  {'ok ' if gut else 'FEHLER'} {ist!r:<32} "
              f"soll {soll!r}")

    print("\nGEGENPROBE: diese Saetze duerfen NICHTS liefern:")
    for satz in LEER:
        ist, grund = einrichtung_aus_satz(satz)
        gut = ist == ""
        ok = ok and gut
        print(f"  {'ok ' if gut else 'FEHLER'} {satz[:52]!r:<56} -> {ist!r}")

    print("\nGEGENPROBE: der zweite Arbeitgeber darf nie gewinnen:")
    ist, _ = einrichtung_aus_satz(
        "ist dualer Masterstudent bei Airbus. Davor absolvierte er ein "
        "duales Bachelorstudium bei Hewlett Packard Enterprise.")
    # ⚠ GEPRUEFT WIRD DIE EIGENSCHAFT, NICHT EIN BESTIMMTES ERGEBNIS.
    # „Airbus" faellt heute durch, weil ein Einwortname ohne Rechtsform
    # und ohne Eintrag im Bestand abgewiesen wird, und das ist richtig.
    # Entscheidend bleibt: Der ZWEITE Arbeitgeber darf nie gewinnen.
    gut = "hewlett" not in (ist or "").lower()
    ok = ok and gut
    print(f"  {'ok ' if gut else 'FEHLER'} {ist!r} (Hewlett darf nicht "
          f"vorkommen)")

    print("\n" + ("Gegentest bestanden." if ok else "GEGENTEST GESCHEITERT."))
    return ok


def eichen():
    _bekannt_laden()
    """Gegen die 84 von Hand gepflegten Paare messen.

    ⚠ Eine Quote ist erst eine Messung, wenn es eine Latte gibt, an der
    sie haengt. Die Interviewtabelle ist diese Latte: Person und
    Einrichtung stehen dort in getrennten, handgepflegten Spalten.
    """
    IV = lade(FREMD / "archiv_interviews.json") or {}
    WP = lade(FREMD / "wp_autoren.json") or {}
    pruefe_wordpress(WP)
    nach_name = {}
    for v in (WP.get("autoren") or {}).values():
        if v.get("nachname") and v.get("vorname"):
            nach_name[(norm(v["nachname"]),
                       norm(v["vorname"]).split()[0]
                       if norm(v["vorname"]).split() else "")] = v

    treffer = fehl = ohne = nicht_da = damals = 0
    beispiele = []
    for e in (IV.get("interviews") or []):
        if not e.get("einrichtung") or not e.get("nachname"):
            continue
        vn = norm(e.get("vorname") or "").split()
        v = nach_name.get((norm(e["nachname"]), vn[0] if vn else ""))
        if not v:
            nicht_da += 1
            continue
        ist, _grund = einrichtung_aus_satz(v.get("satz"))
        soll = e["einrichtung"]
        if not ist:
            if _grund.startswith("Satz spricht von damals"):
                # Das ist KEIN Versagen. Die Handtabelle haelt das Jahr
                # des Interviews, der Satz sagt selbst, dass er von
                # damals spricht. Fuer heute waere jede Angabe falsch.
                damals += 1
            else:
                ohne += 1
            continue
        # ⚠ DER VERGLEICH DARF NICHT SELBST DER FEHLER SEIN. „BARMER GEK"
        # und „BarmerGEK" sind dasselbe, „GKV-Spitzenverbands" und
        # „Spitzenverband Bund" auch. Verglichen wird darum auf
        # Wortstaemmen und zusaetzlich auf Enthaltensein ohne Leerzeichen.
        def stamm(w):
            for e in ("es", "en", "er", "s", "n"):
                if len(w) > 5 and w.endswith(e):
                    return w[:-len(e)]
            return w
        a = {stamm(w) for w in norm(ist).split() if len(w) > 3}
        b = {stamm(w) for w in norm(soll).split() if len(w) > 3}
        # ⚠ NICHT „ohne" nennen: So heisst schon der Zaehler fuenf Zeilen
        # weiter unten, und die Zuweisung wuerde ihn still ueberschreiben.
        # Dieselbe Falle wie frueher bei „zeilen" und „verzeichnis".
        def gepresst(x):
            return norm(x).replace(" ", "")
        if ((a & b) or gepresst(ist) in gepresst(soll)
                or gepresst(soll) in gepresst(ist)):
            treffer += 1
        else:
            fehl += 1
            if len(beispiele) < 8:
                beispiele.append((v.get("name", "")[:26], ist[:30], soll[:30]))

    gesamt = treffer + fehl + ohne
    print("Eichung gegen die 84 handgepflegten Paare")
    print(f"  in beiden Bestaenden      {gesamt}")
    print(f"  nicht in WordPress        {nicht_da}")
    print(f"  Einrichtung getroffen     {treffer}")
    print(f"  Einrichtung daneben       {fehl}")
    print(f"  nichts geschnitten        {ohne}")
    print(f"  bewusst nichts, Satz von damals  {damals}")
    if gesamt:
        print(f"\n  getroffen {100*treffer/gesamt:.0f} %, "
              f"daneben {100*fehl/gesamt:.0f} %, "
              f"nichts {100*ohne/gesamt:.0f} %")
    print("\n  Wo es danebenging:")
    for n, i, s in beispiele:
        print(f"    {n:<26} geschnitten {i!r:<32} von Hand {s!r}")
    return 0


def main():
    if "--gegentest" in sys.argv:
        return 0 if gegentest() else 1
    if "--eichen" in sys.argv:
        return eichen()
    raus, ziel = bauen()
    z = raus["zaehlung"]
    for was in ("aus_wordpress", "mit_einrichtung", "mit_standort",
                "mit_orcid", "orcid_aus_pdf", "aus_interviewtabelle",
                "mit_belegen", "ohne_brauchbaren_namen"):
        print(f"  {was:<24} {z.get(was, 0):5d}")
    print(f"  {'Personen gesamt':<24} {len(raus['personen']):5d}")
    if z.get("aus_wordpress"):
        print(f"\n  Einrichtung erkannt bei "
              f"{100*z.get('mit_einrichtung',0)/z['aus_wordpress']:.0f} % "
              f"der WordPress-Profile")
    print(f"\n-> daten/personen.json")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
