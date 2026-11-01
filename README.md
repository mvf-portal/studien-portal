# Versorgungsstudien-Landkarte

Wer in Deutschland welche Versorgungsstudie führt, wo, und wie weit sie ist.
Aus dem Deutschen Register Klinischer Studien (DRKS), verknüpft mit den 15
Knowledge-Hubs und dem Innovationsfonds-Radar.

Ein Angebot von **Monitor Versorgungsforschung** (eRelation AG – Content in
Health, Bonn).

https://studien.m-vf.de/

## ⚠ Dies ist ein Ausschnitt, kein Gesamtbild

Im DRKS stehen **1.298** Studien mit Versorgungsbezug. Wiedergeben dürfen wir
**710** davon, **588 fehlen hier, obwohl es sie gibt.**

Die CC-BY-4.0-Lizenz des Registers gilt nur für Einträge, die ab 2025
registriert **oder aktualisiert** wurden. Sie wirkt damit wie ein Zeitfilter:

| Jahr | Studien mit Versorgungsbezug | davon zeigbar |
|---|---|---|
| 2015 | 42 | 1 (2 %) |
| 2018 | 79 | 19 (24 %) |
| 2021 | 123 | 45 (37 %) |
| 2024 | 117 | 88 (75 %) |
| 2025 | 151 | 151 (100 %) |
| 2026 | 225 | 225 (100 %) |

Ältere Einträge sind fast nur dabei, wenn sie noch laufen und darum
aktualisiert wurden. **Abgeschlossene Forschung fehlt am stärksten.**

Jede Auswertung auf dieser Grundlage misst deshalb, wer **zuletzt
registriert** hat — nicht, wer über die Jahre am meisten geforscht hat.

**Deshalb die Bitte an alle Forschenden und Einrichtungen:** Tragen Sie ein,
was fehlt — Ihre Studien, Ihr Publikationsverzeichnis, Ihre Arbeitsgruppe.
Auch ohne registrierte Studie: Eine neu gegründete Einrichtung kann in einer
Karte aus dem Studienregister gar nicht auftauchen.

## Was die Seite zeigt

| | |
|---|---|
| Studien | 710 mit Versorgungsbezug |
| Forschungsstandorte | 64 mit eigener Profilseite (ab 2 Studien) |
| Karte | 52 Standorte verortet |
| Einrichtungsverweise | 393 in ROR, OpenAlex, Wikidata, Wikipedia, GND, ISNI, VIAF, GRID, Crossref, re3data |
| Ergebnispublikationen | 357 Arbeiten aus 377 DOIs (94,7 %) |
| Personen | 2.388 Autor:innen, 69,5 % mit ORCID |

**Forschungsstandort ist nicht Studienzentrum.** Gezählt wird nur die
Einrichtung, die eine Studie verantwortet — nicht die Praxis, die
Teilnehmende einschließt.

## Quellen und Lizenzen

| Quelle | Lizenz | wofür |
|---|---|---|
| [DRKS](https://drks.de) (BfArM) | CC BY 4.0 (nur Einträge ab 2025) | Studiendaten |
| [ROR](https://ror.org) | CC0 | Einrichtungskennung, Ort |
| [OpenAlex](https://openalex.org) | CC0 | Publikationen, Fachgebiete, Repositorien, Koordinaten |
| [Wikidata](https://www.wikidata.org) | CC0 | Verweise in alle weiteren Verzeichnisse |
| [re3data](https://www.re3data.org) | offen | Forschungsdaten-Repositorien |
| [Natural Earth](https://www.naturalearthdata.com) | Public Domain | Umriss der Karte |

Keine Kachelserver, keine Cookies, keine fremden Aufrufe: Die Karte ist in
die Seite eingebettet.

Nicht enthalten, weil nicht abfragbar: **OpenDOAR** (Zugang nur mit
Schlüssel), **GERiT** (keine Schnittstelle), **FIS-Landkarte** (kein Export).

## Bauen

```
py holen.py          DRKS-Gesamtexport holen
py hubbezug.py       DOIs der 15 Hub-Archive
py bauen.py          Datengrundlage (CC-BY-Teil, Versorgungsbezug, Hubs)
py repositorien.py   ROR, OpenAlex, Repositorien, Koordinaten   [Netz]
py verzeichnisse.py  Wikidata, re3data                          [Netz]
py doi_bezug.py      Ergebnispublikationen, Fachgebiete, Personen [Netz]
py standorte.py      Profilseiten
py seite.py          index.html
```

⚠ `repositorien.py` und `standorte.py` lesen **wechselseitig** voneinander.
Nach einer Änderung an der Zusammenführung die Kette **zweimal** laufen
lassen und prüfen, ob die Standortzahl stehen bleibt.

Jeder Schritt hat einen Gegentest: `py <schritt>.py --gegentest`.

Ausführlich in [MANUAL.md](MANUAL.md).
