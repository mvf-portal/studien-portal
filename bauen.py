# -*- coding: utf-8 -*-
"""Baut aus dem DRKS-Gesamtexport die Datengrundlage der Landkarte.

Schritte:
  1. Nur die Datensaetze, die unter CC BY 4.0 stehen (ab 2025 registriert
     ODER zuletzt aktualisiert). Alles andere darf nicht wiedergegeben
     werden - siehe MANUAL.md, Abschnitt Lizenz.
  2. Felder herausziehen, OHNE personenbezogene Angaben: Einrichtung, Ort,
     PLZ ja - Name, E-Mail, Telefon der Ansprechpartner nein.
  3. VF-Bezug und Hub-Zuordnung nach `zuschnitt.py`.
  4. Querverweis auf den eigenen Bestand: DOI der Ergebnispublikationen
     gegen die DOIs der 15 Hub-Archive (aus `hubbezug.py`).
  5. Auszaehlungen fuer die Seite - einschliesslich der Angabe, was die
     Landkarte NICHT zeigt.

Aufruf:  py bauen.py
"""
from __future__ import annotations

import collections
import json
import pathlib
import re
import sys
import zipfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from bestandsbezug import Abgleich
from zuschnitt import HUB_NAMEN, VF_SCHWELLE, hubs_fuer, vf_punkte

HIER = pathlib.Path(__file__).resolve().parent
DATEN = HIER / "daten"

# PLZ-Leitregion (zwei Stellen) -> Bundesland. NAEHERUNG: Leitregionen folgen
# der Post, nicht der Landesgrenze; an den Raendern liegt sie daneben. Die
# Seite weist das aus, statt eine Genauigkeit zu behaupten, die es nicht gibt.
PLZ_LAND = {
    "01": "Sachsen", "02": "Sachsen", "03": "Brandenburg", "04": "Sachsen",
    "06": "Sachsen-Anhalt", "07": "Thüringen", "08": "Sachsen", "09": "Sachsen",
    "10": "Berlin", "12": "Berlin", "13": "Berlin", "14": "Brandenburg",
    "15": "Brandenburg", "16": "Brandenburg", "17": "Mecklenburg-Vorpommern",
    "18": "Mecklenburg-Vorpommern", "19": "Mecklenburg-Vorpommern",
    "20": "Hamburg", "21": "Hamburg", "22": "Hamburg",
    "23": "Schleswig-Holstein", "24": "Schleswig-Holstein", "25": "Schleswig-Holstein",
    "26": "Niedersachsen", "27": "Niedersachsen", "28": "Bremen",
    "29": "Niedersachsen", "30": "Niedersachsen", "31": "Niedersachsen",
    "32": "Nordrhein-Westfalen", "33": "Nordrhein-Westfalen",
    "34": "Hessen", "35": "Hessen", "36": "Hessen",
    "37": "Niedersachsen", "38": "Niedersachsen", "39": "Sachsen-Anhalt",
    **{f"{n:02d}": "Nordrhein-Westfalen" for n in range(40, 49)},
    "49": "Niedersachsen",
    **{f"{n:02d}": "Nordrhein-Westfalen" for n in range(50, 54)},
    "54": "Rheinland-Pfalz", "55": "Rheinland-Pfalz", "56": "Rheinland-Pfalz",
    "57": "Nordrhein-Westfalen", "58": "Nordrhein-Westfalen", "59": "Nordrhein-Westfalen",
    **{f"{n:02d}": "Hessen" for n in range(60, 66)},
    "66": "Saarland", "67": "Rheinland-Pfalz", "68": "Baden-Württemberg",
    **{f"{n:02d}": "Baden-Württemberg" for n in range(69, 80)},
    **{f"{n:02d}": "Bayern" for n in range(80, 88)},
    "88": "Baden-Württemberg", "89": "Baden-Württemberg",
    **{f"{n:02d}": "Bayern" for n in range(90, 98)},
    "98": "Thüringen", "99": "Thüringen",
}
# Leitregionen, die sicher ueber eine Landesgrenze laufen.
PLZ_UNSICHER = {"02", "06", "14", "17", "22", "23", "27", "34", "36", "38",
                "49", "57", "66", "67", "68", "88", "89", "98"}

STATUS_DE = {
    "RECRUITING": "rekrutiert",
    "PENDING": "geplant",
    "COMPLETE_FOLLOW_UP_COMPLETE": "abgeschlossen",
    "COMPLETE_FOLLOW_UP_CONTINUING": "in Nachbeobachtung",
    "DISCONTINIUED": "abgebrochen",
    "WITHDRAWN": "zurückgezogen",
    "INVITE_ONLY": "nur auf Einladung",
    "SUSPENDED": "ausgesetzt",
}
FOERDER_DE = {
    "PUBLIC_FUNDING": "öffentlich gefördert",
    "COMMERCIAL": "kommerziell",
    "INSTITUTIONAL": "aus eigenen Mitteln",
    "PRIVATE_SPONSORSHIP": "privat gefördert",
}


