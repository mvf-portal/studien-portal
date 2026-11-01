# -*- coding: utf-8 -*-
"""Schluesselt die PMIDs aller 15 Hub-Archive in DOIs um.

Warum: Das DRKS fuehrt Ergebnispublikationen als Freitext mit DOI-Link, die
Hub-Archive fuehren PMIDs. Ohne Bruecke zwischen beiden gibt es die
wertvollste Verknuepfung der Landkarte nicht - "diese Studie hat zu dieser
Arbeit gefuehrt, und die steht in unserem Hub X".

Gebruecht wird ueber den ID Converter der NLM (PMID -> DOI), 200 IDs je
Anfrage. Ergebnis liegt in daten/hub-dois.json und wird wiederverwendet;
nur neue PMIDs werden nachgeholt.

Aufruf:  py hubbezug.py
"""
from __future__ import annotations

import json
import pathlib
import re
import sys
import time
import urllib.parse
import urllib.request

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HIER = pathlib.Path(__file__).resolve().parent
DATEN = HIER / "daten"
HUBS = HIER.parent                      # ...\Claude-Daten
ZIEL = DATEN / "hub-dois.json"

IDCONV = "https://www.ncbi.nlm.nih.gov/pmc/utils/idconv/v1.0/"
KENNUNG = {"tool": "mvf-vf-landkarte", "email": "stegmaier@m-vf.de"}

# Archivordner -> Hub-Kuerzel und Anzeigename. Die Reihenfolge ist die der
# Uebersichtsseite; wer einen Hub ergaenzt, ergaenzt ihn hier.
PORTALE = {
    "adipositas-portal": ("adipositas", "Adipositas", "https://adipositas.m-vf.de"),
    "diabetes-portal": ("diabetes", "Diabetes", "https://diabetes.m-vf.de"),
    "gender-portal": ("gender", "Geschlechtersensible Medizin", "https://gender.m-vf.de"),
    "healthliteracy-portal": ("healthliteracy", "Gesundheitskompetenz", "https://healthliteracy.m-vf.de"),
    "impfen-portal": ("impfen", "Impfen & Prävention", "https://impfen.m-vf.de"),
    "kardio-portal": ("kardio", "Kardiologie", "https://kardio.m-vf.de"),
    "ki-gesundheit-portal": ("ki", "Digitalisierung, KI & Gesundheit", "https://ki.m-vf.de"),
    "klima-gesundheit-portal": ("klima", "Klima & Gesundheit", "https://klima.m-vf.de"),
    "longevity-portal": ("longevity", "Gesundes Altern & Longevity", "https://longevity.m-vf.de"),
    "mental-portal": ("mental", "Psychische Gesundheit", "https://mental.m-vf.de"),
    "ncd-portal": ("ncd", "NCD / Chronische Krankheiten", "https://ncd.m-vf.de"),
    "onkologie-portal": ("onkologie", "Onkologie", "https://onkologie.m-vf.de"),
    "pflege-portal": ("pflege", "Pflege & Langzeitversorgung", "https://pflege.m-vf.de"),
    "safety-portal": ("safety", "Patientensicherheit", "https://safety.m-vf.de"),
    "versorgungsforschung-portal": ("wissen", "Versorgungsforschung", "https://wissen.m-vf.de"),
}


def archive() -> dict[str, dict]:
    """Liest alle Hub-Archive: PMID -> Eintrag samt Hub-Zuordnung."""
    treffer: dict[str, dict] = {}
    for ordner, (kuerzel, name, url) in PORTALE.items():
        p = HUBS / ordner / "studien-archiv.json"
        if not p.exists():
            print(f"  FEHLT: {p}")
            continue
        eintraege = json.loads(p.read_text(encoding="utf-8"))
        n = 0
        for e in eintraege:
            pmid = str(e.get("pmid") or "").strip()
            if not pmid:
                continue
            n += 1
            treffer.setdefault(pmid, {"pmid": pmid, "hubs": [], "titel": e.get("title"),
                                      "journal": e.get("journal"), "jahr": e.get("year")})
            treffer[pmid]["hubs"].append({"kuerzel": kuerzel, "name": name, "url": url})
        print(f"  {name:<34}{n:>5} PMIDs")
    return treffer


