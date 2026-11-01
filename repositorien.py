# -*- coding: utf-8 -*-
"""Verbindet die 82 Forschungsstandorte mit den Publikationsverzeichnissen
ihrer eigenen Einrichtung - und gleicht ab, was dort steht.

Die Ausgangsfrage war: „Es muss von jeder Uni solche Repositories geben."
Richtig - aber nicht in einer Form, die man abfragen kann. Die Probe am
Beispiel (Publikationsliste Prof. Schmitt, ZEGV Dresden) zeigt eine von Hand
gepflegte Plone-Seite: Freitextzitate in wechselndem Stil, Doppeleintraege,
Impact-Faktoren mitten im Text, kein Export, keine Schnittstelle. Als
Verweisziel taugt sie, als Datenquelle nicht.

Abfragbar ist eine Schicht darunter, und zwar in drei Stufen:

  1. ROR    - die Identitaet der Einrichtung (ID, Typ, Ort, Koordinaten,
              Netzadresse, Namensvarianten). Hochschulen fuer angewandte
              Wissenschaften sind enthalten, Typ `education`.
  2. OpenAlex - haengt an derselben ROR-ID: Einrichtungstyp, Zahl der
              Arbeiten, Namensvarianten und - hier entscheidend - die Liste
              der **eigenen Repositorien** der Einrichtung.
  3. OpenDOAR / OAI-PMH - das Repositorium selbst, maschinenlesbar.

WARUM EIN WAECHTER NOETIG IST
Die ROR-Namensauflösung trifft derselben Klasse von Fehlern auf wie unsere
eigene Verschmelzungsregel (siehe bestandsbezug.py). Gemessen am 31.10.2026:

  „Charité - Universitätsmedizin Berlin"
      -> Charité (0,94) ... aber NICHT als `chosen` markiert
      -> „Wasserstraßen-Neubauamt Berlin" (0,89)   nur wegen „Berlin"
  „Zentralinstitut für die kassenärztliche Versorgung in Deutschland"
      -> „BIO Deutschland" (0,90)                  nur wegen „Deutschland"
  „Institut für Allgemeinmedizin, Universitätsklinikum Frankfurt"
      -> Frankfurt (0,98) und das Institut der LMU Muenchen (0,98), gleich hoch

Der `chosen`-Schalter von ROR hilft also nicht: er laesst die Charité fallen
und waere bei „BIO Deutschland" nicht sicherer. Deshalb nimmt dieses Modul
einen Treffer nur an, wenn mindestens ein UNTERSCHEIDENDES Wort (keines aus
dem Rauschen, kein blosser Ortsname) im ROR-Namen oder einer Namensvariante
wiederkehrt. Der Gegentest prueft genau die drei Faelle oben.

Vorrang hat immer die handgepruefte Liste des Innovationsfonds-Portals
(`innovationsfonds/db/ror_cache.json`, 1.251 Zuordnungen, nur gelesen).

Aufruf:  py repositorien.py
         py repositorien.py --gegentest
         py repositorien.py --ohne-netz      (nur Cache, keine Abfragen)
"""
from __future__ import annotations

import argparse
import collections
import json
import pathlib
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request

HIER = pathlib.Path(__file__).resolve().parent
DATEN = HIER / "daten"
INNO_CACHE = HIER.parent / "innovationsfonds" / "db" / "ror_cache.json"
ZIEL = DATEN / "repositorien.json"
MAILTO = "peterstegmaier7@gmail.com"

sys.path.insert(0, str(HIER))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import bestandsbezug  # noqa: E402  - nur fuer die Rauschliste

