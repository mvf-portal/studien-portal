"""Alle Verzeichnisse, in denen eine Einrichtung vorkommt.

Baut auf daten/repositorien.json auf (dort steht die gepruefte ROR-Kennung)
und holt dazu jeden weiteren Eintrag, der sich NACHPRUEFBAR verlinken laesst.

  py verzeichnisse.py              holt alles, schreibt daten/verzeichnisse.json
  py verzeichnisse.py --gegentest  prueft den Namenswaechter gegen re3data
  py verzeichnisse.py --ohne-netz  nur neu rechnen

Was traegt - gemessen am 01.11.2026:

  ROR          offen, CC0   schon in repositorien.json
  OpenAlex     offen, CC0   schon in repositorien.json (eigene Repositorien)
  Wikidata     offen, CC0   DREHSCHEIBE: ueber P6782 (ROR-ID) haengen dort
                            Wikipedia, GND, ISNI, VIAF, GRID, Crossref-Foerderer-
                            kennung und Scopus-Affiliation - alle mit eigener,
                            aufrufbarer Adresse
  re3data      offen        3.540 Forschungsdaten-Repositorien, ABER ohne
                            ROR-Kennung: nur institutionName. Darum derselbe
                            Namenswaechter wie in repositorien.py

Was nicht traegt - auch gemessen, nicht vermutet:

  OpenDOAR     HTTP 403 auf alles, auch auf die reine Webseite. Braucht einen
               kostenlosen Sherpa-Schluessel. Waere das vollstaendigste
               Verzeichnis der Publikationsrepositorien.
  GERiT (DFG)  kein Endpunkt gefunden; gerit.org antwortet nicht einmal mit
               einem Fehlercode, /api/... gibt 404. 33.000 Einrichtungen bis
               auf Institutsebene, aber nur von Hand.
  FIS-Landkarte  baut sich im Browser auf, kein Export.

Das steht so auch auf der Seite. Ein Verzeichnis, das wir nicht pruefen
koennen, verlinken wir nicht - siehe [[auswahl-nennt-was-fehlt]].
"""
import json
import pathlib
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

import repositorien as R

HIER = pathlib.Path(__file__).parent
DATEN = HIER / "daten"
MAILTO = "stegmaier@m-vf.de"
UA = {"User-Agent": f"vf-landkarte/1.0 (mailto:{MAILTO})"}

# Fremdkennungen aus Wikidata: Eigenschaft -> (Name, Adressmuster)
# Nur Verzeichnisse, deren Einzelseite sich wirklich aufrufen laesst.
KENNUNGEN = {
    "gnd": ("Gemeinsame Normdatei (DNB)", "https://d-nb.info/gnd/{}"),
    "isni": ("ISNI", "https://isni.org/isni/{}"),
    "viaf": ("VIAF", "https://viaf.org/viaf/{}/"),
    "grid": ("GRID", "https://www.grid.ac/institutes/{}"),
    "crossref": ("Crossref-Foerderkennung",
                 "https://api.crossref.org/funders/{}"),
    "scopus": ("Scopus-Affiliation",
               "https://www.scopus.com/affil/profile.uri?afid={}"),
}


def traegt_repo(einrichtung, repo_name):
    """Gehoert dieses Repositorium zu dieser Einrichtung?

    Der Waechter aus repositorien.py passt hier NICHT, und das hat der
    Gegentest gezeigt, nicht das Nachdenken: Er verlangt das Kopfwort in
    beide Richtungen, weil ein Kandidat mit fremdem Kopfwort ENGER ist als
    die Anfrage - ein Teil, nicht das Ganze. Fuer Einrichtungen ist das
    richtig. Ein Repositorium ist aber ABSICHTLICH enger als sein Haus:
    „Zentrale Biomaterialbank der Charite" hat das Kopfwort „zentrale",
    das die Charite nicht kennt - und wurde darum verworfen.

    Also nur die Hinrichtung: Das Kopfwort der EINRICHTUNG muss im
    Repositoriumsnamen wiederkehren. Zusaetzliche Woerter im Namen des
    Repositoriums sind erlaubt.

    Ort und Art als zweiter Weg gibt es hier nicht. Hat eine Einrichtung
    gar kein unterscheidendes Wort - „Universitaetsklinikum Freiburg"
    besteht nur aus Art und Ort -, findet diese Regel nichts. Bekannte
    Untergrenze: „FreiDok plus - Universitaet Freiburg" bleibt dadurch
    unverbunden. Der Preis ist in Kauf genommen, weil die Gegenprobe
    „Universitaet Freiburg" an „Universitaetsklinikum Freiburg" haengen
    wuerde - zwei verschiedene Einrichtungen. Was so verloren geht, tragen
    die Verantwortlichen im Formular selbst nach.
    """
    kopf = R.kopfwort(einrichtung)
    if kopf is None:
        return False
    return kopf in R.kennwoerter(repo_name)


