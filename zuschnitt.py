# -*- coding: utf-8 -*-
"""Die Regeln: Was ist Versorgungsforschung, und zu welchem Hub gehoert es?

Beides sind **Heuristiken**, keine Messungen. Sie stehen hier in einer eigenen
Datei, damit die Landkarte offenlegen kann, womit sie zugeordnet hat - genau
wie `kandidaten/_liesmich.md` festhaelt, dass eine Trefferzahl ohne die
Abfrage wertlos ist.

Zwei getrennte Fragen:

1. **VF-Bezug.** Das DRKS-Feld `studyCharacteristic.type` kennt nur
   INTERVENTIONAL und NON_INTERVENTIONAL. Nicht-interventionell ist NICHT
   dasselbe wie Versorgungsforschung: eine Biomarker-Kohorte ist
   nicht-interventionell und keine Versorgungsforschung, eine
   cluster-randomisierte Hausarztstudie ist interventionell und
   Versorgungsforschung. Deshalb wird auf Titel und Zusammenfassung ein
   Punktwert gebildet. Ab VF_SCHWELLE Punkten gilt eine Studie als
   versorgungsnah.

2. **Hub-Zuordnung.** Primaer ueber die ICD-10-Codes des Datensatzes - die
   sind vergeben und nicht geraten. Nur wo kein Code greift (oder der Hub
   kein Krankheitsbild ist, wie KI oder Patientensicherheit), ueber
   Stichwoerter.
"""
from __future__ import annotations

import re

# ----------------------------------------------------------------- 1. VF-Bezug
# Gewichte: 2 = eindeutig Versorgungsforschung, 1 = Indiz.
VF_BEGRIFFE: list[tuple[int, str]] = [
    (3, r"versorgungsforschung|health services research"),
    (3, r"routinedaten|abrechnungsdaten|claims data|sekund[äa]rdaten"),
    (3, r"regelversorgung|versorgungsqualit|versorgungsforsch"),
    (2, r"\bregister\b|registerstudie|registry"),
    (2, r"leitlinien(treue|adh[äa]renz|konformit)|guideline adherence"),
    (2, r"inanspruchnahme|utilisation|utilization"),
    (2, r"sektoren[üu]bergreifend|schnittstelle|[üu]berleitung|entlassmanagement"),
    (2, r"kosten(effektivit|nutzen|analyse)|gesundheits[öo]konom|cost-effectiveness"),
    (2, r"hausarzt|haus[äa]rztlich|prim[äa]rversorgung|primary care|general practice"),
    (2, r"pflegeheim|langzeitpflege|nursing home|pflegebed[üu]rftig"),
    (2, r"versorgungspfad|behandlungspfad|disease management|dmp\b"),
    (2, r"patient reported outcome|\bprom\b|\bproms\b|patientenberichtet"),
    (2, r"shared decision|partizipative entscheid|entscheidungshilfe"),
    (2, r"implementierung|implementation (science|research)|prozessevaluation"),
    (2, r"versorgungsl[üu]cke|unterversorgung|[üu]berversorgung|fehlversorgung"),
    (1, r"cluster-?randomisiert|cluster.{0,3}randomi"),
    (1, r"screening(programm|teilnahme)|teilnahmerate"),
    (1, r"wartezeit|zugang zur|access to care|erreichbarkeit"),
    (1, r"schulung|fortbildung der|training von|qualifizierung"),
    (1, r"lebensqualit[äa]t|quality of life"),
    (1, r"telemedizin|telehealth|telekonsil"),
    (1, r"krankenkasse|gkv\b|erstattung|verg[üu]tung|reimbursement"),
    (1, r"multiprofessionell|interprofessionell|delegation|substitution"),
    (1, r"qualitativ(e|en) (studie|interview|erhebung)|fokusgruppe|grounded theory"),
    (1, r"befragung|survey|fragebogenstudie"),
]
VF_SCHWELLE = 3