def doi_holen(pmids: list[str]) -> dict[str, str]:
    """PMID -> DOI ueber den ID Converter, 200 je Anfrage."""
    karte: dict[str, str] = {}
    for i in range(0, len(pmids), 200):
        teil = pmids[i:i + 200]
        p = dict(KENNUNG, ids=",".join(teil), format="json", idtype="pmid")
        url = IDCONV + "?" + urllib.parse.urlencode(p)
        for versuch in range(4):
            try:
                with urllib.request.urlopen(url, timeout=60) as r:
                    d = json.loads(r.read().decode("utf-8", "replace"))
                break
            except Exception as e:
                if versuch == 3:
                    print(f"    Block {i//200+1} aufgegeben: {e}")
                    d = {}
                else:
                    time.sleep(3 * (versuch + 1))
        for rec in (d.get("records") or []):
            if rec.get("doi"):
                karte[str(rec.get("pmid"))] = rec["doi"].lower().strip()
        print(f"    Block {i//200+1}/{(len(pmids)-1)//200+1}: {len(karte)} DOIs gesamt")
        sys.stdout.flush()
        time.sleep(0.4)
    return karte


def doi_nachholen(pmids: list[str]) -> dict[str, str]:
    """Zweiter Weg fuer die PMIDs, die der ID Converter nicht kennt.

    Der Converter der NLM bedient PMC und liefert deshalb nur fuer rund 60
    Prozent der PMIDs eine DOI. Die DOI steht aber bei fast jedem
    PubMed-Datensatz im Feld `elocationid` - esummary gibt sie heraus.
    """
    karte: dict[str, str] = {}
    EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
    for i in range(0, len(pmids), 200):
        teil = pmids[i:i + 200]
        p = dict(KENNUNG, db="pubmed", id=",".join(teil), retmode="json")
        url = EUTILS + "?" + urllib.parse.urlencode(p)
        d = {}
        for versuch in range(4):
            try:
                with urllib.request.urlopen(url, timeout=60) as r:
                    d = json.loads(r.read().decode("utf-8", "replace"))
                break
            except Exception as e:
                if versuch == 3:
                    print(f"    esummary-Block {i//200+1} aufgegeben: {e}")
                else:
                    time.sleep(3 * (versuch + 1))
        res = (d.get("result") or {})
        for pmid in teil:
            rec = res.get(pmid) or {}
            # elocationid sieht aus wie "doi: 10.1007/s00103-019-02946-6"
            quellen = [rec.get("elocationid") or ""]
            quellen += [a.get("value", "") for a in (rec.get("articleids") or [])
                        if a.get("idtype") == "doi"]
            for q in quellen:
                m = re.search(r"10\.\d{4,9}/\S+", q)
                if m:
                    karte[pmid] = m.group(0).rstrip(".").lower()
                    break
        print(f"    esummary-Block {i//200+1}/{(len(pmids)-1)//200+1}: "
              f"{len(karte)} zusaetzliche DOIs")
        sys.stdout.flush()
        time.sleep(0.4)
    return karte


def main() -> int:
    DATEN.mkdir(exist_ok=True)
    print("Hub-Archive lesen:")
    treffer = archive()
    print(f"  zusammen {len(treffer)} verschiedene PMIDs")

    alt = {}
    if ZIEL.exists():
        alt = json.loads(ZIEL.read_text(encoding="utf-8")).get("pmid_doi", {})
        print(f"  {len(alt)} DOIs aus frueherem Lauf uebernommen")

    offen = [p for p in treffer if p not in alt]
    print(f"  {len(offen)} PMIDs noch umzuschluesseln")
    neu = doi_holen(offen) if offen else {}
    pmid_doi = {**alt, **neu}

    rest = [p for p in treffer if p not in pmid_doi]
    if rest:
        print(f"  {len(rest)} PMIDs ohne DOI - zweiter Weg ueber esummary")
        pmid_doi.update(doi_nachholen(rest))

    # DOI -> Liste der Hub-Treffer, das ist die Richtung, die bauen.py braucht
    doi_hub: dict[str, dict] = {}
    for pmid, doi in pmid_doi.items():
        if pmid in treffer:
            doi_hub.setdefault(doi, {"pmid": pmid, **{k: v for k, v in treffer[pmid].items()
                                                      if k != "pmid"}})
    ZIEL.write_text(json.dumps({"pmid_doi": pmid_doi, "doi_hub": doi_hub},
                               ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n{len(pmid_doi)} von {len(treffer)} PMIDs haben eine DOI "
          f"({len(pmid_doi)/len(treffer)*100:.1f} %)")
    print(f"geschrieben: {ZIEL}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
