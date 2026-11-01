"""Ergebnispublikationen der Studien gegen OpenAlex.

170 der 710 Studien nennen Ergebnispublikationen, insgesamt 388 DOIs
(377 eindeutig). Jede Arbeit in OpenAlex traegt ein Fachgebiet und die
Einrichtungen ihrer Autor:innen - beides mit ROR-Kennung.

Das gibt die Wissenschaftsrichtung auf STUDIENebene, wo fachrichtung.py
heute nur bei rund 19 Prozent aus dem Einrichtungsnamen schliessen kann.

  py doi_bezug.py              holt die Arbeiten, schreibt daten/doi_bezug.json
  py doi_bezug.py --gegentest  prueft Normalisierung und Zuordnung ohne Netz
  py doi_bezug.py --ohne-netz  rechnet nur aus dem vorhandenen Stand

WICHTIG, und auf der Seite auch so beschriftet: Die Einrichtungen einer
Publikation sind ihre MITAUTOREN. Bei einer Multizenterstudie sind das
Partner, nicht der Forschungsstandort. Sie werden darum getrennt gefuehrt
und nie in die Standortzaehlung gemischt.
"""
import json
import pathlib
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

HIER = pathlib.Path(__file__).parent
DATEN = HIER / "daten"
MAILTO = "stegmaier@m-vf.de"
STAPEL = 50          # OpenAlex erlaubt 50 Werte je filter-Liste
FELDER = ("id,doi,display_name,type,publication_year,primary_topic,topics,"
          "authorships,cited_by_count,open_access")


# --------------------------------------------------------------- DOI putzen

def doi_norm(s):
    """Blanker DOI in Kleinschreibung, ohne Vorsatz und ohne Beiwerk.

    Im DRKS stehen DOIs in jeder Form: nackt, als URL, mit „doi:" davor,
    mit nachlaufendem Punkt oder Klammer. Ohne das hier verliert der
    Stapelabruf still jeden zweiten Treffer.
    """
    if not s:
        return None
    t = str(s).strip()
    t = re.sub(r"^\s*(doi\s*:\s*|https?://(dx\.)?doi\.org/)", "", t, flags=re.I)
    t = t.strip().strip(".,;)]}­–— \t")
    t = t.replace("​", "")
    if not t.lower().startswith("10."):
        return None
    if "/" not in t:
        return None
    return t.lower()


# ------------------------------------------------------------------- abrufen