# Ortsnamen unterscheiden eine Einrichtung nicht: in Berlin sitzen Dutzende.
# Genau hieran scheiterte die ROR-Auflösung (Wasserstraßen-Neubauamt Berlin).
ORTE_RAUSCHEN = {
    "berlin", "hamburg", "muenchen", "koeln", "frankfurt", "stuttgart",
    "duesseldorf", "dortmund", "essen", "leipzig", "bremen", "dresden",
    "hannover", "nuernberg", "duisburg", "bochum", "wuppertal", "bielefeld",
    "bonn", "muenster", "karlsruhe", "mannheim", "augsburg", "wiesbaden",
    "mainz", "kiel", "aachen", "magdeburg", "freiburg", "luebeck", "erfurt",
    "rostock", "jena", "halle", "wuerzburg", "regensburg", "heidelberg",
    "greifswald", "marburg", "giessen", "tuebingen", "ulm", "goettingen",
    "homburg", "witten", "herdecke", "oldenburg", "potsdam", "saarbruecken",
    "deutschland", "germany", "bundesrepublik", "german",
    # Landesteile tragen genauso wenig wie Bundeslaender. Gemessener Fehlgriff:
    # „Kleine Riesen Nordhessen gGmbH" dockte ueber „Nordhessen" an der
    # „Diploma Fachhochschule Nordhessen" an - Punktwert 0,60.
    "nordhessen", "mittelhessen", "osthessen", "suedhessen", "ostwestfalen",
    "niederrhein", "oberfranken", "mittelfranken", "unterfranken", "franken",
    "schwaben", "oberbayern", "niederbayern", "oberpfalz", "nordbayern",
    "suedwest", "nordwest", "nordost", "suedost", "lippe", "weser", "ems",
}

# Bundeslaender unterscheiden keine Einrichtung - aber zusammen mit der Art
# tun sie es: „Universitätsklinikum Schleswig-Holstein" hat gar keinen
# Stadtnamen im Titel, es gibt davon nur eines. Das Land muss darum in
# Regel (b) wie ein Ort zaehlen.
BUNDESLAENDER = {
    "baden", "wuerttemberg", "bayern", "bayerische", "bayerisches",
    "brandenburg", "hessen", "mecklenburg", "vorpommern", "niedersachsen",
    "nordrhein", "westfalen", "rheinland", "pfalz", "saarland", "sachsen",
    "anhalt", "schleswig", "holstein", "thueringen",
}

# Woerter, die jede Forschungseinrichtung von sich sagt. Gemessener
# Fehlgriff: „LVR-Institut für Forschung und Bildung" dockte ueber
# „Forschung" am „Institut für Forschung und Transfer" in Dortmund an.
RAUSCHEN_ALLGEMEIN = {
    "forschung", "forschungs", "forschungszentrum", "forschungsinstitut",
    "bildung", "transfer", "wissenschaft", "wissenschaftliche", "versorgung",
    "gesundheit", "gesundheitswesen", "praxis", "deutsche", "deutscher",
    "deutsches", "bundesweit", "angewandter", "research", "science",
}
# Woerter, die die ART der Einrichtung benennen, nicht welche. Sie allein
# unterscheiden nichts („Hochschule" teilt die HAW Hamburg mit der Hochschule
# Hof), tragen aber ZUSAMMEN mit dem Ort: „Universitätsklinikum Frankfurt"
# und „University Hospital Frankfurt" sind dasselbe Haus, und das ist nur an
# Ort plus Art zu erkennen - einen eigenen Namen hat es nicht.
KLASSE = {
    "universitaet", "universitaets", "universitaetsklinikum", "universitaetsmedizin",
    "universitaetsspital", "hochschule", "fachhochschule", "klinikum", "klinik",
    "university", "hospital", "medical", "college", "angewandte", "wissenschaften",
    "applied", "sciences", "technische", "technical", "medizinische", "fakultaet",
    "faculty", "universitaetsklinik",
}
RAUSCHEN = (set(bestandsbezug.RAUSCHEN) | ORTE_RAUSCHEN | KLASSE
            | RAUSCHEN_ALLGEMEIN)

