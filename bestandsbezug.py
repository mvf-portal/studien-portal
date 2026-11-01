# -*- coding: utf-8 -*-
"""Verknuepft DRKS-Einrichtungen mit dem, was MVF ueber sie schon weiss.

Heute tragfaehig ist genau eine Verbindung: die **Einrichtung**. Das
Innovationsfonds-Projekt haelt in `innovationsfonds/db/ror_namen.json` 419
ueber ROR aufgeloeste Konsortialpartner und in `alias.json` ein handgepflegtes
Woerterbuch fuer die Entitaetenaufloesung. Beides wird hier nur GELESEN - die
Produktions-SQLite des Innofonds wird nicht angefasst, die gehoert seiner
eigenen Sitzung.

Die zweite Verbindung - DOI der Ergebnispublikation gegen die Hub-Archive -
ist in `hubbezug.py` gebaut, liefert aber heute null Treffer: die Hub-Archive
sind zu 99,8 Prozent aus 2026, die DRKS-Ergebnispublikationen aus 2022 bis
2024. Sie ist auf Zuwachs angelegt, nicht auf den heutigen Bestand.
"""
from __future__ import annotations

import json
import pathlib
import re

HIER = pathlib.Path(__file__).resolve().parent
INNO = HIER.parent / "innovationsfonds"

# Wortbestandteile, die keine Einrichtung unterscheiden - sie wuerden sonst
# jede Universitaetsklinik mit jeder anderen verschmelzen.
RAUSCHEN = {
    "universitaet", "universitaets", "universitaetsklinikum", "universitaetsmedizin",
    "klinikum", "klinik", "medizinische", "medizinischen", "fakultaet", "der", "des",
    "die", "das", "und", "am", "an", "zu", "fuer", "ev", "ggmbh", "gmbh", "kgaa",
    "stiftung", "institut", "zentrum", "germany", "university", "hospital", "medical",
    "center", "centre", "school", "of", "the", "department", "abteilung",
}

# Bundeslaender unterscheiden keine Einrichtung - sie benennen ein Gebiet, in
# dem Dutzende sitzen. Sie muessen deshalb ins Rauschen, und zwar aus einem
# Grund, der erst beim Nachsehen auffiel: Die zweiteiligen Landesnamen
# erfuellen die Zwei-Wort-Regel aus sich heraus. „AOK Baden-Wuerttemberg",
# „Krebsregister Baden-Wuerttemberg" und „DRV Baden-Wuerttemberg" teilen
# {baden, wuerttemberg} - zwei gemeinsame Woerter, also Treffer. So wurden
# acht voellig verschiedene Traeger zu EINEM Standort verschmolzen, der dann
# auch noch den Namen des erstbesten ROR-Eintrags trug
# („Landesdenkmalamt Baden Wuerttemberg", 10 Studien).
#
# Die Stadtstaaten Berlin, Hamburg und Bremen bleiben bewusst draussen: Dort
# ist der Name zugleich der Ort und unterscheidet sehr wohl.
RAUSCHEN |= {
    "baden", "wuerttemberg", "nordrhein", "westfalen", "mecklenburg",
    "vorpommern", "schleswig", "holstein", "sachsen", "anhalt", "rheinland",
    "pfalz", "niedersachsen", "thueringen", "brandenburg", "hessen",
    "saarland", "bayern", "bayerische", "bayerisches",
}

# Koerperschaftsformen, von denen es je Bundesland eine gibt. Sie sind
# dasselbe wie „Universitaetsklinikum": eine Gattung, kein Name. Ohne sie
# traf „Kassenaerztliche Vereinigung Baden-Wuerttemberg" die Vereinigung in
# Nordrhein-Westfalen, sobald die Landesnamen als Rauschen wegfielen.
RAUSCHEN |= {
    "kassenaerztliche", "kassenzahnaerztliche", "vereinigung", "vereinigungen",
    "aerztekammer", "zahnaerztekammer", "landesaerztekammer", "apothekerkammer",
    "pflegekammer", "psychotherapeutenkammer", "rentenversicherung",
    "krankenkasse", "krankenkassen", "krebsregister", "landesamt",
    "landesinstitut", "ministerium", "berufsgenossenschaft", "landesverband",
}

