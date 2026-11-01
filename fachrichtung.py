# -*- coding: utf-8 -*-
"""Welche Wissenschaftsrichtung forscht hier?

Die Fachrichtung steht im Register nirgends als Feld. Sie laesst sich aber
oft am NAMEN der fuehrenden Einrichtung ablesen: Deutsche
Versorgungsforschungs-Institute tragen ihr Fach im Namen - „Institut fuer
Allgemeinmedizin", „Institut fuer Sozialmedizin und Epidemiologie",
„Lehrstuhl fuer Gesundheitsoekonomie".

**Das greift aber nur bei einem Teil.** Die grossen Haeuser nennen im
Register bloss „Universitaetsklinikum Heidelberg", nicht das Institut. Fuer
diese Studien gibt das Register die Fachrichtung schlicht nicht her.

**Es wird nichts geraten.** Dieses Modul meldet nur, was im Namen steht, und
weist aus, wie viel es liegen laesst. Eine Schaetzung aus Titel und
Zusammenfassung waere moeglich - sie waere dann aber als Schaetzung zu
kennzeichnen, und das ist eine Entscheidung des Herausgebers, keine des
Skripts.

Aufruf:  py fachrichtung.py
         py fachrichtung.py --gegentest
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

OFFEN = "im Register nicht genannt"

# Reihenfolge zaehlt nicht - eine Einrichtung darf mehrere Faecher fuehren
# („Institut fuer Sozialmedizin und Epidemiologie" ist beides).
FAECHER: list[tuple[str, str]] = [
    ("Allgemein- und Hausarztmedizin",
     r"allgemeinmedizin|hausarztmedizin|hausaerztlich|primaerversorgung|"
     r"general practice|family medicine"),
    ("Versorgungsforschung (als Fach benannt)",
     r"versorgungsforschung|health services research|gesundheitssystemforschung"),
    ("Sozialmedizin und Epidemiologie",
     r"sozialmedizin|epidemiologie|epidemiology|public health|"
     r"bevoelkerungsmedizin|praeventivmedizin"),
    ("Gesundheitsoekonomie",
     r"gesundheitsoekonomie|health economics|oekonomie des gesundheitswesens"),
    ("Pflegewissenschaft",
     r"pflegewissenschaft|pflegeforschung|nursing science"),
    ("Medizinische Psychologie und Psychotherapieforschung",
     r"medizinische psychologie|klinische psychologie|psychotherapieforschung|"
     r"psychosoziale|verhaltenstherapie|psychologisches institut"),
    ("Rehabilitationswissenschaft",
     r"rehabilitationswissenschaft|rehabilitationsforschung|rehabilitationsmedizin"),
    ("Palliativ- und Hospizforschung",
     r"palliativmedizin|palliativversorgung|hospiz|palliative care"),
    ("Medizinische Informatik und digitale Versorgung",
     r"medizinische informatik|gesundheitsinformatik|digitale versorgung|"
     r"ehealth|telemedizin|digital health"),
    ("Biometrie und Statistik",
     r"biometrie|medizinische statistik|biostatistik|biometry"),
    ("Evidenzbasierte Medizin und Leitlinien",
     r"evidenzbasiert|evidence based|cochrane|leitlinien|wissensmanagement"),
    ("Arzneimitteltherapie und Pharmazie",
     r"pharmazie|klinische pharmakologie|arzneimitteltherapie|pharmakoepidemiologie"),
    ("Medizinsoziologie",
     r"medizinische soziologie|medizinsoziologie|gesundheitssoziologie"),
    ("Arbeits- und Umweltmedizin",
     r"arbeitsmedizin|umweltmedizin|arbeits und umwelt"),
    ("Geriatrie und Altersforschung",
     r"geriatrische forschung|alternsforschung|altersmedizin|geriatrie"),
]


def norm(s: str) -> str:
    """Wie in traegerart.py: erst Umlaute aufloesen, DANN Akzente abwerfen."""
    s = (s or "").lower()
    s = (s.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue")
           .replace("ß", "ss").replace("–", " ").replace("-", " "))
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def faecher(name: str) -> list[str]:
    """Alle Faecher, die der Name NENNT. Leere Liste heisst: steht nicht da."""
    n = norm(name)
    return [f for f, m in FAECHER if re.search(m, n)]


def gegentest() -> int:
    faelle = [
        ("Institut für Allgemeinmedizin, Charité - Universitätsmedizin Berlin",
         ["Allgemein- und Hausarztmedizin"]),
        ("Universität zu Lübeck, Institut für Sozialmedizin und Epidemiologie",
         ["Sozialmedizin und Epidemiologie"]),
        ("Technische Universität München, Lehrstuhl für Gesundheitsökonomie",
         ["Gesundheitsoekonomie"]),
        ("Abteilung Allgemeinmedizin und Versorgungsforschung, Universitätsklinikum Heidelberg",
         ["Allgemein- und Hausarztmedizin", "Versorgungsforschung (als Fach benannt)"]),
        ("Charité - Universitätsmedizin Berlin, Institut für Medizinische Soziologie und Rehabilitationswissenschaft",
         ["Rehabilitationswissenschaft", "Medizinsoziologie"]),
        ("Institut für Hausarztmedizin, Universitätsklinikum Bonn",
         ["Allgemein- und Hausarztmedizin"]),
        ("Lehrstuhl für Klinische Psychologie und Psychotherapie, FAU",
         ["Medizinische Psychologie und Psychotherapieforschung"]),
        # Diese Namen nennen KEIN Fach - sie duerfen keines bekommen.
        ("Universitätsklinikum Hamburg-Eppendorf", []),
        ("Charité - Universitätsmedizin Berlin", []),
        ("Medizinische Hochschule Hannover", []),
        ("Techniker Krankenkasse", []),
        ("Wolkenkuckucksheimer Forschungsstelle", []),
    ]
    print("Gegentest Fachrichtung:\n")
    ok = True
    for name, erwartet in faelle:
        ist = faecher(name)
        gut = set(ist) == set(erwartet)
        ok = ok and gut
        print(f"  {'ok  ' if gut else 'FEHL'}  {name[:52]:<54} -> "
              f"{', '.join(ist) if ist else '(keines)'}")
        if not gut:
            print(f"          erwartet: {', '.join(erwartet) or '(keines)'}")
    print("\n" + ("  Gegentest bestanden." if ok else "  GEGENTEST FEHLGESCHLAGEN."))
    return 0 if ok else 1


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--gegentest", action="store_true")
    a = p.parse_args()
    if a.gegentest:
        return gegentest()

    D = json.loads((DATEN / "landkarte.json").read_text(encoding="utf-8"))["studien"]
    je_fach = collections.Counter()
    je_einrichtung: dict[str, list[str]] = {}
    mit, ohne_bsp = 0, collections.Counter()
    ges = 0
    for s in D:
        if not (s.get("sponsor") and s["sponsor"].get("name")):
            continue
        ges += 1
        name = s["sponsor"]["name"].strip()
        f = faecher(name)
        je_einrichtung[name] = f
        if f:
            mit += 1
            for x in f:
                je_fach[x] += 1
        else:
            ohne_bsp[name] += 1

    print(f"{ges} Studien mit fuehrender Einrichtung")
    print(f"  Fachrichtung im Namen genannt : {mit} ({mit/ges*100:.1f} %)")
    print(f"  nicht genannt                 : {ges-mit} ({(ges-mit)/ges*100:.1f} %)")
    print("\nWelche Wissenschaftsrichtung (Mehrfachnennung moeglich):\n")
    for f, n in je_fach.most_common():
        e = sum(1 for v in je_einrichtung.values() if f in v)
        print(f"  {n:>4} Studien  {e:>3} Einrichtungen  {f}")

    print(f"\nWas die Auswahl liegen laesst - haeufigste Einrichtungen "
          f"ohne Fachangabe im Namen:")
    for name, n in ohne_bsp.most_common(10):
        print(f"  {n:>2}  {name[:72]}")

    ziel = DATEN / "fachrichtung.json"
    ziel.write_text(json.dumps({
        "hinweis": "Nur was der Name der fuehrenden Einrichtung NENNT. "
                   "Nichts geschaetzt, nichts aus dem Studientext abgeleitet.",
        "studien": ges, "mit_fach": mit, "ohne_fach": ges - mit,
        "je_fach": je_fach.most_common(),
        "je_einrichtung": je_einrichtung,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\ngeschrieben: {ziel}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
