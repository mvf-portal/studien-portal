# -*- coding: utf-8 -*-
"""Wer traegt die Forschung? Die Art der fuehrenden Einrichtung.

Eine Forschungslandkarte, die nur Namen auflistet, verschweigt das
Wichtigste: unter wessen Auftrag geforscht wird. Das ist kein Beiwerk,
sondern bestimmt Finanzierung, Weisungsbindung und Unabhaengigkeit.

Der Anlass war eine Korrektur des Herausgebers am 30.10.2026. Ich hatte
„Institut fuer Allgemeinmedizin, Socium Bremen, ZI und RKI" pauschal
„Forschungseinrichtungen" genannt. Richtig ist:

  * **Institut fuer Allgemeinmedizin, Socium Bremen** - Hochschuleinrichtungen,
    deren Zweck Forschung ist.
  * **ZI** - Zentralinstitut fuer die kassenaerztliche Versorgung, eine
    Einrichtung der Aerzteschaft (Traeger: KBV), die auch forscht.
  * **RKI** - Bundesoberbehoerde im Geschaeftsbereich des BMG, die auch
    forscht.

Alle vier tauchen im Register gleich aus: als „Sponsor". Die Landkarte muss
sie unterscheiden.

**Was dieses Modul NICHT kann:** Es liest allein den Namen. Eine gGmbH, die
in Wahrheit zu einem Universitaetsklinikum gehoert, ist am Namen nicht zu
erkennen. Die Auswertung weist deshalb aus, wie viel sie zuordnet und was
sie liegen laesst - geraten wird nichts.

Aufruf:  py traegerart.py              # Auswertung der VF-Auswahl
         py traegerart.py --gegentest
"""
from __future__ import annotations

import argparse
import collections
import json
import pathlib
import re
import sys
import unicodedata

HIER = pathlib.Path(__file__).resolve().parent
DATEN = HIER / "daten"
sys.path.insert(0, str(HIER))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Die Reihenfolge ENTSCHEIDET. Oben stehen die namentlich benannten
# Einrichtungen, unten die Gattungswoerter - sonst zieht „Institut" oder
# „gGmbH" einen Traeger in die falsche Klasse.
REGELN: list[tuple[str, str, str]] = [
    # --- namentlich benannt, Bundes- und Landesbehoerden (Ressortforschung)
    ("Ressortforschung des Bundes",
     r"robert koch|\brki\b|paul ehrlich|\bbfarm\b|bundesinstitut fuer arzneimittel|"
     r"\bbzga\b|bundeszentrale fuer gesundheitliche|bundesanstalt|bundesamt|"
     r"umweltbundesamt|bundesinstitut",
     "Bundesoberbehörde im Geschäftsbereich eines Ministeriums; forscht im "
     "gesetzlichen Auftrag"),

    # --- Selbstverwaltung des Gesundheitswesens
    ("Selbstverwaltung im Gesundheitswesen",
     r"zentralinstitut fuer die kassenaerztliche|\bzi\b der kbv|"
     r"kassenaerztliche (bundes)?vereinigung|\bkbv\b|\bkzbv\b|"
     r"gemeinsamer bundesausschuss|\bg ba\b|\biqwig\b|\biqtig\b|"
     r"institut fuer qualitaetssicherung|aerztekammer|apothekerkammer|"
     r"pflegekammer|gkv spitzenverband|deutsche krankenhausgesellschaft",
     "Körperschaft der Selbstverwaltung; Träger sind Ärzteschaft, Kassen "
     "oder Kliniken"),

    # --- Kostentraeger
    ("Kostenträger",
     r"\baok\b|techniker krankenkasse|\btk\b|barmer|\bdak\b|knappschaft|"
     r"mobil krankenkasse|ikk|bkk|krankenkasse|gesundheitskasse|"
     r"deutsche rentenversicherung|\bdrv\b|berufsgenossenschaft|unfallkasse",
     "Zahlt die Versorgung und forscht an eigenen Routinedaten"),

    # --- Hochschule und Universitaetsmedizin (vor allen Gattungswoertern!)
    ("Hochschule und Universitätsmedizin",
     r"universitaet|universitaets|universitaetsklinikum|universitaetsmedizin|"
     r"uniklinik|charite|medizinische hochschule|hochschule|fachhochschule|"
     r"\bfakultaet\b|lehrstuhl|university|\buke\b|\blmu\b|\brwth\b|\btum\b|"
     r"\bmhh\b|socium",
     "Hochschuleinrichtung; Forschung ist ihr satzungsgemäßer Zweck"),

    # --- ausseruniversitaere Forschung
    ("Außeruniversitäre Forschungseinrichtung",
     r"leibniz|helmholtz|max planck|fraunhofer|deutsches zentrum fuer|"
     r"\bdzne\b|\bdzhk\b|\bdkfz\b|deutsches krebsforschungszentrum|"
     r"rheuma forschungszentrum|\bdrfz\b|\bbips\b|forschungszentrum|"
     r"cancer research cent(er|re)|research institute",
     "Außeruniversitäres Forschungsinstitut; Grundfinanzierung von Bund "
     "und Laendern"),

    # --- Fachgesellschaft, Verband, Stiftung
    ("Fachgesellschaft, Verband oder Stiftung",
     r"fachgesellschaft|gesellschaft fuer|deutsche gesellschaft|"
     r"\be\s?v\b|verband|bundesverband|stiftung|akademie|netzwerk",
     "Gemeinnütziger Träger; forscht aus eigenem Antrieb oder im Auftrag"),

    # --- kommunale und kirchliche Traeger
    ("Kommunaler oder kirchlicher Träger",
     r"\blvr\b|landschaftsverband|\blwl\b|bezirkskliniken|staedtisches|"
     r"gesundheitsamt|evangelisch|katholisch|diakonie|caritas|agaplesion|"
     r"\bvivantes\b|\bascklepios\b",
     "Kommune, Landschaftsverband oder kirchlicher Träger"),

    # --- Versorger ohne Hochschulbindung
    ("Krankenhaus oder Praxis",
     r"klinikum|\bklinik\b|krankenhaus|fachklinik|rehaklinik|praxis|"
     r"medizinisches versorgungszentrum|\bmvz\b|aerztehaus|sanatorium",
     "Einrichtung der Versorgung; forscht neben dem Versorgungsauftrag"),

    # --- Unternehmen
    ("Unternehmen",
     r"\bgmbh\b|\bggmbh\b|\bag\b|\bse\b|\bkg\b|\bmbh\b|pharma|\binc\b|"
     r"\bltd\b|health gmbh",
     "Privatwirtschaftlicher Träger"),
]

