# -*- coding: utf-8 -*-
"""Alle Einrichtungen des Registers, nach Traegerart getrennt.

WARUM GETRENNT
--------------
Die 63 Forschungsstandorte mit Profilseite sind zu 51 Hochschulen. Das ist
kein Filter, sondern ein Registerabbild: Von 699 Einrichtungen im Register
sind 510 Hochschule oder Universitaetsmedizin, und ausseruniversitaere
Forschungseinrichtungen sind NEUN.

Peter Stegmaier hat am 01.11.2026 darauf hingewiesen, dass damit ein
ganzer Teil des Fachs fehlt: Zi, IGES, inav, fb+eta und viele andere sind
Forschungseinrichtungen anderer Struktur. Seine Anweisung: darstellen,
aber abgegrenzt von den Hochschulen.

DER BEFUND DAHINTER, gemessen
-----------------------------
Diese Institute registrieren praktisch nicht. Nicht weil sie nicht
forschen, sondern weil ihre Arbeit keine klinische Studie ist:
Sekundaerdatenforschung, Evaluation, Routinedatenanalyse. Das kommt nie
ins DRKS.

    IGES        0 Studien im Register, 16 MVF-Beitraege nennen es
    Prognos     0 und 10
    OptiMedis   0 und  4
    WIdO        0 und  1
    IQTIG       0 und  1
    Zi          4 und  0
    inav        1 und  0

Das Register kann sie strukturell nicht sehen. Darum bekommt die Seite
einen Abschnitt, der das sagt und sie einlaedt, denn von allein koennen
sie nie auftauchen.

WIE DER LETZTE ABSCHNITT ENTSTEHT
---------------------------------
NICHT aus einer Liste, die ich mir ausdenke. Sondern gemessen: Die
Autorenboxen der MVF-Beitraege nennen Mailbereiche, und ein Mailbereich
gehoert genau einem Haus. Jeder Bereich, zu dem im Register keine Studie
steht, ist ein Haus, das bei uns publiziert und im Register fehlt. Das
waechst mit jedem Heft von allein mit.

⚠ EIN MAILBEREICH IST KEIN EINRICHTUNGSNAME
„wido.bv.aok.de“ ist nicht „Wissenschaftliches Institut der AOK“. Die
Uebersetzung steht in BEREICH_HAUS und ist Handarbeit, bewusst. Was dort
nicht steht, wird als Bereich gezeigt, nicht erfunden.

  py einrichtungen.py              baut daten/einrichtungen.json
  py einrichtungen.py --gegentest  prueft ohne Netz
"""
import collections
import json
import pathlib
import re
import sys
import time
import unicodedata

HIER = pathlib.Path(__file__).parent
DATEN = HIER / "daten"
sys.path.insert(0, str(HIER))

# Der geprueffte Kopfwort-Waechter. Nicht nachbauen: Er kennt fuenf Klassen
# Rauschen (Bundesland, Koerperschaftsform, Fachgebiet, Hochschulart,
# Allgemeinwoerter), und ohne die matcht jede Namensauflösung auf Ortsnamen.
try:
    from repositorien import kopfwort
except Exception:                       # pragma: no cover
    def kopfwort(name):
        return None

# Reihenfolge der Abschnitte. Hochschulen zuerst, dann klar abgesetzt die
# anderen Traeger. Die Schluessel sind die Werte aus traegerart.json.
ORDNUNG = [
    ("Hochschule und Universitaetsmedizin",
     "Hochschulen und Universitätsmedizin",
     "Universitäten, Universitätskliniken, medizinische Fakultäten und "
     "Fachhochschulen. Sie stellen die große Mehrheit der Einträge im "
     "Register."),
    ("Ausseruniversitaere Forschungseinrichtung",
     "Außeruniversitäre Forschungseinrichtungen",
     "Institute, die selbst forschen, aber keiner Hochschule angehören. "
     "Im Register sind sie auffällig wenige, und der Abschnitt ganz unten "
     "erklärt, warum."),
    ("Ressortforschung des Bundes",
     "Ressortforschung des Bundes",
     "Einrichtungen, die für ein Bundesministerium forschen, etwa das "
     "Robert Koch-Institut."),
    ("Kostentraeger",
     "Kostenträger",
     "Krankenkassen und Versicherungen. Sie führen eigene Studien, meist "
     "zu Versorgungsmodellen und Selektivverträgen."),
    ("Selbstverwaltung im Gesundheitswesen",
     "Selbstverwaltung im Gesundheitswesen",
     "Kassenärztliche Vereinigungen, Kammern und die Einrichtungen der "
     "gemeinsamen Selbstverwaltung."),
    ("Krankenhaus oder Praxis",
     "Krankenhäuser und Praxen",
     "Häuser und Praxen in anderer Trägerschaft als einer Hochschule."),
    ("Kommunaler oder kirchlicher Traeger",
     "Kommunale und kirchliche Träger",
     "Gesundheitsämter, kommunale Kliniken und Einrichtungen in "
     "kirchlicher Trägerschaft."),
    ("Gemeinnuetziger Traeger",
     "Gemeinnützige Träger",
     "Vereine, Wohlfahrtsverbände und gemeinnützige Gesellschaften."),
    ("Fachgesellschaft, Verband oder Stiftung",
     "Fachgesellschaften, Verbände und Stiftungen",
     "Wissenschaftliche Fachgesellschaften, Berufsverbände und Stiftungen."),
    ("Unternehmen",
     "Unternehmen",
     "Gesellschaften, die Studien als Sponsor führen, von Herstellern bis "
     "zu Anbietern digitaler Anwendungen."),
    ("nicht zuzuordnen",
     "Nicht zuzuordnen",
     "Hier steht, was der Name allein nicht hergibt. Oft sind es "
     "Abteilungsnamen ohne ihr Haus, etwa Augenklinik oder Institut für "
     "Allgemeinmedizin. Wir raten nicht, welches Haus gemeint ist."),
]

