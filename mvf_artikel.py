# -*- coding: utf-8 -*-
"""Alle MVF-Artikeldatensaetze aus WordPress, mit PDF-Adresse.

WARUM DIESER UMWEG
------------------
Die Affiliationen der MVF-Autor:innen stehen nirgends in einer
Schnittstelle. Nicht bei Crossref, nicht bei OpenAlex (gemessen: 5 von 80
Beitraegen tragen dort eine Einrichtung), nicht im Autorenprofil auf
m-vf.de (1.340 Profile, alle ohne Inhaltstext), nicht im Artikeltext (der
endet mit dem Fazit).

Sie stehen in der Autorenbox am Ende des PDF, und dort stehen sie
vollstaendig. Geprueft an MVF 05/26, DOI ...2874:

    Prof. Dr. rer. med. habil. Karel Kostev MA  ORCID: 0000-0002-2124-7227
    ist Scientific Principal und Leiter des Epidemiologie-Teams bei IQVIA
    in Frankfurt. ... Kontakt: vorname.name@beispielfirma.example

Name, ORCID, Funktion, Einrichtung, Ort, Kontakt. Und die Einrichtung ist
IQVIA, also genau die Art Haus, die das Studienregister strukturell nicht
sieht: Sekundaerdatenforschung und Evaluation werden nicht registriert.
Gemessen am 01.11.2026: IGES 0 Studien im Register und 16 MVF-Beitraege,
Prognos 0 und 10, OptiMedis 0 und 4.

Dieses Skript holt nur die Datensaetze und die PDF-Adressen. Das Lesen der
PDFs macht `mvf_autorenbox.py`.

⚠ 1.528 DATENSAETZE, 936 DOIs BEI CROSSREF
Die Differenz sind eFirst-Dubletten und Beitraege ohne Deposit. Verbunden
wird darum ueber den DOI, nie ueber die Reihenfolge.

  py mvf_artikel.py              holt alles
  py mvf_artikel.py --gegentest  prueft ohne Netz
"""
import json
import pathlib
import re
import sys
import time
import urllib.request

HIER = pathlib.Path(__file__).parent
DATEN = HIER / "daten"
ZIEL = DATEN / "mvf_artikel.json"
BASIS = "https://www.monitor-versorgungsforschung.de/wp-json/wp/v2/"
UA = {"User-Agent": "Mozilla/5.0 (vf-landkarte; stegmaier@m-vf.de)"}
FELDER = "id,title,link,date,acf,slug"


def hol(u):
    """Antwort und Kopfzeilen. None, wenn es nach fuenf Versuchen nicht geht."""
    warte = 4
    for versuch in range(5):
        try:
            with urllib.request.urlopen(
                    urllib.request.Request(u, headers=UA), timeout=120) as f:
                kopf = {k.lower(): v for k, v in f.headers.items()}
                return json.loads(f.read()), kopf
        except Exception as e:
            if versuch == 4:
                print(f"     aufgegeben: {str(e)[:90]}")
                return None, {}
            time.sleep(warte)
            warte = min(warte * 2, 60)
    return None, {}


def doi_norm(s):
    """„http://doi.org/10.24945/MVF.05.26..." -> „10.24945/mvf.05.26..."

    Die DOAJ-Falle: MVF steht dort gross und mit Vorsatz. Wer nicht
    normalisiert, findet nichts.
    """
    s = (s or "").strip().lower()
    for v in ("https://doi.org/", "http://doi.org/", "https://dx.doi.org/",
              "http://dx.doi.org/", "doi:"):
        if s.startswith(v):
            s = s[len(v):]
    return s.strip().strip("/")


def heft_aus_doi(doi):
    """Heft und Jahr aus dem DOI, nicht aus volume/issue.

    ⚠ volume und issue sind bei MVF unbrauchbar: Im Jahrgang 2019 stehen
    dort 06, 12 und 2019 durcheinander. Der DOI dagegen traegt das Muster
    mvf.<heft>.<jahr>. verlaesslich.
    """
    m = re.search(r"mvf\.(\d\d)\.(\d\d)\.", doi or "")
    if not m:
        return "", ""
    return m.group(1), "20" + m.group(2)


def medien(nummern):
    """Zu Mediennummern die Adressen. In Bloecken, nicht einzeln."""
    raus = {}
    nummern = [str(n) for n in nummern if n]
    for i in range(0, len(nummern), 80):
        teil = nummern[i:i + 80]
        d, _ = hol(BASIS + "media?per_page=100&_fields=id,source_url,mime_type"
                   "&include=" + ",".join(teil))
        for m in (d or []):
            raus[str(m["id"])] = m.get("source_url") or ""
        time.sleep(0.3)
    return raus


