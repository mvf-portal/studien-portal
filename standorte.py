# -*- coding: utf-8 -*-
"""Profilseiten je Standort der Versorgungsforschung.

Vorbild sind die Projekt-Profilseiten des Innofonds-Radars: oeffentliche
Seite mit Steckbrief, darunter der Block „Sie leiten diesen Standort?" mit
Zugangsanforderung per E-Mail. Was aus dem Register stammt, bleibt
unveraendert; Ergaenzungen stehen als Angaben der Einrichtung daneben.

**Standortidentitaet ueber die Traegerliste des Innovationsfonds.** Das DRKS
normiert Einrichtungsnamen nicht - „Charité - Universitätsmedizin Berlin" und
„Charité – Universitätsmedizin Berlin" sind dort zwei Eintraege (13 und 5
Studien). Die ueber ROR aufgeloeste Liste aus `innovationsfonds/db` fuehrt sie
zusammen und gibt dem Standort eine stabile Kennung. Ohne Treffer dort bleibt
der normalisierte Name die Kennung.

Aufruf:
    py standorte.py              # Standorte ab 2 Studien
    py standorte.py --ab 1       # alle
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import html
import json
import pathlib
import re
import sys
import unicodedata

HIER = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HIER))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import fachrichtung
import leisten
import repositorien
import traegerart
import vfserie
from bestandsbezug import Abgleich
from zuschnitt import HUB_NAMEN

DATEN = HIER / "daten"
ZIEL = HIER / "standort"
ENDPUNKT = ""          # noch nicht eingerichtet - siehe MANUAL.md

# Traegerarten, die keine Forschungsstandorte sind. Sie tauchen im Register
# als „Sponsor" auf, weil sie die Studie verantworten oder bezahlen - aber
# eine Krankenkasse und ein Pharmaunternehmen sind Geldgeber, keine
# Forschungseinrichtungen. Entscheidung des Herausgebers vom 30.10.2026.
AUSGESCHLOSSEN = {"Kostenträger", "Unternehmen"}


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", (s or "").lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.replace("–", "-").replace("—", "-")
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def schluessel(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", norm(name)).strip("-")[:60] or "standort"


def e(s) -> str:
    return html.escape(str(s if s is not None else ""), quote=True)


REPOS: dict[str, dict] = {}
# Schreibweise -> wurde sie ueber die ROR-Kennung zusammengefuehrt?
# nach_ror() fuellt das; der Kasten auf der Profilseite nennt damit
# den richtigen Weg statt pauschal die Innofonds-Traegerliste.
RORWEG: dict[str, bool] = {}
VERZ: dict[str, list] = {}
DOIB: dict = {}


def darf_verschmelzen(a: str, b: str) -> tuple[bool, str]:
    """Duerfen zwei Standortnamen mit DERSELBEN ROR-Kennung ein Haus werden?

    Die ROR-Kennung ist ein zweites, namensunabhaengiges Merkmal und findet
    darum, was der Namensabgleich nicht findet: „Universitaetsklinikum
    Heidelberg" und „Neurologische Klinik, Universitaetsklinikum Heidelberg"
    teilen kein unterscheidendes Wort - Heidelberg ist Ortsrauschen -, sind
    aber dasselbe Haus.

    Blind darf man ihr nicht folgen. In der Innofonds-Traegerliste traegt
    ROR einen allgemeinen Satz „AOK", auf dem AOK Bundesverband, AOK Hessen
    und AOK NordWest zusammen gelandet sind - drei verschiedene
    Koerperschaften. Darum diese Sperre: Nennen beide Namen einen Ort oder
    ein Bundesland und sind diese VERSCHIEDEN, bleiben sie getrennt.

    Diese Sperre faengt den AOK-Fall nur zur Haelfte: „AOK Hessen" gegen
    „AOK Bundesverband" nennt nur EINER einen Ort, also greift sie nicht.
    Hier schadet das nicht, weil Kostentraeger ueberhaupt nicht Standort
    werden (siehe AUSGESCHLOSSEN) - aber wer diese Regel woanders benutzt,
    muss das wissen.
    """
    oa, ob = repositorien.orte(a), repositorien.orte(b)
    if oa and ob and not (oa & ob):
        return False, (f"verschiedene Orte: {sorted(oa)} gegen {sorted(ob)}")
    return True, ""


def nach_ror(orte: dict) -> int:
    """Zweiter Durchgang: Standorte mit gleicher gepruefter ROR vereinen.

    Die ROR-Kennung kommt aus repositorien.json und ist dort schon gegen
    Name UND Ort geprueft. Fehlt die Datei, passiert hier nichts.

    Die Zuordnung haengt an der SCHREIBWEISE aus dem Register, nicht am
    Standortnamen. Das ist kein Schoenheitsfehler, sondern der Grund, warum
    die Kette ueberhaupt stillsteht: repositorien.py laeuft auf dem Ergebnis
    von standorte.py, und standorte.py liest repositorien.json. Haengt die
    Zuordnung am Standortnamen, findet der zweite Durchgang die schon
    verschmolzenen Haeuser als Einzelgruppen vor und loest die Verschmelzung
    wieder auf - gemessen am 01.11.2026: 83 -> 65 -> 83 -> 65. Schreibweisen
    aendern sich nie, also ist die Gruppierung nach dem ersten Durchgang
    fest.
    """
    if not REPOS:
        return 0
    # Schreibweise -> ROR, aus allen Saetzen zusammengetragen.
    je_schreibweise: dict[str, str] = {}
    for r in REPOS.values():
        if r.get("geprueft") and r.get("ror"):
            for sw in r.get("schreibweisen") or [r["name"]]:
                je_schreibweise[sw.strip()] = r["ror"]

    nach_kennung: dict[str, list] = {}
    uneinig = 0
    for z in orte.values():
        treffer = {je_schreibweise[sw.strip()] for sw in z["schreibweisen"]
                   if sw.strip() in je_schreibweise}
        if len(treffer) == 1:
            nach_kennung.setdefault(treffer.pop(), []).append(z)
        elif len(treffer) > 1:
            # Zwei verschiedene Kennungen unter einem Standort: Dann ist
            # entweder die Zusammenfuehrung vorher falsch gewesen oder eine
            # Aufloesung. Nicht weiterverschmelzen, sondern melden.
            uneinig += 1
            print(f"    uneinige ROR-Kennungen bei {z['name'][:44]}")
    if uneinig:
        print(f"  {uneinig} Standorte mit mehr als einer ROR-Kennung - "
              f"nicht weiter zusammengeführt")

    verschmolzen, abgelehnt = 0, []
    for ror, gruppe in nach_kennung.items():
        if len(gruppe) < 2:
            continue
        # Das Haus mit den meisten Studien fuehrt; bei Gleichstand der
        # kuerzeste Name, weil der die Abteilung nicht mitnennt.
        gruppe.sort(key=lambda z: (-len(z["studien"]), len(z["name"])))
        haupt = gruppe[0]
        for z in gruppe[1:]:
            gut, grund = darf_verschmelzen(haupt["name"], z["name"])
            if not gut:
                abgelehnt.append((haupt["name"], z["name"], grund))
                continue
            haupt["studien"].extend(z["studien"])
            for sw in z["schreibweisen"]:
                RORWEG[sw.strip()] = True
            haupt["schreibweisen"] |= z["schreibweisen"]
            for feld in ("orte", "hubs", "kommissionen", "laender",
                         "traegerart", "faecher", "zentren"):
                haupt[feld].update(z[feld])
            haupt["zentrenname"].update(z.get("zentrenname") or {})
            orte.pop(z["kennung"], None)
            verschmolzen += 1

    if verschmolzen:
        print(f"  über die ROR-Kennung zusammengeführt: {verschmolzen} "
              f"weitere Standorte")
    for h, z, grund in abgelehnt:
        print(f"    NICHT verschmolzen ({grund}): {h[:34]} / {z[:34]}")
    return verschmolzen


def gegentest() -> int:
    """Prueft die Zusammenfuehrung nach ROR - vor allem, wo sie NICHT greifen darf."""
    global REPOS
    sicher = REPOS
    ok = True

    def standort(kennung, name, schreibweisen, studien):
        return {"kennung": kennung, "name": name,
                "schreibweisen": set(schreibweisen),
                "studien": [{"id": x} for x in studien],
                "orte": collections.Counter(), "hubs": collections.Counter(),
                "kommissionen": collections.Counter(),
                "laender": collections.Counter(),
                "traegerart": collections.Counter(),
                "faecher": collections.Counter(),
                "zentren": collections.Counter(), "zentrenname": {},
                "ror": None}

    print("Gleiche ROR-Kennung, gleiches Haus - muss verschmelzen:")
    REPOS = {
        "Universitätsklinikum Heidelberg": {
            "name": "Universitätsklinikum Heidelberg", "geprueft": True,
            "ror": "https://ror.org/013czdx64",
            "schreibweisen": ["Universitätsklinikum Heidelberg"]},
        "Neurologische Klinik, Universitätsklinikum Heidelberg": {
            "name": "Neurologische Klinik, Universitätsklinikum Heidelberg",
            "geprueft": True, "ror": "https://ror.org/013czdx64",
            "schreibweisen": ["Neurologische Klinik, Universitätsklinikum Heidelberg"]},
    }
    orte = {
        "a": standort("a", "Universitätsklinikum Heidelberg",
                      ["Universitätsklinikum Heidelberg"], ["S1", "S2"]),
        "b": standort("b", "Neurologische Klinik, Universitätsklinikum Heidelberg",
                      ["Neurologische Klinik, Universitätsklinikum Heidelberg"],
                      ["S3"]),
    }
    n = nach_ror(orte)
    pruef = [
        ("ein Standort bleibt übrig", len(orte) == 1),
        ("eine Verschmelzung gezählt", n == 1),
        ("alle drei Studien erhalten",
         len(next(iter(orte.values()))["studien"]) == 3),
        # Das Haus fuehrt, nicht die Abteilung.
        ("das Klinikum führt, nicht die Klinik",
         next(iter(orte.values()))["name"] == "Universitätsklinikum Heidelberg"),
        ("beide Schreibweisen erhalten",
         len(next(iter(orte.values()))["schreibweisen"]) == 2),
    ]
    # Ein zweiter Durchgang darf NICHTS mehr tun - sonst schwingt die Kette.
    vorher = len(orte)
    n2 = nach_ror(orte)
    pruef.append(("zweiter Durchgang ändert nichts",
                  n2 == 0 and len(orte) == vorher))
    for text, gut in pruef:
        ok = ok and gut
        print(f"  {'ok ' if gut else 'FEHLER'} {text}")

    print("\nGleiche ROR-Kennung, VERSCHIEDENE Orte - darf nicht verschmelzen:")
    # Der gemessene Fall aus der Innofonds-Traegerliste: ROR fuehrt einen
    # allgemeinen Satz „AOK", auf dem drei Koerperschaften gelandet sind.
    REPOS = {
        "AOK Hessen": {"name": "AOK Hessen", "geprueft": True,
                       "ror": "https://ror.org/004cmqw89",
                       "schreibweisen": ["AOK Hessen"]},
        "AOK Bayern": {"name": "AOK Bayern", "geprueft": True,
                       "ror": "https://ror.org/004cmqw89",
                       "schreibweisen": ["AOK Bayern"]},
    }
    orte = {"a": standort("a", "AOK Hessen", ["AOK Hessen"], ["S1"]),
            "b": standort("b", "AOK Bayern", ["AOK Bayern"], ["S2"])}
    nach_ror(orte)
    gut = len(orte) == 2
    ok = ok and gut
    print(f"  {'ok ' if gut else 'FEHLER'} zwei Landes-AOKs bleiben getrennt")

    print("\nUngepruefte Zuordnung - darf nicht verschmelzen:")
    REPOS = {
        "Haus A": {"name": "Haus A", "geprueft": False,
                   "ror": "https://ror.org/x", "schreibweisen": ["Haus A"]},
        "Haus B": {"name": "Haus B", "geprueft": False,
                   "ror": "https://ror.org/x", "schreibweisen": ["Haus B"]},
    }
    orte = {"a": standort("a", "Haus A", ["Haus A"], ["S1"]),
            "b": standort("b", "Haus B", ["Haus B"], ["S2"])}
    nach_ror(orte)
    gut = len(orte) == 2
    ok = ok and gut
    print(f"  {'ok ' if gut else 'FEHLER'} ungeprüfte ROR verschmilzt nicht")

    print("\nOhne repositorien.json - darf nicht abstürzen:")
    REPOS = {}
    orte = {"a": standort("a", "Haus A", ["Haus A"], ["S1"])}
    gut = nach_ror(orte) == 0 and len(orte) == 1
    ok = ok and gut
    print(f"  {'ok ' if gut else 'FEHLER'} fehlende Datei lässt alles stehen")

    REPOS = sicher
    print("\n" + ("Gegentest bestanden." if ok else "GEGENTEST GESCHEITERT."))
    return 0 if ok else 1


def _laden(name: str, was: str, bauer: str):
    """Eine Zusatzdatei einlesen - oder ehrlich sagen, dass sie fehlt.

    Keine dieser Dateien wird heimlich nachgebaut. Fehlt sie, bleibt der
    zugehoerige Kasten leer und das Skript nennt den Befehl, der sie macht.
    """
    p = DATEN / name
    if not p.exists():
        print(f"  HINWEIS: daten/{name} fehlt - keine {was}. "
              f"Erst `py {bauer}` laufen lassen.")
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--ab", type=int, default=2,
                   help="ab wie vielen Studien eine Profilseite entsteht")
    p.add_argument("--gegentest", action="store_true",
                   help="prueft die Zusammenfuehrung nach ROR, ohne zu bauen")
    a = p.parse_args()

    if a.gegentest:
        return gegentest()

    # Die Einrichtungsverweise aus repositorien.py. Fehlt die Datei, bleiben
    # die Kaesten leer - sie wird NICHT heimlich nachgebaut.
    global REPOS
    rp = DATEN / "repositorien.json"
    if rp.exists():
        REPOS = {x["name"]: x for x in
                 json.loads(rp.read_text(encoding="utf-8"))["standorte"]}
        geprueft = sum(1 for x in REPOS.values() if x.get("geprueft"))
        print(f"  Einrichtungsverweise: {geprueft} von {len(REPOS)} geprueft")
    else:
        print("  HINWEIS: daten/repositorien.json fehlt - keine "
              "Einrichtungsverweise. Erst `py repositorien.py` laufen lassen.")

    global VERZ, DOIB
    v = _laden("verzeichnisse.json", "Verzeichniseintraege", "verzeichnisse.py")
    if v:
        VERZ = v["standorte"]
        n = sum(1 for x in VERZ.values() if x)
        print(f"  Verzeichniseintraege: {n} Standorte, "
              f"{sum(len(x) for x in VERZ.values())} Verweise")
    d = _laden("doi_bezug.json", "Fachgebiete aus Publikationen", "doi_bezug.py")
    if d:
        DOIB = d
        print(f"  Publikationsbezug  : {d['zaehlung']['studien_mit_fach']} "
              f"Studien mit Fachgebiet aus {len(d['arbeiten'])} Arbeiten")

    lk = json.loads((DATEN / "landkarte.json").read_text(encoding="utf-8"))
    stand = lk["stand"]
    abgleich = Abgleich()

    # ---------------------------------------------------- Standorte bilden
    cache: dict[str, tuple[str, str, str | None]] = {}

    def identitaet(name: str) -> tuple[str, str, str | None]:
        """(Kennung, Anzeigename, ROR) fuer einen Einrichtungsnamen."""
        if name in cache:
            return cache[name]
        k = abgleich.kanonisch(name)
        if k:
            erg = (k["ror"], k["name"], k["ror"])
        else:
            erg = (schluessel(name), name.strip(), None)
        cache[name] = erg
        return erg

    orte: dict[str, dict] = {}
    weggelassen = collections.Counter()
    ohne_fuehrende = 0
    for s in lk["studien"]:
        # NUR die fuehrende Einrichtung wird zum Forschungsstandort.
        #
        # Vorher zaehlte jede genannte Einrichtung - also auch die 1.477
        # Praxen und Kliniken, die bloss rekrutieren. Dadurch kamen 200
        # „Standorte der Versorgungsforschung" zusammen, eine Zahl, die es
        # in Deutschland nicht gibt. Eine Hausarztpraxis, die Patient:innen in
        # eine Studie einschliesst, betreibt keine Versorgungsforschung.
        if not (s.get("sponsor") and s["sponsor"].get("name")):
            ohne_fuehrende += 1
            continue
        name = s["sponsor"]["name"].strip()
        ort = s["sponsor"].get("ort")

        # Kassen und Firmen sind Geldgeber, keine Forschenden. Sie stehen in
        # der Foerdererliste (`py foerderer.py`), nicht unter den Standorten.
        tart, tgrund = traegerart.art(name)
        if tart in AUSGESCHLOSSEN:
            weggelassen[tart] += 1
            continue

        kennung, anzeige, ror = identitaet(name)
        z = orte.setdefault(kennung, {
            "kennung": kennung, "name": anzeige, "ror": ror,
            "orte": collections.Counter(), "schreibweisen": set(),
            "studien": [], "hubs": collections.Counter(),
            "kommissionen": collections.Counter(), "laender": collections.Counter(),
            "traegerart": collections.Counter(), "traegergrund": tgrund,
            "faecher": collections.Counter(), "zentren": collections.Counter(),
            "zentrenname": {},
        })
        z["schreibweisen"].add(name)
        z["traegerart"][tart] += 1
        for f in fachrichtung.faecher(name):
            z["faecher"][f] += 1
        if ort:
            z["orte"][ort.strip()] += 1
        z["studien"].append(s)
        # Die rekrutierenden Einrichtungen gehoeren zur Studie, nicht zum
        # Standort - sie bekommen keine eigene Seite, werden aber gezaehlt.
        # Nach dem NORMALISIERTEN Namen zaehlen, sonst steht dieselbe Klinik
        # fuenfmal da - das Register schreibt sie jedes Mal anders. Das ist
        # ein reiner Zeichenkettenvergleich, keine Wortmengen-Heuristik.
        for o in s["orte"]:
            if o.get("name"):
                z["zentren"][norm(o["name"])] += 1
                z["zentrenname"].setdefault(norm(o["name"]),
                                            collections.Counter())[o["name"].strip()] += 1
        for h in s["hubs"]:
            z["hubs"][h] += 1
        for v in s["voten"]:
            if v.get("kommission"):
                z["kommissionen"][v["kommission"]] += 1
        if s.get("land"):
            z["laender"][s["land"]] += 1

    print(f"  {ohne_fuehrende} Studien ohne fuehrende Einrichtung im Register")
    for k, n in weggelassen.most_common():
        print(f"  {n:>3} Studien weggelassen: {k} (stehen in der Foerdererliste)")

    nach_ror(orte)

    gross = {k: v for k, v in orte.items() if len(v["studien"]) >= a.ab}
    roh = {n.strip() for v in orte.values() for n in v["schreibweisen"]}
    print(f"{len(roh)} Schreibweisen im Register → {len(orte)} Standorte")
    zusammengefuehrt = [v for v in orte.values() if len(v["schreibweisen"]) > 1]
    print(f"  davon über die Innofonds-Trägerliste zusammengeführt: {len(zusammengefuehrt)}")
    for v in sorted(zusammengefuehrt, key=lambda x: -len(x["studien"]))[:6]:
        print(f"     {len(v['studien']):>3} Studien  {v['name'][:48]}  "
              f"← {len(v['schreibweisen'])} Schreibweisen")
    print(f"  Profilseiten ab {a.ab} Studien: {len(gross)}")

    # ---------------------------------------------------- Seiten schreiben
    vorlage = (HIER / "standort-vorlage.html").read_text(encoding="utf-8")
    # Dieselben Leisten wie auf der Karte - EIN Baustein, siehe leisten.py.
    netz, fuss = leisten.beide()
    ZIEL.mkdir(exist_ok=True)
    for alt in ZIEL.glob("*.html"):
        alt.unlink()

    STATUS_KLASSE = {"rekrutiert": "rekrutiert", "geplant": "geplant",
                     "abgeschlossen": "abgeschlossen"}
    verzeichnis = []
    for z in sorted(gross.values(), key=lambda x: -len(x["studien"])):
        st = collections.Counter(s["status_de"] for s in z["studien"])
        ort = z["orte"].most_common(1)[0][0] if z["orte"] else ""
        land = z["laender"].most_common(1)[0][0] if z["laender"] else ""

        kz = [("", len(z["studien"]), "Studien mit Versorgungsbezug"),
              ("g", st.get("rekrutiert", 0), "suchen Teilnehmende"),
              ("", st.get("geplant", 0), "geplant"),
              ("", st.get("abgeschlossen", 0), "abgeschlossen")]
        ohne_pub = sum(1 for s in z["studien"]
                       if s["status_de"] == "abgeschlossen" and not s["dois"])
        if ohne_pub:
            kz.append(("w", ohne_pub, "abgeschlossen ohne Publikationsangabe"))
        kennzahlen = "".join(
            f'<div><div class="n {k}">{v}</div><div class="t">{e(t)}</div></div>'
            for k, v, t in kz)

        studien = []
        for s in sorted(z["studien"], key=lambda x: (x["status_de"] != "rekrutiert",
                                                     x["titel"] or "")):
            kl = STATUS_KLASSE.get(s["status_de"], "sonst")
            chips = "".join(
                f'<a class="chip hub" href="{e(HUB_NAMEN[h][1])}" target="_blank" '
                f'rel="noopener">{e(HUB_NAMEN[h][0])}</a>' for h in s["hubs"]
                if h in HUB_NAMEN)
            studien.append(
                f'<li><span class="st {kl}">{e(s["status_de"])}</span> '
                f'<b>{e(s["titel"] or "(ohne Titel)")}</b>'
                + (f' <i>{e(s["akronym"])}</i>' if s["akronym"] else "")
                + f'<div class="meta">{e(s["indikation"])}'
                + (f' · {s["teilnehmer"]} Teilnehmende' if s.get("teilnehmer") else "")
                + f' · <a href="https://drks.de/search/de/trial/{e(s["id"])}" '
                  f'target="_blank" rel="noopener">{e(s["id"])}</a></div>'
                + (f'<div class="chips">{chips}</div>' if chips else "")
                + "</li>")

        hubs = "".join(
            f'<a class="chip hub" href="{e(HUB_NAMEN[h][1])}" target="_blank" '
            f'rel="noopener">{e(HUB_NAMEN[h][0])} · {n}</a>'
            for h, n in z["hubs"].most_common() if h in HUB_NAMEN) or \
            '<span class="chip">keine Zuordnung</span>'

        # Traegerart: wer die Forschung traegt, bestimmt Auftrag und
        # Finanzierung. Das gehoert sichtbar auf die Seite.
        tart = z["traegerart"].most_common(1)[0][0]
        traeger = ('<div class="box"><h3>Art der Einrichtung</h3>'
                   f'<p class="tart">{e(tart)}</p>'
                   f'<p class="hinweis">{e(z["traegergrund"])}. Abgeleitet aus '
                   "dem Namen, nicht aus einem Feld des Registers.</p></div>")

        # Fachrichtung - nur was der Name nennt, nichts geraten.
        if z["faecher"]:
            zeilen = "".join(f'<span class="chip fach">{e(f)} · {n}</span>'
                             for f, n in z["faecher"].most_common())
            fach = ('<div class="box"><h3>Wissenschaftsrichtung</h3>'
                    f'<div class="chips">{zeilen}</div>'
                    "<p class='hinweis'>Aus dem Namen der Einrichtung "
                    "abgelesen.</p></div>")
        else:
            fach = ('<div class="box"><h3>Wissenschaftsrichtung</h3>'
                    "<p class='hinweis'>Das Register nennt hier nur den Namen "
                    "des Hauses, nicht das Institut. Die Fachrichtung ist "
                    "daraus nicht abzulesen, und wird nicht geraten. Die "
                    "Einrichtung kann sie unten selbst eintragen.</p></div>")

        # Studienzentren: rekrutierende Einrichtungen bekommen KEINE eigene
        # Seite, werden aber genannt - sie sind Teil der Studie.
        zentren = ""
        if z["zentren"]:
            liste = "".join(
                f'<li>{e(z["zentrenname"][k].most_common(1)[0][0])}'
                + (f" · {c} Studien" if c > 1 else "") + "</li>"
                for k, c in z["zentren"].most_common(25))
            mehr = (f"<p class='hinweis'>und {len(z['zentren']) - 25} weitere</p>"
                    if len(z["zentren"]) > 25 else "")
            zentren = ('<div class="box"><h3>Wo rekrutiert wurde</h3>'
                       "<p class='hinweis'>Praxen, Kliniken und Einrichtungen, "
                       "die Teilnehmende für die Studien dieses Standorts "
                       "eingeschlossen haben. Sie forschen nicht selbst und "
                       "haben deshalb keine eigene Profilseite.</p>"
                       "<ul style='margin:8px 0 0;padding-left:18px;"
                       f"font-size:12.5px;color:var(--ink-soft)'>{liste}</ul>"
                       f"{mehr}</div>")

        ethik = ""
        if z["kommissionen"]:
            zeilen = "".join(f"<li>{e(k)} · {n}</li>"
                             for k, n in z["kommissionen"].most_common(4))
            ethik = ('<div class="box"><h3>Ethikvoten</h3><ul style="margin:8px 0 0;'
                     f'padding-left:18px;font-size:13px;color:var(--ink-soft)">{zeilen}'
                     "</ul></div>")

        # Die Einrichtung selbst: Netzadresse, ROR-Kennung, eigenes
        # Publikationsverzeichnis. Nur was dem Waechter in repositorien.py
        # standgehalten hat - ungeprueftes wird nicht verlinkt.
        imnetz = ""
        netzzeilen: list[str] = []   # NICHT „zeilen": der Name gehoert dem Ethik-Kasten
        rep = REPOS.get(z["name"])
        if rep and rep.get("geprueft"):
            netzzeilen = []
            if rep.get("netzadresse"):
                netzzeilen.append(
                    f'<li><a href="{e(rep["netzadresse"])}" target="_blank" '
                    'rel="noopener">Netzauftritt der Einrichtung ↗</a></li>')
            for r in rep.get("repositorien", []):
                if not r.get("name"):
                    continue
                titel = e(r["name"])
                if r.get("adresse"):
                    titel = (f'<a href="{e(r["adresse"])}" target="_blank" '
                             f'rel="noopener">{titel} ↗</a>')
                zahl = (f" · {r['arbeiten']:,} Arbeiten".replace(",", ".")
                        if r.get("arbeiten") else "")
                netzzeilen.append(f'<li>{titel}'
                              '<br><span style="color:var(--ink-faint)">'
                              f"Publikationsverzeichnis der Einrichtung{zahl}"
                              "</span></li>")
            if rep.get("ror"):
                netzzeilen.append(
                    f'<li><a href="{e(rep["ror"])}" target="_blank" '
                    f'rel="noopener">{e(rep["ror"].rsplit("/", 1)[-1])} ↗</a>'
                    '<br><span style="color:var(--ink-faint)">'
                    "Kennung im Research Organization Registry</span></li>")
        # In welchen oeffentlichen Verzeichnissen die Einrichtung vorkommt.
        # Jeder Verweis fuehrt auf den Eintrag DIESER Einrichtung - nicht auf
        # die Startseite des Verzeichnisses.
        verzweise = ""
        eintraege = [x for x in VERZ.get(z["name"], [])
                     if x.get("adresse") and x["verzeichnis"] not in
                     ("ROR", "OpenAlex")]
        if eintraege:
            teile = []
            for x in eintraege:
                beschr = e(x.get("was") or x["verzeichnis"])
                teile.append(
                    f'<li><a href="{e(x["adresse"])}" target="_blank" '
                    f'rel="noopener">{e(x["verzeichnis"])} ↗</a>'
                    + (f' <span style="color:var(--ink-faint)">'
                       f'{e(str(x["kennung"]))}</span>' if x.get("kennung")
                       else "")
                    + f'<br><span style="color:var(--ink-faint)">{beschr}'
                    + (f' · <a href="{e(x["ziel"])}" target="_blank" '
                       f'rel="noopener">zum Repositorium ↗</a>'
                       if x.get("ziel") else "")
                    + "</span></li>")
            verzweise = (
                "<p style='margin:14px 0 4px;font-weight:700;font-size:13px'>"
                f"In weiteren Verzeichnissen ({len(eintraege)})</p>"
                "<ul style='margin:0;padding-left:18px;font-size:13px'>"
                + "".join(teile) + "</ul>")

        # Der Kasten erscheint IMMER - auch wenn wir nichts gefunden haben.
        # Gerade dann ist er wichtig: Dann ist er die Einladung, es selbst
        # einzutragen. Ein stillschweigend fehlender Kasten sieht fuer die
        # Verantwortlichen so aus, als sei nichts zu melden.
        selbst = (
            "<p class='hinweis' style='margin-top:12px'>Fehlt hier Ihr "
            "Publikationsverzeichnis, oder steht etwas falsch? Diese "
            "Verzeichnisse pflegt Ihre Einrichtung nicht selbst. "
            "richtigstellen können das nur Sie: "
            "<a href='#eintragen' class='zum-formular' "
            "data-feld='repositorien'>selbst eintragen</a>.</p>")
        if netzzeilen or verzweise:
            imnetz = (
                '<div class="box"><h3>Die Einrichtung im Netz</h3>'
                "<ul style='margin:8px 0 0;padding-left:18px;font-size:13px'>"
                + "".join(netzzeilen) + "</ul>" + verzweise
                + "<p class='hinweis'>Zusammengetragen über die "
                "ROR-Kennung aus ROR, OpenAlex, Wikidata und re3data "
                "(alle offen), geprüft gegen Name und Ort. Nicht enthalten: "
                "OpenDOAR (Zugang nur mit Schlüssel), GERiT (keine "
                "Schnittstelle), FIS-Landkarte (kein Export).</p>"
                + selbst + "</div>")
        else:
            imnetz = (
                '<div class="box"><h3>Die Einrichtung im Netz</h3>'
                "<p style='font-size:13px;color:var(--ink-soft);margin:8px 0 0'>"
                "Zu diesem Standort haben wir <b>keinen gesicherten "
                "Verzeichniseintrag</b>. Entweder führt ihn keines der "
                "offenen Register, oder der Name im Studienregister lässt "
                "sich nicht zweifelsfrei zuordnen. Dann verlinken wir "
                "lieber nichts als das Falsche.</p>" + selbst + "</div>")

        # Was die Ergebnispublikationen hergeben: Fachgebiet auf Studienebene
        # und die mitwirkenden Einrichtungen. Beides aus OpenAlex, aufgeloest
        # ueber die im DRKS genannten DOIs.
        publik = ""
        if DOIB:
            fach_zahl: collections.Counter = collections.Counter()
            mit: dict[str, dict] = {}
            arbeiten_n = 0
            studien_mit = 0
            for s in z["studien"]:
                b = DOIB["studien"].get(s["id"])
                if not b or not b["arbeiten"]:
                    continue
                studien_mit += 1
                arbeiten_n += len(b["arbeiten"])
                for f in b.get("fach") or []:
                    fach_zahl[f] += 1
                for arb in b["arbeiten"]:
                    for ins in arb.get("einrichtungen") or []:
                        # Die eigene Einrichtung ist kein Mitwirkender.
                        if rep and rep.get("ror") == ins["ror"]:
                            continue
                        m = mit.setdefault(ins["ror"], dict(ins, n=0))
                        m["n"] += 1
            if studien_mit:
                t = ["<div class=\"box\"><h3>Aus den Ergebnispublikationen</h3>",
                     "<p style='font-size:13px;color:var(--ink-soft);"
                     "margin:8px 0 0'>",
                     f"{studien_mit} der {len(z['studien'])} Studien nennen "
                     f"Veröffentlichungen; dazu sind {arbeiten_n} "
                     "Arbeiten auffindbar.</p>"]
                if fach_zahl:
                    t.append("<p style='margin:14px 0 4px;font-weight:700;"
                             "font-size:13px'>Fachgebiete der Arbeiten</p>"
                             "<div class='chips'>")
                    for f, n in fach_zahl.most_common(8):
                        t.append(f'<span class="chip">{e(f)}'
                                 + (f" · {n}" if n > 1 else "") + "</span>")
                    t.append("</div><p class='hinweis'>Systematik von OpenAlex, "
                             "unverändert englisch, weil die Quelle englisch "
                             "ist. Wir übersetzen und fassen nicht zusammen.</p>")
                if mit:
                    oben = sorted(mit.values(), key=lambda x: -x["n"])[:12]
                    t.append("<p style='margin:14px 0 4px;font-weight:700;"
                             f"font-size:13px'>Mitwirkende Einrichtungen "
                             f"({len(mit)})</p><div class='chips'>")
                    for m in oben:
                        land = (f' · {e(m["land"])}'
                                if m.get("land") and m["land"] != "DE" else "")
                        t.append(
                            f'<a class="chip" href="{e(m["ror"])}" '
                            f'target="_blank" rel="noopener">'
                            f'{e(m["name"] or m["ror"])}{land} ↗</a>')
                    t.append("</div>")
                    # Dieser Satz ist der Grund, warum der Kasten getrennt
                    # steht und nicht in die Standortzaehlung einfliesst.
                    t.append("<p class='hinweis'><b>Das sind Mitautoren, "
                             "nicht Forschungsstandorte.</b> Bei einer "
                             "Multizenterstudie stehen hier die Partner aller "
                             "beteiligten Häuser. Wer die Studie leitet, "
                             "sagt diese Liste nicht. Sie zählt auch nicht in "
                             "die Studienzahl dieses Standorts.</p>")
                # Wer hier veroeffentlicht hat. BEWUSST OHNE RANGPLATZ:
                # Die Grundlage sind nur die Studien, die Ergebnis-DOIs
                # nennen - eine einzige DOI-reiche Studie hebt ihr ganzes
                # Team. Das waere keine Rangliste, sondern ein Artefakt.
                eigen: dict[str, dict] = {}
                eigen_ror = (rep or {}).get("ror")
                if eigen_ror:
                    for s in z["studien"]:
                        b = DOIB["studien"].get(s["id"])
                        for arb in (b or {}).get("arbeiten", []):
                            for pers in arb.get("personen") or []:
                                if eigen_ror not in (pers.get("rors") or []):
                                    continue
                                m = eigen.setdefault(pers["oa_id"], {
                                    "name": pers.get("name"),
                                    "orcid": pers.get("orcid"),
                                    "oa_id": pers["oa_id"],
                                    "arbeiten": 0, "erst_letzt": 0})
                                m["arbeiten"] += 1
                                if pers.get("stelle") in ("first", "last"):
                                    m["erst_letzt"] += 1
                if eigen:
                    liste = sorted(eigen.values(),
                                   key=lambda x: (-x["arbeiten"],
                                                  x["name"] or ""))
                    zeilen_p = []
                    for m in liste[:14]:
                        ziel_p = m["orcid"] or m["oa_id"]
                        rolle = (" · davon %d mal erst- oder letztgenannt"
                                 % m["erst_letzt"]) if m["erst_letzt"] else ""
                        zeilen_p.append(
                            f'<li><a href="{e(ziel_p)}" target="_blank" '
                            f'rel="noopener">{e(m["name"] or "ohne Namen")} ↗</a>'
                            '<br><span style="color:var(--ink-faint)">'
                            f'{m["arbeiten"]} '
                            f'{"Arbeit" if m["arbeiten"] == 1 else "Arbeiten"}'
                            f"{rolle}</span></li>")
                    rest = (f" · {len(liste) - 14} weitere"
                            if len(liste) > 14 else "")
                    t.append(
                        "<p style='margin:16px 0 4px;font-weight:700;"
                        f"font-size:13px'>Wer hier veröffentlicht hat "
                        f"({len(liste)}){rest}</p>"
                        "<ul style='margin:6px 0 0;padding-left:18px;"
                        "font-size:13px'>" + "".join(zeilen_p) + "</ul>"
                        "<p class='hinweis'><b>Keine Rangliste.</b> Gezählt "
                        "sind nur die Arbeiten, die zu den hier gelisteten "
                        "Studien als Ergebnis angegeben sind. Eine einzige "
                        "publikationsreiche Studie hebt ihr ganzes Team. "
                        "Wer hier fehlt, hat nicht weniger geforscht, "
                        "sondern führt keine Studie mit Ergebnis-DOI. "
                        "Zuordnung über die ROR-Kennung der Einrichtung in "
                        "der jeweiligen Arbeit; Verweis auf ORCID, sonst "
                        "OpenAlex.</p>")
                publik = "".join(t) + "</div>"

        inno = ""
        if z["ror"]:
            inno = ('<div class="box"><h3>Im Innovationsfonds-Radar</h3>'
                    "<p style='font-size:13px;color:var(--ink-soft);margin:8px 0 0'>"
                    "Diese Einrichtung ist im Innovationsfonds-Radar als "
                    "Projektträger geführt.</p>"
                    '<div class="chips"><a class="chip inno" '
                    'href="https://innofonds.m-vf.de" target="_blank" '
                    'rel="noopener">Innovationsfonds-Radar ↗</a></div></div>')

        # MVF hat diesen Standort vielleicht schon portraetiert.
        serie = vfserie.beitraege(z["name"], ort)
        dnvf = ""
        if serie:
            zeilen = "".join(
                f'<li><a href="{e(b["link"])}" target="_blank" rel="noopener">'
                f'{e(b["titel"])}</a><br><span style="color:var(--ink-faint)">'
                f'MVF {e(b["ausgabe"])} · {e(b["einrichtung"])}</span></li>'
                for b in serie)
            dnvf = ('<div class="box"><h3>In der MVF-Serie porträtiert</h3>'
                    "<ul style='margin:8px 0 0;padding-left:18px;font-size:13px'>"
                    f"{zeilen}</ul>"
                    "<p class='hinweis'>Aus der Serie „Versorgungsforschung made "
                    f'in …" · <a href="{e(vfserie.UEBERSICHT)}" target="_blank" '
                    'rel="noopener">alle Beiträge ↗</a></p></div>')
        hinweis_schreib = ""
        if len(z["schreibweisen"]) > 1:
            # Seit dem 01.11.2026 gibt es ZWEI Wege: die handgepruefte
            # Traegerliste des Innovationsfonds und die ROR-Kennung aus
            # repositorien.json. Der Kasten muss sagen, welcher es war -
            # „ueber die Traegerliste" allein waere jetzt falsch.
            ror_wege = {RORWEG.get(sw.strip()) for sw in z["schreibweisen"]}
            if ror_wege == {True}:
                wege = "über die ROR-Kennung"
            elif True in ror_wege:
                wege = ("über die Trägerliste des Innovationsfonds und "
                        "über die ROR-Kennung")
            else:
                wege = "über die Trägerliste des Innovationsfonds"
            hinweis_schreib = (
                '<div class="box"><h3>Zusammengeführte Schreibweisen</h3>'
                "<p style='font-size:12.5px;color:var(--ink-faint);margin:8px 0 0'>"
                "Im Register erscheint dieser Standort unter "
                f"{len(z['schreibweisen'])} Schreibweisen; "
                f"zusammengeführt {wege}:</p>"
                "<ul style='margin:6px 0 0;padding-left:18px;font-size:12.5px;"
                "color:var(--ink-faint)'>"
                + "".join(f"<li>{e(s)}</li>" for s in sorted(z["schreibweisen"]))
                + "</ul></div>")

        seite = (vorlage
                 .replace("{{NAME}}", e(z["name"]))
                 .replace("{{NAME_ROH}}", e(z["name"]))
                 .replace("{{ORT}}", e(ort))
                 .replace("{{LAND}}", f" · {e(land)}" if land else "")
                 .replace("{{STAND}}", e(stand))
                 .replace("{{KENNZAHLEN}}", kennzahlen)
                 .replace("{{STUDIEN}}", "".join(studien))
                 .replace("{{HUBS}}", hubs)
                 .replace("{{TRAEGER}}", traeger + fach)
                 .replace("{{VERZEICHNIS}}", imnetz)
                 .replace("{{PUBLIKATIONEN}}", publik)
                 .replace("{{ZENTREN}}", zentren)
                 .replace("{{ETHIK}}", ethik)
                 .replace("{{INNO}}", inno)
                 .replace("{{DNVF}}", dnvf + hinweis_schreib)
                 .replace("{{ENDPUNKT}}", ENDPUNKT)
                 .replace("{{STANDORT_JSON}}",
                          json.dumps({"kennung": z["kennung"], "name": z["name"],
                                      "ror": z["ror"], "ort": ort},
                                     ensure_ascii=False)))

        datei = schluessel(z["name"]) + ".html"
        (ZIEL / datei).write_text(leisten.einsetzen(seite, netz, fuss),
                                  encoding="utf-8")
        # `schreibweisen` traegt die Verbindung: Die Landkarte kennt nur die
        # Rohnamen aus dem Register und findet darueber die Profilseite.
        verzeichnis.append({"datei": datei, "name": z["name"], "ort": ort,
                            "land": land, "studien": len(z["studien"]),
                            "ror": z["ror"],
                            # Koordinaten nur aus GEPRUEFTEN Zuordnungen. Ein
                            # Punkt an der falschen Stelle ist schlimmer als
                            # gar kein Punkt: Er behauptet etwas.
                            "lat": (rep or {}).get("lat") if (rep or {}).get("geprueft") else None,
                            "lon": (rep or {}).get("lon") if (rep or {}).get("geprueft") else None,
                            "rekrutiert": st.get("rekrutiert", 0),
                            "hubs": [h for h, _ in z["hubs"].most_common()],
                            "traegerart": tart,
                            "faecher": [f for f, _ in z["faecher"].most_common()],
                            "zentren": len(z["zentren"]),
                            "schreibweisen": sorted(z["schreibweisen"])})

    (DATEN / "standorte.json").write_text(
        json.dumps({"stand": stand, "standorte": verzeichnis},
                   ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n{len(verzeichnis)} Profilseiten in {ZIEL}")
    print(f"Verzeichnis: {DATEN / 'standorte.json'}")
    if not ENDPUNKT:
        print("\nHINWEIS: ENDPUNKT ist leer. Die Formulare sagen das ehrlich und "
              "senden nichts. Siehe MANUAL.md, Abschnitt Endpunkt.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