# Mailbereich zu Einrichtungsname. Handarbeit, und das ist Absicht: Ein
# Bereich laesst sich nicht aus sich selbst uebersetzen. Was hier fehlt,
# wird als Bereich gezeigt.
BEREICH_HAUS = {
    "iges.com": "IGES Institut",
    "wido.bv.aok.de": "Wissenschaftliches Institut der AOK (WIdO)",
    "zi.de": "Zentralinstitut für die kassenärztliche Versorgung (Zi)",
    "iqvia.com": "IQVIA",
    "optimedis.de": "OptiMedis AG",
    "prognos.com": "Prognos AG",
    "iqtig.org": "IQTIG",
    "aqua-institut.de": "aQua Institut",
    "inav-berlin.de": "inav, privates Institut für angewandte "
                      "Versorgungsforschung",
    "igv-research.com": "IGV Research",
    "zi-mannheim.de": "Zentralinstitut für Seelische Gesundheit Mannheim",
    "wip-pkv.de": "Wissenschaftliches Institut der PKV (WIP)",
    "gesundheitsforen.net": "Gesundheitsforen Leipzig",
    "iqwig.de": "IQWiG",
    "bertelsmann-stiftung.de": "Bertelsmann Stiftung",
    "rki.de": "Robert Koch-Institut",
    "dkfz.de": "Deutsches Krebsforschungszentrum (DKFZ)",
    "fbeta.de": "fb+eta, Forschung Beratung Evaluation",
    "vitis-healthcare.com": "Vitis Healthcare",
    # Hochschulen, deren Mailbereich ein blosses Kuerzel ist. Das Muster
    # HOCHSCHUL_BEREICH kann die nicht erkennen, denn „tum" sieht aus wie
    # ein Firmenname. Hier benannt, damit der Abgleich sie als bekannt
    # erkennt und nicht behauptet, sie fehlten im Register.
    "tum.de": "Technische Universität München",
    "fom.de": "FOM Hochschule für Oekonomie und Management",
    "hhu.de": "Heinrich-Heine-Universität Düsseldorf",
    "kit.edu": "Karlsruher Institut für Technologie",
    "uol.de": "Carl von Ossietzky Universität Oldenburg",
    "zhaw.ch": "Zürcher Hochschule für Angewandte Wissenschaften",
    "iges.de": "IGES Institut",
    "de.imshealth.com": "IQVIA",
    "bkk-dv.de": "BKK Dachverband",
    "hertie-school.org": "Hertie School",
    "takeda.com": "Takeda",
    "novonordisk.com": "Novo Nordisk",
    "diakonie-sw.de": "Diakonie Südwestfalen",
}

# Mailbereiche aus dem Ausland. Sie koennen im DEUTSCHEN Studienregister
# nicht fehlen, weil sie dort nicht hingehoeren. Sie in der Fehlliste zu
# fuehren waere ein Denkfehler.
AUSLAND = re.compile(r"\.(at|ch|nl|be|dk|se|no|fi|uk|fr|it|es|pl|cz|lu|li)$")

# Bereiche, die keine Forschungseinrichtung sind. Sie sollen den letzten
# Abschnitt nicht zumuellen.
BEREICH_RAUS = {
    "m-vf.de", "monitor-versorgungsforschung.de", "erelation.org",
    "bundestag.de", "bmg.bund.de", "g-ba.de",
}


