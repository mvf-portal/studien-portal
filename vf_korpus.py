"""Baut einen etikettierten Bestand fuer die Frage: Was ist Versorgungsforschung?

WARUM ES DIESE DATEI GIBT
-------------------------
Der Textfilter in zuschnitt.py waehlt aus dem DRKS 710 Studien aus. Ob er
gut waehlt, liess sich bisher nicht sagen: Lernt man aus seinen eigenen
Treffern, rekonstruiert man nur die eigene Regel (97 Prozent Erkennung bei
0 Prozent Fehlalarm, und beides bedeutungslos).

Das Etikett muss von aussen kommen. Peters Hinweis: die Abstracts des
Deutschen Kongresses fuer Versorgungsforschung (DKVF), die das DNVF bei
Zenodo ablegt. Was dort vorgetragen wird, IST Versorgungsforschung, ohne
dass wir etwas schaetzen muessen.

Dazu die Hochschullehrenden der VF-Standorte: 52 Namen mit Ort.

  py vf_korpus.py              baut daten/vf_korpus.json          [Netz]
  py vf_korpus.py --gegentest  prueft die Personen-Zuordnung
  py vf_korpus.py --zenodo     nur die DKVF-Abstracts holen

WAS HERAUSKOMMT
---------------
  titel_positiv   DKVF-Titel, sicher Versorgungsforschung
  personen        Menschen der VF-Gemeinschaft, mit OpenAlex-Kennung
  arbeiten        ihre Veroeffentlichungen, nach Teilgebiet etikettiert

⚠ ZWEI DINGE, DIE MAN WISSEN MUSS
---------------------------------
1. Zenodo liefert KEINEN Abstracttext, nur Titel, Namen und Zugehoerigkeit.
   Die Vortraege liegen als Datei dahinter. Positiv sind also die TITEL.
2. Eine VF-Professorin veroeffentlicht auch klinisch. Gemessen an 14
   Personen: 50 Prozent ihrer Arbeiten liegen in versorgungsnahen
   Teilgebieten, gegen eine Nulllinie von 3,5 Prozent. Das ist ein starkes
   Signal, aber kein Etikett. Darum wird je ARBEIT etikettiert, nicht je
   Person.
"""
import json
import pathlib
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request

import repositorien as R

HIER = pathlib.Path(__file__).parent
DATEN = HIER / "daten"
DNVF = (HIER.parent / "dnvf-hochschullehrende" / "namen.json")
MAILTO = "stegmaier@m-vf.de"
UA = {"User-Agent": f"vf-landkarte/1.0 (mailto:{MAILTO})"}
GEMEINSCHAFTEN = ["dkvf2025", "dkvf2026"]

# Teilgebiete, in denen Versorgungsforschung erscheint.
#
# ⚠ GEEICHT, NICHT GERATEN. Die erste Fassung dieser Liste war von Hand
# geschrieben und falsch. Gemessen am 01.11.2026 an den 1.011 Artikeln des
# Monitor Versorgungsforschung - einem Bestand, der zu 100 Prozent
# Versorgungsforschung ist - lagen nur 42 Prozent darin. Die zweitgroesste
# Gruppe war "Economics and Econometrics", also Gesundheitsoekonomie, die
# gefehlt hatte.
#
# Darum neu bestimmt ueber die Anreicherung: Anteil im reinen VF-Bestand
# geteilt durch Weltanteil des Teilgebiets. Aufgenommen ist, was mindestens
# fuenffach angereichert ist.
#
#    33x  Health Information Management        12x  Economics and Econometrics
#    31x  General Health Professions            8x  Emergency Medical Services
#    28x  Modeling and Simulation               7x  Statistics, Probability
#     7x  Public Health, Environmental ...      7x  Information Systems
#
# Nicht aufgenommen, obwohl angereichert: Pharmacology, Oncology, Immunology,
# Endocrinology. Die stehen bei MVF, weil MVF ueber diese Indikationen
# berichtet, nicht weil das Teilgebiet Versorgungsforschung waere. Wer sie
# aufnimmt, holt sich die ganze klinische Literatur ins Netz.
VF_NAH = {
    "Health Information Management",
    "General Health Professions",
    "Modeling and Simulation",
    "Economics and Econometrics",
    "Public Health, Environmental and Occupational Health",
    "Information Systems and Management",
    "Statistics, Probability and Uncertainty",
    "Emergency Medical Services",
    "Health Policy", "Epidemiology", "Nursing",
    "Health (social science)", "Rehabilitation",
    "Physical Therapy, Sports Therapy and Rehabilitation",
    "Geriatrics and Gerontology", "Clinical Psychology",
    "Sociology and Political Science", "Education",
}