def gegentest():
    ok = True
    print("DOI normalisieren:")
    for roh, soll in (
            ("http://doi.org/10.24945/MVF.05.26.1866-0533.2874",
             "10.24945/mvf.05.26.1866-0533.2874"),
            ("https://doi.org/10.24945/MVF.01.24.1866-0533.2600",
             "10.24945/mvf.01.24.1866-0533.2600"),
            ("10.24945/MVF.03.25.1866-0533.2719",
             "10.24945/mvf.03.25.1866-0533.2719"),
            ("", "")):
        ist = doi_norm(roh)
        gut = ist == soll
        ok = ok and gut
        print(f"  {'ok ' if gut else 'FEHLER'} {ist!r}")

    print("\nHeft und Jahr aus dem DOI, nicht aus volume/issue:")
    for doi, soll in (("10.24945/mvf.05.26.1866-0533.2874", ("05", "2026")),
                      ("10.24945/mvf.01.19.1866-0533.2100", ("01", "2019")),
                      ("10.24945/kein-muster", ("", ""))):
        ist = heft_aus_doi(doi)
        gut = ist == soll
        ok = ok and gut
        print(f"  {'ok ' if gut else 'FEHLER'} {doi[-24:]:<24} -> {ist}")

    print("\n" + ("Gegentest bestanden." if ok else "GEGENTEST GESCHEITERT."))
    return ok


def main():
    if "--gegentest" in sys.argv:
        return 0 if gegentest() else 1

    d, kopf = hol(BASIS + "abstract?per_page=1&_fields=id")
    gesamt = int(kopf.get("x-wp-total") or 0)
    print(f"Artikeldatensaetze auf m-vf.de: {gesamt}")

    artikel, seite = {}, 1
    while True:
        d, _ = hol(BASIS + f"abstract?per_page=100&page={seite}&_fields={FELDER}")
        if not d:
            break
        for e in d:
            a = e.get("acf") or {}
            doi = doi_norm(a.get("doi_link"))
            heft, jahr = heft_aus_doi(doi)
            artikel[str(e["id"])] = {
                "id": e["id"],
                "titel": (e.get("title") or {}).get("rendered", ""),
                "link": e.get("link"),
                "doi": doi,
                "doi_efirst": doi_norm(a.get("doi_link_efirst")),
                "rubrik": a.get("rubrik") or "",
                "ausgabe": a.get("ausgabe") or "",
                "heft": heft, "jahr": jahr,
                "lizenz": a.get("lizenz") or "",
                "zitation": a.get("citation_tips") or "",
                "abstract_de": a.get("abstract_text_de") or "",
                "abstract_en": a.get("abstract_text_en") or "",
                "pdf_nummer": a.get("pdf_link") or "",
                "pdf_nummer_en": a.get("pdf_link_en") or "",
                "pdf": "", "pdf_en": "",
            }
        print(f"  Seite {seite:3d} | gesammelt {len(artikel)}")
        if len(d) < 100:
            break
        seite += 1
        time.sleep(0.3)

    nummern = set()
    for a in artikel.values():
        nummern.add(a["pdf_nummer"])
        nummern.add(a["pdf_nummer_en"])
    print(f"\nPDF-Adressen zu {len(nummern)} Mediennummern holen...")
    tab = medien(nummern)
    for a in artikel.values():
        a["pdf"] = tab.get(str(a["pdf_nummer"]), "")
        a["pdf_en"] = tab.get(str(a["pdf_nummer_en"]), "")

    mit_doi = sum(1 for a in artikel.values() if a["doi"])
    mit_pdf = sum(1 for a in artikel.values() if a["pdf"])
    mit_abs = sum(1 for a in artikel.values() if a["abstract_de"].strip())
    wiss = sum(1 for a in artikel.values() if a["rubrik"] == "wissenschaft")
    ohne_rub = sum(1 for a in artikel.values() if not a["rubrik"])

    ZIEL.write_text(json.dumps({
        "stand": time.strftime("%Y-%m-%d"),
        "quelle": "monitor-versorgungsforschung.de, WordPress-Schnittstelle",
        "hinweis": ("1.528 Datensaetze gegen 936 DOIs bei Crossref. Die "
                    "Differenz sind eFirst-Dubletten und Beitraege ohne "
                    "Deposit. Verbunden wird ueber den DOI."),
        "gesamt": len(artikel), "mit_doi": mit_doi, "mit_pdf": mit_pdf,
        "mit_abstract_feld": mit_abs, "rubrik_wissenschaft": wiss,
        "ohne_rubrik": ohne_rub,
        "artikel": artikel,
    }, ensure_ascii=False, indent=1), encoding="utf-8")

    print()
    print(f"  Datensaetze              {len(artikel):5d}")
    print(f"  mit DOI                  {mit_doi:5d}")
    print(f"  mit PDF-Adresse          {mit_pdf:5d}")
    print(f"  mit gefuelltem Abstract  {mit_abs:5d}  <- kuerzester Weg, wenn hoch")
    print(f"  Rubrik wissenschaft      {wiss:5d}")
    print(f"  ohne jede Rubrik         {ohne_rub:5d}  <- darum taugt rubrik nicht als Filter")
    print(f"\n-> daten/mvf_artikel.json")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