# Unter diesem Punktwert wird ein ROR-Treffer gar nicht erst betrachtet.
# „Diploma Hochschule" kam mit 0,60 durch, „Institut für Forschung und
# Transfer" mit 0,82 - beide falsch. Richtige Treffer lagen bei 0,90 bis 1,00.
PUNKTWERT_MINDESTENS = 0.90


def norm(s: str) -> str:
    """Erst Umlaute aufloesen, DANN Akzente abwerfen - sonst faellt das é weg."""
    s = (s or "").lower()
    s = (s.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue")
           .replace("ß", "ss").replace("–", " ").replace("-", " "))
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def kennwoerter(name: str) -> set[str]:
    """Die Woerter, die diese Einrichtung von anderen unterscheiden."""
    return {w for w in norm(name).split() if len(w) > 2 and w not in RAUSCHEN}


# OpenAlex fuehrt Staedte in englischer Form. Ohne diese Tabelle meldet der
# Ortsabgleich 9 Fehlalarme (Munich/München, Cologne/Köln, Hanover/Hannover)
# und verdeckt damit die drei echten Funde.
STADT_GLEICH = {
    "munich": "muenchen", "cologne": "koeln", "hanover": "hannover",
    "nuremberg": "nuernberg", "brunswick": "braunschweig",
    "freiburg im breisgau": "freiburg", "frankfurt am main": "frankfurt",
    "halle (saale)": "halle", "vienna": "wien", "zurich": "zuerich",
    "mayence": "mainz", "treves": "trier", "ratisbon": "regensburg",
}


def stadt(s: str) -> str:
    n = norm(s)
    return STADT_GLEICH.get(n, n)


def kopfwort(name: str) -> str | None:
    """Das erste unterscheidende Wort - es traegt den Namen.

    „Kleine Riesen Nordhessen gGmbH" -> „kleine". „LVR-Institut für Forschung
    und Bildung" -> „lvr". Wer das Kopfwort nicht teilt, ist eine andere
    Einrichtung, auch wenn ein spaeteres Wort zufaellig uebereinstimmt.
    """
    for w in norm(name).split():
        if len(w) > 2 and w not in RAUSCHEN:
            return w
    return None


def orte(name: str) -> set[str]:
    """Stadt ODER Bundesland - beides verortet die Einrichtung."""
    w = set(norm(name).split())
    return (w & ORTE_RAUSCHEN) | (w & BUNDESLAENDER)


def klassen(name: str) -> set[str]:
    return {w for w in norm(name).split() if w in KLASSE}


def traegt(anfrage: str, kandidat: str, aliase: list[str]) -> bool:
    """Darf dieser ROR-Treffer angenommen werden?

    Zwei Wege fuehren hin, und beide wurden an echten Fehltreffern geschaerft:

      (a) Ein UNTERSCHEIDENDES Wort kehrt wieder - „charite", „socium",
          „zentralinstitut". Das ist der Regelfall.
      (b) Die Einrichtung hat gar keinen eigenen Namen, nur Art und Ort:
          „Universitätsklinikum Frankfurt". Dann muessen BEIDE uebereinstimmen.

    Weg (b) ist die Huerde, an der die Fehltreffer scheitern:
    „Wasserstraßen-Neubauamt Berlin" teilt den Ort, aber keine Art;
    „BIO Deutschland" teilt „Deutschland", aber die Anfrage nennt keine Art;
    „Hochschule Hof" teilt die Art, aber nicht den Ort.
    """
    a_kenn, a_ort, a_klasse = kennwoerter(anfrage), orte(anfrage), klassen(anfrage)
    kopf = kopfwort(anfrage)
    def fremder_kopf(text: str) -> bool:
        """Traegt dieser Name ein Kopfwort, das die Anfrage nicht kennt?

        Dann ist er ENGER als die Anfrage - ein Teil, nicht das Ganze.
        Gemessener Fall: die Innofonds-Liste fuehrt „LMU Klinikum München"
        auf das „Institut für Infektions- und Tropenmedizin". Ueber die
        Variante „Tropeninstitut am LMU Klinikum München" teilen beide
        „lmu", und Ort und Art stimmen auch - aber das Tropeninstitut ist
        ein Teil des Klinikums, nicht das Klinikum.
        """
        kw = kopfwort(text)
        return kw is not None and kw not in a_kenn

    for text in [kandidat, *aliase]:
        if fremder_kopf(text):
            continue
        gemeinsam = a_kenn & kennwoerter(text)
        # Nicht JEDES gemeinsame Wort reicht: es muss das Kopfwort sein, also
        # das erste unterscheidende Wort des Namens. Sonst genuegt ein
        # beiliegendes „Nordhessen" oder „Forschung" fuer einen Fehltreffer.
        if gemeinsam and (kopf is None or kopf in gemeinsam):
            return True
    if not (a_ort and a_klasse):
        return False
    for text in [kandidat, *aliase]:
        if fremder_kopf(text):
            continue
        if (a_ort & orte(text)) and (a_klasse & klassen(text)):
            return True
    return False


