# -*- coding: utf-8 -*-
"""Wer die Versorgungsforschung bezahlt - die Foerderer hinter den vier Balken.

Die Landkarte zeigt bisher nur die vier Kategorien aus `materialSupports.type`
(oeffentlich / eigene Mittel / privat / kommerziell). Das Feld traegt aber je
Eintrag einen vollstaendigen Kontaktsatz: Name, Strasse oder Postfach, PLZ,
Ort, Land, dazu haeufig Telefon und Webseite.

**Keine Personendaten.** In allen Eintraegen der VF-Auswahl sind `firstName`
und `lastName` leer - das sind Institutionsanschriften, keine
Ansprechpartner. Dieses Skript uebernimmt deshalb den ganzen Kontaktsatz,
prueft das aber nach und laesst Namensfelder grundsaetzlich weg.

**Das Zusammenfuehren ist die eigentliche Arbeit.** Das Register normiert die
Namen nicht: Der Innovationsausschuss erscheint unter mindestens fuenf
Schreibweisen, das BMBF unter vier. Eine Rangliste ohne Zusammenfuehrung ist
wertlos.

Aufruf:  py foerderer.py            # Rangliste + daten/foerderer.json
         py foerderer.py --gegentest
"""
from __future__ import annotations

import argparse
import collections
import json
import pathlib
import re
import sys
import zipfile

HIER = pathlib.Path(__file__).resolve().parent
DATEN = HIER / "daten"
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

FOERDER_DE = {
    "PUBLIC_FUNDING": "öffentlich gefördert",
    "COMMERCIAL": "kommerziell",
    "INSTITUTIONAL": "aus eigenen Mitteln",
    "PRIVATE_SPONSORSHIP": "privat gefördert",
}

# Die grossen Geldgeber, die unter vielen Schreibweisen auftauchen. Reihenfolge
# zaehlt: Die erste passende Regel gewinnt, deshalb stehen die engeren oben.
#
# Jede Regel ist bewusst an einem MERKMAL festgemacht, das nur dieser
# Geldgeber hat - nie an einem Gattungswort. „Bundesministerium" allein
# wuerde BMG, BMBF und BMFTR zusammenwerfen; das faengt der Gegentest.
ALIAS: list[tuple[str, str]] = [
    (r"innovationsausschuss|innovationsfonds",
     "Innovationsausschuss beim Gemeinsamen Bundesausschuss (G-BA)"),
    (r"gemeinsamer bundesausschuss|g\W?ba\b", "Gemeinsamer Bundesausschuss (G-BA)"),
    (r"bildung und forschung|\bbmbf\b", "Bundesministerium für Bildung und Forschung (BMBF)"),
    (r"forschung, technologie und raumfahrt|\bbmftr\b",
     "Bundesministerium für Forschung, Technologie und Raumfahrt (BMFTR)"),
    (r"bundesministerium f(ue|ü)r gesundheit|\bbmg\b",
     "Bundesministerium für Gesundheit (BMG)"),
    (r"deutsche forschungsgemeinschaft|\bdfg\b", "Deutsche Forschungsgemeinschaft (DFG)"),
    (r"deutsche rentenversicherung bund|\bdrv bund\b",
     "Deutsche Rentenversicherung Bund"),
    (r"krebshilfe", "Stiftung Deutsche Krebshilfe"),
    (r"kinderkrebsstiftung", "Deutsche Kinderkrebsstiftung"),
    (r"gkv\W?spitzenverband", "GKV-Spitzenverband"),
    (r"robert\W?bosch", "Robert Bosch Stiftung"),
    (r"else kr(oe|ö)ner", "Else Kröner-Fresenius-Stiftung"),
    (r"volkswagen\W?stiftung|volkswagenstiftung", "VolkswagenStiftung"),
    (r"europ(ae|ä)ische union|europ(ae|ä)ische kommission|horizon|\beu\b",
     "Europäische Union"),
]

# Rechtsformen und Zusaetze, die keinen Foerderer unterscheiden.
RECHTSFORM = re.compile(
    r"\b(gmbh|ggmbh|mbh|ag|kgaa|kg|ohg|se|e\s?v|ev|gbr|inc|ltd|llc|plc|"
    r"co|deutschland|germany|dienstsitz (berlin|bonn))\b", re.I)


def norm(s: str) -> str:
    s = (s or "").lower()
    s = (s.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue")
           .replace("ß", "ss").replace("–", "-").replace("—", "-"))
    s = RECHTSFORM.sub(" ", s)
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def schluessel(name: str) -> str:
    """Der Gruppenschluessel eines Foerderers.

    Ohne Alias ist es der NORMALISIERTE Name, nicht der rohe: Sonst bleiben
    „Novartis Pharma GmbH" und „Novartis Pharma" zwei Geldgeber, obwohl die
    Rechtsform laengst als Rauschen abgezogen ist. Genau das hat der
    Gegentest gefangen.
    """
    n = norm(name)
    for muster, ziel in ALIAS:
        if re.search(muster, n):
            return ziel
    return n