# Fachgebiete. Dritte Klasse desselben Fehlers, und die teuerste: Eine
# Fachrichtung benennt eine Disziplin, keine Einrichtung - es gibt sie an
# jedem Haus. Ohne diese Liste verschmolz „Klinik und Poliklinik fuer
# Psychiatrie und Psychotherapie" sieben Kliniken aus sieben Staedten
# (Bethel, Duesseldorf, Regensburg, Essen, TUM, Leipzig, Koeln) zu EINEM
# Standort, und „Kinder- und Jugendmedizin" noch einmal sieben.
#
# Der Verlust ist gering und faellt auf die sichere Seite: Namen, deren Kern
# dadurch leer wird, treffen weiterhin ueber den exakten Namen - sie treffen
# nur nicht mehr ueber eine Wortmenge, die nichts unterscheidet.
RAUSCHEN |= {
    "psychiatrie", "psychotherapie", "psychosomatik", "psychosomatische",
    "psychiatrische", "psychologie", "neurologie", "neurologische",
    "kinder", "jugendmedizin", "jugendpsychiatrie", "jugendalters",
    "kinderheilkunde", "paediatrie", "paediatrische", "kardiologie",
    "onkologie", "haematologie", "chirurgie", "chirurgische", "viszeral",
    "anaesthesiologie", "allgemeinmedizin", "innere", "gynaekologie",
    "geburtshilfe", "urologie", "dermatologie", "radiologie", "strahlentherapie",
    "radioonkologie", "pneumologie", "infektiologie", "gastroenterologie",
    "endokrinologie", "diabetologie", "rheumatologie", "nephrologie",
    "orthopaedie", "unfallchirurgie", "augenheilkunde", "hno", "palliativmedizin",
    "geriatrie", "altersmedizin", "rehabilitation", "epidemiologie",
    "sozialmedizin", "arbeitsmedizin", "hygiene", "poliklinik", "ambulanz",
    "versorgungsforschung", "gesundheitsoekonomie", "pflegewissenschaft",
}

# Vierte Klasse, gefunden am 31.10.2026 beim Abgleich der Standorte gegen
# ROR: die HOCHSCHULART. „Hochschule fuer angewandte Wissenschaften" ist
# keine Einrichtung, sondern ein Typ - und die drei Woerter erfuellen die
# Zwei-Wort-Regel aus sich heraus, genau wie die zweiteiligen
# Bundeslaendernamen. Dadurch verschmolzen Ostfalia, Kempten, Muenchen und
# die Zuercher Hochschule zu einem einzigen „Standort" mit 5 Studien.
# Dazu die Woerter, die jede Forschungseinrichtung von sich sagt: „German
# Cancer Research Center" dockte ueber {german, research} an Helmholtz
# Muenchen an, SOCIUM Bremen ueber {forschungszentrum, gesundheit}.
RAUSCHEN |= {
    "hochschule", "fachhochschule", "angewandte", "angewandten", "angewandter",
    "wissenschaften", "wissenschaft", "applied", "sciences", "katholische",
    "katholisches", "evangelische", "evangelisches", "staatliche", "duale",
    "technische", "technischen", "technical", "wirtschaft", "soziales",
    "forschungszentrum", "forschungsinstitut", "forschung", "gesundheit",
    "gesundheits", "gesundheitswesen", "german", "deutsche", "deutscher",
    "deutsches", "research", "science", "management", "bildung", "transfer",
}


def _norm(s: str) -> str:
    s = (s or "").lower()
    s = (s.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue")
           .replace("ß", "ss").replace("–", "-"))
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _kern(s: str) -> frozenset[str]:
    """Die unterscheidenden Woerter eines Einrichtungsnamens."""
    return frozenset(w for w in _norm(s).split()
                     if w not in RAUSCHEN and len(w) > 3)


