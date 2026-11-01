"""Koordinaten der Orte, in denen Forschungsstandorte sitzen.

WARUM
-----
52 der 63 Standorte tragen die Koordinate ihrer Einrichtung, geprueft
gegen Name und Ort. Bei 11 haelt die Zuordnung dem Waechter nicht stand,
und das ist meistens RICHTIG: Die ROR-Kennung gehoert zur
Mutterorganisation in einer anderen Stadt.

    Institut fuer Allgemeinmedizin, UK Luebeck -> Kiel
    Rheinhessen-Fachklinik Mainz               -> Mainz, sitzt aber in Alzey
    Vestische Kinder- und Jugendklinik Datteln -> Witten

Ein Punkt an der Stelle der Mutter waere falsch. Der ORT aber steht im
Register und ist richtig. Darum fuer diese elf die Koordinate der STADT,
auf der Karte als solche kenntlich.

DREI QUELLEN, in dieser Reihenfolge
-----------------------------------
  1. die schon gepruefeten Standorte selbst   35 Staedte
  2. der Innofonds-Cache (nur gelesen)       137 Staedte
  3. ROR, nach Ortsnamen gefragt             fuer den Rest

Die dritte Quelle fragt nur, was die ersten beiden nicht hergeben. Am
01.11.2026 waren das zwei Staedte: Alzey und Kempten.

  py ortskoordinaten.py              baut daten/ortskoordinaten.json
  py ortskoordinaten.py --gegentest  prueft ohne Netz
"""
import json
import pathlib
import re
import sys
import time
import unicodedata
import urllib.parse
import urllib.request

HIER = pathlib.Path(__file__).parent
DATEN = HIER / "daten"
INNO = (HIER.parent / "innovationsfonds" / "db" / "ror_cache.json")
UA = {"User-Agent": "vf-landkarte/1.0 (mailto:stegmaier@m-vf.de)"}


def norm(s):
    s = (s or "").lower()
    for a, b in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"),
                 ("ß", "ss")):
        s = s.replace(a, b)
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    # „Kempten (Allgaeu)" und „Kempten" sind dieselbe Stadt.
    return s.split("(")[0].strip().strip(",").strip()


def aus_standorten():
    p = DATEN / "standorte.json"
    if not p.exists():
        return {}
    raus = {}
    for s in json.loads(p.read_text(encoding="utf-8"))["standorte"]:
        if s.get("lat") and s.get("ort"):
            raus.setdefault(norm(s["ort"]),
                            {"lat": s["lat"], "lon": s["lon"],
                             "ort": s["ort"].strip(), "quelle": "eigener Bestand"})
    return raus


def aus_innofonds():
    if not INNO.exists():
        return {}
    raus = {}
    for v in json.loads(INNO.read_text(encoding="utf-8")).values():
        if v and v.get("lat") and v.get("ort"):
            raus.setdefault(norm(v["ort"]),
                            {"lat": v["lat"], "lon": v["lon"],
                             "ort": v["ort"].strip(),
                             "quelle": "Innofonds-Cache"})
    return raus


def aus_ror(stadt):
    """ROR nach einer Einrichtung in dieser Stadt fragen, Koordinate nehmen."""
    u = ("https://api.ror.org/v2/organizations"
         "?filter=country.country_name:Germany&query="
         + urllib.parse.quote(stadt))
    try:
        with urllib.request.urlopen(
                urllib.request.Request(u, headers=UA), timeout=90) as f:
            d = json.loads(f.read())
    except Exception:
        return None
    ziel = norm(stadt)
    for o in d.get("items", []):
        for loc in (o.get("locations") or []):
            g = loc.get("geonames_details") or {}
            if g.get("lat") is None:
                continue
            # Der Ortsname muss stimmen. Ein Treffer, der nur im NAMEN der
            # Einrichtung den Ort traegt, aber anderswo sitzt, waere falsch.
            if norm(g.get("name")) == ziel:
                return {"lat": g["lat"], "lon": g["lng"],
                        "ort": stadt, "quelle": "ROR"}
    return None