# ---------------------------------------------------------------- Netzabfragen

def _hol(url: str, versuche: int = 3) -> dict:
    letzte: Exception | None = None
    for i in range(versuche):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": f"MVF-Versorgungsstudien-Landkarte ({MAILTO})"})
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:  # noqa: BLE001
            letzte = e
            time.sleep(1.5 * (i + 1))
    raise RuntimeError(f"Abfrage fehlgeschlagen: {url}\n  {letzte}")


def _ror_frage(anfrage: str, pruefname: str):
    """Eine ROR-Abfrage, gewaechtert gegen `pruefname`.

    Geprueft wird IMMER gegen den vollen Namen aus dem Register, auch wenn
    die Abfrage verkuerzt war - sonst pruefte der Waechter nur noch seine
    eigene Vorauswahl.
    """
    url = ("https://api.ror.org/v2/organizations?affiliation="
           + urllib.parse.quote(anfrage))
    d = _hol(url)
    bester = None
    for it in d.get("items", []):
        if it["score"] < PUNKTWERT_MINDESTENS:
            continue
        o = it["organization"]
        anzeige = next((n["value"] for n in o.get("names", [])
                        if "ror_display" in n.get("types", [])), "")
        aliase = [n["value"] for n in o.get("names", [])]
        if not traegt(pruefname, anzeige, aliase):
            continue
        if bester is None or it["score"] > bester[0]:
            bester = (it["score"], o["id"], anzeige)
    return bester


def ror_suchen(name: str) -> tuple[str | None, str, str]:
    """(ROR-ID, angenommener Name, Begruendung) - oder (None, '', Grund).

    ZWEI Anlaeufe. Der ROR-Abgleicher kann sich an einem Allerweltswort
    festbeissen und den offensichtlichen Treffer gar nicht erst liefern:

        „Charité Campus Charité Mitte"
            -> International College of Business and Technology  0,82
            -> University of Rizal System-Cainta                 0,77
            -> CINEC Campus (Pvt) Ltd.                           0,75
        „Charité"
            -> Charité – Universitätsmedizin Berlin              1,00

    „Campus" hat die Abfrage uebernommen, „Charité" fiel weg. Darum: Wenn
    der erste Anlauf nichts liefert, das KOPFWORT allein fragen - das erste
    nicht-generische Wort. Der Waechter prueft danach weiter gegen den
    vollen Namen, und der Ortsabgleich kommt ohnehin noch.
    """
    try:
        bester = _ror_frage(name, name)
    except RuntimeError as e:
        return None, "", f"Abfrage fehlgeschlagen: {e}"
    if bester:
        return (bester[1], bester[2],
                "ROR-Namensauflösung, Punktwert %.2f" % bester[0])

    kopf = kopfwort(name)
    if not kopf or norm(name).strip() == kopf:
        return None, "", "kein Treffer haelt dem Waechter stand"
    # MIT Umlauten fragen. `kopfwort` liefert die normalisierte Form, und
    # ROR findet „charite" nicht, „Charité" dagegen mit Punktwert 1,00.
    # Also das Originalwort heraussuchen, dessen Normalform das Kopfwort ist.
    frage = next((w.strip(",;:()") for w in name.split()
                  if norm(w.strip(",;:()")) == kopf), kopf)
    try:
        time.sleep(0.2)
        bester = _ror_frage(frage, name)
    except RuntimeError as e:
        return None, "", f"Abfrage fehlgeschlagen: {e}"
    if bester:
        return (bester[1], bester[2],
                "ROR-Namensauflösung über das Kopfwort „" + kopf
                + "“, Punktwert %.2f" % bester[0])
    return None, "", "kein Treffer haelt dem Waechter stand"