def kanonisch(name: str) -> str:
    """Nur fuer den Gegentest: gleicher Schluessel heisst gleicher Foerderer."""
    return schluessel(name)


def _vollstaendigkeit(k: dict) -> int:
    """Wie vollstaendig ist dieser Kontaktsatz? Der beste gewinnt je Gruppe."""
    return sum(1 for f in ("streetAndNo", "zip", "city", "url", "phone") if k.get(f))


def sammeln(vf: list[dict]) -> dict:
    gruppen: dict[str, dict] = {}
    personenfelder = 0
    eintraege = 0
    for x in vf:
        gesehen = set()
        for m in (x.get("materialSupports") or []):
            k = m.get("contact") or {}
            name = (k.get("affiliation") or "").strip()
            if not name:
                continue
            eintraege += 1
            if k.get("firstName") or k.get("lastName"):
                personenfelder += 1
            ziel = schluessel(name)
            g = gruppen.setdefault(ziel, {
                "schluessel": ziel, "schreibweisen": collections.Counter(),
                "studien": set(), "arten": collections.Counter(),
                "anschrift": None, "guete": -1,
            })
            g["schreibweisen"][name] += 1
            g["studien"].add(x.get("drksId"))
            art = FOERDER_DE.get(m.get("type"), m.get("type"))
            if art and (ziel, art) not in gesehen:
                g["arten"][art] += 1
                gesehen.add((ziel, art))
            v = _vollstaendigkeit(k)
            if v > g["guete"]:
                g["guete"] = v
                # NUR Institutionsfelder - niemals firstName/lastName/email.
                g["anschrift"] = {
                    "strasse": k.get("streetAndNo"), "plz": k.get("zip"),
                    "ort": k.get("city"), "land": k.get("country"),
                    "telefon": k.get("phone"), "web": k.get("url"),
                }
    # Anzeigename: der Alias, wo es einen gibt - sonst die haeufigste
    # Schreibweise der Gruppe.
    ziele = {z for _, z in ALIAS}
    for k, v in gruppen.items():
        v["name"] = k if k in ziele else v["schreibweisen"].most_common(1)[0][0]
    return {"gruppen": gruppen, "eintraege": eintraege,
            "personenfelder": personenfelder}