def jahr(v) -> str:
    return str(v)[:4] if v else "0"


def text_de(liste, *felder) -> str:
    """Zieht die deutschen Textfelder zusammen, sonst die englischen."""
    for ziel in ("de", "en"):
        for e in (liste or []):
            if ((e.get("idLocale") or {}).get("locale")) == ziel:
                teile = [str(e.get(f) or "") for f in felder]
                if any(teile):
                    return " ".join(teile).strip()
    return ""


def kommission_norm(name: str) -> str:
    """848 Schreibweisen fuer rund 51 Kommissionen - grob zusammenfuehren."""
    s = (name or "").lower()
    s = s.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    s = re.sub(r"ethik[-\s]?kommission(en)?", " ", s)
    s = re.sub(r"\b(der|des|die|an|bei|fuer|zu|und|am|medizinischen?|fakultaet|"
               r"universitaets?|universitaet|klinikum|e\.?\s?v\.?)\b", " ", s)
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def main() -> int:
    quelle = sorted(DATEN.glob("drks-export-*.zip"))[-1]
    stand = re.search(r"(\d{4}-\d{2}-\d{2})", quelle.name).group(1)
    print(f"Quelle: {quelle.name}  (Abrufdatum {stand})")

    z = zipfile.ZipFile(quelle)
    name = [n for n in z.namelist() if n.endswith(".json") and n.startswith("DRKS")][0]
    roh = json.loads(z.read(name).decode("utf-8"))
    print(f"  {len(roh)} Datensaetze im Export")

    frei = [x for x in roh
            if jahr(x.get("lastUpdate")) >= "2025" or jahr(x.get("registrationDrks")) >= "2025"]
    print(f"  {len(frei)} davon unter CC BY 4.0 ({len(frei)/len(roh)*100:.1f} %)")

    # Wie viele Studien mit Versorgungsbezug stehen im GANZEN Register - also
    # auch in dem Teil, den wir nicht wiedergeben duerfen? Ohne diese Zahl
    # sieht die Landkarte vollstaendiger aus, als sie ist. Gezaehlt wird nur;
    # wiedergegeben wird nach wie vor allein der CC-BY-Teil.
    vf_im_register = 0
    for x in roh:
        b = x.get("trialDescriptions") or []
        if vf_punkte(f'{text_de(b, "title")} {text_de(b, "summary")}')[0] >= VF_SCHWELLE:
            vf_im_register += 1
    print(f"  {vf_im_register} Studien mit Versorgungsbezug im ganzen Register")

    doi_hub = json.loads((DATEN / "hub-dois.json").read_text(encoding="utf-8"))["doi_hub"]
    print(f"  {len(doi_hub)} DOIs aus den 15 Hub-Archiven zum Abgleich")
    abgleich = Abgleich()

    studien = []
    for x in frei:
        beschr = x.get("trialDescriptions") or []
        titel = text_de(beschr, "title")
        akronym = text_de(beschr, "acronym")
        summary = text_de(beschr, "summary")
        text = f"{titel} {summary}"

        icd = [c.get("code") for c in (x.get("studiedHealthConditions") or []) if c.get("code")]
        indikation = text_de([d for c in (x.get("studiedHealthConditions") or [])
                              for d in (c.get("studiedHealthConditionDescriptions") or [])],
                             "comment")

        rek = x.get("recruitment") or {}
        orte = [{"name": i.get("name"), "ort": i.get("city"), "art": i.get("type")}
                for i in (rek.get("institutes") or []) if i.get("name")]

        # Sponsor: nur Einrichtung und Ort, keine Person, keine Kontaktdaten.
        sponsor, plz = None, None
        for k in (x.get("trialContacts") or []):
            if ((k.get("idContactIdType") or {}).get("type")) == "PRIMARY_SPONSOR":
                c = k.get("contact") or {}
                sponsor = {"name": c.get("affiliation"), "ort": c.get("city")}
                plz = (c.get("zip") or "")[:2]
                break

        ek = x.get("ethicsCommittee") or {}
        voten = []
        for v in (ek.get("ethicVotes") or []):
            c = v.get("contact") or {}
            voten.append({"kommission": c.get("affiliation"), "ort": c.get("city"),
                          "plz": (c.get("zip") or "")[:2],
                          "datum": v.get("dateOfVote"), "votum": v.get("vote")})
        if not plz and voten:
            plz = voten[0]["plz"]

        land = PLZ_LAND.get(plz or "")
        dois = []
        for p in ((x.get("trialResults") or {}).get("publications") or []):
            for m in re.findall(r"10\.\d{4,9}/[-._;()/:A-Za-z0-9]+",
                                f"{p.get('link') or ''} {p.get('description') or ''}"):
                d = m.rstrip(".,;)").lower()
                if d not in dois:
                    dois.append(d)

        bestand = [{"doi": d, **doi_hub[d]} for d in dois if d in doi_hub]
        namen = [o["name"] for o in orte] + ([sponsor["name"]] if sponsor and sponsor.get("name") else [])
        innofonds = abgleich.innofonds(namen)
        punkte, begriffe = vf_punkte(text)
        hubs, hubquelle = hubs_fuer(text, icd)

        studien.append({
            "id": x.get("drksId"), "url": x.get("url"),
            "titel": titel, "akronym": akronym,
            "kurz": (summary[:400] + "…") if len(summary) > 400 else summary,
            "indikation": indikation, "icd": icd[:6],
            "art": (x.get("studyCharacteristic") or {}).get("type"),
            "status": rek.get("status"),
            "status_de": STATUS_DE.get(rek.get("status"), rek.get("status")),
            "zentrik": rek.get("centricType"),
            "teilnehmer": rek.get("plannedParticipants") or rek.get("totalParticipants"),
            "orte": orte[:6], "sponsor": sponsor, "land": land,
            "land_unsicher": (plz in PLZ_UNSICHER) if plz else False,
            "foerderung": sorted({FOERDER_DE.get(m.get("type"), m.get("type"))
                                  for m in (x.get("materialSupports") or []) if m.get("type")}),
            "voten": voten, "registriert": x.get("registrationDrks"),
            "aktualisiert": x.get("lastUpdate"),
            "retrospektiv": x.get("registrationType") == "RETROSPECTIVE",
            "dois": dois, "bestand": bestand, "innofonds": innofonds,
            "vf_punkte": punkte, "vf_begriffe": begriffe[:8],
            "vf": punkte >= VF_SCHWELLE,
            "hubs": hubs, "hubquelle": hubquelle,
        })

    # ------------------------------------------------------------- Auszaehlung
    vf = [s for s in studien if s["vf"]]
    z_status = collections.Counter(s["status_de"] for s in vf)
    z_land = collections.Counter(s["land"] for s in vf if s["land"])
    z_hub = collections.Counter(h for s in vf for h in s["hubs"])
    z_art = collections.Counter(s["art"] for s in vf)
    z_foerder = collections.Counter(f for s in vf for f in s["foerderung"])
    z_komm_roh = collections.Counter(v["kommission"] for s in vf for v in s["voten"]
                                     if v.get("kommission"))
    z_komm = collections.Counter(kommission_norm(k) for k in z_komm_roh.elements())
    ohne_hub = sum(1 for s in vf if not s["hubs"])
    mit_bestand = [s for s in vf if s["bestand"]]
    abgeschlossen = [s for s in vf if s["status"] == "COMPLETE_FOLLOW_UP_COMPLETE"]
    abg_ohne_pub = sum(1 for s in abgeschlossen if not s["dois"])

    ergebnis = {
        "stand": stand,
        "quelle": "Deutsches Register Klinischer Studien (DRKS), BfArM",
        "lizenz": "CC BY 4.0 (nur Einträge ab 2025 registriert oder aktualisiert)",
        "roh_gesamt": len(roh), "ccby_gesamt": len(frei), "vf_gesamt": len(vf),
        "vf_im_register": vf_im_register,
        "vf_nicht_zeigbar": vf_im_register - len(vf),
        "zaehlung": {
            "status": z_status.most_common(),
            "land": z_land.most_common(),
            "hub": [(h, HUB_NAMEN[h][0], HUB_NAMEN[h][1], n) for h, n in z_hub.most_common()],
            "art": z_art.most_common(),
            "foerderung": z_foerder.most_common(),
            "kommissionen_schreibweisen": len(z_komm_roh),
            "kommissionen_zusammengefuehrt": len(z_komm),
            "kommissionen_top": z_komm_roh.most_common(12),
            "ohne_hub": ohne_hub,
            "mit_bestandstreffer": len(mit_bestand),
            "mit_innofonds": sum(1 for s in vf if s["innofonds"]),
            "innofonds_einrichtungen": collections.Counter(
                i["name"] for s in vf for i in s["innofonds"]).most_common(15),
            "abgeschlossen": len(abgeschlossen),
            "abgeschlossen_ohne_publikation": abg_ohne_pub,
            "retrospektiv": sum(1 for s in vf if s["retrospektiv"]),
            "land_unsicher": sum(1 for s in vf if s["land_unsicher"]),
        },
        "studien": vf,
    }
    ziel = DATEN / "landkarte.json"
    ziel.write_text(json.dumps(ergebnis, ensure_ascii=False), encoding="utf-8")

    print(f"\n  {len(vf)} Studien mit Versorgungsbezug (Schwelle {VF_SCHWELLE} Punkte)")
    print(f"  Status: {z_status.most_common(5)}")
    print(f"  ohne Hub-Zuordnung: {ohne_hub} ({ohne_hub/len(vf)*100:.1f} %)")
    print(f"  mit Treffer im eigenen Bestand: {len(mit_bestand)}")
    print(f"  abgeschlossen ohne Publikationsangabe: {abg_ohne_pub} von {len(abgeschlossen)}")
    print(f"  Kommissionen: {len(z_komm_roh)} Schreibweisen -> {len(z_komm)} zusammengefuehrt")
    print(f"\ngeschrieben: {ziel}  ({ziel.stat().st_size/1e6:.1f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