# Vierte Stufe der Einordnung, nach traegerart.json und dem Partnernetz.
#
# WARUM SIE GEBRAUCHT WIRD
# Von 1.513 Registernamen kennt traegerart.json 562 und das Partnernetz
# weitere 43. 881 blieben ohne Art, und damit landeten 1.185 Einrichtungen
# unter „nicht zuzuordnen" samt 1.082 Studien. Eine Seite, die zwei Drittel
# ihrer Einrichtungen nicht einordnen kann, ordnet nichts ein.
#
# Gemessen am 01.11.2026: Diese Regeln ordnen 675 der 881 ein. Die 206,
# die offen bleiben, sind wirklich offen: Seniorenzentren,
# Selbsthilfegruppen, eine Schule, das blosse Kuerzel „LMU" und
# „17 Einrichtungen vollstationaere Langzeitpflege". Die bleiben stehen,
# wo sie stehen. Wir raten nicht, siehe die Hausregel „wir werten nicht".
#
# ⚠ DIE REIHENFOLGE IST DIE REGEL
# „Universitaetsklinikum Bonn" traegt „universit" UND „klinikum". Die
# Hochschulzeile steht zuerst, also gilt sie. Umgekehrt waere das Haus
# ein Krankenhaus ohne Hochschule.
REGEL = [
    ("Hochschule und Universitaetsmedizin",
     r"universit|uniklinik|charite|hochschule|medizinische fakultaet"
     r"|\bmhh\b|technische universitaet|medizinische universitaet"),
    ("Ressortforschung des Bundes",
     r"robert koch|bundesinstitut|bundesamt|bundeszentrale|\bbzga\b"
     r"|paul ehrlich"),
    ("Kostentraeger",
     r"krankenkasse|\baok\b|barmer|techniker krankenkasse|\bdak\b"
     r"|\bikk\b|\bbkk\b|\bkkh\b|gesundheitskasse|knappschaft|versicherung"),
    ("Selbstverwaltung im Gesundheitswesen",
     r"kassenaerztliche|kassenzahnaerztliche|aerztekammer"
     r"|zahnaerztekammer|pflegekammer|psychotherapeutenkammer"),
    ("Ausseruniversitaere Forschungseinrichtung",
     r"leibniz|fraunhofer|max planck|helmholtz|dkfz|krebsforschungszentrum"
     r"|zentralinstitut|forschungsinstitut|forschungszentrum"),
    ("Kommunaler oder kirchlicher Traeger",
     r"gesundheitsamt|landkreis|caritas|diakonie|evangelisch|katholisch"
     r"|bezirksklinik|bezirkskrankenhaus"),
    ("Gemeinnuetziger Traeger",
     r"gemeinnuetzig|ggmbh|lebenshilfe|\bawo\b|wohlfahrt|rotes kreuz"
     r"|malteser|johanniter|paritaetische"),
    ("Krankenhaus oder Praxis",
     r"klinikum|klinik|krankenhaus|hospital|praxis|\bmvz\b|aerztenetz"
     r"|praxisnetz|rehazentrum|sanatorium"),
    ("Fachgesellschaft, Verband oder Stiftung",
     r"gesellschaft fuer|fachgesellschaft|\be\.? ?v\.?\b|verband"
     r"|bundesverband|stiftung|\bliga\b|akademie"),
    ("Unternehmen",
     r"gmbh|\bag\b|\bse\b|\bkg\b|\bmbh\b|\bltd\b|\binc\b|pharma|\bgbr\b"),
]

# Mailbereiche, die eine Hochschule oder ein Universitaetsklinikum
# bezeichnen. Sie gehoeren NICHT in die Liste der im Register fehlenden
# Haeuser, denn dort stehen sie unter ihrem ausgeschriebenen Namen.
#
# ⚠ DER FEHLER, DEN DAS BEHEBT
# Mein erster Lauf nannte „uni-bremen.de" und „ukbonn.de" als Haeuser, die
# im Register fehlen. Beide stehen dort, nur ausgeschrieben. Der Abgleich
# ueber den Kern des Mailbereichs scheitert, weil „uni bremen" nicht
# „universitaet bremen" ist. Ueber den ORT abzugleichen waere der naechste
# Fehler, das matcht alles in derselben Stadt.
# ⚠ „uk" DARF OHNE TRENNSTRICH STEHEN: ukbonn.de, ukw.de, ukgm.de. Das
# Muster laesst darum „uk" plus Stadtkuerzel gelten. Es trifft damit auch
# gelegentlich ein Haus, das keine Klinik ist, und das ist die SICHERE
# Richtung des Irrtums: Ein zu viel verworfener Bereich fehlt in der
# Liste, ein zu wenig verworfener behauptet fälschlich, eine Universität
# fehle im Register.
HOCHSCHUL_BEREICH = re.compile(
    r"^(uni|uk|med|klinik|klinikum|charite|hs|th|fh|tu|rwth|lmu|mhh"
    r"|smhh|evkb|ukgm)[\-.]"
    r"|^uk[a-z]{0,14}\."
    r"|(^|\.)(uni|uk|klinik|klinikum|charite|hochschule|campus"
    r"|medizin|medschool|med)\."
    r"|(uni|klinik|klinikum|hochschule|charite|universitaet|university"
    r"|hospital|fakultaet|faculty)")