# ----------------------------------------------------------------- 2. Hubs
# ICD-10-Praefixe. Reihenfolge zaehlt: die erste passende Regel gewinnt,
# damit Spezialfaelle vor Oberbegriffen stehen (F00-F03 vor F).
ICD_REGELN: list[tuple[str, list[str]]] = [
    ("longevity", ["F00", "F01", "F02", "F03", "G30", "R54"]),
    ("diabetes", ["E10", "E11", "E12", "E13", "E14", "O24"]),
    ("adipositas", ["E65", "E66", "E67", "E68"]),
    ("onkologie", ["C"] + [f"D{n:02d}" for n in range(0, 49)]),
    ("kardio", ["I"]),
    ("mental", ["F"]),
    ("impfen", ["A", "B", "U07", "U08", "U09", "Z25", "Z26", "Z27"]),
    ("ncd", ["J40", "J41", "J42", "J43", "J44", "J45", "J46", "J47",
             "N18", "N19", "K70", "K71", "K72", "K73", "K74", "K75", "K76", "K77",
             "E78", "M05", "M06", "M15", "M16", "M17", "M18", "M19", "M80", "M81"]),
    ("pflege", ["Z74", "Z75", "R26", "W19"]),
]

# Stichwoerter fuer die Hubs, die kein Krankheitsbild sind - und als
# Rueckfallebene fuer Datensaetze ohne ICD-Code.
WORT_REGELN: dict[str, str] = {
    "ki": r"k[üu]nstliche intelligenz|\bki-|machine learning|deep learning|algorithmus|"
          r"digitale? (anwendung|gesundheits)|\bapp\b|smartphone|wearable|telemedizin|"
          r"telehealth|artificial intelligence|digital health|diga\b",
    "safety": r"patientensicherheit|patient safety|medikationsfehler|unerw[üu]nschte "
              r"(arzneimittel)?(ereignis|wirkung)|sturzpr[äa]vention|st[üu]rze|delir|"
              r"h[äa]ndehygiene|krankenhausinfektion|nosokomial|behandlungsfehler|"
              r"critical incident|arzneimitteltherapiesicherheit",
    "healthliteracy": r"gesundheitskompetenz|health literacy|patientenschulung|"
                      r"patienteninformation|entscheidungshilfe|decision aid|"
                      r"verst[äa]ndlichkeit|aufkl[äa]rung[s]?(gespr|material)",
    "gender": r"geschlechtsspezifisch|geschlechterunterschied|gendermedizin|"
              r"sex differences|gender differences|frauengesundheit|m[äa]nnergesundheit|"
              r"schwangere|schwangerschaft|transgender|divers",
    "klima": r"klimawandel|hitzewelle|hitzeperiode|luftqualit[äa]t|feinstaub|"
             r"umweltbelastung|climate change|heat wave|air pollution|nachhaltigkeit",
    "pflege": r"pflegende angeh[öo]rige|pflegeheim|pflegekr[äa]fte|langzeitpflege|"
              r"ambulante pflege|pflegebed[üu]rftig|nursing home|caregiver",
    "longevity": r"geriatrisch|hochaltrig|frailty|gebrechlichkeit|polypharmazie|"
             r"[äa]ltere menschen|older adults|demenz|alzheimer|gesundes altern",
    "impfen": r"impf|vakzin|vaccin|immunisierung|durchimpfung",
    "wissen": r"versorgungsforschung|routinedaten|regelversorgung|sektoren[üu]bergreifend|"
              r"health services research|versorgungsqualit",
    "onkologie": r"\bkrebs\b|karzinom|tumor|onkolog|chemotherapie|melanom|leuk[äa]mie",
    "kardio": r"herzinsuffizienz|myokardinfarkt|vorhofflimmern|schlaganfall|stroke|"
              r"koronar|hypertonie|bluthochdruck|kardiolog",
    "ncd": r"\bcopd\b|asthma|chronisch obstruktiv|niereninsuffizienz|dialyse|"
           r"leberzirrhose|arthrose|osteoporose|rheumatoid",
    "mental": r"depress|angstst[öo]rung|schizophren|psychotherap|psychiatrisch|"
              r"psychische (gesundheit|erkrankung|belastung)|suizid|burnout|sucht|"
              r"abh[äa]ngigkeit|alkohol",
    "diabetes": r"diabetes|diabetisch|blutzucker|hba1c|insulin",
    "adipositas": r"adipositas|[üu]bergewicht|obesity|bariatr|gewichtsreduktion|bmi\b",
}