def gegentest() -> int:
    """Was zusammengehoert, muss zusammenfallen - und sonst nichts.

    Die Lehre aus dem Einrichtungsabgleich gilt hier genauso: Eine
    Zusammenfuehrung ist erst dann eine Messung, wenn geprueft ist, dass sie
    Verschiedenes NICHT zusammenwirft. „Bundesministerium" ist ein
    Gattungswort - danach duerfte nie gruppiert werden.
    """
    gleich = [
        ["Innovationsausschuss beim Gemeinsamen Bundesausschuss",
         "Innovationsausschuss beim G-BA", "Innovationsausschuss des G-BA",
         "Innovationsfonds beim Gemeinsamen Bundesausschuss",
         "Innovationsausschuss beim Gemeinsamen Bundesausschuss (G-BA)"],
        ["Bundesministerium für Bildung und Forschung",
         "Bundesministerium für Bildung und Forschung Dienstsitz Berlin",
         "Bundesministerium für Bildung und Forschung Dienstsitz Bonn", "BMBF"],
        ["Bundesministerium für Gesundheit", "Bundesministerium für Gesundheit (BMG)"],
        ["Novartis Pharma GmbH", "Novartis Pharma"],
    ]
    verschieden = [
        "Bundesministerium für Gesundheit",
        "Bundesministerium für Bildung und Forschung",
        "Bundesministerium für Forschung, Technologie und Raumfahrt",
        "Bayerisches Staatsministerium für Gesundheit, Pflege und Prävention",
        "Universitätsklinikum Heidelberg",
        "Universitätsklinikum Hamburg-Eppendorf",
        "Deutsche Rentenversicherung Bund",
        "Deutsche Forschungsgemeinschaft",
        "Deutsche Kinderkrebsstiftung",
        "Stiftung Deutsche Krebshilfe",
    ]
    ok = True
    print("Gegentest Foerderer-Zusammenfuehrung:\n")
    print("  Was zusammengehoert, muss zusammenfallen:")
    for gruppe in gleich:
        ziele = {kanonisch(n) for n in gruppe}
        gut = len(ziele) == 1
        ok = ok and gut
        print(f"    {'ok  ' if gut else 'FEHL'}  {gruppe[0][:46]:<48} "
              f"-> {len(ziele)} Gruppe(n)")
        if not gut:
            for z in sorted(ziele):
                print(f"            {z}")

    print("\n  Was verschieden ist, darf NICHT zusammenfallen:")
    nach = collections.defaultdict(list)
    for n in verschieden:
        nach[kanonisch(n)].append(n)
    for ziel, namen in nach.items():
        if len(namen) > 1:
            ok = False
            print(f"    FEHL  {len(namen)} Foerderer auf EINER Gruppe: "
                  f"{', '.join(n[:34] for n in namen)}")
    if all(len(v) == 1 for v in nach.values()):
        print(f"    ok    {len(verschieden)} Foerderer, keiner faelschlich "
              "zusammengelegt")

    # Erfundenes darf in KEINE der gepflegten Alias-Gruppen fallen. Dass es
    # einen eigenen Schluessel bekommt, ist richtig - jeder unbekannte Name
    # bekommt einen.
    print("\n  Erfundenes darf keiner Alias-Gruppe zufallen:")
    alias_ziele = {z for _, z in ALIAS}
    for e in ["Stiftung Flunkerologie", "Wolkenkuckucksheimer Fonds",
              "Bundesamt für Hintertupfingen"]:
        traf = kanonisch(e) in alias_ziele
        ok = ok and not traf
        print(f"    {'FEHL' if traf else 'ok  '}  {e:<34} -> "
              f"{'Gruppe ' + kanonisch(e) if traf else 'eigene Gruppe'}")

    print("\n" + ("  Gegentest bestanden." if ok else "  GEGENTEST FEHLGESCHLAGEN."))
    return 0 if ok else 1


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--gegentest", action="store_true")
    p.add_argument("--zeige", type=int, default=30)
    a = p.parse_args()
    if a.gegentest:
        return gegentest()

    quelle = sorted(DATEN.glob("drks-export-*.zip"))[-1]
    stand = re.search(r"(\d{4}-\d{2}-\d{2})", quelle.name).group(1)
    z = zipfile.ZipFile(quelle)
    name = [n for n in z.namelist() if n.startswith("DRKS") and n.endswith(".json")][0]
    roh = json.loads(z.read(name).decode("utf-8"))

    lk = json.loads((DATEN / "landkarte.json").read_text(encoding="utf-8"))
    ids = {s["id"] for s in lk["studien"]}
    vf = [x for x in roh if x.get("drksId") in ids]

    erg = sammeln(vf)
    g = erg["gruppen"]
    roh_namen = sum(len(v["schreibweisen"]) for v in g.values())

    print(f"Quelle: {quelle.name}  (Abruf {stand})")
    print(f"{len(vf)} Studien mit Versorgungsbezug, {erg['eintraege']} Foerdereintraege")
    print(f"  {roh_namen} Schreibweisen -> {len(g)} Foerderer")
    print(f"  Eintraege mit Personennamen: {erg['personenfelder']} "
          f"(uebernommen werden nur Institutionsfelder)")

    reihe = sorted(g.values(), key=lambda v: (-len(v["studien"]), v["name"]))
    print(f"\nDie {a.zeige} groessten Geldgeber der deutschen "
          f"Versorgungsforschung:\n")
    print(f"  {'Studien':>7}  {'Art':<22}  Foerderer / Anschrift")
    for v in reihe[:a.zeige]:
        art = v["arten"].most_common(1)[0][0] if v["arten"] else ""
        an = v["anschrift"] or {}
        adr = " ".join(x for x in [an.get("strasse"), an.get("plz"),
                                   an.get("ort")] if x)
        print(f"  {len(v['studien']):>7}  {art:<22}  {v['name'][:52]}")
        if adr:
            print(f"  {'':>7}  {'':<22}  {adr[:64]}"
                  + (f" · {an['web'][:38]}" if an.get("web") else ""))
        if len(v["schreibweisen"]) > 1:
            print(f"  {'':>7}  {'':<22}  ({len(v['schreibweisen'])} Schreibweisen "
                  "zusammengeführt)")

    anteil = collections.Counter()
    for v in g.values():
        for art, n in v["arten"].items():
            anteil[art] += n
    print("\nGeldgeber je Kategorie (Kategorie stammt aus der Selbstauskunft):")
    for art, n in anteil.most_common():
        wie_viele = sum(1 for v in g.values() if art in v["arten"])
        print(f"  {n:>4} Nennungen von {wie_viele:>3} verschiedenen Geldgebern  {art}")

    ziel = DATEN / "foerderer.json"
    ziel.write_text(json.dumps({
        "stand": stand,
        "quelle": "Deutsches Register Klinischer Studien (DRKS), BfArM",
        "hinweis": "Nur Institutionsanschriften. Personenbezogene Felder des "
                   "Registers werden nicht übernommen.",
        "studien": len(vf), "eintraege": erg["eintraege"],
        "schreibweisen": roh_namen, "foerderer": len(g),
        "liste": [{"name": v["name"], "studien": len(v["studien"]),
                   "arten": v["arten"].most_common(),
                   "anschrift": v["anschrift"],
                   "schreibweisen": sorted(v["schreibweisen"])}
                  for v in reihe],
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\ngeschrieben: {ziel}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