def _quelle(quell_id: str) -> dict | None:
    """Der Quellendatensatz eines Repositoriums - dort steht die Adresse."""
    if not quell_id:
        return None
    url = (f"https://api.openalex.org/sources/{quell_id.rsplit('/', 1)[-1]}"
           f"?mailto={urllib.parse.quote(MAILTO)}")
    try:
        d = _hol(url)
        time.sleep(0.15)
        return d
    except RuntimeError:
        return None


def openalex(ror: str) -> dict | None:
    url = (f"https://api.openalex.org/institutions/{ror}"
           f"?mailto={urllib.parse.quote(MAILTO)}")
    try:
        return _hol(url)
    except RuntimeError:
        return None


# ------------------------------------------------------------------- Gegentest

def gegentest() -> int:
    """Die drei gemessenen Fallen muessen abgewiesen werden."""
    faelle = [
        # (Anfrage, ROR-Name des Kandidaten, Aliase, darf angenommen werden?)
        ("Charité - Universitätsmedizin Berlin",
         "Charité – Universitätsmedizin Berlin", ["Charité"], True),
        ("Charité - Universitätsmedizin Berlin",
         "Wasserstraßen-Neubauamt Berlin", [], False),
        ("Zentralinstitut für die kassenärztliche Versorgung in Deutschland",
         "BIO Deutschland", [], False),
        ("Zentralinstitut für die kassenärztliche Versorgung in Deutschland",
         "Diakonie Deutschland", [], False),
        ("Zentralinstitut für die kassenärztliche Versorgung in Deutschland",
         "Zentralinstitut für die kassenärztliche Versorgung", ["Zi"], True),
        ("Institut für Allgemeinmedizin, Universitätsklinikum Frankfurt",
         "University Hospital Frankfurt", ["Universitätsklinikum Frankfurt"], True),
        ("Hochschule für Angewandte Wissenschaften Hamburg",
         "HAW Hamburg", ["Hochschule für Angewandte Wissenschaften Hamburg"], True),
        ("Hochschule für Angewandte Wissenschaften Hamburg",
         "Hof University of Applied Sciences", ["Hochschule Hof"], False),
        # Ein erfundener Name darf nirgends andocken.
        ("Wolkenkuckucksheimer Forschungsstelle", "Universitätsklinikum Köln",
         [], False),
        # Reine Rechtsform- und Ortsgleichheit reicht nicht.
        ("Klinikum der Universität München", "Universitätsklinikum Hamburg-Eppendorf",
         [], False),
        # Gleiche Art, verschiedene Stadt - zwei verschiedene Haeuser.
        ("Universitätsklinikum Köln", "Universitätsklinikum Bonn", [], False),
        # Gleiche Stadt, verschiedene Art - Uniklinik ist nicht Universitaet.
        ("Universitätsklinikum Frankfurt", "Goethe-Universität Frankfurt am Main",
         [], False),
        # Der eigene Name traegt auch ohne Ort.
        ("SOCIUM Forschungszentrum Ungleichheit und Sozialpolitik",
         "SOCIUM Research Center on Inequality and Social Policy", [], True),
        # Behoerde mit Ort, aber ohne Art: darf nicht an eine Klinik andocken.
        ("Robert Koch-Institut", "Universitätsklinikum Berlin", [], False),
        # Am 31.10.2026 gemessene Fehltreffer - sie muessen fallen.
        ("Kleine Riesen Nordhessen gGmbH", "Diploma Hochschule",
         ["Diploma Fachhochschule Nordhessen", "Diploma University"], False),
        ("LVR-Institut für Forschung und Bildung",
         "Institut für Forschung und Transfer", [], False),
        # Das Fach allein traegt nicht: der ROR-Eintrag „Institut für
        # Allgemeinmedizin" ist der der LMU Muenchen. Ein gleichnamiges
        # Institut in Jena darf dort nicht andocken - sonst waere es
        # derselbe Fehler wie die sieben verschmolzenen Psychiatrien.
        ("Institut für Allgemeinmedizin, Universitätsklinikum Jena",
         "Institut für Allgemeinmedizin", ["Institut für Allgemeinmedizin"], False),
        # Ueber Art und Ort findet dieselbe Anfrage aber ihr Haus.
        ("Institut für Allgemeinmedizin, Universitätsklinikum Jena",
         "Universitätsklinikum Jena", ["Jena University Hospital"], True),
        ("Deutsches Zentrum für Herz-Kreislauf-Forschung",
         "Institut für Forschung und Transfer", [], False),
        # Der Kandidat ist enger als die Anfrage - ein Teil, nicht das Ganze.
        ("LMU Klinikum München", "Institut für Infektions- und Tropenmedizin",
         ["Tropeninstitut am LMU Klinikum München", "Tropeninstitut"], False),
        # Umgekehrt traegt es: der Kandidat ist das Haus, die Anfrage ein Teil.
        ("Charité - Universitätsmedizin Berlin, Institut für Allgemeinmedizin",
         "Charité – Universitätsmedizin Berlin", ["Charité"], True),
    ]
    print("Gegentest Waechter der Namensauflösung:\n")
    ok = True
    for anfrage, kandidat, aliase, erwartet in faelle:
        ist = traegt(anfrage, kandidat, aliase)
        gut = ist == erwartet
        ok = ok and gut
        print(f"  {'ok  ' if gut else 'FEHL'}  {anfrage[:44]:<46} ~ "
              f"{kandidat[:36]:<38} -> {'angenommen' if ist else 'abgewiesen'}")
        if not gut:
            print(f"          erwartet: "
                  f"{'angenommen' if erwartet else 'abgewiesen'}")
    print("\n" + ("  Gegentest bestanden." if ok
                  else "  GEGENTEST FEHLGESCHLAGEN."))
    return 0 if ok else 1