def _hol(url, versuche=4):
    for i in range(versuche):
        try:
            with urllib.request.urlopen(
                    urllib.request.Request(url, headers=UA), timeout=120) as f:
                return json.loads(f.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and i < versuche - 1:
                time.sleep(3 * (i + 1))
                continue
            return None
        except Exception:
            if i < versuche - 1:
                time.sleep(3 * (i + 1))
                continue
            return None
    return None


# ------------------------------------------------------------------- Zenodo

def dkvf_holen():
    """Alle DKVF-Abstracts aus den Zenodo-Gemeinschaften.

    Zenodo blaettert ueber `page`. Die Satzgroesse ist bei 100 gedeckelt.
    """
    saetze = []
    for slug in GEMEINSCHAFTEN:
        seite, geholt = 1, 0
        while True:
            # Zenodo deckelt die Satzgroesse. size=100 antwortet mit
            # HTTP 400, size=25 traegt.
            u = (f"https://zenodo.org/api/communities/{slug}/records"
                 f"?size=25&page={seite}")
            d = _hol(u)
            if not d or not d["hits"]["hits"]:
                break
            gesamt = d["hits"]["total"]
            for r in d["hits"]["hits"]:
                m = r.get("metadata") or {}
                saetze.append({
                    "quelle": slug,
                    "id": r.get("id"),
                    "doi": r.get("doi"),
                    "jahr": (m.get("publication_date") or "")[:4],
                    "titel": m.get("title") or "",
                    "personen": [
                        {"name": a.get("name"),
                         "zugehoerigkeit": a.get("affiliation")}
                        for a in (m.get("creators") or []) if a.get("name")],
                })
                geholt += 1
            print(f"  {slug}: {geholt} von {gesamt}")
            if geholt >= gesamt:
                break
            seite += 1
            time.sleep(0.3)
    return saetze


# ------------------------------------------------------- Personen aufloesen

def norm(s):
    s = (s or "").lower()
    for a, b in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"),
                 ("ß", "ss")):
        s = s.replace(a, b)
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()


def ort_passt(erwartet, einrichtung):
    """Stimmt der Ort? Mit derselben Synonymtabelle wie repositorien.py.

    Ohne sie scheitert „Koeln" an „University of Cologne" - gemessen am
    01.11.2026, und zwar an Holger Pfaff, dem bekanntesten Namen der Liste.
    """
    if not erwartet:
        return None
    stadt_e = R.stadt(erwartet)
    if not stadt_e:
        return None
    kandidaten = [einrichtung.get("display_name") or ""]
    v = ((einrichtung.get("geo") or {}).get("city")) or ""
    if v:
        kandidaten.append(v)
    for k in kandidaten:
        # WORTWEISE durch die Synonymtabelle. `stadt()` auf die ganze
        # Zeichenkette anzuwenden hilft nicht: „University of Cologne"
        # normalisiert zu „university of cologne", und darin steht
        # „cologne" als Wort, nicht als ganzer Wert. Genau daran ist der
        # Gegentest am 01.11.2026 gescheitert, bei Koeln und bei Muenchen.
        if stadt_e == R.stadt(k):
            return True
        for wort in re.split(r"[^A-Za-zÀ-ɏ]+", k):
            if wort and R.stadt(wort) == stadt_e:
                return True
    return False


def person_aufloesen(name, ort=None, zugehoerigkeit=None):
    """Eine Person in OpenAlex, gewaechtert ueber Ort oder Zugehoerigkeit.

    Der Name allein genuegt nicht. „Michael Freitag" trifft sonst einen
    Produktionstechniker in Bremen mit 345 Arbeiten statt des
    Allgemeinmediziners in Oldenburg mit 163.
    """
    d = _hol("https://api.openalex.org/authors?per-page=10&search="
             + urllib.parse.quote(name)
             + f"&mailto={urllib.parse.quote(MAILTO)}")
    if not d or not d.get("results"):
        return None, "nicht gefunden"

    merkmal = ort or zugehoerigkeit
    deutsche = []
    for a in d["results"]:
        for i in (a.get("last_known_institutions") or []):
            if (i or {}).get("country_code") != "DE":
                continue
            deutsche.append((a, i))
            if merkmal and ort_passt(merkmal, i):
                return a, f"Ort haelt: {i.get('display_name')}"
            if zugehoerigkeit and norm(zugehoerigkeit)[:14] \
                    and norm(zugehoerigkeit)[:14] in norm(i.get("display_name")):
                return a, f"Zugehoerigkeit haelt: {i.get('display_name')}"
    if merkmal:
        # Ein Merkmal war da und hat NICHT gehalten. Dann lieber nichts.
        return None, "Ort oder Zugehoerigkeit halten nicht"
    if len(deutsche) == 1:
        return deutsche[0][0], "einzige deutsche Person dieses Namens"
    return None, "mehrdeutig, kein Merkmal zum Pruefen"