def _kopf(s: str) -> str | None:
    """Das erste unterscheidende Wort eines Namens - es traegt ihn.

    „Hochschule fuer angewandte Wissenschaften Kempten" -> „kempten".
    „Westfaelische Hochschule" -> „westfaelische". Wer das Kopfwort nicht
    teilt, ist eine andere Einrichtung, auch wenn zwei spaetere Woerter
    zufaellig uebereinstimmen.
    """
    for w in _norm(s).split():
        if w not in RAUSCHEN and len(w) > 3:
            return w
    return None


def innofonds_einrichtungen() -> tuple[dict[str, dict], list[tuple[frozenset, dict]]]:
    """Zwei Indizes: exakter Name und Kern-Wortmenge.

    **Der Fallstrick, der diesen Abgleich beim ersten Anlauf unbrauchbar
    machte:** 204 der 759 Namensvarianten haben nach Abzug des Rauschens nur
    EIN unterscheidendes Wort - `{freiburg}`, `{koeln}`, `{heidelberg}`. Wer
    darauf eine Teilmengenregel anwendet, laesst jede Multizenterstudie, die
    irgendeine Klinik dieser Stadt nennt, als Treffer durchgehen; die Quote
    stieg so auf unglaubwuerdige 86,6 Prozent. Einwortkerne duerfen deshalb
    nur ueber den exakten Namen treffen, nie ueber die Wortmenge.
    """
    p = INNO / "db" / "ror_namen.json"
    if not p.exists():
        print(f"  HINWEIS: {p} fehlt - Innofonds-Verknuepfung entfaellt")
        return {}, []
    roh = json.loads(p.read_text(encoding="utf-8"))
    exakt: dict[str, dict] = {}
    kerne: dict[frozenset, dict] = {}
    for ror, e in roh.items():
        namen = [e.get("de"), e.get("en")]
        namen += [a.get("wert") for a in (e.get("alle") or []) if a.get("wert")]
        anzeige = e.get("de") or e.get("en") or ror
        eintrag = {"name": anzeige, "ror": ror}
        for n in namen:
            if not n:
                continue
            exakt.setdefault(_norm(n), eintrag)
            k = _kern(n)
            if len(k) >= 2:                      # Einwortkerne bleiben draussen
                kerne.setdefault(k, eintrag)
    return exakt, list(kerne.items())