def _hol(url, versuche=4, roh=False):
    for i in range(versuche):
        try:
            r = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(r, timeout=120) as f:
                b = f.read()
            return b if roh else json.loads(b.decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and i < versuche - 1:
                time.sleep(3 * (i + 1))
                continue
            raise
        except Exception:
            if i < versuche - 1:
                time.sleep(3 * (i + 1))
                continue
            raise
    return None


# ------------------------------------------------------------------ Wikidata

SPARQL = """
SELECT ?ror ?item ?itemLabel ?gnd ?isni ?viaf ?grid ?crossref ?scopus ?dewiki
WHERE {
  VALUES ?ror { %s }
  ?item wdt:P6782 ?ror .
  OPTIONAL { ?item wdt:P227  ?gnd }
  OPTIONAL { ?item wdt:P213  ?isni }
  OPTIONAL { ?item wdt:P214  ?viaf }
  OPTIONAL { ?item wdt:P2427 ?grid }
  OPTIONAL { ?item wdt:P3153 ?crossref }
  OPTIONAL { ?item wdt:P1155 ?scopus }
  OPTIONAL { ?dewiki schema:about ?item ;
             schema:isPartOf <https://de.wikipedia.org/> }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "de,en" }
}
"""


def wikidata(ror_ids, stapel=40):
    """ROR-Kennung -> Wikidata-Satz samt Fremdkennungen.

    Wikidata liefert ein KREUZPRODUKT: hat ein Haus zwei Netzadressen und
    drei VIAF-Nummern, kommen sechs Zeilen. Darum wird je Feld die erste
    Angabe genommen und doppelte Zeilen verworfen.
    """
    raus = {}
    # Wikidata fuehrt P6782 als BLANKE Kennung ("001w7jn25"), nicht als
    # Adresse. Mit "https://ror.org/..." kommen null Treffer zurueck - und
    # zwar lautlos, denn eine leere Antwort ist kein Fehler.
    kurz = {}
    for r in ror_ids:
        kurz[str(r).rstrip("/").rsplit("/", 1)[-1]] = r
    ids = sorted(kurz)
    for i in range(0, len(ids), stapel):
        teil = ids[i:i + stapel]
        werte = " ".join('"%s"' % x for x in teil)
        url = ("https://query.wikidata.org/sparql?format=json&query="
               + urllib.parse.quote(SPARQL % werte))
        d = _hol(url)
        for b in (d or {}).get("results", {}).get("bindings", []):
            k = kurz.get(b["ror"]["value"], b["ror"]["value"])
            s = raus.setdefault(k, {"wikidata": None, "label": None,
                                    "dewiki": None, "kennungen": {}})
            item = b.get("item", {}).get("value")
            if item and not s["wikidata"]:
                s["wikidata"] = item.rsplit("/", 1)[-1]
            if b.get("itemLabel") and not s["label"]:
                s["label"] = b["itemLabel"]["value"]
            if b.get("dewiki") and not s["dewiki"]:
                s["dewiki"] = b["dewiki"]["value"]
            for feld in KENNUNGEN:
                if b.get(feld) and feld not in s["kennungen"]:
                    s["kennungen"][feld] = b[feld]["value"]
        print(f"  Wikidata, Stapel {i // stapel + 1}: {len(teil)} angefragt, "
              f"{len(raus)} aufgeloest")
        time.sleep(0.4)
    return raus


# -------------------------------------------------------------------- re3data

def re3data_verzeichnis():
    """Das ganze re3data-Verzeichnis einmal holen.

    Nur id, doi und name - die Trageradresse steht erst im Einzelsatz, und
    3.540 Einzelabrufe waeren unhoeflich. Darum erst nach Namen vorsortieren
    und nur die Kandidaten einzeln nachschlagen.
    """
    b = _hol("https://www.re3data.org/api/v1/repositories", roh=True)
    t = b.decode("utf-8")
    raus = []
    for m in re.finditer(r"<repository>(.*?)</repository>", t, re.S):
        s = m.group(1)
        i = re.search(r"<id>(r3d\d+)</id>", s)
        n = re.search(r"<name[^>]*>(.*?)</name>", s, re.S)
        if i and n:
            raus.append({"id": i.group(1),
                         "name": re.sub(r"\s+", " ", n.group(1)).strip()})
    return raus


def _tag(x, name):
    m = re.search(r"<(?:r3d:)?%s[^>]*>(.*?)</(?:r3d:)?%s>" % (name, name),
                  x, re.S)
    return re.sub(r"\s+", " ", m.group(1)).strip() if m else None


def re3data_satz(rid):
    x = _hol(f"https://www.re3data.org/api/v1/repository/{rid}",
             roh=True).decode("utf-8")
    traeger = []
    for m in re.finditer(r"<(?:r3d:)?institution>(.*?)</(?:r3d:)?institution>",
                         x, re.S):
        n = _tag(m.group(1), "institutionName")
        if n:
            traeger.append(n)
    return {
        "name": _tag(x, "repositoryName"),
        "adresse": _tag(x, "repositoryURL"),
        "traeger": traeger,
        "art": [m.group(1) for m in
                re.finditer(r"<(?:r3d:)?type>(.*?)</(?:r3d:)?type>", x)],
    }


def re3data_zuordnen(standorte, index, nachschlagen=True):
    """re3data-Repositorien den Standorten zuordnen - ueber den Waechter.

    re3data traegt KEINE ROR-Kennung, nur institutionName. Dasselbe Problem
    wie bei der ROR-Namensauflosung, also derselbe Waechter: Kopfwort
    beidseitig, Ort-und-Art als zweiter Weg. Ein Treffer gilt nur, wenn er
    den Waechter sowohl ueber den Repositoriumsnamen als auch ueber einen
    Traegernamen besteht - oder ueber den Traegernamen allein.
    """
    zu = {}
    for s in standorte:
        name = s["name"]
        kandidaten = []
        for r in index:
            if traegt_repo(name, r["name"]):
                kandidaten.append(r)
        if not kandidaten:
            continue
        bestaetigt = []
        for r in kandidaten:
            if not nachschlagen:
                bestaetigt.append({**r, "traeger": [], "adresse": None})
                continue
            try:
                e = re3data_satz(r["id"])
            except Exception as ex:
                print(f"    {r['id']}: {ex}")
                continue
            time.sleep(0.2)
            # Der Traegername ist das staerkere Merkmal: er nennt das Haus,
            # der Repositoriumsname oft nur die Sammlung.
            if e["traeger"] and not any(R.traegt(name, t, [])
                                        or traegt_repo(name, t)
                                        for t in e["traeger"]):
                continue
            bestaetigt.append({
                "id": r["id"],
                "name": e["name"] or r["name"],
                "adresse": e["adresse"],
                "seite": f"https://www.re3data.org/repository/{r['id']}",
                "traeger": e["traeger"],
                "art": e["art"],
            })
        if bestaetigt:
            zu[name] = bestaetigt
            print(f"    {name[:46]:<48} {len(bestaetigt)}")
    return zu


# ------------------------------------------------------------------ Gegentest

def gegentest():
    """Der Waechter muss re3data-Namen genauso aussortieren wie ROR-Namen."""
    ok = True
    print("re3data-Namen gegen den Waechter:")
    faelle = [
        # (Standort, re3data-Name, soll treffen)
        # Ein Repositorium ist ABSICHTLICH enger als sein Haus - darum darf
        # es ein eigenes Kopfwort tragen, solange das Kopfwort der
        # Einrichtung darin wiederkehrt.
        ("Charité - Universitätsmedizin Berlin",
         "Zentrale Biomaterialbank der Charité", True),
        ("Charité - Universitätsmedizin Berlin",
         "BIH / Charité Virtual Research Environment", True),
        # Gattung allein darf nicht reichen - sonst haengt an jeder
        # Universitaetsmedizin jedes Repositorium jeder anderen.
        ("Charité - Universitätsmedizin Berlin",
         "Universitätsmedizin Greifswald Forschungsdaten", False),
        ("Universitätsklinikum Heidelberg",
         "Forschungsdaten der Universität Tübingen", False),
        # Ein Ortsname allein ist Rauschen: ‚Berlin‘ verbindet nichts.
        ("Charité - Universitätsmedizin Berlin",
         "Datenbank Berlin", False),
        ("Hochschule für angewandte Wissenschaften Hamburg",
         "Hochschule für angewandte Wissenschaften München", False),
        # Allgemeinwoerter: ein ‚Forschungsdatenzentrum‘ ist kein Name.
        ("Deutsches Zentrum für Lungenforschung",
         "Forschungsdatenzentrum Gesundheit", False),
        # BEKANNTE UNTERGRENZE, bewusst auf False gesetzt: Eine Einrichtung
        # ganz ohne unterscheidendes Wort - nur Art und Ort - findet nichts.
        # Die Gegenprobe zeigt, warum: Wer hier lockerer wird, haengt die
        # Universitaet an das Universitaetsklinikum.
        ("Universitätsklinikum Freiburg",
         "FreiDok plus - Universität Freiburg", False),
        ("Universitätsklinikum Freiburg",
         "Forschungsdaten der Universität Freiburg", False),
    ]
    for standort, kandidat, soll in faelle:
        ist = traegt_repo(standort, kandidat)
        gut = ist == soll
        ok = ok and gut
        print(f"  {'ok ' if gut else 'FEHLER'} {kandidat[:46]:<48} "
              f"{'trifft' if ist else 'trifft nicht'}")

    print("\nWikidata-Kreuzprodukt wird eingefangen:")
    # Zwei Netzadressen beim UKE geben zwei gleiche Zeilen zurueck. Wenn der
    # Einleser die nicht verdichtet, stehen Kennungen doppelt auf der Seite.
    roh = {"results": {"bindings": [
        {"ror": {"value": "r1"}, "item": {"value": "http://wd/Q1"},
         "itemLabel": {"value": "Eins"}, "viaf": {"value": "123"}},
        {"ror": {"value": "r1"}, "item": {"value": "http://wd/Q1"},
         "itemLabel": {"value": "Eins"}, "viaf": {"value": "456"}},
    ]}}
    s = {}
    for b in roh["results"]["bindings"]:
        k = b["ror"]["value"]
        e = s.setdefault(k, {"kennungen": {}})
        for feld in KENNUNGEN:
            if b.get(feld) and feld not in e["kennungen"]:
                e["kennungen"][feld] = b[feld]["value"]
    gut = s["r1"]["kennungen"] == {"viaf": "123"}
    ok = ok and gut
    print(f"  {'ok ' if gut else 'FEHLER'} nur die erste VIAF-Nummer "
          f"({s['r1']['kennungen']})")

    print("\n" + ("Gegentest bestanden." if ok else "GEGENTEST GESCHEITERT."))
    return ok


# ----------------------------------------------------------------------- Lauf

def main():
    if "--gegentest" in sys.argv:
        return 0 if gegentest() else 1

    rp = DATEN / "repositorien.json"
    if not rp.exists():
        print("FEHLER: daten/repositorien.json fehlt - erst `py repositorien.py`")
        return 1
    rep = json.loads(rp.read_text(encoding="utf-8"))
    standorte = rep["standorte"]
    geprueft = [s for s in standorte if s.get("geprueft") and s.get("ror")]
    print(f"Standorte          : {len(standorte)}")
    print(f"mit gepruefter ROR : {len(geprueft)}")

    ziel = DATEN / "verzeichnisse.json"
    if "--ohne-netz" in sys.argv:
        if not ziel.exists():
            print("FEHLER: daten/verzeichnisse.json fehlt")
            return 1
        alt = json.loads(ziel.read_text(encoding="utf-8"))
        wd, r3 = alt.get("_wikidata", {}), alt.get("_re3data", {})
    else:
        print("\nWikidata (ROR-Kennung P6782):")
        wd = wikidata([s["ror"] for s in geprueft])

        print("\nre3data (Namenswaechter, ohne ROR-Kennung):")
        index = re3data_verzeichnis()
        print(f"  Verzeichnis: {len(index)} Repositorien")
        r3 = re3data_zuordnen(standorte, index)

    # ---------------------------------------------------- je Standort bauen
    raus, mit_wd, mit_r3, kennzahl = {}, 0, 0, {}
    for s in standorte:
        eintraege = []
        if s.get("geprueft") and s.get("ror"):
            kurz = s["ror"].rsplit("/", 1)[-1]
            eintraege.append({
                "verzeichnis": "ROR",
                "was": "Einrichtungskennung",
                "kennung": kurz,
                "adresse": s["ror"],
            })
            if s.get("oa_id"):
                eintraege.append({
                    "verzeichnis": "OpenAlex",
                    "was": "Publikationen der Einrichtung",
                    "kennung": s["oa_id"].rsplit("/", 1)[-1],
                    "adresse": s["oa_id"],
                })
            w = wd.get(s["ror"])
            if w:
                mit_wd += 1
                if w.get("wikidata"):
                    eintraege.append({
                        "verzeichnis": "Wikidata",
                        "was": "Datenobjekt",
                        "kennung": w["wikidata"],
                        "adresse": "https://www.wikidata.org/wiki/"
                                   + w["wikidata"],
                    })
                if w.get("dewiki"):
                    eintraege.append({
                        "verzeichnis": "Wikipedia",
                        "was": "Artikel",
                        "kennung": None,
                        "adresse": w["dewiki"],
                    })
                for feld, wert in w.get("kennungen", {}).items():
                    bez, muster = KENNUNGEN[feld]
                    eintraege.append({
                        "verzeichnis": bez,
                        "was": "Kennung",
                        "kennung": wert,
                        "adresse": muster.format(
                            urllib.parse.quote(str(wert), safe="")),
                    })
                    kennzahl[bez] = kennzahl.get(bez, 0) + 1
        for r in r3.get(s["name"], []):
            mit_r3 += 1
            eintraege.append({
                "verzeichnis": "re3data",
                "was": "Forschungsdaten-Repositorium: " + (r["name"] or ""),
                "kennung": r["id"],
                "adresse": r.get("seite"),
                "ziel": r.get("adresse"),
            })
        raus[s["name"]] = eintraege

    mit = sum(1 for v in raus.values() if v)
    print(f"\nStandorte mit Verzeichniseintrag : {mit} von {len(standorte)}")
    print(f"  davon in Wikidata              : {mit_wd}")
    print(f"  re3data-Repositorien zugeordnet : {mit_r3}")
    print("\nje Verzeichnis:")
    for k, n in sorted(kennzahl.items(), key=lambda x: -x[1]):
        print(f"  {n:>3}  {k}")
    print(f"\nVerweise gesamt: {sum(len(v) for v in raus.values())}")

    (DATEN / "verzeichnisse.json").write_text(json.dumps({
        "stand": rep.get("stand"),
        "hinweis": (
            "Jeder Verweis fuehrt auf den Eintrag DIESER Einrichtung in einem "
            "oeffentlichen Verzeichnis. Zusammengetragen ueber die ROR-Kennung "
            "(Wikidata P6782) und, wo ein Verzeichnis keine ROR-Kennung fuehrt "
            "(re3data), ueber einen geprueften Namensabgleich. Nicht enthalten: "
            "OpenDOAR (Zugang nur mit Schluessel), GERiT (keine Schnittstelle), "
            "FIS-Landkarte (kein Export). Diese Verzeichnisse pflegt die "
            "Einrichtung nicht selbst - Fehler darin koennen nur die "
            "Verantwortlichen richtigstellen."),
        "nicht_enthalten": [
            {"verzeichnis": "OpenDOAR", "grund":
             "HTTP 403 auf alle Adressen; braucht einen kostenlosen "
             "Sherpa-Schluessel", "gemessen": "2026-11-01"},
            {"verzeichnis": "GERiT (DFG)", "grund":
             "kein Endpunkt; 33.000 Einrichtungen nur ueber die Oberflaeche",
             "gemessen": "2026-11-01"},
            {"verzeichnis": "FIS-Landkarte (KFiD/DINI)", "grund":
             "baut sich im Browser auf, kein Export", "gemessen": "2026-10-31"},
        ],
        "zaehlung": {"standorte": len(standorte), "mit_eintrag": mit,
                     "in_wikidata": mit_wd, "re3data": mit_r3,
                     "je_verzeichnis": kennzahl},
        "standorte": raus,
        "_wikidata": wd,
        "_re3data": r3,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"-> daten/verzeichnisse.json "
          f"({(DATEN / 'verzeichnisse.json').stat().st_size / 1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