def art_aus_regel(name):
    """Die Traegerart allein aus dem Namen, als letzte Stufe.

    Gibt None, wenn keine Regel greift. Das ist der richtige Ausgang: Ein
    Seniorenzentrum ist keine Forschungseinrichtung, und es zu einer zu
    machen, waere schlimmer als es offen zu lassen.
    """
    k = norm(name)
    if not k:
        return None
    for art, muster in REGEL:
        if re.search(muster, k):
            return art
    return None


def norm(s):
    s = (s or "").lower()
    for a, b in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")):
        s = s.replace(a, b)
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return " ".join(s.replace("-", " ").split())


def lade(name):
    p = DATEN / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def ist_bruchstueck(name):
    """Ein Abteilungsname ohne sein Haus.

    „Augenklinik“ und „Institut fuer Allgemeinmedizin“ nennen eine
    Abteilung, nicht eine Einrichtung. Sie gehoeren zu einem Haus, aber zu
    welchem, sagt der Name nicht, und mehrere Haeuser teilen denselben
    Abteilungsnamen. Wir raten nicht.
    """
    n = norm(name)
    if not n:
        return True
    # Kein Eigenname darin: kein Ort, keine Marke, nur Gattungswoerter.
    GATTUNG = {
        "klinik", "kliniken", "klinikum", "institut", "institute", "zentrum",
        "abteilung", "praxis", "ambulanz", "poliklinik", "fuer", "und", "der",
        "des", "die", "das", "allgemeinmedizin", "augenklinik", "sektion",
        "arbeitsbereich", "lehrstuhl", "professur", "medizin", "chirurgie",
        "innere", "kinder", "jugendmedizin", "psychiatrie", "psychotherapie",
        "neurologie", "palliativmedizin", "anaesthesiologie", "intensivmedizin",
        "sozialmedizin", "epidemiologie", "pflege", "versorgungsforschung",
        "gesundheitsoekonomie", "hauttumorzentrum", "sozialpaediatrisches",
        "geriatrie", "onkologie", "haematologie", "kardiologie", "zahn",
        "mund", "kieferheilkunde", "radiologie", "urologie", "gynaekologie",
        "orthopaedie", "unfallchirurgie", "dermatologie", "hno", "forschung",
        "wissenschaft", "ethik", "public", "health", "zahnerhaltung",
    }
    worte = set(n.split())
    return not (worte - GATTUNG)


# Das Partnernetz des Innovationsfonds-Radars. 1.051 Einrichtungen mit
# eigener Typangabe. Nur LESEN, die Datei gehoert der Innofonds-Sitzung.
PARTNERNETZ = (HIER.parent / "innovationsfonds" / "out" / "partnernetz.json")

# Die Typen des Partnernetzes auf unsere Abschnitte abbilden.
TYP_ZU_ART = {
    "Universität / Hochschule": "Hochschule und Universitaetsmedizin",
    "Universitätsklinikum": "Hochschule und Universitaetsmedizin",
    "Forschungsinstitut": "Ausseruniversitaere Forschungseinrichtung",
    "Forschung": "Ausseruniversitaere Forschungseinrichtung",
    "Krankenkasse / Kostenträger": "Kostentraeger",
    "Kassenärztliche Vereinigung": "Selbstverwaltung im Gesundheitswesen",
    "Kammer": "Selbstverwaltung im Gesundheitswesen",
    "Krankenhaus / Klinik": "Krankenhaus oder Praxis",
    "Öffentliche Verwaltung": "Kommunaler oder kirchlicher Traeger",
    "Pflege / Wohlfahrt": "Gemeinnuetziger Traeger",
    "Verband / Fachgesellschaft": "Fachgesellschaft, Verband oder Stiftung",
    "Unternehmen": "Unternehmen",
    "Sonstige": "nicht zuzuordnen",
}