HUB_NAMEN = {
    "adipositas": ("Adipositas", "https://adipositas.m-vf.de"),
    "diabetes": ("Diabetes", "https://diabetes.m-vf.de"),
    "gender": ("Geschlechtersensible Medizin", "https://gender.m-vf.de"),
    "healthliteracy": ("Gesundheitskompetenz", "https://healthliteracy.m-vf.de"),
    "impfen": ("Impfen & Prävention", "https://impfen.m-vf.de"),
    "kardio": ("Kardiologie", "https://kardio.m-vf.de"),
    "ki": ("Digitalisierung, KI & Gesundheit", "https://ki.m-vf.de"),
    "klima": ("Klima & Gesundheit", "https://klima.m-vf.de"),
    "longevity": ("Gesundes Altern & Longevity", "https://longevity.m-vf.de"),
    "mental": ("Psychische Gesundheit", "https://mental.m-vf.de"),
    "ncd": ("NCD / Chronische Krankheiten", "https://ncd.m-vf.de"),
    "onkologie": ("Onkologie", "https://onkologie.m-vf.de"),
    "pflege": ("Pflege & Langzeitversorgung", "https://pflege.m-vf.de"),
    "safety": ("Patientensicherheit", "https://safety.m-vf.de"),
    "wissen": ("Versorgungsforschung", "https://wissen.m-vf.de"),
}

_VF_RE = [(g, re.compile(m, re.I)) for g, m in VF_BEGRIFFE]
_WORT_RE = {h: re.compile(m, re.I) for h, m in WORT_REGELN.items()}


def vf_punkte(text: str) -> tuple[int, list[str]]:
    """Punktwert und die Begriffe, die ihn ausgeloest haben."""
    p, treffer = 0, []
    for gewicht, rx in _VF_RE:
        m = rx.search(text)
        if m:
            p += gewicht
            treffer.append(m.group(0).lower())
    return p, treffer


def hubs_fuer(text: str, icd_codes: list[str]) -> tuple[list[str], str]:
    """Hub-Kuerzel plus die Angabe, woraus zugeordnet wurde."""
    aus_icd: list[str] = []
    for hub, praefixe in ICD_REGELN:
        for c in icd_codes:
            c = (c or "").upper().replace(".", "")
            if any(c.startswith(p) for p in praefixe):
                if hub not in aus_icd:
                    aus_icd.append(hub)
                break
    aus_wort = [h for h, rx in _WORT_RE.items() if rx.search(text)]
    alle = aus_icd + [h for h in aus_wort if h not in aus_icd]
    if aus_icd and aus_wort:
        quelle = "ICD-10 und Stichwort"
    elif aus_icd:
        quelle = "ICD-10"
    elif aus_wort:
        quelle = "Stichwort"
    else:
        quelle = "keine Zuordnung"
    return alle, quelle