# gGmbH ist gemeinnuetzig - das unterscheidet sie von einer GmbH. Wo sonst
# nichts greift, wird das ausgewiesen statt verschwiegen.
GEMEINNUETZIG = re.compile(r"\bggmbh\b|gemeinnuetzig")

UNBEKANNT = "nicht zuzuordnen"


def norm(s: str) -> str:
    """Kleinschreiben, Umlaute aufloesen, uebrige Akzente abwerfen.

    **Die Reihenfolge ist entscheidend, und sie war schon einmal falsch.**
    Zuerst die deutschen Umlaute zu ae/oe/ue - sonst wuerde NFKD aus „ü" ein
    „u" machen und „Universitaet" nie treffen. Erst DANACH die uebrigen
    Akzente abwerfen: Ohne diesen zweiten Schritt fiel das „é" in „Charité"
    durch die Zeichenklasse heraus, der Name wurde zu `charit`, und das
    Muster `charite` traf nicht ein einziges Mal. 11 Studien der Charité
    standen deshalb als „nicht zuzuordnen".
    """
    s = (s or "").lower()
    s = (s.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue")
           .replace("ß", "ss").replace("–", " ").replace("-", " "))
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def art(name: str) -> tuple[str, str]:
    """(Traegerart, Begruendung in einem Satz)."""
    n = norm(name)
    for klasse, muster, erklaerung in REGELN:
        if re.search(muster, n):
            if klasse == "Unternehmen" and GEMEINNUETZIG.search(n):
                return ("Gemeinnütziger Träger",
                        "Gemeinnützige Gesellschaft; der Name nennt keinen "
                        "Hochschul- oder Behördenträger")
            return klasse, erklaerung
    return UNBEKANNT, "Der Name laesst die Traegerschaft nicht erkennen"


