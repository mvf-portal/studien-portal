# -*- coding: utf-8 -*-
"""Die MVF-Serie „Versorgungsforschung made in …" als Standortbezug.

45 Institutsportraets seit 2016, abgerufen am 30.10.2026 von
https://www.monitor-versorgungsforschung.de/cooperations/vf-serie/

Das ist MVFs eigenes Standortprofil - wo die Serie ein Institut portraetiert
hat, gehoert der Beitrag auf dessen Profilseite. Zugeordnet wird ueber Ort
und kennzeichnende Woerter der Einrichtung, nie ueber ein einzelnes
Allerweltswort; `pruefe()` faehrt den Gegentest.
"""
from __future__ import annotations

import re
import sys
import unicodedata

# (Ausgabe, Titel, Einrichtung laut Serie, Ort, Link)
SERIE = [
 ("01/2025", "Pflegerische Versorgung im Sozialraum partizipativ gestalten", "Bayerisches Zentrum Pflege Digital, HS Kempten", "Kempten", "https://www.monitor-versorgungsforschung.de/wp-content/uploads/2025/01/MVF0125_Kempten_230125.pdf"),
 ("03/2025", "Der perfekte Standort für diversitätssensible Versorgungsforschung", "Institut für Diversitätsmedizin, Ruhr-Universität Bochum", "Bochum", "https://www.monitor-versorgungsforschung.de/wp-content/uploads/2025/05/MVF0325_220525_Otte.pdf"),
 ("02/2025", "Forschen in einer Modellregion für die Digitalisierung in der Pflege", "Universitätsklinikum Halle", "Halle", "https://www.monitor-versorgungsforschung.de/wp-content/uploads/2025/03/MVF0225_Halle_240325.pdf"),
 ("01/2024", "„In der Lausitz wird der Strukturwandel erforscht“", "BTU Cottbus-Senftenberg", "Senftenberg", "https://www.monitor-versorgungsforschung.de/wp-content/uploads/2024/01/MOVS01_Senftenberg.pdf"),
 ("05/2024", "„Abbau von Überversorgung steht im Fokus“", "Universitätsklinikum Jena", "Jena", "https://www.monitor-versorgungsforschung.de/wp-content/uploads/2024/09/MOVS-0524_JENA_160924.pdf"),
 ("04/2024", "„Daten für Taten“ gegen Über-, Unter- und Fehlversorgung", "APOLLON Hochschule Bremen", "Bremen", "https://www.monitor-versorgungsforschung.de/wp-content/uploads/2024/07/APOLLON.pdf"),
 ("05/2024", "„Grundlagenarbeit rund um die Behandlung der Demenz“", "Universitätsklinikum Erlangen", "Erlangen", "https://www.monitor-versorgungsforschung.de/wp-content/uploads/2024/09/MOVS-0524_Erlangen_160924.pdf"),
 ("06/2024", "„Ziel ist es, die Pflegeversorgung evidenzbasiert zu verbessern“", "Universität Oldenburg", "Oldenburg", "https://www.monitor-versorgungsforschung.de/wp-content/uploads/2024/11/MOVS-0624_Oldenburg.pdf"),
 ("06/2023", "Verzahnung von Praxis, Wissenschaft und Lehre", "THM Gießen, Willy-Robert-Pitzer-Institut", "Gießen", "https://www.monitor-versorgungsforschung.de/wp-content/uploads/2023/11/MOVS-0623_WillyRobert-Pitzer-Institut.pdf"),
 ("06/2022", "Versorgungsforschung „aus der Praxis – für die Praxis“", "Universitätsklinikum Erlangen", "Erlangen", "https://www.monitor-versorgungsforschung.de/wp-content/uploads/2023/01/MVF_06_Erlangen_241122.pdf"),
 ("03/2022", "Energetische Atmosphäre mit inspirierendem Austausch", "Lehrstuhl Multimedikation und Versorgungsforschung", "Frankfurt", "https://www.monitor-versorgungsforschung.de/wp-content/uploads/2023/01/MVF03-22_vandenAkker.pdf"),
 ("05/2022", "Mit der Verpflichtung am „point of care“ zu forschen", "Katholische Stiftungshochschule München", "München", "https://www.monitor-versorgungsforschung.de/wp-content/uploads/2023/08/MVF05_KSH.pdf"),
 ("01/2022", "Nationales Kompetenzzentrum Gesundheitsökonomik", "CINCH, Universität Duisburg-Essen", "Essen", "https://www.monitor-versorgungsforschung.de/wp-content/uploads/2023/01/MVF_01-22_CINCH.pdf"),
 ("06/2021", "Studienort für kritische Hinterfrager und Veränderer", "Medizinische Hochschule Brandenburg", "Rüdersdorf", "https://www.monitor-versorgungsforschung.de/wp-content/uploads/2023/01/MVF_06-21_Ruedersdorf.pdf"),
 ("04/2021", "Schnittstelle Ökonomie und Versorgungsforschung", "Hamburg Center for Health Economics", "Hamburg", "https://www.monitor-versorgungsforschung.de/wp-content/uploads/2023/01/MVF_04_21_HCHE.pdf"),
 ("05/2021", "Gemeinsames Denken und Forschen für die Rehabilitation", "Universität zu Lübeck", "Lübeck", "https://www.monitor-versorgungsforschung.de/wp-content/uploads/2023/01/MVF_05-21_Bethge220921.pdf"),
 ("03/2021", "Versorgungsforschung mit hoher Translation", "Charité – Universitätsmedizin Berlin", "Berlin", "https://www.monitor-versorgungsforschung.de/wp-content/uploads/2023/01/MVF0321_S_S.pdf"),
 ("02/2021", "„Deutlich bessere Sichtbarkeit für die Pflege“", "Abteilung Pflegewissenschaftliche Versorgungsforschung, Universität Bremen", "Bremen", "https://www.monitor-versorgungsforschung.de/wp-content/uploads/2023/01/MVF_0221_Bremen_290321.pdf"),
 ("01/2021", "„Drehscheibe zwischen Hausärzten und Kliniken“", "Institut für Allgemeinmedizin und evidenzbasierte Versorgungsforschung, Graz/Frankfurt", "Frankfurt", "https://www.monitor-versorgungsforschung.de/wp-content/uploads/2023/01/MVF_0121_Siebenhofer-Kroitzsch.pdf"),
 ("06/2020", "„Am Menschen orientierte Gesundheitsversorgung“", "Ruhr-Universität Bochum", "Bochum", "https://www.monitor-versorgungsforschung.de/wp-content/uploads/2023/01/MVF_0620_Bochum.pdf"),
 ("05/2020", "„Die Stimme der Patienten“", "Medizinische Hochschule Hannover", "Hannover", "https://www.monitor-versorgungsforschung.de/wp-content/uploads/2023/01/MVF_05-2020_MHH.pdf"),
 ("02/2020", "Arbeitsmedizinische Versorgungsforschung", "Universität Tübingen", "Tübingen", "https://www.monitor-versorgungsforschung.de/wp-content/uploads/2023/01/MVF_02-2020_Tuebingen.pdf"),
 ("02/2020", "Offen für verschiedene Perspektiven", "Universität Witten/Herdecke", "Witten", "https://www.monitor-versorgungsforschung.de/wp-content/uploads/2023/01/MVF_02-2020_Witten.pdf"),
 ("01/2020", "„Enge Verzahnung von Theorie und Praxis“", "Europäische Fachhochschule EUFH", "Köln", "https://www.monitor-versorgungsforschung.de/wp-content/uploads/2023/01/MVF_01-2020_EUFH.pdf"),
 ("06/2019", "Authentizität und Spaß an der universitären Forschung", "Institut für Medizinische Soziologie", "", "https://www.monitor-versorgungsforschung.de/wp-content/uploads/2023/01/0619-17.pdf"),
 ("05/2019", "„Versorgungsforschung soll die Probleme lösen“", "Medizinische Hochschule Brandenburg", "Rüdersdorf", "https://www.monitor-versorgungsforschung.de/wp-content/uploads/2023/01/0519-Serie_MHB.pdf"),
 ("04/2019", "„Wissenschaft und Praxis stärker zusammenführen“", "Versorgungsforschung und Gesundheitsökonomische Evaluation, Bergische Universität Wuppertal", "Wuppertal", "https://www.monitor-versorgungsforschung.de/wp-content/uploads/2023/02/0419-Koeblerien-Wissenschaft.pdf"),
 ("03/2019", "„Praxisbezug, Translation und Evaluation“", "Wiesbaden Business School", "Wiesbaden", "https://www.monitor-versorgungsforschung.de/wp-content/uploads/2023/02/0319-Praxisbezug-Hartweg.pdf"),
 ("02/2019", "„Basis für evidenzbasierte Gesundheitspolitik“", "Technische Universität Berlin", "Berlin", "https://www.monitor-versorgungsforschung.de/wp-content/uploads/2023/02/0219-BUSSE-TU.pdf"),
 ("01/2019", "„Soziale Wissenschaft“ im Fokus", "Institut für Versorgungsforschung und Klinische Epidemiologie, Marburg", "Marburg", "https://www.monitor-versorgungsforschung.de/wp-content/uploads/2023/02/0119-Geraedts.pdf"),
 ("06/2018", "„Plattform für die Digitalisierung“", "Universität Bayreuth", "Bayreuth", "https://www.monitor-versorgungsforschung.de/wp-content/uploads/2023/02/0618-Digitalisierung-Digitali.pdf"),
 ("05/2018", "Primärdatenforscher aus Leidenschaft", "ISAP, Universität Leipzig", "Leipzig", "https://www.monitor-versorgungsforschung.de/wp-content/uploads/2023/02/0518Riedel-Primaerdatenforscher.pdf"),
 ("04/2018", "Den Menschen im Fokus", "Abteilung Versorgungsforschung, Universitätsklinikum Hamburg-Eppendorf", "Hamburg", "https://www.monitor-versorgungsforschung.de/wp-content/uploads/2023/02/0418Menschen-Haerter.pdf"),
 ("03/2018", "Raus aus dem Diskussionsmodus", "Institut für Qualitätssicherung und Versorgungsforschung, Regensburg", "Regensburg", "https://www.monitor-versorgungsforschung.de/wp-content/uploads/2023/02/0318Regensburg-Klinkhammer.pdf"),
 ("02/2018", "Zwei Seiten einer Medaille", "Universität Regensburg", "Regensburg", "https://www.monitor-versorgungsforschung.de/wp-content/uploads/2023/02/0218-Medaille-Apfelbacher.pdf"),
 ("01/2018", "Adhoc-Rückkopplung in die Praxis", "Institut für Versorgungsforschung in der Dermatologie IVDP, UKE", "Hamburg", "https://www.monitor-versorgungsforschung.de/wp-content/uploads/2023/02/0118-Rueckkopplung-Augustin.pdf"),
 ("06/2017", "Mehr Gehör für Patienten", "Universität Bielefeld", "Bielefeld", "https://www.monitor-versorgungsforschung.de/wp-content/uploads/2023/02/0617-Patienten-Schaeffer.pdf"),
 ("05/2017", "„Mein Interesse gilt der Langstrecke“", "Ludwig-Maximilians-Universität München", "München", "https://www.monitor-versorgungsforschung.de/wp-content/uploads/2023/01/0517-12.pdf"),
 ("04/2017", "2 Institute in enger Kooperation", "Heinrich-Heine-Universität Düsseldorf", "Düsseldorf", "https://www.monitor-versorgungsforschung.de/wp-content/uploads/2023/02/0417-Kooperation-icks.pdf"),
 ("03/2017", "Forschung mit hoher Relevanz", "Universität Oldenburg", "Oldenburg", "https://www.monitor-versorgungsforschung.de/wp-content/uploads/2023/01/0317-13.pdf"),
 ("02/2017", "Nullmeridian der „letzten Meile“", "Zentrum für Versorgungsforschung Köln, IMVR", "Köln", "https://www.monitor-versorgungsforschung.de/wp-content/uploads/2023/02/0217-IMVF-Pfaff.pdf"),
 ("06/2016", "„From bedside to practise“", "Technische Universität Dresden", "Dresden", "https://www.monitor-versorgungsforschung.de/wp-content/uploads/2023/02/0616-12.pdf"),
 ("05/2016", "Wo Daten für Taten zuhause sind", "Universität Bremen", "Bremen", "https://www.monitor-versorgungsforschung.de/wp-content/uploads/2023/02/0516-13.pdf"),
 ("02/2016", "Medizin seit 1386 – Versorgungsforschung seit 2001", "Universitätsklinikum Heidelberg", "Heidelberg", "https://www.monitor-versorgungsforschung.de/wp-content/uploads/2023/02/0216-11.pdf"),
 ("01/2016", "Neue Serie: „Versorgungsforschung inside“", "Institut für Community Medicine, Greifswald", "Greifswald", "https://www.monitor-versorgungsforschung.de/wp-content/uploads/2023/08/MVF_1-16_Greifswald.pdf"),
]