# ------------------------------------------------- 3. Redaktion, nicht Forschung
#
# Peter Stegmaier am 02.11.2026: „Das sind rein redaktionelle Beitraege,
# keine wissenschaftlichen. die verzerren hier alles."
#
# Die Forschendenliste sortiert nach Belegen. Ganz oben standen damit drei
# Menschen aus der Redaktion, weil sie seit Jahren jedes Heft mit
# Nachrichten, Interviews und Editorials fuellen:
#
#     Peter Stegmaier    326 MVF-Beitraege, 0 Studien, 0 DKVF
#     Reinhold Roski      43 MVF-Beitraege, 0 Studien, 0 DKVF
#     Kathrin Pieloth     39 MVF-Beitraege, 0 Studien, 0 DKVF
#
# ⚠ DAS IST KEINE WERTUNG UEBER MENSCHEN, SONDERN UEBER DIE EINHEIT. Ein
# redaktioneller Beitrag ist kein Forschungsbeleg, und eine Liste, die
# beides zusammenzaehlt, misst nicht, was sie zu messen behauptet.
#
# ⚠ WARUM NICHT UEBER DIE RUBRIK. Sauberer waere, redaktionelle Rubriken
# auszunehmen statt Personen. Das geht nicht: Von den 1.528 Datensaetzen
# der WordPress-Schnittstelle tragen 1.507 KEINE Rubrik (gemessen
# 02.11.2026). Eine Regel auf ein Feld zu bauen, das in 99 Prozent der
# Faelle leer ist, waere eine Regel, die nie greift.
#
# Diese Liste ist deshalb von Hand gepflegt und bewusst kurz. Wer sie
# erweitert, traegt den Grund daneben ein. Der Schluessel ist derselbe
# wie ueberall: norm(nachname) + ", " + erster Vorname.
REDAKTION = {
    "stegmaier, peter":  "Chefredakteur und Verleger",
    "roski, reinhold":   "Herausgeber",
    "pieloth, kathrin":  "Redaktion",
    "gilbers, olga":     "Redakteurin bei MVF (Peter, 02.11.2026)",
}


def ist_redaktion(schluessel: str) -> bool:
    """Gehoert dieser Personenschluessel zur Redaktion?"""
    return (schluessel or "").strip().lower() in REDAKTION


# ---------------------------------------- 4. Einrichtung, von Hand gesetzt
#
# Peter am 02.11.2026 zu Ursula Marschall: „warum steht keine Affiliation
# bei ihr? Dr. Ursula Marschall ist Forschungsbereichsleiterin des Barmer
# Instituts für Gesundheitssystemforschung."
#
# Der Grund: Ihr Institut steht im ZWEITEN Satz ihres Vorstellungstextes
# („Seit 2007 führt sie ... im BARMER Institut für
# Gesundheitssystemforschung"). Der automatische Schnitt liest nur den
# ersten Satzteil, damit niemand an seinen vorletzten Arbeitgeber
# gehängt wird.
#
# ⚠ DIE REGEL WURDE NICHT GELOCKERT, UND DAS MIT ABSICHT. Gemessen am
# 02.11.2026: Den zweiten Satz mitzulesen brächte 117 Einrichtungen
# dazu, aber etwa die Hälfte davon falsch - „Medic Center" aus einem
# Satz über ein Studium in Wien, „Danone Deutschland" aus einem Satz
# über ökonomische Schwerpunkte, „USA und Japan" als Einrichtung. Selbst
# eine enge Fassung, die nur Sätze ab „Seit 2007" liest, liefert bei
# Marschall „Forschungsbereich Medizin" statt „BARMER Institut" und
# anderswo „Preisstrategien und Nutzenbewertungsverfahren".
#
# Eine falsche Einrichtung unter einem Namen ist schlechter als keine.
# Deshalb hier eine kurze Liste von Hand, die den automatischen Schnitt
# STICHT - so wie es die 84 gepflegten Interviewpaare auch tun.
#
# ⚠ DIESE LISTE IST KEIN ERSATZ FÜR DAS FORMULAR. Wer sich selbst
# einträgt, hat immer recht. Hier stehen nur Fälle, die uns aufgefallen
# sind, bevor die Betroffenen es konnten.
EINRICHTUNG_VON_HAND = {
    "marschall, ursula": "BARMER Institut für Gesundheitssystemforschung",
}