def _hol(url, versuche=4):
    for i in range(versuche):
        try:
            r = urllib.request.Request(
                url, headers={"User-Agent": f"vf-landkarte/1.0 (mailto:{MAILTO})"})
            with urllib.request.urlopen(r, timeout=90) as f:
                return json.loads(f.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and i < versuche - 1:
                time.sleep(2 * (i + 1))
                continue
            raise
        except Exception:
            if i < versuche - 1:
                time.sleep(2 * (i + 1))
                continue
            raise
    return None


def arbeiten_holen(dois):
    """Arbeiten in Stapeln von 50 holen. Rueckgabe: DOI -> Rohsatz."""
    gefunden = {}
    doppel = 0
    for i in range(0, len(dois), STAPEL):
        teil = dois[i:i + STAPEL]
        liste = "|".join(urllib.parse.quote(d, safe="") for d in teil)
        url = (f"https://api.openalex.org/works?per-page={STAPEL}"
               f"&mailto={urllib.parse.quote(MAILTO)}&select={FELDER}"
               f"&filter=doi:{liste}")
        d = _hol(url)
        for w in (d or {}).get("results", []):
            k = doi_norm(w.get("doi"))
            if not k:
                continue
            if k in gefunden:
                doppel += 1
            gefunden[k] = w
        print(f"  Stapel {i // STAPEL + 1:>2}: {len(teil):>2} angefragt, "
              f"{len(gefunden)} gefunden")
        time.sleep(0.2)
    if doppel:
        print(f"  Hinweis: {doppel} Arbeiten kamen doppelt zurueck")
    return gefunden


# ------------------------------------------------------------------ auswerten

def fach(w):
    """Fachgebiet der Arbeit, wie OpenAlex es fuehrt - unveraendert.

    Wir uebersetzen die Systematik nicht und fassen sie nicht zusammen.
    Sie ist englisch, weil die Quelle englisch ist; das steht auf der Seite.
    """
    pt = w.get("primary_topic") or {}
    if not pt:
        return None
    return {
        "thema": (pt.get("display_name") or None),
        "teilgebiet": ((pt.get("subfield") or {}).get("display_name") or None),
        "gebiet": ((pt.get("field") or {}).get("display_name") or None),
        "bereich": ((pt.get("domain") or {}).get("display_name") or None),
        "sicherheit": pt.get("score"),
    }


def personen(w):
    """Die Autor:innen einer Arbeit, mit ORCID wo vorhanden.

    Das sind veroeffentlichte Namen aus Publikationen - oeffentliche
    Angaben, keine Kontaktdaten aus dem Register. Die bleiben draussen,
    siehe die Fusszeile der Seiten.

    Die Reihenfolge der Autorenschaft wird MITGEFUEHRT (erste, mittlere,
    letzte). Ohne sie waere jede Zaehlung irrefuehrend: In der Medizin
    sagen Erst- und Letztautorenschaft etwas anderes aus als eine Nennung
    in der Mitte einer Multizenterarbeit.
    """
    raus, gesehen = [], set()
    for a in w.get("authorships") or []:
        au = a.get("author") or {}
        k = au.get("id")
        if not k or k in gesehen:
            continue
        gesehen.add(k)
        raus.append({
            "oa_id": k,
            "name": au.get("display_name"),
            "orcid": au.get("orcid"),
            "stelle": a.get("author_position"),
            # Die Einrichtungen DIESER Person in DIESER Arbeit. Ohne sie
            # liesse sich auf einer Standortseite nicht sagen, wer von dort
            # kommt und wer Mitautor:in eines anderen Hauses ist.
            "rors": [i["ror"] for i in (a.get("institutions") or [])
                     if i.get("ror")],
        })
    return raus


def einrichtungen(w):
    """ROR-Einrichtungen der Autorenschaft. MITAUTOREN, nicht Standort."""
    raus, gesehen = [], set()
    for a in w.get("authorships") or []:
        for inst in a.get("institutions") or []:
            r = inst.get("ror")
            if not r or r in gesehen:
                continue
            gesehen.add(r)
            raus.append({
                "ror": r,
                "name": inst.get("display_name"),
                "land": inst.get("country_code"),
                "typ": inst.get("type"),
            })
    return raus


def satz(w):
    oa = w.get("open_access") or {}
    return {
        "oa_id": w.get("id"),
        "titel": w.get("display_name"),
        "jahr": w.get("publication_year"),
        "art": w.get("type"),
        "zitiert": w.get("cited_by_count"),
        "frei": oa.get("is_oa"),
        "frei_url": oa.get("oa_url"),
        "fach": fach(w),
        "einrichtungen": einrichtungen(w),
        "personen": personen(w),
    }


def bauen(studien, arbeiten):
    """Je Studie: gefundene Arbeiten, Fachgebiete, Mitautoren-Einrichtungen."""
    je_studie = {}
    for s in studien:
        rohe = [d for d in (s.get("dois") or [])]
        norm = [doi_norm(d) for d in rohe]
        paare = [(r, n) for r, n in zip(rohe, norm) if n]
        if not paare:
            continue
        treffer, fehlt, unlesbar = [], [], [r for r, n in zip(rohe, norm) if not n]
        for roh, n in paare:
            if n in arbeiten:
                t = dict(arbeiten[n])
                t["doi"] = n
                treffer.append(t)
            else:
                fehlt.append(n)
        je_studie[s["id"]] = {
            "dois_genannt": len(rohe),
            "dois_unlesbar": unlesbar,
            "dois_ohne_arbeit": fehlt,
            "arbeiten": treffer,
        }
    return je_studie


def verdichten(je_studie):
    """Zaehlungen - und je Einrichtung die Studien, in denen sie mitwirkt."""
    je_fach, je_einrichtung, je_bereich = {}, {}, {}
    mit_fach = 0
    for sid, e in je_studie.items():
        faecher = []
        for a in e["arbeiten"]:
            f = a.get("fach") or {}
            if f.get("teilgebiet"):
                faecher.append(f["teilgebiet"])
                je_bereich[f.get("bereich") or "ohne"] = \
                    je_bereich.get(f.get("bereich") or "ohne", 0) + 1
            for inst in a.get("einrichtungen") or []:
                k = inst["ror"]
                z = je_einrichtung.setdefault(
                    k, {"ror": k, "name": inst["name"], "land": inst.get("land"),
                        "studien": [], "arbeiten": 0})
                z["arbeiten"] += 1
                if sid not in z["studien"]:
                    z["studien"].append(sid)
        if faecher:
            mit_fach += 1
            # haeufigstes Teilgebiet der Studie; bei Gleichstand alle behalten
            zahl = {}
            for f in faecher:
                zahl[f] = zahl.get(f, 0) + 1
            spitze = max(zahl.values())
            e["fach"] = sorted(f for f, n in zahl.items() if n == spitze)
            for f in e["fach"]:
                je_fach[f] = je_fach.get(f, 0) + 1
        else:
            e["fach"] = []
    return {
        "studien_mit_doi": len(je_studie),
        "studien_mit_fach": mit_fach,
        "je_fach": dict(sorted(je_fach.items(), key=lambda x: -x[1])),
        "je_bereich": dict(sorted(je_bereich.items(), key=lambda x: -x[1])),
        "je_einrichtung": dict(sorted(
            je_einrichtung.items(), key=lambda x: -len(x[1]["studien"]))),
    }


# ------------------------------------------------------------------ Gegentest

def gegentest():
    """Prueft, was ohne Netz pruefbar ist: Normalisierung und Zuordnung."""
    ok = True

    print("DOI-Normalisierung:")
    faelle = [
        ("10.1055/a-2357-8306", "10.1055/a-2357-8306"),
        ("https://doi.org/10.1055/A-2357-8306", "10.1055/a-2357-8306"),
        ("http://dx.doi.org/10.1055/a-2357-8306", "10.1055/a-2357-8306"),
        ("doi: 10.1055/a-2357-8306", "10.1055/a-2357-8306"),
        ("10.1055/a-2357-8306.", "10.1055/a-2357-8306"),
        ("  10.1055/a-2357-8306 ", "10.1055/a-2357-8306"),
        ("DOI:10.1055/a-2357-8306)", "10.1055/a-2357-8306"),
        # Was KEIN DOI ist, muss None werden - sonst wandert Muell in die
        # Stapelabfrage und faelscht die Fundquote nach unten.
        ("", None),
        (None, None),
        ("siehe Publikationsliste", None),
        ("www.example.org/bericht.pdf", None),
        ("10.1055", None),                       # ohne Schraegstrich
        ("PMID 12345678", None),
        ("ISRCTN12345678", None),
    ]
    for roh, soll in faelle:
        ist = doi_norm(roh)
        gut = ist == soll
        ok = ok and gut
        print(f"  {'ok ' if gut else 'FEHLER'} {str(roh)[:38]:<40} -> {ist}")

    print("\nZuordnung Studie -> Arbeit:")
    studien = [
        {"id": "S1", "dois": ["10.1/a", "https://doi.org/10.1/B", "kein doi"]},
        {"id": "S2", "dois": ["10.1/c"]},
        {"id": "S3", "dois": []},
    ]
    arbeiten = {
        "10.1/a": {"titel": "A", "fach": {"teilgebiet": "Epidemiology",
                                          "bereich": "Health Sciences"},
                   "einrichtungen": [{"ror": "r1", "name": "Eins", "land": "DE"}]},
        "10.1/b": {"titel": "B", "fach": {"teilgebiet": "Epidemiology",
                                          "bereich": "Health Sciences"},
                   "einrichtungen": [{"ror": "r1", "name": "Eins", "land": "DE"},
                                     {"ror": "r2", "name": "Zwei", "land": "AT"}]},
    }
    js = bauen(studien, arbeiten)
    pruefungen = [
        ("S3 hat keinen DOI und darf nicht auftauchen", "S3" not in js),
        ("S1 findet beide Arbeiten", len(js["S1"]["arbeiten"]) == 2),
        ("S1 merkt sich den unlesbaren Eintrag",
         js["S1"]["dois_unlesbar"] == ["kein doi"]),
        ("S2 nennt den DOI ohne Arbeit",
         js["S2"]["dois_ohne_arbeit"] == ["10.1/c"]),
        ("S2 hat keine Arbeit", js["S2"]["arbeiten"] == []),
    ]
    v = verdichten(js)
    pruefungen += [
        ("Fach nur aus gefundenen Arbeiten", v["studien_mit_fach"] == 1),
        ("S1 traegt Epidemiology", js["S1"]["fach"] == ["Epidemiology"]),
        ("S2 bleibt ohne Fach", js["S2"]["fach"] == []),
        # Eine Einrichtung, die in ZWEI Arbeiten derselben Studie steht,
        # darf die Studie nur EINMAL zaehlen - sonst sieht ein Haus mit
        # vielen Veroeffentlichungen nach vielen Studien aus.
        ("Einrichtung zaehlt die Studie einmal",
         v["je_einrichtung"]["r1"]["studien"] == ["S1"]),
        ("Einrichtung zaehlt beide Arbeiten",
         v["je_einrichtung"]["r1"]["arbeiten"] == 2),
        ("Auslaendischer Mitautor bleibt erhalten",
         v["je_einrichtung"]["r2"]["land"] == "AT"),
    ]

    # Personen: Reihenfolge der Autorenschaft muss erhalten bleiben, und
    # dieselbe Person darf in EINER Arbeit nur einmal stehen (OpenAlex
    # fuehrt sie mehrfach, wenn sie mehrere Einrichtungen angibt).
    w = {"authorships": [
        {"author": {"id": "A1", "display_name": "Erste",
                    "orcid": "https://orcid.org/0000-0001-0000-0001"},
         "author_position": "first"},
        {"author": {"id": "A1", "display_name": "Erste"},
         "author_position": "first"},
        {"author": {"id": "A2", "display_name": "Letzte"},
         "author_position": "last",
         "institutions": [{"ror": "https://ror.org/abc", "display_name": "X"},
                          {"display_name": "ohne ROR"}]},
        {"author": {}, "author_position": "middle"},
    ]}
    pp = personen(w)
    pruefungen += [
        ("Person mit zwei Einrichtungen zaehlt einmal", len(pp) == 2),
        ("Reihenfolge der Autorenschaft bleibt",
         [x["stelle"] for x in pp] == ["first", "last"]),
        ("ORCID uebernommen",
         pp[0]["orcid"] == "https://orcid.org/0000-0001-0000-0001"),
        ("Autor ohne Kennung faellt weg",
         all(x["oa_id"] for x in pp)),
        ("Einrichtung der Person mitgefuehrt",
         pp[1]["rors"] == ["https://ror.org/abc"]),
        ("Einrichtung ohne ROR faellt weg", len(pp[1]["rors"]) == 1),
        ("Person ohne Einrichtung bleibt, mit leerer Liste",
         pp[0]["rors"] == []),
    ]
    for text, gut in pruefungen:
        ok = ok and gut
        print(f"  {'ok ' if gut else 'FEHLER'} {text}")

    print("\n" + ("Gegentest bestanden." if ok else "GEGENTEST GESCHEITERT."))
    return ok


# ----------------------------------------------------------------------- Lauf

def main():
    if "--gegentest" in sys.argv:
        return 0 if gegentest() else 1

    lk = json.loads((DATEN / "landkarte.json").read_text(encoding="utf-8"))
    studien = lk["studien"]

    rohe = []
    for s in studien:
        rohe.extend(s.get("dois") or [])
    norm = [doi_norm(d) for d in rohe]
    unlesbar = [r for r, n in zip(rohe, norm) if not n]
    dois = sorted(set(n for n in norm if n))

    print(f"Studien           : {len(studien)}")
    print(f"mit Ergebnis-DOI  : {sum(1 for s in studien if s.get('dois'))}")
    print(f"DOI-Angaben       : {len(rohe)}")
    if unlesbar:
        print(f"  davon unlesbar  : {len(unlesbar)}  {unlesbar[:4]}")
    print(f"eindeutige DOIs   : {len(dois)}")

    ziel = DATEN / "doi_bezug.json"
    if "--ohne-netz" in sys.argv:
        if not ziel.exists():
            print("FEHLER: daten/doi_bezug.json fehlt - erst ohne --ohne-netz laufen")
            return 1
        alt = json.loads(ziel.read_text(encoding="utf-8"))
        arbeiten = {k: v for k, v in alt["arbeiten"].items()}
        print(f"\naus dem Bestand   : {len(arbeiten)} Arbeiten")
    else:
        print(f"\nOpenAlex, {len(dois)} DOIs in Stapeln von {STAPEL}:")
        roh = arbeiten_holen(dois)
        arbeiten = {k: satz(w) for k, w in roh.items()}

    je_studie = bauen(studien, arbeiten)
    v = verdichten(je_studie)

    fehlt = sorted(set(dois) - set(arbeiten))
    print(f"\nArbeiten gefunden : {len(arbeiten)} von {len(dois)} "
          f"({100.0 * len(arbeiten) / max(1, len(dois)):.1f} %)")
    print(f"nicht in OpenAlex : {len(fehlt)}")
    print(f"Studien mit Fach  : {v['studien_mit_fach']} von {len(studien)} "
          f"({100.0 * v['studien_mit_fach'] / max(1, len(studien)):.1f} %)")
    print(f"Einrichtungen     : {len(v['je_einrichtung'])} (Mitautoren!)")

    print("\nhaeufigste Teilgebiete:")
    for f, n in list(v["je_fach"].items())[:10]:
        print(f"  {n:>3}  {f}")
    print("\nBereiche:")
    for f, n in v["je_bereich"].items():
        print(f"  {n:>3}  {f}")

    raus = {
        "stand": lk.get("stand"),
        "hinweis": (
            "Fachgebiete und Einrichtungen stammen aus OpenAlex (CC0), "
            "aufgeloest ueber die im DRKS genannten Ergebnis-DOIs. Die "
            "Systematik ist unveraendert englisch, weil die Quelle englisch "
            "ist. Die Einrichtungen einer Publikation sind die Einrichtungen "
            "ihrer Autor:innen - bei einer Multizenterstudie also "
            "Mitwirkende, NICHT der Forschungsstandort."),
        "quelle": "https://openalex.org",
        "dois_genannt": len(rohe),
        "dois_eindeutig": len(dois),
        "dois_unlesbar": unlesbar,
        "dois_ohne_arbeit": fehlt,
        "zaehlung": {k: v[k] for k in
                     ("studien_mit_doi", "studien_mit_fach", "je_fach",
                      "je_bereich")},
        "je_einrichtung": v["je_einrichtung"],
        "studien": je_studie,
        "arbeiten": arbeiten,
    }
    ziel.write_text(json.dumps(raus, ensure_ascii=False, indent=1),
                    encoding="utf-8")
    print(f"\n-> {ziel.relative_to(HIER)}  "
          f"({ziel.stat().st_size / 1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