UEBERSICHT = "https://www.monitor-versorgungsforschung.de/cooperations/vf-serie/"

# Woerter, die keine Einrichtung unterscheiden.
RAUSCHEN = {
    "universitaet", "universitaets", "universitaetsklinikum", "universitaetsmedizin",
    "klinikum", "klinik", "medizinische", "medizinischen", "hochschule", "fakultaet",
    "institut", "zentrum", "abteilung", "lehrstuhl", "fuer", "und", "der", "die",
    "das", "des", "von", "zur", "zum", "versorgungsforschung", "gmbh", "ggmbh",
}


def _n(s: str) -> str:
    """Umlaute werden AUFGELOEST (ä→ae), nicht abgeworfen (ä→a).

    Das ist kein Geschmack, sondern Bedingung dafuer, dass die Rauschliste
    greift: sie steht in der ae/ue/oe-Schreibweise. Wer hier auf NFKD
    umstellt, macht aus „universitätsklinikum" ein „universitatsklinikum",
    das in keiner Rauschliste steht - und dann trifft Düsseldorf auf
    Heidelberg, weil beide das Wort „universitätsklinikum" teilen. Genau das
    hat der Gegentest in pruefe() gefangen.
    """
    s = (s or "").lower()
    s = (s.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue")
          .replace("ß", "ss"))
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