def arbeiten_holen(oa_id, hoechstens=200):
    kurz = oa_id.rsplit("/", 1)[-1]
    d = _hol(f"https://api.openalex.org/works?per-page={hoechstens}"
             f"&mailto={urllib.parse.quote(MAILTO)}"
             "&select=id,doi,display_name,publication_year,primary_topic,language"
             f"&filter=author.id:{kurz},publication_year:2015-2026")
    if not d:
        return [], 0
    raus = []
    for w in d.get("results", []):
        pt = w.get("primary_topic") or {}
        tg = (pt.get("subfield") or {}).get("display_name")
        raus.append({
            "oa_id": w.get("id"),
            "doi": w.get("doi"),
            "titel": w.get("display_name"),
            "jahr": w.get("publication_year"),
            "sprache": w.get("language"),
            "teilgebiet": tg,
            "vf_nah": tg in VF_NAH,
        })
    return raus, d["meta"]["count"]


# ------------------------------------------------------------------ Gegentest

def gegentest():
    """Prueft den Waechter der Personen-Zuordnung, ohne Netz."""
    ok = True
    print("Ortsabgleich mit Synonymtabelle:")
    faelle = [
        # (erwarteter Ort, Einrichtung aus OpenAlex, soll passen)
        ("Köln", {"display_name": "University of Cologne"}, True),
        ("Köln", {"display_name": "Universität zu Köln"}, True),
        ("Oldenburg", {"display_name": "Carl von Ossietzky Universität "
                                        "Oldenburg"}, True),
        ("Oldenburg", {"display_name": "University of Bremen"}, False),
        ("München", {"display_name": "Technical University of Munich"}, True),
        ("Hannover", {"display_name": "Hannover Medical School"}, True),
        # Ueber geo.city, wenn der Name den Ort nicht nennt
        ("Berlin", {"display_name": "Charité",
                    "geo": {"city": "Berlin"}}, True),
        ("Berlin", {"display_name": "Charité",
                    "geo": {"city": "Hamburg"}}, False),
        # Ohne erwarteten Ort gibt es nichts zu pruefen
        ("", {"display_name": "irgendwas"}, None),
    ]
    for ort, einr, soll in faelle:
        ist = ort_passt(ort, einr)
        gut = ist == soll
        ok = ok and gut
        print(f"  {'ok ' if gut else 'FEHLER'} {ort or '(ohne Ort)':<12} "
              f"{einr['display_name'][:40]:<42} {ist}")

    print("\nNamensnormalisierung:")
    for a, b in (("München", "muenchen"), ("Köln", "koeln"),
                 ("Straße", "strasse"), ("Charité", "charite")):
        gut = norm(a) == b
        ok = ok and gut
        print(f"  {'ok ' if gut else 'FEHLER'} {a} -> {norm(a)}")

    print("\n" + ("Gegentest bestanden." if ok else "GEGENTEST GESCHEITERT."))
    return ok


# ----------------------------------------------------------------------- Lauf