def gegentest() -> int:
    """Die vier Faelle der Korrektur vom 30.10.2026 - und was nicht rutschen darf."""
    faelle = [
        # Die Korrektur des Herausgebers
        ("Institut für Allgemeinmedizin, Charité - Universitätsmedizin Berlin",
         "Hochschule und Universitätsmedizin"),
        ("Universität Bremen - Socium", "Hochschule und Universitätsmedizin"),
        ("Zentralinstitut für die kassenärztliche Versorgung in Deutschland",
         "Selbstverwaltung im Gesundheitswesen"),
        ("Robert Koch-Institut", "Ressortforschung des Bundes"),
        # Kostentraeger duerfen nie als Forschungseinrichtung durchgehen
        ("AOK Rheinland/Hamburg – Die Gesundheitskasse", "Kostenträger"),
        ("Techniker Krankenkasse", "Kostenträger"),
        ("BARMER Abteilung Digitale Versorgung / Prävention", "Kostenträger"),
        ("Deutsche Rentenversicherung Bund", "Kostenträger"),
        # Unternehmen
        ("Orthopy Health GmbH", "Unternehmen"),
        ("Novartis Pharma GmbH", "Unternehmen"),
        # Hochschule schlaegt Gattungswort: „Klinik" und „gGmbH" im Namen
        ("Neurologische Klinik, Universitätsklinikum Heidelberg",
         "Hochschule und Universitätsmedizin"),
        ("Vestische Kinder- und Jugendklinik Datteln, Universität Witten/Herdecke",
         "Hochschule und Universitätsmedizin"),
        ("Technische Hochschule Rosenheim", "Hochschule und Universitätsmedizin"),
        # Versorger ohne Hochschulbindung
        ("Rheinhessen-Fachklinik Alzey", "Krankenhaus oder Praxis"),
        ("Orthopädische Klinik König-Ludwig-Haus Würzburg", "Krankenhaus oder Praxis"),
        # Kommunal und kirchlich
        ("LVR-Institut für Forschung und Bildung", "Kommunaler oder kirchlicher Träger"),
        ("Viszeralmedizinisches Zentrum, Evangelisches Diakoniekrankenhaus Freiburg",
         "Kommunaler oder kirchlicher Träger"),
        # Fachgesellschaft
        ("Deutsche Krebsgesellschaft e. V.", "Fachgesellschaft, Verband oder Stiftung"),
        # Akzente: „Charité" darf nicht am é scheitern
        ("Charité Campus Charité Mitte", "Hochschule und Universitätsmedizin"),
        ("Deutsches Herzzentrum der Charité", "Hochschule und Universitätsmedizin"),
        ("Charité Centre for Global Health", "Hochschule und Universitätsmedizin"),
        # englischer Name
        ("German Cancer Research Center", "Außeruniversitäre Forschungseinrichtung"),
        # Erfundenes darf nicht zugeordnet werden
        ("Wolkenkuckucksheimer Forschungsstelle", UNBEKANNT),
    ]
    print("Gegentest Traegerart:\n")
    ok = True
    for name, erwartet in faelle:
        ist, _ = art(name)
        gut = ist == erwartet
        ok = ok and gut
        print(f"  {'ok  ' if gut else 'FEHL'}  {name[:54]:<56} -> {ist}")
        if not gut:
            print(f"          erwartet: {erwartet}")
    print("\n" + ("  Gegentest bestanden." if ok else "  GEGENTEST FEHLGESCHLAGEN."))
    return 0 if ok else 1


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--gegentest", action="store_true")
    a = p.parse_args()
    if a.gegentest:
        return gegentest()

    D = json.loads((DATEN / "landkarte.json").read_text(encoding="utf-8"))["studien"]
    je_studie = collections.Counter()
    je_einrichtung: dict[str, str] = {}
    offen = collections.Counter()
    for s in D:
        if not (s.get("sponsor") and s["sponsor"].get("name")):
            continue
        name = s["sponsor"]["name"].strip()
        k, _ = art(name)
        je_studie[k] += 1
        je_einrichtung[name] = k
        if k == UNBEKANNT:
            offen[name] += 1

    ges = sum(je_studie.values())
    zugeordnet = ges - je_studie[UNBEKANNT]
    print(f"{ges} Studien mit fuehrender Einrichtung, "
          f"{len(je_einrichtung)} verschiedene Einrichtungen")
    print(f"  zugeordnet: {zugeordnet} ({zugeordnet/ges*100:.1f} %)\n")
    print("Wer traegt die Versorgungsforschung?\n")
    print(f"  {'Studien':>7}  {'Einrichtungen':>13}  Traegerart")
    for k, n in je_studie.most_common():
        e = sum(1 for v in je_einrichtung.values() if v == k)
        print(f"  {n:>7}  {e:>13}  {k}")

    print(f"\nWas die Auswahl liegen laesst ({je_studie[UNBEKANNT]} Studien, "
          f"{len(offen)} Einrichtungen) - haeufigste:")
    for name, n in offen.most_common(12):
        print(f"  {n:>2}  {name[:74]}")

    ziel = DATEN / "traegerart.json"
    ziel.write_text(json.dumps({
        "hinweis": "Zuordnung allein aus dem Namen der fuehrenden Einrichtung. "
                   "Was der Name nicht hergibt, steht als 'nicht zuzuordnen'.",
        "studien": ges, "zugeordnet": zugeordnet,
        "je_art": je_studie.most_common(),
        "je_einrichtung": je_einrichtung,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\ngeschrieben: {ziel}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