_RAUSCHEN_N = {_n(w) for w in RAUSCHEN}


def _kern(s: str) -> set[str]:
    return {w for w in _n(s).split() if w not in _RAUSCHEN_N and len(w) > 3}


def beitraege(einrichtung: str, ort: str) -> list[dict]:
    """Welche Serienbeitraege gehoeren zu diesem Standort?

    Bedingung: gleicher Ort UND mindestens ein unterscheidendes Wort gemeinsam
    - oder ein sehr deutlicher Namenstreffer (zwei gemeinsame Woerter) auch
    ohne Ortsangabe. Der Ort allein genuegt nicht: in Berlin sitzen Charité
    und TU, und beide haben einen eigenen Beitrag.
    """
    ke, ko = _kern(einrichtung), _n(ort)
    raus = []
    for ausg, titel, einr, sort, link in SERIE:
        ks, so = _kern(einr), _n(sort)
        # Der Ortsname steckt oft im Einrichtungsnamen („Universität
        # Duisburg-Essen"). Als gemeinsames Wort taugt er nicht: sonst trifft
        # das Elisabeth-Krankenhaus Essen auf das CINCH in Essen. Beide
        # Ortsnamen fliegen deshalb aus dem Vergleich.
        ortswoerter = set(ko.split()) | set(so.split())
        gemeinsam = (ke & ks) - ortswoerter

        # Drei Wege zu einem Treffer, vom staerksten zum schwaechsten.
        ne, ns = _n(einrichtung), _n(einr)
        gleich = bool(ne) and bool(ns) and (ne == ns or
                                            (len(ne) > 14 and ne in ns) or
                                            (len(ns) > 14 and ns in ne))
        if gleich:
            grund = "gleicher Name"
        elif len(gemeinsam) >= 2:
            grund = "zwei gemeinsame Kennwörter"
        elif so and ko and so == ko and gemeinsam:
            grund = "gleicher Ort und ein Kennwort"
        else:
            continue
        raus.append({"ausgabe": ausg, "titel": titel, "einrichtung": einr,
                     "link": link, "grund": grund})
    return raus