class Abgleich:
    def __init__(self) -> None:
        self.exakt, self.kerne = innofonds_einrichtungen()
        print(f"  Innofonds-Bestand: {len(self.exakt)} Namen exakt, "
              f"{len(self.kerne)} mehrwortige Kerne")

    def kanonisch(self, name: str) -> dict | None:
        """Die ROR-Fassung eines Einrichtungsnamens, falls bekannt.

        Das DRKS normiert Einrichtungsnamen nicht: „Charité -
        Universitätsmedizin Berlin" (Bindestrich) und „Charité – …"
        (Gedankenstrich) sind dort zwei Standorte. Die ueber ROR aufgeloeste
        Traegerliste des Innovationsfonds ist die gepflegte Kanonisierung -
        ein Treffer darin macht aus beiden Schreibweisen einen Standort mit
        stabiler Kennung (der ROR-ID).
        """
        t = self.innofonds([name])
        return t[0] if len(t) == 1 else None

    def innofonds(self, namen: list[str]) -> list[dict]:
        """Welche der uebergebenen Einrichtungen kennt das Innofonds-Radar?

        Bewusst streng: Treffer nur bei identischem Namen oder bei
        mindestens ZWEI gemeinsamen unterscheidenden Woertern, von denen
        eines das KOPFWORT sein muss. Damit meldet der Abgleich eher zu
        wenig als zu viel - was er meldet, traegt.

        **Der dritte Fallstrick, gefunden am 31.10.2026:** Die erste Fassung
        nahm den ERSTEN Kern mit zwei gemeinsamen Woertern und brach ab. Die
        Reihenfolge der Kerne ist aber die eines Woerterbuchs, also
        willkuerlich. „Westfaelische Hochschule" hatte sich selbst im
        Bestand - genommen wurde die „Hochschule fuer Technik und Wirtschaft
        des Saarlandes", weil sie frueher in der Liste stand. Und
        „Technische Hochschule Rosenheim" wurde zur „Leibniz Universitaet
        Hannover". Es muss der BESTE Treffer gewaehlt werden, nicht der
        erste - und bei Gleichstand keiner.
        """
        gefunden: dict[str, dict] = {}
        for n in namen:
            s = _norm(n)
            if s in self.exakt:
                t = self.exakt[s]
                gefunden[t["ror"]] = t
                continue
            k = _kern(n)
            if len(k) < 2:
                continue
            kopf = _kopf(n)
            if kopf is None:
                continue
            # Rang: viele gemeinsame Woerter zaehlt zuerst, dann moeglichst
            # wenige UNGEDECKTE Woerter im Namen des Kandidaten.
            #
            # Dieses zweite Mass war noetig, weil sonst ein Gleichstand die
            # Charité zerriss: „Charité - Universitätsmedizin Berlin"
            # {berlin, charit} und „Berliner Institut für
            # Gesundheitsforschung" {berlin, charit, health, institute}
            # teilen beide zwei Woerter mit der Anfrage. Der erste Kandidat
            # ist aber restlos gedeckt, der zweite bringt zwei fremde
            # Woerter mit - er meint eine andere Einrichtung.
            beste: list[tuple[int, int, dict]] = []
            for kk, t in self.kerne:
                g = k & kk
                if len(g) >= 2 and kopf in g:
                    beste.append((len(g), -len(kk - k), t))
            if not beste:
                continue
            rang = max((n_, u) for n_, u, _ in beste)
            spitze = {t["ror"]: t for n_, u, t in beste if (n_, u) == rang}
            if len(spitze) != 1:
                continue          # echter Gleichstand ist kein Treffer
            t = next(iter(spitze.values()))
            gefunden[t["ror"]] = t
        return list(gefunden.values())