def main():
    if "--gegentest" in sys.argv:
        return 0 if gegentest() else 1

    print("1. DKVF-Abstracts aus Zenodo")
    dkvf = dkvf_holen()
    print(f"   {len(dkvf)} Abstracts, sicher Versorgungsforschung")

    # Personen aus den Abstracts zusammentragen
    aus_dkvf = {}
    for s in dkvf:
        for p in s["personen"]:
            n = p["name"].strip()
            e = aus_dkvf.setdefault(n, {"name": n, "zugehoerigkeit": None,
                                        "abstracts": 0, "herkunft": "DKVF"})
            e["abstracts"] += 1
            if p.get("zugehoerigkeit") and not e["zugehoerigkeit"]:
                e["zugehoerigkeit"] = p["zugehoerigkeit"]
    print(f"   {len(aus_dkvf)} verschiedene Personen darin")

    if "--zenodo" in sys.argv:
        (DATEN / "dkvf.json").write_text(json.dumps(
            {"abstracts": dkvf, "personen": list(aus_dkvf.values())},
            ensure_ascii=False, indent=1), encoding="utf-8")
        print("-> daten/dkvf.json")
        return 0

    print("\n2. Personen aufloesen")
    namen = []
    if DNVF.exists():
        for n in json.loads(DNVF.read_text(encoding="utf-8")):
            namen.append({"name": f'{n["vorname"]} {n["nachname"]}',
                          "ort": n.get("ort"), "herkunft": "DNVF",
                          "zugehoerigkeit": None})
        print(f"   {len(namen)} Hochschullehrende aus der DNVF-Liste")
    else:
        print("   HINWEIS: dnvf-hochschullehrende/namen.json fehlt")

    # Aus dem DKVF die haeufigsten, sonst wird der Lauf sehr lang.
    oft = sorted(aus_dkvf.values(), key=lambda x: -x["abstracts"])
    grenze = 2
    dazu = [x for x in oft if x["abstracts"] >= grenze]
    print(f"   {len(dazu)} DKVF-Personen mit mindestens {grenze} Abstracts")
    for x in dazu:
        namen.append({"name": x["name"], "ort": None, "herkunft": "DKVF",
                      "zugehoerigkeit": x.get("zugehoerigkeit")})

    personen, ungeloest = [], []
    for i, n in enumerate(namen, 1):
        a, grund = person_aufloesen(n["name"], n.get("ort"),
                                    n.get("zugehoerigkeit"))
        time.sleep(0.25)
        if not a:
            ungeloest.append({**n, "grund": grund})
            continue
        personen.append({**n, "oa_id": a["id"],
                         "oa_name": a.get("display_name"),
                         "orcid": a.get("orcid"),
                         "werke_gesamt": a.get("works_count"),
                         "grund": grund})
        if i % 25 == 0:
            print(f"   {i} von {len(namen)}, aufgeloest {len(personen)}")
    print(f"   aufgeloest: {len(personen)} von {len(namen)}, "
          f"offen {len(ungeloest)}")

    print("\n3. Arbeiten holen und etikettieren")
    arbeiten, gesehen = [], set()
    nah = 0
    for i, p in enumerate(personen, 1):
        ws, gesamt = arbeiten_holen(p["oa_id"])
        time.sleep(0.25)
        for w in ws:
            if w["oa_id"] in gesehen:
                continue
            gesehen.add(w["oa_id"])
            w["person"] = p["name"]
            arbeiten.append(w)
            nah += 1 if w["vf_nah"] else 0
        if i % 25 == 0:
            print(f"   {i} von {len(personen)}, Arbeiten {len(arbeiten)}")

    print(f"\n   Arbeiten gesamt      : {len(arbeiten)}")
    print(f"   davon versorgungsnah : {nah} "
          f"({100.0 * nah / max(1, len(arbeiten)):.1f} %)")
    print("   Nulllinie aller deutschen Arbeiten: 3,5 %")

    ziel = DATEN / "vf_korpus.json"
    ziel.write_text(json.dumps({
        "stand": time.strftime("%Y-%m-%d"),
        "hinweis": (
            "Etikettierter Bestand fuer die Frage, was Versorgungsforschung "
            "ist. Die DKVF-Titel sind sicher positiv: Was auf dem Deutschen "
            "Kongress fuer Versorgungsforschung vorgetragen wird, IST "
            "Versorgungsforschung. Die Arbeiten der Personen sind je Arbeit "
            "etikettiert, nicht je Person - eine VF-Professorin "
            "veroeffentlicht auch klinisch."),
        "quellen": {
            "DKVF": "https://zenodo.org/communities/dkvf2025 und dkvf2026",
            "DNVF": "Hochschullehrende der VF-Standorte, Hausliste",
            "OpenAlex": "https://openalex.org (CC0)",
        },
        "zaehlung": {
            "dkvf_abstracts": len(dkvf),
            "dkvf_personen": len(aus_dkvf),
            "personen_aufgeloest": len(personen),
            "personen_offen": len(ungeloest),
            "arbeiten": len(arbeiten),
            "arbeiten_vf_nah": nah,
        },
        "titel_positiv": [{"titel": s["titel"], "jahr": s["jahr"],
                           "doi": s["doi"], "quelle": s["quelle"]}
                          for s in dkvf],
        "personen": personen,
        "personen_offen": ungeloest,
        "arbeiten": arbeiten,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"-> daten/vf_korpus.json ({ziel.stat().st_size / 1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