def aus_innofonds():
    """Die Einrichtungen des Innovationsfonds-Partnernetzes.

    WARUM DIESE ZWEITE QUELLE UNVERZICHTBAR IST
    Das Studienregister kennt NEUN ausseruniversitaere
    Forschungseinrichtungen. Das Partnernetz kennt 86. Gemessen am
    01.11.2026:

        aQua         0 Studien im Register, 48 Innovationsfonds-Projekte
        WIdO         0 und 27
        Zi           4 und 25
        inav         1 und 23

    aQua fuehrt 48 Projekte und steht im Register mit null. Wer nur das
    Register zeigt, zeigt das Fach nicht, sondern nur den Teil, der
    klinische Studien registriert.
    """
    if not PARTNERNETZ.exists():
        return {}
    d = json.loads(PARTNERNETZ.read_text(encoding="utf-8"))
    raus = {}
    for k in d.get("knoten", []):
        name = (k.get("name") or "").strip()
        if not name:
            continue
        raus[name] = {
            "name": name,
            "art": TYP_ZU_ART.get(k.get("typ") or "", "nicht zuzuordnen"),
            "typ_innofonds": k.get("typ") or "",
            "ort": k.get("ort") or "",
            "bundesland": k.get("bundesland") or "",
            "ror": k.get("ror") or "",
            "projekte": k.get("projekte") or 0,
            "projekte_leitung": k.get("projekte_leitung") or 0,
            "partner": k.get("grad") or 0,
        }
    return raus