def gegentest() -> None:
    """Eine erfundene Einrichtung darf NICHT treffen, eine echte muss."""
    a = Abgleich()
    faelle = [
        # muessen treffen
        ("Universitätsklinikum Freiburg", True),
        ("Universität zu Köln", True),
        ("Charité - Universitätsmedizin Berlin", True),
        ("Universitätsklinikum Hamburg-Eppendorf", True),
        # duerfen NICHT treffen - das sind die Faelle, an denen der erste
        # Anlauf gescheitert ist: echte Kliniken, die ein einzelnes Wort mit
        # einem Innofonds-Partner teilen.
        ("Klinikum links der Weser", False),
        ("Krankenhaus Bad Gandersheim", False),
        ("Stadtteilklinik Essen-Stoppenberg", False),
        ("St. Marienkrankenhaus", False),
        ("Praxis Dr. Schmidt, Freiburg", False),
        # Erfundenes und blosses Rauschen
        ("Klinikum der Stadt Wolkenkuckucksheim", False),
        ("Zentralinstitut für Flunkerologie Hintertupfingen", False),
        ("Universitätsklinikum", False),
    ]
    # Der zweite Fallstrick: zweiteilige Bundeslaendernamen erfuellen die
    # Zwei-Wort-Regel aus sich heraus. Diese Einrichtungen haben NICHTS
    # miteinander zu tun ausser dem Bundesland - sie duerfen weder treffen
    # noch untereinander verschmelzen.
    land = ["AOK Baden-Württemberg", "Krebsregister Baden-Württemberg",
            "Deutsche Rentenversicherung Baden-Württemberg",
            "Kassenärztliche Vereinigung Baden-Württemberg",
            "RehaZentren Baden-Württemberg gGmbH",
            "Ärztekammer Nordrhein-Westfalen",
            "Kassenärztliche Vereinigung Nordrhein-Westfalen"]
    # Dieselbe Pruefung fuer Fachgebiete: Kliniken desselben Fachs in
    # verschiedenen Staedten sind verschiedene Standorte.
    fach = ["Klinik und Poliklinik für Psychiatrie und Psychotherapie Regensburg",
            "LVR Klinikum Essen, Klinik für Psychiatrie und Psychotherapie",
            "Universität zu Köln, Klinik und Poliklinik für Psychiatrie und Psychotherapie",
            "Städtisches Klinikum Görlitz, Klinik für Kinder- und Jugendmedizin",
            "Klinik für Kinder- und Jugendmedizin (UKU) Sektion Endokrinologie",
            "Freiburg, Klinik für Kinder- und Jugendmedizin"]
    # Vierte Pruefung: die Hochschulart. Diese fuenf sind fuenf
    # verschiedene Hochschulen in fuenf Staedten (eine davon in Zuerich) -
    # am 31.10.2026 waren sie zu EINEM Standort verschmolzen.
    hoch = ["Ostfalia Hochschule für Angewandte Wissenschaften",
            "Hochschule für angewandte Wissenschaften Kempten, Institut für Gesundheit und Generationen (IGG)",
            "Hochschule für angewandte Wissenschaften München",
            "Zürcher Hochschule für angewandte Wissenschaften, Department Gesundheit, Institut für Pflege",
            "Hochschule für Angewandte Wissenschaften Hamburg, Fakultät Wirtschaft und Soziales, Department Pflege und Management",
            "Hochschule für Technik und Wirtschaft des Saarlandes",
            "Westfälische Hochschule (Institut für Arbeit und Technik)",
            "Katholische Hochschule Freiburg", "Katholische Hochschule Mainz"]
    # Fuenfte Pruefung: Woerter, die jede Forschungseinrichtung von sich
    # sagt. Diese drei hatten nichts gemeinsam und wurden doch eins.
    allg = ["German Cancer Research Center",
            "Institut für Gesundheitsökonomie und Management im Gesundheitswesen, Helmholtz Zentrum München",
            "Universität Bremen, SOCIUM Forschungszentrum Ungleichheit und Sozialpolitik, Abteilung Gesundheit, Pflege und Alterssicherung"]
    print("\nGegentest Einrichtungsabgleich:")
    ok = True
    for name, erwartet in faelle:
        t = a.innofonds([name])
        traf = bool(t)
        zeichen = "ok " if traf == erwartet else "FEHL"
        if traf != erwartet:
            ok = False
        print(f"  {zeichen}  {name:<48} -> {t[0]['name'] if t else 'kein Treffer'}")

    def nicht_verschmelzen(titel: str, namen: list[str]) -> bool:
        print(f"\n  {titel}")
        kennungen: dict[str, list[str]] = {}
        for name in namen:
            k = a.kanonisch(name)
            kennungen.setdefault(k["ror"] if k else "(kein Treffer)", []).append(name)
        sauber = True
        for ror, gruppe in kennungen.items():
            if ror != "(kein Treffer)" and len(gruppe) > 1:
                sauber = False
                print(f"    FEHL  {len(gruppe)} Einrichtungen auf EINER Kennung: "
                      f"{', '.join(n[:34] for n in gruppe)}")
        if sauber:
            print(f"    ok    {len(namen)} Einrichtungen, keine faelschlich zusammengelegt")
        return sauber

    ok = nicht_verschmelzen("Bundeslaender duerfen nicht verschmelzen:", land) and ok
    ok = nicht_verschmelzen("Fachgebiete duerfen nicht verschmelzen:", fach) and ok
    ok = nicht_verschmelzen("Hochschularten duerfen nicht verschmelzen:", hoch) and ok
    ok = nicht_verschmelzen("Allgemeinwoerter duerfen nicht verschmelzen:", allg) and ok

    print("  Gegentest bestanden." if ok else "  GEGENTEST FEHLGESCHLAGEN.")


if __name__ == "__main__":
    gegentest()