def pruefe() -> None:
    """Gegentest: richtige Zuordnung muss treffen, falsche nicht."""
    faelle = [
        ("Universitätsklinikum Heidelberg", "Heidelberg", True),
        ("Medizinische Hochschule Hannover", "Hannover", True),
        ("Universitätsklinikum Erlangen", "Erlangen", True),
        # gleicher Ort, anderes Haus - darf NICHT treffen
        ("Universitätsklinikum Charité", "Bayreuth", False),
        ("Universitätsklinikum Düsseldorf", "Heidelberg", False),
        ("Praxis Dr. Meier", "Hannover", False),
        ("Klinikum Wolkenkuckucksheim", "Wolkenheim", False),
        # Ortsname als vermeintlich unterscheidendes Wort: das
        # Elisabeth-Krankenhaus Essen traf das CINCH der Universität
        # Duisburg-Essen, weil beide das Wort „essen" enthalten.
        ("Elisabeth-Krankenhaus Essen", "Essen", False),
        ("St. Josef-Hospital Bochum", "Bochum", False),
    ]
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(f"VF-Serie: {len(SERIE)} Beiträge\n")
    ok = True
    for einr, ort, erwartet in faelle:
        t = beitraege(einr, ort)
        if bool(t) != erwartet:
            ok = False
        print(f"  {'ok  ' if bool(t) == erwartet else 'FEHL'}  {einr[:40]:<42}"
              f"{ort:<14}{len(t)} Treffer"
              + (f"  → {t[0]['ausgabe']}" if t else ""))
    print("\n  Gegentest bestanden." if ok else "\n  GEGENTEST FEHLGESCHLAGEN.")


if __name__ == "__main__":
    pruefe()