def bauen():
    L = lade("landkarte.json") or {}
    studien = L.get("studien", [])
    TA = (lade("traegerart.json") or {}).get("je_einrichtung", {})
    SV = (lade("standorte.json") or {}).get("standorte", [])

    # Profilseite je Schreibweise, damit jede Einrichtung ihre findet.
    profil = {}
    for s in SV:
        for w in [s["name"]] + (s.get("schreibweisen") or []):
            profil[norm(w)] = {"name": s["name"], "datei": s.get("datei"),
                               "ort": s.get("ort"), "studien": s.get("studien"),
                               "rekrutiert": s.get("rekrutiert")}

    # Jede Organisation im Register zaehlen, als Sponsor und als Ort.
    zahl = collections.Counter()
    rekrut = collections.Counter()
    orte = {}
    for x in studien:
        laeuft = x.get("status") == "RECRUITING"
        namen = {}
        sp = (x.get("sponsor") or {}).get("name") or ""
        if sp.strip():
            namen[sp.strip()] = ""
        for o in (x.get("orte") or []):
            n = (o.get("name") or "").strip()
            if n:
                namen[n] = (o.get("ort") or "").strip()
        for n, ort in namen.items():
            zahl[n] += 1
            if laeuft:
                rekrut[n] += 1
            if ort and n not in orte:
                orte[n] = ort

    # Nach Traegerart sortieren. Was traegerart.json nicht kennt, kommt in
    # „nicht zuzuordnen“, und Bruchstuecke ebenfalls.
    # Vier Stufen, in dieser Reihenfolge. Das Bruchstueck sticht alles:
    # Ein Abteilungsname ohne Haus laesst sich nicht einordnen, auch wenn
    # „Klinik" darin steht.
    IF_VOR = aus_innofonds()
    if_norm = {norm(n): v for n, v in IF_VOR.items()}
    nach_art = collections.defaultdict(dict)
    bruch = 0
    stufe = collections.Counter()
    for n, c in zahl.items():
        if ist_bruchstueck(n):
            art = "nicht zuzuordnen"
            bruch += 1
            stufe["Abteilungsname ohne Haus"] += 1
        elif TA.get(n):
            art = TA[n]
            stufe["traegerart.json"] += 1
        elif norm(n) in if_norm:
            art = if_norm[norm(n)]["art"]
            stufe["Innofonds-Partnernetz"] += 1
        elif art_aus_regel(n):
            art = art_aus_regel(n)
            stufe["Regel aus dem Namen"] += 1
        else:
            art = "nicht zuzuordnen"
            stufe["keine Regel greift"] += 1
        p = profil.get(norm(n))
        nach_art[art][norm(n)] = {
            "name": n, "ort": orte.get(n, "") or (p or {}).get("ort", ""),
            "studien": c, "rekrutiert": rekrut[n],
            "projekte": 0, "projekte_leitung": 0,
            "datei": (p or {}).get("datei", ""),
            "quellen": ["Studienregister"],
        }

    # Das Partnernetz dazu. Wer schon aus dem Register bekannt ist, bekommt
    # die Projektzahl angehaengt. Wer neu ist, kommt hinzu, und die Seite
    # sagt dann, dass er NUR aus dem Innovationsfonds bekannt ist.
    IF = IF_VOR
    nur_if = 0
    for name, e in IF.items():
        k = norm(name)
        art = e["art"]
        # In welchem Abschnitt steht er schon? Dort anhaengen, nicht neu.
        wo = next((a for a in nach_art if k in nach_art[a]), None)
        if wo:
            z = nach_art[wo][k]
            z["projekte"] = e["projekte"]
            z["projekte_leitung"] = e["projekte_leitung"]
            if "Innovationsfonds" not in z["quellen"]:
                z["quellen"].append("Innovationsfonds")
            if not z["ort"]:
                z["ort"] = e["ort"]
        else:
            nur_if += 1
            nach_art[art][k] = {
                "name": name, "ort": e["ort"], "studien": 0, "rekrutiert": 0,
                "projekte": e["projekte"],
                "projekte_leitung": e["projekte_leitung"],
                "datei": profil.get(k, {}).get("datei", ""),
                "quellen": ["Innovationsfonds"],
            }

    # Aus den Tabellen Listen machen, nach Gewicht sortiert. Gewicht ist
    # Studien plus Projekte: Beides ist Forschung, und eine Einrichtung mit
    # 48 Projekten und 0 Studien darf nicht hinter einer mit 1 Studie stehen.
    nach_art = {a: sorted(t.values(),
                          key=lambda e: (-(e["studien"] + e["projekte"]),
                                         norm(e["name"])))
                for a, t in nach_art.items()}

    # Der letzte Abschnitt: Haeuser, die bei MVF publizieren und im
    # Register fehlen. Gemessen ueber die Mailbereiche der Autorenboxen.
    AB = lade("mvf_autorenbox.json") or {}
    bereiche = collections.Counter()
    for b in (AB.get("beitraege") or {}).values():
        for a in (b.get("autoren") or []):
            if a.get("bereich"):
                bereiche[a["bereich"]] += 1
    bekannt = {norm(n) for n in zahl} | {norm(n) for n in IF}
    bekannte_koepfe = {k for k in (kopfwort(n) for n in
                                   list(zahl) + list(IF)) if k}
    fehlen, verworfen = [], collections.Counter()
    for ber, n in bereiche.most_common():
        if ber in BEREICH_RAUS:
            verworfen["eigenes Haus oder Behoerde"] += 1
            continue
        # ⚠ Ein Hochschul- oder Klinikbereich wird NICHT behauptet. Mein
        # erster Lauf nannte „uni-bremen.de" als fehlend, und die
        # Universitaet Bremen steht im Register, nur ausgeschrieben.
        if HOCHSCHUL_BEREICH.search(ber):
            verworfen["Hochschule oder Klinik, steht ausgeschrieben drin"] += 1
            continue
        if AUSLAND.search(ber):
            verworfen["Ausland, kann im deutschen Register nicht fehlen"] += 1
            continue
        haus = BEREICH_HAUS.get(ber, "")
        if haus:
            # ⚠ Ein Vergleich auf den GANZEN Namen ist zu streng. „Zi.de"
            # heisst „Zentralinstitut fuer die kassenaerztliche
            # Versorgung (Zi)", im Register steht „... in Deutschland".
            # Darum ueber das Kopfwort, also das erste unterscheidende
            # Wort, mit dem geprueften Waechter aus repositorien.py.
            if norm(haus) in bekannt:
                verworfen["Haus ist bekannt"] += 1
                continue
            kopf = kopfwort(haus)
            if kopf and kopf in bekannte_koepfe:
                verworfen["Haus ist bekannt"] += 1
                continue
        kern = norm(ber.split(".")[0])
        if len(kern) > 4 and any(kern in r for r in bekannt):
            verworfen["Haus ist bekannt"] += 1
            continue
        # ⚠ Mehrere Bereiche desselben Hauses zusammenfuehren. „iges.de"
        # und „iges.com" sind EIN Haus. Zweimal gefuehrt liesse die
        # Luecke doppelt so gross erscheinen, wie sie ist.
        vorher = next((f for f in fehlen if haus and f["haus"] == haus), None)
        if vorher:
            vorher["beitraege"] += n
            vorher["bereiche"].append(ber)
            continue
        fehlen.append({"bereich": ber, "bereiche": [ber], "haus": haus,
                       "beitraege": n, "benannt": bool(haus)})

    raus = {
        "stand": time.strftime("%Y-%m-%d"),
        "hinweis": ("Einrichtungen aus zwei Quellen, nach Traegerart "
                    "getrennt: dem Studienregister und dem Partnernetz des "
                    "Innovationsfonds. Jede Einrichtung nennt, aus welcher "
                    "Quelle sie bekannt ist. Abteilungsnamen ohne ihr Haus "
                    "stehen unter „nicht zuzuordnen“, wir raten das Haus "
                    "nicht."),
        "aus_register": len(zahl),
        "aus_innofonds": len(IF),
        "nur_innofonds": nur_if,
        "bruchstuecke": bruch,
        "einordnung": dict(stufe),
        "verworfene_bereiche": dict(verworfen),
        "gesamt": sum(len(a) for a in nach_art.values()),
        "mit_profil": sum(1 for a in nach_art.values() for e in a if e["datei"]),
        "abschnitte": [
            {"art": art, "titel": titel, "was": was,
             "anzahl": len(nach_art.get(art, [])),
             "studien": sum(e["studien"] for e in nach_art.get(art, [])),
             "projekte": sum(e["projekte"] for e in nach_art.get(art, [])),
             "nur_innofonds": sum(1 for e in nach_art.get(art, [])
                                  if e["quellen"] == ["Innovationsfonds"]),
             "einrichtungen": nach_art.get(art, [])}
            for art, titel, was in ORDNUNG
        ],
        "fehlen_im_register": {
            "hinweis": ("Mailbereiche aus den Autorenboxen der "
                        "MVF-Beitraege, zu denen im Register keine Studie "
                        "steht. Gemessen, nicht ausgewaehlt."),
            "geprueft_beitraege": len(AB.get("beitraege") or {}),
            "liste": sorted(fehlen,
                            key=lambda f: -f["beitraege"]),
        },
    }
    ziel = DATEN / "einrichtungen.json"
    ziel.write_text(json.dumps(raus, ensure_ascii=False, indent=1),
                    encoding="utf-8")
    return raus, ziel