# ------------------------------------------------------------------ Hauptlauf

def innofonds_liste() -> dict[str, dict]:
    """Die handgepruefte Liste des Innovationsfonds-Portals. Nur gelesen."""
    if not INNO_CACHE.exists():
        print(f"  Hinweis: {INNO_CACHE} fehlt - nur ROR-Auflösung moeglich.")
        return {}
    roh = json.loads(INNO_CACHE.read_text(encoding="utf-8"))
    return {norm(k): v for k, v in roh.items() if v and v.get("ror_id")}


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--gegentest", action="store_true")
    p.add_argument("--ohne-netz", action="store_true",
                   help="keine Abfragen, nur die Innofonds-Liste")
    a = p.parse_args()
    if a.gegentest:
        return gegentest()

    st = json.loads((DATEN / "standorte.json").read_text(encoding="utf-8"))
    standorte = st["standorte"]
    inno = innofonds_liste()
    print(f"{len(standorte)} Forschungsstandorte, "
          f"{len(inno)} handgepruefte Zuordnungen aus dem Innofonds-Portal\n")

    quelle = collections.Counter()
    ergebnis = []
    typvergleich = collections.Counter()
    abweichung = []

    for i, s in enumerate(standorte, 1):
        namen = [s["name"], *s.get("schreibweisen", [])]
        ror, rname, grund = s.get("ror"), "", ""
        if ror:
            quelle["schon im Standortsatz"] += 1
            grund = "bereits aufgeloest"
        if not ror:
            for n in namen:
                tr = inno.get(norm(n))
                if tr and traegt(s["name"], tr.get("ror_name", ""), [n]):
                    ror, rname = tr["ror_id"], tr.get("ror_name", "")
                    grund = "Innofonds-Portal (handgeprueft)"
                    quelle["Innofonds-Portal"] += 1
                    break
        if not ror and not a.ohne_netz:
            ror, rname, grund = ror_suchen(s["name"])
            quelle["ROR-Auflösung" if ror else "kein Treffer"] += 1
            time.sleep(0.2)
        elif not ror:
            quelle["kein Treffer"] += 1
            grund = "ohne Netzabfrage"

        satz = {"name": s["name"], "datei": s.get("datei"),
                # Die Schreibweisen aus dem Register wandern MIT. Sie sind das
                # einzige stabile Merkmal: standorte.py fuehrt Standorte ueber
                # die ROR-Kennung zusammen und liest sie hier wieder - haengt
                # die Zuordnung am Standortnamen, schwingt die Kette (83 -> 65
                # -> 83 -> ...), weil jeder Durchgang andere Namen vorfindet.
                "schreibweisen": sorted(s.get("schreibweisen") or [s["name"]]),
                "studien": s.get("studien"), "traegerart": s.get("traegerart"),
                "ror": ror, "ror_name": rname, "ror_grund": grund,
                "netzadresse": None, "oa_typ": None, "oa_arbeiten": None,
                "repositorien": [], "namensvarianten": [], "geprueft": None,
                "name_haelt": None, "ort_haelt": None, "oa_ort": None,
                "lat": None, "lon": None}

        if ror and not a.ohne_netz:
            o = openalex(ror)
            time.sleep(0.2)
            if o:
                satz["netzadresse"] = o.get("homepage_url")
                satz["oa_typ"] = o.get("type")
                satz["oa_arbeiten"] = o.get("works_count")
                satz["namensvarianten"] = (
                    o.get("display_name_alternatives") or [])[:8]
                for r in (o.get("repositories") or []):
                    # Der Einrichtungsdatensatz nennt das Repositorium nur
                    # beim Namen. Die Adresse steht am Quellendatensatz -
                    # ohne sie waere der Verweis nicht anklickbar, und
                    # genau der Verweis ist der Zweck der Uebung.
                    adresse, oai = None, None
                    q = _quelle(r.get("id") or "")
                    if q:
                        adresse = q.get("homepage_url")
                        oai = (q.get("ids") or {}).get("fatcat")
                    satz["repositorien"].append({
                        "name": r.get("display_name"),
                        "id": r.get("id"),
                        "adresse": adresse,
                        "arbeiten": (q or {}).get("works_count"),
                        "traeger": r.get("host_organization_name")})
                typvergleich[(satz["traegerart"], satz["oa_typ"])] += 1
                # Auch die 55 schon vorhandenen Zuordnungen muessen durch
                # denselben Waechter - sonst prueft die Regel nur die Haelfte.
                satz["name_haelt"] = traegt(
                    s["name"], o.get("display_name") or "",
                    satz["namensvarianten"] + [satz["ror_name"] or ""])
                # Zweite, unabhaengige Pruefung: Sitzt die aufgeloeste
                # Einrichtung in derselben Stadt, die wir aus dem Register
                # haben? Das haengt nicht am Namen und faellt darum anders.
                geo = o.get("geo") or {}
                satz["oa_ort"] = geo.get("city")
                # Koordinaten fuer die Karte. Sie kommen aus demselben
                # Satz wie der Ort, werden also vom selben Ortsabgleich
                # mitgeprueft - haelt der Ort nicht, ist auch der Punkt
                # auf der Karte falsch und wird nicht gezeigt.
                satz["lat"] = geo.get("latitude")
                satz["lon"] = geo.get("longitude")
                unser_ort = (s.get("ort") or "").strip()
                if unser_ort and satz["oa_ort"]:
                    satz["ort_haelt"] = stadt(unser_ort) == stadt(satz["oa_ort"])
                else:
                    satz["ort_haelt"] = None
                satz["geprueft"] = (satz["name_haelt"]
                                    and satz["ort_haelt"] is not False)
                if not satz["geprueft"]:
                    warum = []
                    if not satz["name_haelt"]:
                        warum.append("Name haelt nicht")
                    if satz["ort_haelt"] is False:
                        warum.append(f"Ort {unser_ort} vs. {satz['oa_ort']}")
                    abweichung.append((s["name"], o.get("display_name"),
                                       "; ".join(warum) + f" [{grund}]"))
        ergebnis.append(satz)
        print(f"  {i:>3}/{len(standorte)}  {s['name'][:44]:<46} "
              f"{(ror or '-').replace('https://ror.org/',''):<10} "
              f"{(satz['oa_typ'] or '-'):<11} "
              f"Rep. {len(satz['repositorien'])}")

    # ----------------------------------------------------------- Bilanz
    mit_ror = sum(1 for e in ergebnis if e["ror"])
    mit_netz = sum(1 for e in ergebnis if e["netzadresse"])
    mit_rep = sum(1 for e in ergebnis if e["repositorien"])
    n = len(ergebnis)
    print(f"\nBilanz:")
    print(f"  Einrichtung eindeutig aufgeloest : {mit_ror:>3} von {n} "
          f"({mit_ror/n*100:.1f} %)")
    print(f"  Netzadresse der Einrichtung      : {mit_netz:>3} "
          f"({mit_netz/n*100:.1f} %)")
    print(f"  eigenes Publikationsrepositorium : {mit_rep:>3} "
          f"({mit_rep/n*100:.1f} %)")
    print("\nWoher die Zuordnung kommt:")
    for k, v in quelle.most_common():
        print(f"  {v:>3}  {k}")

    if abweichung:
        print(f"\n⚠ {len(abweichung)} Zuordnungen halten dem Waechter NICHT "
              f"stand - sie werden auf der Seite nicht verlinkt:")
        for name, oa, grund in abweichung:
            print(f"  {name[:48]:<50} -> {(oa or '-')[:34]:<36} ({grund})")
    else:
        print("\nAlle aufgeloesten Zuordnungen halten dem Waechter stand.")

    if typvergleich:
        print("\nAbgleich: unsere Traegerart gegen den OpenAlex-Typ")
        for (unser, oa), v in sorted(typvergleich.items(),
                                     key=lambda x: -x[1]):
            print(f"  {v:>3}  {(unser or '-')[:42]:<44} <-> {oa or '-'}")

    ZIEL.write_text(json.dumps({
        "stand": st.get("stand"),
        "hinweis": "Die Publikationslisten der Einrichtungen selbst sind von "
                   "Hand gepflegte Webseiten ohne Schnittstelle. Abfragbar "
                   "sind ROR (Identitaet) und OpenAlex (Typ, Netzadresse, "
                   "eigene Repositorien). Jede Namensauflösung ist durch den "
                   "Waechter in traegt() gelaufen.",
        "quellen": {
            "ROR": "https://ror.org - CC0",
            "OpenAlex": "https://openalex.org - CC0",
            "Innofonds-Portal": "db/ror_cache.json, handgeprueft, nur gelesen",
        },
        "standorte": ergebnis,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\ngeschrieben: {ZIEL}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
