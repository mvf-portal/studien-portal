# -*- coding: utf-8 -*-
"""Die gemeinsamen Leisten - EIN Baustein fuer alle Seiten dieses Angebots.

Marianns Vorgabe aus Canvas 2 (`c1-kopfFuss`): „Schwarzer Kopf und Fussleiste
sind auf allen Seiten aller Angebote gleich und kommen aus je einem
gemeinsamen Baustein. Aendert sich etwas, wird es an einer Stelle angepasst
und gilt ueberall."

Vorher setzte nur `seite.py` die Leisten ein; die 192 Profilseiten hatten
keine. Das war nicht bloss ein Stilbruch: Der Pflichthinweis „Quelle DRKS,
Abrufdatum" steht im Fuss, also stand er auf den Profilseiten nirgends - und
das verletzt die CC-BY-Auflage, unter der die Daten ueberhaupt gezeigt werden
duerfen.

Quelle ist `portal-vorlage/`, nicht eine Kopie. Wer dort etwas aendert, baut
diese Seiten neu und hat die Aenderung auch hier.
"""
from __future__ import annotations

import base64
import pathlib

HIER = pathlib.Path(__file__).resolve().parent
WURZEL = HIER.parent
VORLAGE = WURZEL / "portal-vorlage"
LOGO = WURZEL / "versorgungsforschung-portal" / "logo"

PLATZ_NETZ = "<!--__NETZLEISTE__-->"
PLATZ_FUSS = "<!--__FUSSLEISTE__-->"
UTM = "vf-landkarte"

IMPRESSUM = "https://www.monitor-versorgungsforschung.de/impressum/"
DATENSCHUTZ = "https://www.monitor-versorgungsforschung.de/datenschutz/"


def datauri(p: pathlib.Path, typ: str) -> str:
    """Bilder als data:-URI - ein Artifact laedt Bilder fremder Hosts nicht (CSP)."""
    return f"data:{typ};base64," + base64.b64encode(p.read_bytes()).decode("ascii")


def _lies(name: str, ersetzungen: dict[str, str]) -> str:
    p = VORLAGE / name
    if not p.exists():
        print(f"  HINWEIS: {p} fehlt - Leiste entfaellt")
        return ""
    s = p.read_text(encoding="utf-8")
    for k, v in ersetzungen.items():
        s = s.replace("{{" + k + "}}", v)
    return s


def beide() -> tuple[str, str]:
    """(Netzleiste, Fussleiste), fertig zum Einsetzen."""
    hub_icon = datauri(LOGO / "hub-icon.svg", "image/svg+xml")
    mvf_neg = datauri(LOGO / "mvf-logo-negativ.png", "image/png")
    netz = _lies("netzleiste.html", {
        "DOMAIN": "knowledge-hubs.m-vf.de", "UTM": UTM,
    }).replace('src="logo/hub-icon.svg"', f'src="{hub_icon}"')
    fuss = _lies("fussleiste.html", {
        "NF_LOGO": mvf_neg, "NF_IMPRESSUM": IMPRESSUM,
        "NF_DATENSCHUTZ": DATENSCHUTZ, "UTM": UTM,
    })
    return netz, fuss


def einsetzen(seite: str, netz: str, fuss: str, pflicht: bool = True) -> str:
    """Setzt beide Leisten in eine Seite. Fehlt ein Platzhalter, bricht es ab."""
    for platz in (PLATZ_NETZ, PLATZ_FUSS):
        if platz not in seite:
            if pflicht:
                raise SystemExit(f"FEHLER: Platzhalter {platz} fehlt in der Vorlage")
            return seite
    return seite.replace(PLATZ_NETZ, netz).replace(PLATZ_FUSS, fuss)