def gegentest():
    ok = True
    print("Bruchstueck erkennen, also Abteilung ohne Haus:")
    for name, soll in (
            ("Augenklinik", True),
            ("Institut für Allgemeinmedizin", True),
            ("Klinik für Palliativmedizin", True),
            ("Klinik und Poliklinik für Neurologie", True),
            ("Universitätsklinikum Hamburg-Eppendorf", False),
            ("IGES Institut", False),
            ("Vivantes Klinikum im Friedrichshain", False),
            ("Institut für Allgemeinmedizin, UK Lübeck", False),
            ("LVR-Institut für Forschung und Bildung", False),
            ("Techniker Krankenkasse", False),
            ("", True)):
        ist = ist_bruchstueck(name)
        gut = ist == soll
        ok = ok and gut
        print(f"  {'ok ' if gut else 'FEHLER'} {name!r:<44} "
              f"{'Bruchstueck' if ist else 'Einrichtung'}")

    print("\nGEGENPROBE: die Regel darf nicht alles zum Bruchstueck machen:")
    echte = ["Charité - Universitätsmedizin Berlin", "IGES Institut",
             "Robert Koch-Institut", "AOK Rheinland/Hamburg",
             "Medizinische Hochschule Hannover", "OptiMedis AG",
             "Krebsregister Schleswig-Holstein", "SCO:SSiS"]
    falsch = [n for n in echte if ist_bruchstueck(n)]
    gut = not falsch
    ok = ok and gut
    print(f"  {'ok ' if gut else 'FEHLER'} 8 echte Einrichtungen bleiben "
          f"Einrichtungen. Falsch einsortiert: {falsch}")

    print("\nTraegerart allein aus dem Namen:")
    for name, soll in (
            # Die Reihenfolge der Regeln entscheidet: Hochschule sticht Klinik.
            ("Universitätsklinikum Bonn", "Hochschule und Universitaetsmedizin"),
            ("Medizinische Fakultät der Otto-von-Guericke-Universität",
             "Hochschule und Universitaetsmedizin"),
            ("Vivantes Klinikum Berlin am Urban", "Krankenhaus oder Praxis"),
            ("Techniker Krankenkasse", "Kostentraeger"),
            ("AOK Rheinland/Hamburg", "Kostentraeger"),
            ("Robert Koch-Institut", "Ressortforschung des Bundes"),
            ("Leibniz-Institut für Präventionsforschung",
             "Ausseruniversitaere Forschungseinrichtung"),
            ("Kassenärztliche Vereinigung Bayerns",
             "Selbstverwaltung im Gesundheitswesen"),
            ("Deutsche Gesellschaft für Wundheilung e. V.",
             "Fachgesellschaft, Verband oder Stiftung"),
            ("Orthopy Health GmbH", "Unternehmen"),
            ("Caritas-Krankenhaus St. Josef",
             "Kommunaler oder kirchlicher Traeger")):
        ist = art_aus_regel(name)
        gut = ist == soll
        ok = ok and gut
        print(f"  {'ok ' if gut else 'FEHLER'} {name[:44]:<44} -> {ist}")

    print("\nGEGENPROBE: was die Regel NICHT einordnen darf:")
    # Diese kamen in der Messung als „bleibt offen" heraus. Sie offen zu
    # lassen ist richtig. Eine Regel, die sie einordnet, raet.
    for name in ("Seniorenzentrum Herzog Christoph",
                 "Selbsthilfegruppe Halbwegs schön",
                 "Sekundarschule Gsteighof",
                 "17 Einrichtungen vollstationäre Langzeitpflege",
                 "Kinderspital",
                 "KinderPalliativTeam Mittelhessen"):
        ist = art_aus_regel(name)
        gut = ist is None
        ok = ok and gut
        print(f"  {'ok ' if gut else 'FEHLER'} {name[:44]:<44} -> {ist}")

    print("\nHochschulbereiche im Mailbereich erkennen:")
    for ber, soll in (("uni-bremen.de", True), ("ukbonn.de", True),
                      ("uk-koeln.de", True), ("charite.de", True),
                      ("hs-fresenius.de", True), ("uni-koeln.de", True),
                      ("iges.com", False), ("optimedis.de", False),
                      ("wido.bv.aok.de", False), ("iqvia.com", False),
                      ("inav-berlin.de", False), ("progewi.de", False)):
        ist = bool(HOCHSCHUL_BEREICH.search(ber))
        gut = ist == soll
        ok = ok and gut
        print(f"  {'ok ' if gut else 'FEHLER'} {ber:<22} "
              f"{'Hochschule oder Klinik' if ist else 'anderes Haus'}")

    print("\nReihenfolge der Abschnitte:")
    gut = ORDNUNG[0][0] == "Hochschule und Universitaetsmedizin" \
        and ORDNUNG[1][0] == "Ausseruniversitaere Forschungseinrichtung" \
        and ORDNUNG[-1][0] == "nicht zuzuordnen"
    ok = ok and gut
    print(f"  {'ok ' if gut else 'FEHLER'} Hochschulen zuerst, "
          f"ausseruniversitaere gleich danach, Unklares zuletzt")
    gut = len({a for a, _, _ in ORDNUNG}) == len(ORDNUNG)
    ok = ok and gut
    print(f"  {'ok ' if gut else 'FEHLER'} keine Art doppelt")

    print("\n" + ("Gegentest bestanden." if ok else "GEGENTEST GESCHEITERT."))
    return ok