def aus_wikidata(stadt):
    """Die Stadt selbst bei Wikidata, nicht eine Einrichtung darin.

    ⚠ Der Grund fuer diese vierte Quelle: ROR fuehrt „DRK Krankenhaus
    Alzey" und verortet es in HACHENBURG, 130 Kilometer entfernt. Eine
    Einrichtung, die den Ort im Namen traegt, sitzt nicht unbedingt dort.
    Wikidata dagegen kennt den Ort als Ort.

    Gefragt wird ausdruecklich nach einer SIEDLUNG in DEUTSCHLAND
    (P31/P279* Q486972, P17 Q183). Ohne diese beiden Bedingungen trifft
    die Abfrage auch Vereine, Bahnhoefe und Verwaltungsgebilde gleichen
    Namens.
    """
    q = ('SELECT ?koord WHERE { ?ort rdfs:label "%s"@de . '
         '?ort wdt:P17 wd:Q183 . ?ort wdt:P31/wdt:P279* wd:Q486972 . '
         '?ort wdt:P625 ?koord . } LIMIT 5' % stadt.replace('"', ""))
    u = ("https://query.wikidata.org/sparql?format=json&query="
         + urllib.parse.quote(q))
    try:
        with urllib.request.urlopen(
                urllib.request.Request(u, headers=UA), timeout=90) as f:
            d = json.loads(f.read())
    except Exception:
        return None
    for b in d.get("results", {}).get("bindings", []):
        m = re.match(r"Point\(([-\d.]+) ([-\d.]+)\)",
                     b.get("koord", {}).get("value", ""))
        if m:
            return {"lat": float(m.group(2)), "lon": float(m.group(1)),
                    "ort": stadt, "quelle": "Wikidata"}
    return None


def gegentest():
    ok = True
    print("Ortsnamen auf eine Form bringen:")
    for roh, soll in (("Kempten (Allgäu)", "kempten"),
                      ("Kempten", "kempten"),
                      ("München", "muenchen"),
                      ("Frankfurt am Main", "frankfurt am main"),
                      ("  Köln ", "koeln"),
                      ("", "")):
        ist = norm(roh)
        gut = ist == soll
        ok = ok and gut
        print(f"  {'ok ' if gut else 'FEHLER'} {roh!r:<22} -> {ist!r}")
    print("\nReihenfolge der Quellen:")
    a = {"koeln": {"lat": 1, "lon": 1, "ort": "Köln", "quelle": "eigener Bestand"}}
    b = {"koeln": {"lat": 9, "lon": 9, "ort": "Koeln", "quelle": "Innofonds-Cache"},
         "kassel": {"lat": 5, "lon": 5, "ort": "Kassel", "quelle": "Innofonds-Cache"}}
    zus = dict(b)
    zus.update(a)        # der eigene Bestand sticht
    gut = zus["koeln"]["quelle"] == "eigener Bestand" and "kassel" in zus
    ok = ok and gut
    print(f"  {'ok ' if gut else 'FEHLER'} eigener Bestand sticht den Cache, "
          f"Cache ergaenzt")
    print("\n" + ("Gegentest bestanden." if ok else "GEGENTEST GESCHEITERT."))
    return ok


def main():
    if "--gegentest" in sys.argv:
        return 0 if gegentest() else 1

    tabelle = aus_innofonds()
    print(f"aus dem Innofonds-Cache : {len(tabelle)} Staedte")
    eigen = aus_standorten()
    tabelle.update(eigen)          # der eigene, geprueftere Bestand sticht
    print(f"aus eigenen Standorten  : {len(eigen)} Staedte")

    st = json.loads((DATEN / "standorte.json").read_text(encoding="utf-8"))
    gebraucht = {norm(s["ort"]): s["ort"].strip()
                 for s in st["standorte"] if s.get("ort")}
    fehlt = [o for k, o in gebraucht.items() if k not in tabelle]
    print(f"\nnoch offen              : {len(fehlt)}  {fehlt}")
    for o in fehlt:
        e = aus_ror(o)
        time.sleep(0.5)
        if not e:
            e = aus_wikidata(o)
            time.sleep(0.5)
        if e:
            tabelle[norm(o)] = e
            print(f"   {o:<16} {e['lat']:.5f} / {e['lon']:.5f}  ({e['quelle']})")
        else:
            print(f"   {o:<16} nicht gefunden")

    gedeckt = sum(1 for k in gebraucht if k in tabelle)
    print(f"\nOrte der Standorte gedeckt: {gedeckt} von {len(gebraucht)}")
    ziel = DATEN / "ortskoordinaten.json"
    ziel.write_text(json.dumps({
        "stand": time.strftime("%Y-%m-%d"),
        "hinweis": ("Koordinate der STADT, nicht der Einrichtung. Nur "
                    "benutzt, wo die Einrichtung sich nicht zweifelsfrei "
                    "zuordnen laesst. Auf der Karte als solche kenntlich."),
        "orte": tabelle,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"-> daten/ortskoordinaten.json ({len(tabelle)} Orte)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