def main():
    if "--gegentest" in sys.argv:
        return 0 if gegentest() else 1
    raus, ziel = bauen()
    print(f"aus dem Studienregister        : {raus['aus_register']}")
    print(f"aus dem Innofonds-Partnernetz  : {raus['aus_innofonds']}")
    print(f"davon NUR aus dem Innofonds    : {raus['nur_innofonds']}")
    print(f"Abteilungsnamen ohne Haus      : {raus['bruchstuecke']}")
    print(f"zusammen                       : {raus['gesamt']}")
    print(f"mit eigener Profilseite        : {raus['mit_profil']}")
    print()
    print("%-42s %6s %8s %9s %7s"
          % ("Abschnitt", "Einr.", "Studien", "Projekte", "nur IF"))
    print("-" * 78)
    for a in raus["abschnitte"]:
        print("%-42s %6d %8d %9d %7d"
              % (a["titel"][:42], a["anzahl"], a["studien"], a["projekte"],
                 a["nur_innofonds"]))
    print()
    print("Die groessten ausseruniversitaeren Forschungseinrichtungen:")
    fe = next((a for a in raus["abschnitte"]
               if a["art"] == "Ausseruniversitaere Forschungseinrichtung"), None)
    for e in (fe or {}).get("einrichtungen", [])[:12]:
        print("   %-48s %3d Studien %4d Projekte  %s"
              % (e["name"][:48], e["studien"], e["projekte"],
                 "+".join(q[:4] for q in e["quellen"])))
    f = raus["fehlen_im_register"]
    print(f"\nHaeuser, die bei MVF publizieren und im Register fehlen: "
          f"{len(f['liste'])}")
    print(f"(geprueft an {f['geprueft_beitraege']} Beitraegen mit Autorenbox)")
    for e in f["liste"][:14]:
        print("   %-38s %-34s %3d" % (e["bereich"][:38],
                                      (e["haus"] or "Name nicht hinterlegt")[:34],
                                      e["beitraege"]))
    print(f"\n-> daten/einrichtungen.json")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
