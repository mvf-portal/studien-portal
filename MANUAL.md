# Versorgungsstudien-Landkarte — Baukette und Handbuch

Prototyp vom 30.10.2026. Zeigt, wer in Deutschland welche **Versorgungsstudie**
plant, durchführt, abgebrochen oder abgeschlossen hat — tagesaktuell aus dem
Deutschen Register Klinischer Studien (DRKS), im Design der Knowledge-Hubs und
verknüpft mit dem eigenen Bestand.

Anlass: Die DOG-Forschungslandkarte 2026 leistet das für ein Fach (36
Einrichtungen, 777 Studien, Daten 2021–2023, PDF, Selbstauskunft). Für die
Versorgungsforschung gibt es nichts Vergleichbares — die dafür gebaute
Datenbank `versorgungsforschung-deutschland.de` ist tot (Strato-Parkseite),
das DNVF hat keinen Nachfolger, der Innovationsfonds deckt einen Fördertopf ab.

**Veröffentlicht als Artifact:** https://claude.ai/artifact/VZRDfLa4yBYyQBSohRJHCK
(privat — zum Zeigen muss er über das Teilen-Menü der Seite freigegeben werden).

## Die Kette

Vier Schritte, in dieser Reihenfolge:

```
py holen.py        # DRKS-Gesamtexport nach daten/drks-export-JJJJ-MM-TT.zip
py hubbezug.py     # PMIDs der 15 Hub-Archive -> DOIs (daten/hub-dois.json)
py bauen.py        # Auswahl, Zuordnung, Verknüpfung (daten/landkarte.json)
py standorte.py    # Profilseiten + daten/standorte.json  (MUSS vor seite.py)
py seite.py        # Vorlage + Daten + Standorte + Leisten -> landkarte.html

py foerderer.py    # eigene Auswertung: wer bezahlt (daten/foerderer.json)
```

`hubbezug.py` muss nur laufen, wenn die Hub-Archive gewachsen sind; sein
Ergebnis wird wiederverwendet und nur um neue PMIDs ergänzt.

### Dateien

| Datei | Zweck |
|---|---|
| `holen.py` | lädt den DRKS-Gesamtexport |
| `hubbezug.py` | Brücke PMID → DOI über NLM-ID-Converter und esummary |
| `zuschnitt.py` | **die Regeln**: was gilt als Versorgungsforschung, welcher Hub |
| `bestandsbezug.py` | Einrichtungsabgleich gegen den Innofonds-Bestand, mit Gegentest |
| `bauen.py` | baut `daten/landkarte.json` samt Auszählungen |
| `vorlage.html` | die ganze Seite: HTML, CSS, JavaScript |
| `seite.py` | setzt Daten, Standortverzeichnis und Leisten ein, schreibt `landkarte.html` |
| `leisten.py` | **EIN Baustein** für Netz- und Fussleiste, von Karte UND Profilseiten benutzt |
| `traegerart.py` | **wer die Forschung trägt** — Hochschule, Behörde, Selbstverwaltung, Kasse, Firma |
| `fachrichtung.py` | welche Wissenschaftsrichtung, nur wo der Name sie nennt (19 %) |
| `foerderer.py` | die Geldgeber mit Anschrift, Schreibweisen zusammengeführt |

**Code gehört nicht in Python-Zeichenketten.** Deshalb liegt die ganze Seite in
`vorlage.html` und `seite.py` ersetzt nur Platzhalter.

## Die Datenquelle

`https://drks.de/search/en/download/all-json` — ZIP, kein Anmelden, keine API.
Am 30.10.2026: 87,8 MB ZIP, 349 MB JSON, **22.737 Datensätze**, Stand = Abruftag.

Tragende Felder: `studyCharacteristic.type` (NON_INTERVENTIONAL 54 %),
`recruitment.status`, `recruitment.institutes[]` (Name, Ort, Art),
`trialContacts[]` (Einrichtung, Ort, Rolle), `ethicsCommittee` (Kommission,
Nummer, Datum, Votum), `studiedHealthConditions` (ICD-10), `trialResults`.

### ⚠ Lizenz — die harte Grenze

**Nur Einträge, die ab 2025 registriert ODER zuletzt aktualisiert wurden, stehen
unter CC BY 4.0.** Das waren 10.046 von 22.737 (44,2 %). Ältere Einträge dürfen
ohne Zustimmung der Rechteinhaber **nicht wiedergegeben** werden — verlinken ist
immer erlaubt. `bauen.py` filtert darauf; wer den Filter entfernt, verletzt die
Nutzungsbedingungen.

Pflichten bei jeder Veröffentlichung: Quelle „DRKS" nennen, **Abrufdatum**
nennen, DRKS-Logo nicht verwenden. Beides steht im Seitenkopf und im Fuß.

**Personenbezug:** `bauen.py` übernimmt aus `trialContacts` nur Einrichtung und
Ort — nie Name, E-Mail, Telefon. Das ist eine bewusste Entscheidung, keine
Lücke; wer das ändert, veröffentlicht Kontaktdaten Dritter.

## Die beiden Heuristiken (und warum sie offenliegen)

Beides steht in `zuschnitt.py`, damit die Seite offenlegen kann, womit sie
zugeordnet hat.

**1. Versorgungsbezug.** Das Register kennt nur interventionell und
nicht-interventionell; beides deckt sich nicht mit Versorgungsforschung (eine
Biomarker-Kohorte ist nicht-interventionell und keine VF, eine
cluster-randomisierte Hausarztstudie ist interventionell und VF). Punktwert auf
Titel und Zusammenfassung, Schwelle 3. Verteilung: Schwelle 3 → 710 Studien,
Schwelle 2 → 1.405, Schwelle 4 → 357.

**2. Hub-Zuordnung.** Primär über die ICD-10-Codes des Datensatzes (die sind
vergeben, nicht geraten), hilfsweise über Stichwörter — und für Hubs, die kein
Krankheitsbild sind (KI, Patientensicherheit, Gesundheitskompetenz, Gender,
Klima), nur über Stichwörter. 68 von 710 Studien (9,6 %) bleiben ohne Hub.

## Die Verknüpfungen zum Bestand

| Verknüpfung | Stand |
|---|---|
| **Knowledge-Hubs** (15) | greift: 642 von 710 Studien, Chip führt zum Hub |
| **Innovationsfonds-Radar** | greift: 486 Studien (68,5 %) an Einrichtungen mit Innofonds-Vorhaben |
| **Netzleiste** aller 16 Seiten | eingebaut, aus `portal-vorlage/netzleiste.html` |
| **Hub-Studienarchive** (DOI) | gebaut, **0 Treffer** — siehe unten |

### Warum der DOI-Abgleich heute null liefert

`hubbezug.py` schlüsselt alle 5.653 PMIDs der 15 Hub-Archive in DOIs um (99,1 %
Trefferquote über zwei Wege) und `bauen.py` gleicht sie gegen die
Ergebnispublikationen im DRKS ab. Ergebnis: **null**. Das ist kein Fehler — der
Gegentest bestätigt, dass der Abgleich funktioniert. Die Hub-Archive stammen zu
**99,8 % aus 2026**, die DRKS-Ergebnispublikationen aus **2022 bis 2024**. Die
Verknüpfung ist auf Zuwachs angelegt: Je länger die Hubs laufen, desto mehr
Studien lassen sich mit ihrem Ergebnis zusammenführen.

### ⚠ Der Fallstrick beim Einrichtungsabgleich

Erster Anlauf: 86,6 % der Studien hatten angeblich Innofonds-Bezug, darunter
„Westküstenkliniken Brunsbüttel und Heide" mit 34 Studien. Ursache: **204 der
759 Namensvarianten im Innofonds-Bestand haben nach Abzug des Rauschens nur EIN
unterscheidendes Wort** — `{freiburg}`, `{koeln}`, `{heidelberg}`. Eine
Teilmengenregel darauf lässt jede Multizenterstudie durchgehen, die irgendeine
Klinik dieser Stadt nennt.

Jetzt: Einwortkerne treffen nur über den **exakten** Namen, sonst sind
**mindestens zwei gemeinsame unterscheidende Wörter** nötig. Quote fiel auf
68,5 %, die Spitzenliste wurde plausibel (Charité 70, UKE 35, Heidelberg 26).

**`py bestandsbezug.py` fährt den Gegentest** — zwölf Fälle, darunter die, an
denen der erste Anlauf gescheitert ist. Vor jeder Änderung an der Matchregel
laufen lassen.

## Design

Aus dem Bestand übernommen, nicht nachgebaut:

- **Farbtokens** der Knowledge-Hubs (hell und dunkel), `--action` ist das MVF-Gold.
- **Lato** 400/700/900 — die Hausschrift der Hubs und des Innofonds-Portals.
- **Netzleiste** (alle 15 Hubs + Übersicht) und **Fußleiste** aus
  `portal-vorlage/`. **Eine Quelle:** Wer sie dort ändert, baut diese Seite neu
  (`py seite.py`) und hat die Änderung auch hier.
- Die beiden Logos werden als `data:`-URI eingebettet, weil ein Artifact Bilder
  von fremden Hosts nicht lädt (CSP).

## Was die Karte nicht kann

Steht auch auf der Seite selbst, im Abschnitt „Was diese Karte nicht zeigt":

- **56 % des Registers fehlen** (Lizenz).
- **Nur registrierte Forschung.** Kleine, qualitative, nicht geförderte VF wird
  oft gar nicht registriert. Sie hat ein Ethikvotum — aber die 51 Kommissionen
  veröffentlichen keine Einzelvoten, nur Antragszahlen in ihren
  Tätigkeitsberichten (Nordrhein z. B. 437/448/484/425/274/242/270 Erstanträge
  2019–2025). **Das Dunkelfeld lässt sich dadurch in seiner Größe schätzen,
  aber nicht auflisten** — das wäre der nächste Ausbauschritt.
- **Kein Methoden- und kein Datenzugangsprofil** (Routinedaten? qualitativ?
  Zugang zum FDZ Gesundheit?). Steht im Register nicht und ist nur durch
  Selbstauskunft zu bekommen — das ist der Teil, für den es das DNVF bräuchte.
- **Keine offenen Stellen.**
- **Bundesland ist aus der PLZ genähert.** Postleitregionen folgen der Post,
  nicht der Landesgrenze; bei 101 von 710 Studien liegt die Zuordnung in einer
  Region, die über eine Landesgrenze läuft. Die Seite weist das aus.
- **143 Schreibweisen für rund 128 Kommissionen** — das Register normiert die
  Namen nicht. `bauen.py` führt sie grob zusammen.

## Erste Befunde, die der Prototyp liefert

- **140 von 263 abgeschlossenen Studien (53 %) tragen keine Publikationsangabe.**
  Im Gesamtregister: 4.556 von 10.570.
- **Jeder Datensatz trägt sein Ethikvotum** — Kommission, Nummer, Datum, Art
  (APPROVED 10.891, NO_APPROVAL_REQUIRED 212, PENDING 112). Eine
  bundeslandbezogene Auswertung der Ethikvoten ist damit erstmals möglich.
- **Rückwirkende Registrierung ist die Regel, nicht die Ausnahme:** 44,7 % des
  Registers wurde erst nach Studienbeginn angemeldet.

## Standort-Profilseiten

```
py standorte.py          # Profilseiten ab 2 Studien nach standort/
py standorte.py --ab 1   # alle
```

Vorbild sind die **Projekt-Profilseiten des Innofonds-Radars**: öffentliche
Seite mit Steckbrief, daneben die Blöcke Themen, Ethikvoten, Innofonds-Bezug
und MVF-Serie, darunter „Sie leiten diesen Standort?" mit Zugangsanforderung
per E-Mail — genau wie dort „Sie verantworten dieses Vorhaben?".

Eintragbar sind: **Personalsuche** (ja/nein plus Text), **aktuelle
Veröffentlichungen**, **Bücher und Buchbeiträge**, **Methoden und
Datenzugänge**, Ansprechbarkeit für Kooperationen, Sonstiges.

### ⚠ Der Endpunkt fehlt noch

`ENDPUNKT` in `standorte.py` ist leer. Die Formulare sagen das dem Nutzer
ehrlich und senden nichts, statt eine Einsendung vorzutäuschen. Für den
Betrieb braucht es auf dem MVF-Server eine PHP-Datei nach dem Muster von
`innofonds-korrektur.php`:

- nimmt JSON per POST,
- begrenzt auf eine Einsendung je Standort und Minute (HTTP 429),
- legt die Einsendung ab und schickt den persönlichen Link an die angegebene
  dienstliche Adresse.

**Das ist eine Serveränderung und geht über [[levan-mail]]** — in dieser
Sitzung wurde nichts dorthin gemeldet.

### Standortidentität über die Innofonds-Trägerliste

Das DRKS normiert Einrichtungsnamen nicht: **1.423 Schreibweisen stehen für
1.123 Standorte.** Die Charité allein erscheint unter 31 Schreibweisen (63
Studien), das UKE unter 13, Aachen unter 11 — der Unterschied ist oft nur ein
Binde- statt eines Gedankenstrichs.

Zusammengeführt wird über die **ROR-aufgelöste Trägerliste des
Innovationsfonds** (`innovationsfonds/db/ror_namen.json`, nur gelesen). Ein
Treffer dort gibt dem Standort eine stabile Kennung (die ROR-ID); ohne
Treffer bleibt der normalisierte Name die Kennung. Die Zahl der zusammengeführten Standorte steht im Lauf von `standorte.py`; sie wurden so
zusammengeführt. Jede Seite weist ihre zusammengeführten Schreibweisen aus.

**Noch nicht gelöst:** Campus- und Teilinstitutsnamen, die nicht in der
Trägerliste stehen, bleiben eigene Standorte (z. B. „Charité Campus
Charité Mitte", „Deutsches Herzzentrum der Charité").

### Die MVF-Serie als Standortbezug

`vfserie.py` hält die 45 Beiträge der Serie **„Versorgungsforschung made in …"**
(seit 2016, abgerufen 30.10.2026). 40 der 82 Profilseiten verlinken ihren
Beitrag. Zugeordnet wird über drei Wege, vom stärksten zum schwächsten:
gleicher Name, zwei gemeinsame Kennwörter, gleicher Ort plus ein Kennwort.

**Zwei Fehler, die der Gegentest gefangen hat** — `py vfserie.py` fährt ihn:

1. **Umlaute aufgelöst statt abgeworfen.** Die Rauschwortliste steht in der
   ae/ue/oe-Schreibweise, die Normalisierung machte aber a/u/o. Dadurch griff
   kein einziges Rauschwort mit Umlaut, „universitätsklinikum" wurde zum
   unterscheidenden Wort — und **Düsseldorf traf Heidelberg**.
2. **Der Ortsname im Einrichtungsnamen.** „Universität Duisburg-**Essen**"
   und „Elisabeth-Krankenhaus **Essen**" teilen das Wort „essen", also traf
   das Krankenhaus den Beitrag über das CINCH. Ortswörter fliegen jetzt aus
   dem Vergleich.

## Abdeckungstests

### Die DNVF-Gruppe der HochschullehrerInnen

`py kontrolle_dnvf.py` prüft die 52 Mitglieder gegen drei Ebenen. Ergebnis
vom 30.10.2026 — ein Trichter:

| | von 52 |
|---|---|
| im gesamten DRKS (Name und Ort) | 37 |
| davon im CC-BY-Teil | 29 |
| davon in der VF-Auswahl der Landkarte | **20** |

**15 Mitglieder stehen in keinem DRKS-Datensatz**, darunter der Sprecher der
Gruppe. Das ist kein Messfehler: Das Register nennt die Kontaktperson einer
Studie, oft die Koordination statt der Lehrstuhlinhaberin — und ein großer
Teil der Versorgungsforschung wird gar nicht registriert. Die Zahl misst
**Sichtbarkeit im Register**, nicht Forschungstätigkeit.

### Innovationsfonds: ergänzt, doppelt nicht

`py kontrolle_innofonds.py` gleicht die 861 Vorhaben des Innofonds-Radars über
Akronym und Titel gegen das DRKS ab:

- **367 (42,6 %)** über das Akronym gefunden, 2 über den Titel
- **477 (55,4 %)** stehen **nicht** im DRKS
- 15 Akronyme sind kürzer als vier Zeichen und als unsicher ausgewiesen

**Der Innovationsfonds ist damit eine Pflichtquelle, keine Dopplung.** Mehr
als die Hälfte seiner Vorhaben wäre ohne ihn unsichtbar.

### GEPRIS: nicht nutzbar

Die DFG-Projektdatenbank hat **keine offizielle API und keinen Export**. Ihre
`robots.txt` lautet `User-agent: * / Disallow: /` — erlaubt sind nur benannte
Suchmaschinen. **Ein automatischer Abruf ist damit nicht gestattet**, und es
wurde keiner gebaut. Wer GEPRIS einbinden will, muss die DFG fragen.

## Die beiden Hälften sind verbunden (30.10.2026)

Vorher lagen Karte und Profilseiten nebeneinander, ohne einen einzigen Link.
Jetzt führen drei Wege hin und zurück:

1. **Reiter** oben auf der Karte: `Studien` | `Standorte`. Der zweite zeigt
   alle Profilseiten als Kacheln, mit derselben Suche.
2. **Jede Studienkarte** verlinkt die Einrichtungen, die eine Profilseite
   haben - dunkelblauer Chip `Name · Profil`.
3. **Jede Profilseite** trägt dieselben Reiter und führt zurück auf
   `../landkarte.html` bzw. `#standorte`.

**Gemessen: 514 der 710 Studien (72,4 %) tragen mindestens einen
Standort-Link**, zusammen 842 Links. Die übrigen 196 nennen nur
Einrichtungen mit einer einzigen Studie - für die entsteht keine
Profilseite (`--ab 2`). Mit `py standorte.py --ab 1` wären es 1.123 Seiten
und 100 %, dafür 900 Seiten mit je einer Studie.

Die Verbindung läuft über das Feld `schreibweisen` in
`daten/standorte.json`: Es nennt je Profilseite alle Namensvarianten, unter
denen der Standort im Register auftaucht. **Deshalb muss `standorte.py` vor
`seite.py` laufen** - fehlt die Datei, bleibt die Karte bedienbar, aber der
Reiter Standorte ist leer, und `seite.py` sagt das.

### ⚠ Drei Klassen von Rauschen - der Fehler, der dreimal wiederkam

Beim Nachsehen der fertigen Seite fiel ein Standort auf, der dort nichts zu
suchen hatte: **„Landesdenkmalamt Baden Württemberg", 10 Studien.** Dahinter
steckten acht völlig verschiedene Träger - AOK, DRV, Kassenärztliche
Vereinigung, Krebsregister, RehaZentren -, die zu EINEM Standort verschmolzen
waren. Grund: Sie teilen zwei unterscheidende Wörter, `{baden, wuerttemberg}`,
und die Regel verlangt genau zwei.

Die Korrektur deckte zwei weitere Fälle derselben Art auf, jeder vom
Gegentest gefangen, nicht vom Auge:

| Klasse | Beispiel | was verschmolz |
|---|---|---|
| **Bundesländer** | `{baden, wuerttemberg}` | 8 Träger eines Landes |
| **Körperschaftsformen** | `{kassenaerztliche, vereinigung}` | KV Baden-Württemberg traf KV Nordrhein-Westfalen |
| **Fachgebiete** | `{psychiatrie, psychotherapie}` | 7 Kliniken aus 7 Städten; dazu `{kinder, jugendmedizin}` noch einmal 7 |

Alle drei sind dasselbe wie „Universitätsklinikum": eine **Gattung, kein
Name**. Sie stehen jetzt in `RAUSCHEN`. Die Stadtstaaten Berlin, Hamburg und
Bremen bleiben bewusst drin - dort ist der Name zugleich der Ort und
unterscheidet sehr wohl.

**Der Preis ist gering und fällt auf die sichere Seite:** Namen, deren Kern
dadurch leer wird, treffen weiterhin über den exakten Namen; sie treffen nur
nicht mehr über eine Wortmenge, die nichts unterscheidet. Die Verlinkung fiel
von 75,4 auf 72,4 Prozent - **diese drei Punkte waren falsche Links.** Die
Spitzenliste der Standorte wurde dafür plausibel: Charité 63, UKE 30,
Heidelberg 25, Aachen 19, MHH 17.

`py bestandsbezug.py` prüft jetzt beides: dass echte Einrichtungen treffen,
und dass Einrichtungen **gleicher Gattung in verschiedenen Städten NICHT
dieselbe Kennung bekommen**. Vor jeder Änderung an der Matchregel laufen
lassen.

## Der Aufbau folgt Marianns Vorgaben (Canvas 2, 30.10.2026)

Die Notizen liegen in `Claude-Daten/mariann-canvas2/notes.txt`. Übernommen
sind die Vorgaben, die für eine einzelne Seite gelten:

| Vorgabe | Zettel | umgesetzt als |
|---|---|---|
| Seite 1.240 px, Fliesstext 760 px | `n-Vorlage-breite` | `.wrap` / `.lesebreite` |
| Kopf: **ein** Satz, kein zweiter Absatz | `n-Main-1` | `.unter` |
| Reiter linksbündig, aktiv fett mit 3 px blauer Linie | `n-Main-0` | `.reiter` |
| Suchkasten ragt in den blauen Kopf | `n-Main-2` | `.blau` + `.suchkasten` |
| Suchfeld leer, grauer Platzhalter mit zwei Beispielen | `n-Main-3` | `::placeholder` #9AA5B4 |
| Hinweis unten rechts im Suchkasten | `n-Main-5` | `.suchfuss` - hier Quelle und **Abrufdatum**, die Lizenzpflicht |
| „Zum ersten Mal hier?" als eigener Kasten mit × | `n-Main-6` | `.ersteMal`, #E8EFF8 |
| EIN zuklappbarer Filterkasten, Pillen, „Alle Filter zurücksetzen" | `n-Main-11` | `.filterkasten` |
| Anzahl links, Kennzeichen als Raster rechts | `n-Main-12` | `.zaehlzeile` / `.legende` |
| Gleich hohe weisse Kacheln auf grauem Grund | `n-Main-8` | `.kz`, `.ortkarte` |
| Grenze links, **was stattdessen hilft** rechts | `n-Seite-Ueber-die-Hubs-6` | `.gzeile` |
| Kopf und Fuss aus EINEM gemeinsamen Baustein | `c1-kopfFuss` | `leisten.py` |

**Bewusst nicht übernommen:** Das Schliessen von „Zum ersten Mal hier?" wird
nicht gespeichert - das Versprechen der Hubs lautet „keine Cookies".

**Der Darstellungsschalter** (hell/dunkel/Gerät) kommt mit der Netzleiste und
läuft über das Cookie `mvf-theme` für ganz `.m-vf.de`. Er wirkt damit auf
dieser Seite genauso wie in den Hubs - ohne eigenen Code.

## ⚠ Forschungsstandort ist nicht Studienzentrum (30.10.2026)

Der Herausgeber hielt die 200 Standorte fuer unglaubwuerdig - zu Recht. So
viele Orte, an denen Versorgungsforschung betrieben wird, gibt es in
Deutschland nicht.

**Die Ursache:** `standorte.py` nahm jede im Datensatz genannte Einrichtung.
Das sind drei verschiedene Dinge, die das Register gleich aussehen laesst:

```
1.642 rekrutierende Einrichtungen in den 710 Studien
1.477 davon NUR rekrutierend, nie fuehrend   <- Praxen und Kliniken
  568 fuehrende Einrichtungen (PRIMARY_SPONSOR)
```

Eine Hausarztpraxis, die Teilnehmende in eine Studie einschliesst, betreibt
keine Versorgungsforschung. Jetzt gilt:

| | was es ist | eigene Seite? |
|---|---|---|
| **Forschungsstandort** | die fuehrende Einrichtung (`PRIMARY_SPONSOR`) | ja |
| **Studienzentrum** | rekrutierende Praxis oder Klinik | nein, nur genannt |
| **Geldgeber** | Kasse, Ministerium, Unternehmen | nein, steht in der Foerdererliste |

**Ergebnis: 82 statt 82 Profilseiten.** Charite 46, UKE 25, Aachen 13,
Goethe-Universitaet 12, Heidelberg 10.

Dabei fliegen **25 Studien von Unternehmen und 15 von Kostentraegern** aus
den Standorten heraus (`AUSGESCHLOSSEN` in `standorte.py`). Sie sind damit
nicht verschwunden - sie stehen als Geldgeber in `foerderer.json`. Der
Anlass war der Hinweis des Herausgebers: *„Novartis Pharma GmbH ist
Foerderer, kein Forschender."* Vorher standen AOK, Techniker Krankenkasse,
BARMER, Mobil Krankenkasse und Orthopy Health GmbH als
„Versorgungsforschungs-Standorte" auf der Karte.

### Wer traegt die Forschung? (`traegerart.py`)

Zweite Korrektur des Herausgebers am selben Tag. Ich hatte „Institut fuer
Allgemeinmedizin, Socium Bremen, ZI und RKI" pauschal
„Forschungseinrichtungen" genannt. Das ist falsch:

- **Institut fuer Allgemeinmedizin, Socium Bremen** - Hochschuleinrichtungen,
  deren Zweck Forschung ist.
- **ZI** - Zentralinstitut fuer die kassenaerztliche Versorgung, eine
  Einrichtung der Aerzteschaft (Traeger: KBV), die auch forscht.
- **RKI** - Bundesoberbehoerde im Geschaeftsbereich des BMG, die auch forscht.

Wer die Forschung traegt, bestimmt Auftrag, Finanzierung und Unabhaengigkeit.
Das steht jetzt auf jeder Profilseite und ist ein Filter auf der Karte:

| Studien | Traegerart |
|---:|---|
| 510 | Hochschule und Universitaetsmedizin |
| 42 | Krankenhaus oder Praxis |
| 25 | Unternehmen *(nicht als Standort gefuehrt)* |
| 24 | Fachgesellschaft, Verband oder Stiftung |
| 15 | Kostentraeger *(nicht als Standort gefuehrt)* |
| 11 | Selbstverwaltung im Gesundheitswesen |
| 11 | Gemeinnuetziger Traeger |
| 9 | Kommunaler oder kirchlicher Traeger |
| 9 | Ausseruniversitaere Forschungseinrichtung |
| 3 | Ressortforschung des Bundes |
| 50 | nicht zuzuordnen (7,1 %) |

**Die Reihenfolge der Regeln entscheidet.** „Neurologische Klinik,
Universitaetsklinikum Heidelberg" muss Hochschule werden, nicht Krankenhaus;
„Zentrum fuer Integrative Psychiatrie gGmbH" nicht Unternehmen, sondern
gemeinnuetzig. `py traegerart.py --gegentest` prueft 23 Faelle, darunter
alle vier aus der Korrektur.

#### ⚠ Das `é` in „Charité"

`norm()` loeste die deutschen Umlaute auf und warf alle uebrigen Akzente
**weg**: „Charité" wurde zu `charit`, das Muster `charite` traf kein
einziges Mal, und 11 Studien der Charite standen als „nicht zuzuordnen".
Richtig ist: erst die Umlaute zu ae/oe/ue, **dann** NFKD fuer die uebrigen
Akzente. Dieselbe Falle wie in `vfserie.py`, nur andersherum.

### Welche Wissenschaftsrichtung? (`fachrichtung.py`)

Deutsche VF-Institute tragen ihr Fach im Namen. Aber: **nur 136 von 709
Studien (19,2 %)** nennen es, weil die grossen Haeuser im Register bloss
„Universitaetsklinikum Heidelberg" angeben.

| Studien | Fach |
|---:|---|
| 47 | Allgemein- und Hausarztmedizin |
| 29 | Versorgungsforschung (als Fach benannt) |
| 20 | Sozialmedizin und Epidemiologie |
| 17 | Rehabilitationswissenschaft |
| 10 | Medizinische Psychologie und Psychotherapieforschung |
| 9 | Geriatrie und Altersforschung · 9 Medizinsoziologie |
| 8 | Palliativ- und Hospizforschung · 8 Gesundheitsoekonomie |
| 4 | Pflegewissenschaft · 4 Biometrie und Statistik |

**Es wird nichts geraten.** Wo der Name kein Fach nennt, steht das auf der
Seite - und im Filter gibt es dafuer eine eigene Auswahl („im Register nicht
genannt", 54 Standorte). Eine Schaetzung aus Titel und Zusammenfassung waere
moeglich, muesste aber als Schaetzung gekennzeichnet werden; das ist eine
Entscheidung des Herausgebers, keine des Skripts.

### Die Geldgeber (`foerderer.py`)

Das Feld `materialSupports` traegt je Eintrag einen vollstaendigen
Kontaktsatz. **Personennamen sind in allen 795 Eintraegen leer** - das sind
Institutionsanschriften.

566 Schreibweisen fuehren auf **484 Geldgeber**. Der Innovationsausschuss
allein stand unter 29 Schreibweisen, das BMBF unter 16.

| Studien | Geldgeber |
|---:|---|
| 100 | Innovationsausschuss beim G-BA, Postfach 12 06 06, 10596 Berlin |
| 50 | BMBF, Kapelle-Ufer 1, 10117 Berlin |
| 22 | BMG, Friedrichstrasse 108, 10117 Berlin |
| 20 | Gemeinsamer Bundesausschuss, 10596 Berlin |
| 10 | Stiftung Deutsche Krebshilfe, Buschstrasse 32, 53113 Bonn |

339 oeffentliche Nennungen verteilen sich auf nur **111** Geldgeber, 292
Nennungen „aus eigenen Mitteln" dagegen auf **250** Haeuser.

`py foerderer.py --gegentest` prueft, dass BMG, BMBF und BMFTR **nicht**
zusammenfallen - „Bundesministerium" ist ein Gattungswort und darf nie
gruppieren.

### Die Innofonds-Liste als Quelle (Hinweis des Herausgebers)

`innovationsfonds/db/ror_cache.json` ist die bessere Quelle als
`ror_namen.json`: **1.251 gepruefte Zuordnungen Rohname -> ROR-ID, Ort,
Bundesland, Koordinaten**, ganz ohne Wortmengen-Regel.

Gemessen: Sie deckt **20,9 %** der DRKS-Namen exakt ab - die Schreibweisen
sind andere. Sie ersetzt die Heuristik also nicht, sondern ueberstimmt sie
dort, wo sie greift. **Noch nicht eingebaut.**

Ein Nebenbefund: Wo beide Quellen etwas sagen, stimmt die PLZ-Naeherung in
**137 von 141 Faellen (97 %)**. Die vier Abweichungen sind genau die
Grenzregionen, die die Seite als unsicher ausweist (Jena, Cottbus, Luebeck,
FU Berlin). Die Koordinaten waeren der Weg zu einer echten Karte.

## Was vor dem Liveschalten fehlt

**Hart (ohne das geht es nicht live):**

~~1. Die beiden Hälften sind nicht verbunden.~~ **Erledigt 30.10.2026**, siehe
   oben: Reiter, Standort-Chips auf den Studienkarten, Rückweg auf jeder
   Profilseite.
~~2. Die Profilseiten tragen weder Netz- noch Fussleiste.~~ **Erledigt
   30.10.2026** über `leisten.py`; der Lizenzhinweis steht jetzt auf allen 200
   Profilseiten.
3. **Der Formular-Endpunkt fehlt** (siehe oben) - Serveränderung über
   [[levan-mail]]. Noch nichts gemeldet.
4. **Kein Auslieferungsweg.** Kein git, kein Repo unter `mvf-portal`, kein DNS.
   Die anderen Portale laufen über GitHub Pages plus Subdomain.

**Entscheidungen:**

- **Subdomain `studien.m-vf.de`** - vom Herausgeber am 30.10.2026 gewählt.
  Repo und DNS sind noch nicht angelegt.
- Mit oder ohne DNVF.

**⚠ Der Herausgeber hat den Live-Gang am 30.10.2026 ausdrücklich angehalten
(„warte mit live"). Nichts veröffentlichen, kein Repo, keine Meldung an
Levan, bis er es sagt.**

**Kann nach dem Liveschalten kommen:**

- Innovationsfonds als **zweite Quelle einbauen** (gemessen, nicht eingebaut:
  477 seiner Vorhaben stehen nicht im DRKS).
- Zweite Schicht Selbstauskunft (Methoden, Datenzugaenge, Stellen), Vorbild
  sind die Innofonds-Pruefseiten.
- Automatischer Nachlauf: `holen.py` laeuft nicht von allein, es gibt keine
  geplante Aufgabe.
- Bundesland genauer als ueber die PLZ.

## Die Einrichtungen im Netz: Repositorien und ROR (31.10.2026)

Der Auftrag war: „Es muss von jeder Uni solche Repositories geben. Die
suchen, mit den Institutionen verlinken und abgleichen" – ausdrücklich auch
für **Hochschulen**, nicht nur Universitäten.

### Was es wirklich gibt – und was nicht

Die Probe am genannten Beispiel (Publikationsliste Prof. Schmitt, ZEGV
Dresden) hat die Erwartung widerlegt: Das ist eine **von Hand gepflegte
Plone-Seite**. Freitextzitate in wechselndem Stil (2026 APA-artig, 2024
Vancouver-artig), Doppeleinträge derselben Arbeit, Impact-Faktoren mitten im
Text, Überschriften „Erst- oder Letztautorenschaft" / „Ko-Autorenschaft",
kein Export, keine Schnittstelle. Der einzige äußere Verweis geht auf ein
Google-Scholar-Profil. **Als Verweisziel taugt das, als Datenquelle nicht.**

Geprüft, was an zentralen Verzeichnissen abfragbar ist:

| Quelle | Zugang | Taugt wofür |
|---|---|---|
| **ROR** | offen, CC0 | Identität: ID, Typ, Ort, Koordinaten, Netzadresse, Namensvarianten. **Hochschulen enthalten**, Typ `education` |
| **OpenAlex** | offen, CC0 | hängt an derselben ROR-ID: Typ, Zahl der Arbeiten, Namensvarianten und die **eigenen Repositorien** der Einrichtung |
| **OpenDOAR** | **HTTP 403**, Schlüssel nötig | wäre das vollständigste Repositorienverzeichnis |
| **re3data** | offen (HTTP 200) | Forschungs**daten**, nicht Publikationen |
| **GERiT** (DFG) | keine Schnittstelle gefunden | 33.000 Einrichtungen bis auf Institutsebene, nur über die Oberfläche |
| **FIS-Landkarte** (KFiD/DINI) | Seite baut sich im Browser auf, kein Export | welche Einrichtung welches Forschungsinformationssystem betreibt |

Ergebnis der Kette `repositorien.py` für die 82 Forschungsstandorte:

```
Einrichtung eindeutig aufgeloest :  74 von 82 (90,2 %)
Netzadresse der Einrichtung      :  74 (90,2 %)
eigenes Publikationsrepositorium :  22 (26,8 %)
```

**Die 26,8 % sind nicht die Wahrheit über Deutschland, sondern über
OpenAlex.** Qucosa der TU Dresden zum Beispiel fehlt dort. Mehr geht erst
mit einem OpenDOAR-Schlüssel (kostenlos, Anmeldung) oder über die
OAI-PMH-Adressen direkt.

### ⚠ Die ROR-Namensauflösung ist unbrauchbar ohne Wächter

Gemessen am 31.10.2026, Rohergebnisse der ROR-Schnittstelle:

```
„Charité - Universitätsmedizin Berlin"
    -> Charité (0,94) ... aber NICHT als `chosen` markiert
    -> „Wasserstraßen-Neubauamt Berlin" (0,89)   nur wegen „Berlin"
„Zentralinstitut für die kassenärztliche Versorgung in Deutschland"
    -> „BIO Deutschland" (0,90)                  nur wegen „Deutschland"
„Institut für Allgemeinmedizin, Universitätsklinikum Frankfurt"
    -> Frankfurt (0,98) UND das Institut der LMU München (0,98), gleich hoch
```

Der `chosen`-Schalter von ROR hilft nicht: er lässt die Charité fallen.
`traegt()` in `repositorien.py` nimmt einen Treffer deshalb nur auf zwei
Wegen an, und der Gegentest prüft **22 Fälle**:

1. Ein **unterscheidendes Wort** kehrt wieder, und es muss das **Kopfwort**
   sein – das erste nicht-generische Wort des Namens.
2. Die Einrichtung hat gar keinen eigenen Namen, nur **Art und Ort**
   („Universitätsklinikum Frankfurt"). Dann müssen **beide** stimmen.

Dazu drei Sperren, jede aus einem echten Fehltreffer entstanden:

- **Punktwert unter 0,90 wird nicht betrachtet.** „Diploma Hochschule" kam
  mit 0,60 durch, „Institut für Forschung und Transfer" mit 0,82.
- **Landesteile sind Rauschen.** „Kleine Riesen Nordhessen gGmbH" dockte
  über „Nordhessen" an der „Diploma Fachhochschule Nordhessen" an.
- **Das Kopfwort muss in BEIDE Richtungen stimmen.** Trägt der Kandidat ein
  Kopfwort, das die Anfrage nicht kennt, ist er *enger* – ein Teil, nicht
  das Ganze. So fiel „LMU Klinikum München" → „Institut für Infektions- und
  Tropenmedizin" auf, das über die Variante „Tropeninstitut am LMU Klinikum
  München" sogar in Ort und Art übereinstimmte.

### Der Ortsabgleich ist die zweite, unabhängige Prüfung

Sie hängt nicht am Namen und fällt darum anders. Ohne die Tabelle
`STADT_GLEICH` (Munich/München, Cologne/Köln, Hanover/Hannover, Freiburg im
Breisgau) meldet sie **9 Fehlalarme** und verdeckt die echten Funde.

Mit ihr bleiben **6 ungeprüfte Zuordnungen** übrig; sie werden auf der Seite
**nicht verlinkt**:

| Standort | aufgelöst auf | warum verworfen |
|---|---|---|
| Institut für Allgemeinmedizin | Institut für Allgemeinmedizin (LMU) | Ort Düsseldorf vs. München |
| Institut für Allgemeinmedizin, UK Lübeck | UK Schleswig-Holstein | Ort Lübeck vs. Kiel (zwei Campus, eine ROR) |
| Rheinhessen-Fachklinik Mainz | dieselbe | Ort Alzey vs. Mainz |
| Vestische Kinder- und Jugendklinik Datteln | Universität Witten/Herdecke | die Klinik ist nicht die Universität |
| LMU Klinikum München | Institut für Infektions- und Tropenmedizin | Teil statt Ganzes |
| Universität Heidelberg | Medizinische Fakultät Mannheim | andere Einrichtung |

### ⚠ Zwei Fehler in der handgeprüften Innofonds-Trägerliste

`innovationsfonds/db/ror_cache.json` führt mit Punktwert **100,0**:

```
„Universität Heidelberg"   -> „Medizinische Fakultät Mannheim"
„LMU Klinikum München"     -> „Institut für Infektions- und Tropenmedizin"
```

Beides ist falsch. Die Datei wird hier **nur gelesen** – sie gehört der
Innofonds-Sitzung. **Dort melden, nicht hier ändern.**

### ⚠ Vierte und fünfte Klasse von Rauschen: Hochschulart und Allgemeinwörter

Der Abgleich gegen ROR hat einen Fehler in **unseren eigenen** Daten
aufgedeckt. Fünf der 82 Standorte trugen die falsche Stadt – Ostfalia saß in
Kempten, die Leibniz Universität Hannover in Rosenheim, die Katholische
Hochschule Mainz in Freiburg. Die Ursache war keine Ortsnäherung, sondern
**falsche Verschmelzung**:

```
[19] „Ostfalia Hochschule für Angewandte Wissenschaften" (5 Studien) war:
       Hochschule für angewandte Wissenschaften Kempten
       Hochschule für angewandte Wissenschaften München
       Zürcher Hochschule für angewandte Wissenschaften   <- Schweiz!
[28] „Helmholtz Munich" (3 Studien) war:
       German Cancer Research Center          (Heidelberg)
       Helmholtz Zentrum München
       Universität Bremen, SOCIUM             (Bremen)
```

**„Hochschule für angewandte Wissenschaften" ist keine Einrichtung, sondern
ein Typ** – und die drei Wörter erfüllen die Zwei-Wort-Regel aus sich heraus,
genau wie die zweiteiligen Bundesländernamen. Dasselbe gilt für Wörter, die
jede Forschungseinrichtung von sich sagt: „German Cancer Research Center"
dockte über {german, research} an Helmholtz München an, SOCIUM Bremen über
{forschungszentrum, gesundheit}.

### ⚠ Und ein struktureller Fehler: der erste Treffer statt des besten

Die alte Fassung von `Abgleich.innofonds()` nahm den **ersten** Kern mit zwei
gemeinsamen Wörtern und brach ab. Die Reihenfolge der Kerne ist aber die
eines Wörterbuchs, also willkürlich:

- „Westfälische Hochschule" **hatte sich selbst im Bestand** – genommen wurde
  die „Hochschule für Technik und Wirtschaft des Saarlandes", weil sie früher
  in der Liste stand.
- „Technische Hochschule Rosenheim" wurde zur „Leibniz Universität Hannover".

Jetzt gilt: bester Treffer, gemessen an (1) Zahl der gemeinsamen Wörter,
(2) möglichst wenige **ungedeckte** Wörter im Namen des Kandidaten. Das
zweite Maß war nötig, weil ein Gleichstand sonst die Charité zerriss:
„Charité - Universitätsmedizin Berlin" {berlin, charit} und „Berliner
Institut für Gesundheitsforschung" {berlin, charit, health, institute} teilen
beide zwei Wörter – aber der erste Kandidat ist restlos gedeckt, der zweite
bringt zwei fremde Wörter mit. Echter Gleichstand ist kein Treffer.

Wirkung auf den Bestand: 532 Schreibweisen → **449** Standorte (vorher 471),
Profilseiten wieder **82** – aber ein anderes, richtiges 82. Die Charité
steht wieder mit 41 Studien aus 23 Schreibweisen zusammen.

Bekannte Untergrenze, bewusst in Kauf genommen: Einwortkerne treffen nur
über den exakten Namen. „Hochschule Rosenheim" (3 Studien) und „Technische
Hochschule Rosenheim, Fakultät …" (2 Studien) bleiben darum zwei Standorte,
obwohl es dieselbe Hochschule ist. Zu wenig verschmelzen ist hier der
kleinere Schaden als zu viel.

`py bestandsbezug.py --gegentest` prüft jetzt **fünf** Klassen:
Bundesländer · Fachgebiete · **Hochschularten** · **Allgemeinwörter** ·
Erfundenes.

### Was die Studien-DOIs zusätzlich hergeben

170 der 710 Studien (23,9 %) nennen Ergebnispublikationen, insgesamt 388
DOIs. Probe über 100 davon gegen OpenAlex:

```
in OpenAlex gefunden            : 94 von 100 (94,0 %)
Arbeiten ohne ROR-Einrichtung   : 0
```

Das ist ein belastbarer Weg zu **Fachgebiet und Mitwirkenden auf
Studienebene** – das OpenAlex-Subfield des ersten Topics ergab Public Health
(12), General Health Professions (11), Clinical Psychology (7), Pediatrics
(6), Epidemiology (4). **Noch nicht eingebaut**, und bei Einbau zu
kennzeichnen: Die Einrichtungen einer Publikation sind alle Mitautoren einer
Multizenterstudie, nicht der Forschungsstandort.

### Neue Kette

```
holen -> hubbezug -> bauen -> standorte -> seite
                                 ^
                       repositorien.py (eigener Schritt, braucht Netz)
```

`repositorien.py` schreibt `daten/repositorien.json`; `standorte.py` liest es
und baut daraus den Kasten **„Die Einrichtung im Netz"** – Netzauftritt,
anklickbares Publikationsverzeichnis mit Zahl der Arbeiten, ROR-Kennung.
Er erscheint auf **68 der 82** Profilseiten; fehlt die Datei, bleibt der
Kasten leer und das Skript sagt das.

## Publikationen, Verzeichnisse und das Selbsteintragen (01.11.2026)

Drei Aufträge an einem Tag: den DOI-Weg gehen, zu jeder Einrichtung **alle
Verzeichnisse** verlinken, in denen sie vorkommt, und den Verantwortlichen
eine Möglichkeit geben, **selbst** einzutragen – Repositorien, neue
Studiengänge, Professuren, Stellen, eigene Kongresse.

### 1. Der DOI-Weg: `doi_bezug.py`

170 der 710 Studien nennen Ergebnispublikationen, 388 DOI-Angaben, davon
377 eindeutig. Über `filter=doi:a|b|…` in Stapeln zu 50 gegen OpenAlex:

```
Arbeiten gefunden : 357 von 377 (94,7 %)
Studien mit Fach  : 157 von 710 (22,1 %)
Einrichtungen     : 583  (MITAUTOREN!)
```

Der eigentliche Gewinn steht nicht in diesen Zahlen, sondern in der
**Vereinigung** mit dem bisherigen Weg über den Einrichtungsnamen:

```
Fach aus dem Namen :  136  (19,2 %)
Fach aus dem DOI   :  157  (22,1 %)
   davon neu       :  116
ZUSAMMEN           :  252  (35,5 %)
```

Fast eine Verdopplung. Die beiden Systematiken werden **nicht vermischt**:
Der Namensweg liefert deutsche Fachgebiete, OpenAlex eine englische
Systematik. Beide stehen getrennt auf der Seite, jede mit ihrer Herkunft.
Übersetzt wird nichts – siehe [[in-eigenen-worten-erfindet]].

Der Kasten „Aus den Ergebnispublikationen" nennt die mitwirkenden
Einrichtungen mit einem Satz, der dort stehen bleiben muss:

> **Das sind Mitautoren, nicht Forschungsstandorte.** Bei einer
> Multizenterstudie stehen hier die Partner aller beteiligten Häuser — wer
> die Studie leitet, sagt diese Liste nicht. Sie zählt auch nicht in die
> Studienzahl dieses Standorts.

Der Gegentest (`py doi_bezug.py --gegentest`) prüft vor allem die
DOI-Normalisierung – 14 Fälle, davon 7 **negative**: „siehe
Publikationsliste", „PMID 12345678", „10.1055" ohne Schrägstrich. Ohne das
wandert Müll in die Stapelabfrage und drückt die Fundquote, ohne dass man
den Grund sieht. Dazu 11 Prüfungen der Zuordnung, darunter: Eine
Einrichtung, die in zwei Arbeiten derselben Studie steht, darf die Studie
nur **einmal** zählen.

### 2. Alle Verzeichnisse: `verzeichnisse.py`

**Wikidata ist die Drehscheibe.** Über die Eigenschaft P6782 (ROR-ID) hängen
dort die Kennungen aller übrigen Verzeichnisse – mit je einer aufrufbaren
Einzelseite:

```
 52  Wikidata-Datenobjekt       52  Wikipedia-Artikel
 50  VIAF                       50  GRID
 49  Gemeinsame Normdatei (DNB) 45  ISNI
 22  Crossref-Förderkennung      4  Scopus-Affiliation
  9  re3data
```

384 Verweise auf 53 der 65 Standorte.

⚠ **Eine Falle, die lautlos null Treffer liefert:** Wikidata führt P6782 als
**blanke** Kennung (`001w7jn25`), nicht als Adresse. Fragt man mit
`https://ror.org/001w7jn25`, kommen null Zeilen zurück – und eine leere
Antwort ist kein Fehler, das Skript läuft sauber durch und schreibt nichts.
Genau so ist der erste Lauf ausgegangen.

Zweite Falle: Wikidata liefert ein **Kreuzprodukt**. Hat ein Haus zwei
Netzadressen und drei VIAF-Nummern, kommen sechs Zeilen. Je Feld wird die
erste Angabe genommen; der Gegentest prüft das.

**re3data trägt keine ROR-Kennung**, nur `institutionName`. Also wieder ein
Namensabgleich – aber **nicht** der aus `repositorien.py`:

> Der dortige Wächter verlangt das Kopfwort in **beide** Richtungen, weil
> ein Kandidat mit fremdem Kopfwort *enger* ist als die Anfrage. Für
> Einrichtungen stimmt das. Ein Repositorium ist aber **absichtlich** enger
> als sein Haus: „Zentrale Biomaterialbank der Charité" hat das Kopfwort
> „zentrale", das die Charité nicht kennt – und flog raus.

`traegt_repo()` prüft darum nur die Hinrichtung. Bekannte Untergrenze,
bewusst in Kauf genommen: Eine Einrichtung ganz ohne unterscheidendes Wort –
„Universitätsklinikum Freiburg" ist nur Art und Ort – findet nichts.
„FreiDok plus" bleibt unverbunden. Die Gegenprobe zeigt den Grund: Wer hier
lockerer wird, hängt die *Universität* Freiburg an das *Universitätsklinikum*
Freiburg. Beide Fälle stehen als `False` im Gegentest.

**Was nicht geht – gemessen, nicht vermutet:**

| Verzeichnis | Befund |
|---|---|
| OpenDOAR | HTTP **403** auf alles, auch auf die reine Webseite. Braucht einen kostenlosen Sherpa-Schlüssel. Wäre das vollständigste. |
| GERiT (DFG) | kein Endpunkt; `gerit.org` antwortet nicht einmal mit Fehlercode, `/api/…` gibt 404 |
| FIS-Landkarte | baut sich im Browser auf, kein Export |

Das steht so auch auf jeder Profilseite. Ein Verzeichnis, das wir nicht
prüfen können, wird nicht verlinkt – siehe [[auswahl-nennt-was-fehlt]].

### 3. ⚠ Die ROR-Kennung führt zusammen – und die Kette fing an zu schwingen

Beim Abgleich fiel auf: **11 ROR-Kennungen gehörten 22 Standorten.**
Siebenmal dasselbe Haus in Heidelberg (Klinikum plus sechs Abteilungen),
dreimal Lübeck, dazu Hannover, Bonn, Köln, Witten/Herdecke, Halle,
Rosenheim, Mainz, Würzburg, Erlangen.

Der Namensabgleich kann das nicht finden: „Universitätsklinikum Heidelberg"
und „Neurologische Klinik, Universitätsklinikum Heidelberg" teilen **kein**
unterscheidendes Wort – Heidelberg ist Ortsrauschen. Die ROR-Kennung ist das
zweite, namensunabhängige Merkmal, und sie fällt anders.

`nach_ror()` in `standorte.py` führt danach zusammen: 18 weitere Standorte,
**Profilseiten 83 → 65**. Heidelberg steht jetzt mit 25 Studien aus 9
Schreibweisen zusammen.

⚠ **Blind darf man ihr nicht folgen.** In der Innofonds-Trägerliste führt ROR
einen allgemeinen Satz „AOK", auf dem *AOK Bundesverband*, *AOK Hessen* und
*AOK NordWest* gelandet sind – drei verschiedene Körperschaften. Sperre:
Nennen beide Namen einen Ort oder ein Bundesland und sind diese
**verschieden**, bleiben sie getrennt. Die Sperre fängt den AOK-Fall nur zur
Hälfte („AOK Hessen" gegen „AOK Bundesverband" nennt nur einer einen Ort);
hier schadet das nicht, weil Kostenträger gar nicht Standort werden – wer
die Regel woanders benutzt, muss das wissen.

⚠⚠ **Und der Fehler, den erst das Nachmessen zeigte: Die Kette schwang.**

`repositorien.py` läuft auf dem Ergebnis von `standorte.py`, und
`standorte.py` liest jetzt `repositorien.json`. Hing die Zuordnung am
**Standortnamen**, fand der nächste Durchgang die schon verschmolzenen
Häuser als Einzelgruppen vor und löste die Verschmelzung wieder auf:

```
83 -> 65 -> 83 -> 65 -> 83 ...
```

Jeder einzelne Lauf sah dabei völlig gesund aus. Aufgefallen ist es nur,
weil die Kette **zweimal hintereinander** gelaufen ist.

Behoben, indem `repositorien.json` die **Schreibweisen** aus dem Register
mitführt und `nach_ror()` danach gruppiert. Schreibweisen ändern sich nie,
also steht die Gruppierung nach dem ersten Durchgang fest. Nachgemessen über
drei volle Durchgänge:

```
Durchgang 1: 83 Standorte -> 18 verschmolzen -> 65
Durchgang 2: 65 Standorte -> 18 verschmolzen -> 65
Durchgang 3: 65 Standorte -> 18 verschmolzen -> 65
```

`py standorte.py --gegentest` prüft das seitdem ausdrücklich mit: *„zweiter
Durchgang ändert nichts"*.

### 4. ⚠ Zum zweiten Mal: ein Variablenname aus einem anderen Kasten

`zeilen` gehört in `standorte.py` dem Fach-, Ethik- und Zentrenkasten. Mein
neuer Netzkasten benutzte denselben Namen – aber nur **innerhalb** von
`if rep and rep.get("geprueft")`. Bei jedem Standort ohne geprüfte Zuordnung
stand in `zeilen` darum noch der Wert des **Ethikkastens**, eine
Zeichenkette; `"".join(zeilen)` zerlegte sie in Einzelzeichen und baute sie
wieder zusammen. Auf der Seite „Kleine Riesen Nordhessen gGmbH" stand unter
*Die Einrichtung im Netz*: „Ethikkommission Fachbereich Humanwissenschaften
Universität Kassel · 2".

Heißt jetzt `netzzeilen` und wird **vor** dem `if` vorbelegt. Beim ersten Mal
war es `verzeichnis` gegen die Verzeichnisliste – dieselbe Falle, zweite
Auflage. Siehe [[bauketten-nicht-im-scratchpad]]: lange Schleifen mit vielen
Kästen brauchen Namen mit Präfix.

### 5. Selbst eintragen: das Formular je Standort

Der Kasten „Sie sind hier verantwortlich?" ist von vier auf **sieben
Abschnitte mit 20 Feldern** gewachsen:

| Abschnitt | Felder |
|---|---|
| Zugang | dienstliche E-Mail, Name und Funktion |
| Die Einrichtung im Netz | **Repositorien** (mehrzeilig), Netzauftritt, Zuordnung richtig? (ja / falsche Einrichtung / nur ein Teil) mit Freitext |
| Lehre | **Studiengänge**, Promotions- und Weiterbildungsangebote |
| Menschen | **Professuren**, wissenschaftliche Mitarbeitende, Ansprechperson |
| Offene Stellen | sucht Personal?, **Ausschreibungen** mit Frist |
| Eigene Kongresse und Veranstaltungen | **Veranstaltungen**, regelmäßige Reihen |
| Forschung | Veröffentlichungen, Bücher, Methoden, fehlende Studien, Kooperationen |

Zwei Entscheidungen, die man nicht übersehen darf:

1. **Der Netzkasten erscheint IMMER** – auch wenn wir nichts gefunden haben.
   Gerade dann: Er ist die Einladung, es selbst einzutragen. Ein
   stillschweigend fehlender Kasten sieht für die Verantwortlichen so aus,
   als sei nichts zu melden. Ohne Fund steht dort: *„Zu diesem Standort
   haben wir keinen gesicherten Verzeichniseintrag … dann verlinken wir
   lieber nichts als das Falsche."*
2. **Der Verweis springt ins richtige Feld.** `a.zum-formular` mit
   `data-feld="repositorien"` klappt das `<details>` auf, hebt den Kasten
   kurz hervor und setzt den Fokus. Ein bloßes `#eintragen` landet auf einer
   Überschrift, und der Mensch sucht selbst weiter.

Ausschreibungen zeigen wir **mit Frist** und nehmen sie danach von der
Seite; das Formular sagt das und verlangt die Frist.

Der `ENDPUNKT` ist weiterhin leer – das Formular sagt das ehrlich und sendet
nichts. Solange bleibt alles davon ein Prototyp.

### Neue Kette

```
holen -> hubbezug -> bauen -> standorte -> seite
                                 ^  ^
                   repositorien.py  |   (Netz, einmal je Standortsatz)
                   verzeichnisse.py |   (Netz, baut auf repositorien.json)
                   doi_bezug.py ----+   (Netz, unabhängig)
```

`repositorien.py` und `standorte.py` sind **wechselseitig** – darum: nach
einer Änderung an der Zusammenführung die Kette **zweimal** laufen lassen
und prüfen, ob die Standortzahl stehen bleibt.

## Karte, Ranglisten, Personen — und was die 710 wirklich sind (01.11.2026)

### ⚠ Zuerst das Wichtigste: Die 710 sind ein Ausschnitt

Auf die Frage „das sollen alle Versorgungsforschungsstudien eines Jahres
sein? der letzten 10? das kann nicht sein" — nachgemessen am ganzen Export:

```
DRKS-Gesamtexport                              22.737 Einträge
davon mit Versorgungsbezug (ganzes Register)    1.298   (5,7 %)
davon unter CC BY 4.0, also zeigbar               710   (55 %)
──────────────────────────────────────────────────────────────
Es gibt sie, wir dürfen sie nur nicht zeigen      588
```

**Die Lizenz ist in Wahrheit ein Zeitfilter.** CC BY 4.0 gilt nur für
Einträge ab 2025 registriert **oder aktualisiert**:

```
 Jahr   VF gesamt   davon zeigbar
 2015         42          1    2 %
 2018         79         19   24 %
 2021        123         45   37 %
 2024        117         88   75 %
 2025        151        151  100 %
 2026        225        225  100 %
```

Die 53 Prozent aus 2025/26 sind kein Forschungsboom, sondern ein
Lizenzartefakt. Ältere Einträge sind fast nur dabei, wenn sie noch laufen
und darum aktualisiert wurden — **abgeschlossene Forschung fehlt am
stärksten.**

Daraus folgt für jede Auswertung auf dieser Grundlage: Sie misst, **wer
zuletzt registriert hat**, nicht wer über die Jahre am meisten geforscht
hat. Dieser Satz steht so unter der Rangliste und muss dort bleiben.

`bauen.py` zählt den Versorgungsbezug seitdem im **ganzen** Register mit
(`vf_im_register`, `vf_nicht_zeigbar`) — gezählt, nicht wiedergegeben. Der
Kasten „Dies ist ein Ausschnitt, kein Gesamtbild" steht **über** den
Kennzahlen, die er einordnet, und ist **nicht wegklickbar**. Der alte Satz
„Nur 44 Prozent des Registers" war eine Aussage über Datensätze und hat die
eigentliche Zahl verschwiegen.

### Das Mitmach-Formular: aus der Lücke eine Einladung

Die Lücke ist lösbar, wenn die Einrichtungen selbst eintragen. Darum auf
der Hauptseite `#mitmachen` — für alle, auch ohne Profilseite:

| Abschnitt | Felder |
|---|---|
| Zugang | Einrichtung, dienstliche E-Mail, Name und Funktion |
| **Ist das eine neue Einrichtung?** | neu / bestehend, seit wann, Arbeitsschwerpunkte |
| Studien, die hier fehlen | Studien (auch nicht registrierte), Ergebnispublikationen |
| Die Einrichtung im Netz | Repositorien, Netzauftritt, ROR-Kennung |
| Lehre, Menschen, Stellen, Veranstaltungen | je ein Feld |

**Der Fall, der das Formular überhaupt nötig macht:** Eine neu gegründete
Einrichtung kann in einer Karte aus dem Studienregister **gar nicht**
auftauchen, solange sie keine Studie registriert hat. Die Medizinische
Universität Lausitz – Carl Thiem ist genau so ein Fall. Der Text sagt das
ausdrücklich und nennt sie als Beispiel: *„Tragen Sie sich trotzdem ein:
Wir legen die Einrichtung an, auch wenn das Feld ‚Studien' leer bleibt."*

### Die Karte: mitgeliefert, nicht nachgeladen

`kontur.py` holt **einmal** den Umriss Deutschlands aus Natural Earth
(1:50m, **Public Domain**, über das Paket `world-atlas`) und entpackt das
TopoJSON hier — Bogenketten, negative Indizes, Delta-Kodierung,
Quantisierung. Auf der Seite stehen nur fertige Koordinaten: 6 Ringe,
561 Punkte, 12 KB.

**Warum keine Kartenbibliothek:** Ein Kachelserver bekommt jede Bewegung
der Lesenden zu sehen. Das Versprechen der Knowledge-Hubs lautet „keine
Cookies". Also Umriss einbetten, SVG zeichnen, fertig — keine fremden
Aufrufe.

⚠ **Der Fehler, den der erste Versuch gemacht hat:** Längengrade in **Grad**
und Breitengrade in **Mercator-Einheiten** (die sind im Bogenmaß) gemischt.
Die Spannweiten unterscheiden sich dann um den Faktor 57 — Deutschland wird
zu einem waagerechten Strich. Beide Achsen gehören ins Bogenmaß.

Kreise nach **Fläche**, nicht nach Radius: Ein Kreis mit doppeltem Radius
sieht viermal so groß aus und übertreibt den Unterschied.

52 der 65 Standorte sind eingezeichnet. Die 13 ohne Punkt stehen als Satz
unter der Karte: *„ein Punkt an der falschen Stelle wäre schlimmer als
keiner."* Koordinaten nur aus **geprüften** Zuordnungen (`repositorien.py`,
OpenAlex `geo`, mitgeprüft vom bestehenden Ortsabgleich).

### Personen je Standort — ausdrücklich ohne Rangplatz

`doi_bezug.py` führt jetzt auch die Autor:innen mit: 3.775 Nennungen,
2.388 verschiedene Personen, 69,5 % mit ORCID. Je Person wird die
**Reihenfolge der Autorenschaft** (first / middle / last) und ihre
**eigene ROR-Kennung in dieser Arbeit** gespeichert — ohne letzteres ließe
sich auf einer Standortseite nicht sagen, wer von dort kommt und wer
Mitautor:in eines anderen Hauses ist.

⚠ **Warum es keine Hitliste der Forschenden gibt**, obwohl die Daten es
hergäben:

```
100 Arbeiten -> 1.205 Nennungen -> 871 Personen -> 1,38 Nennungen je Person
```

1,38 ist die Antwort: **Es gibt keine Spitze.** Die vermeintliche Spitze
kam aus einer einzigen Studie — DRKS00024494, ein Register für
immunvermittelte Neuropathien in Bochum, das **21 DOIs** nennt, mehr als
jede andere der 710. Ihre vier Erstautor:innen erschienen dadurch je sechs-
bis siebenmal. Die Liste hätte nicht gemessen, wer viel forscht, sondern
welche Studie viele Publikationen eingetragen hat:

```
Median DOIs je Studie        :  1
Die 5 größten Studien stellen: 80 von 388 DOIs = 21 %
```

Geprüft wurde auch, ob OpenAlex eine saubere Grundlage hergibt: **Es gibt
dort kein Thema „Versorgungsforschung"** — die Suche liefert
Krebsfrüherkennung und Stadtgrün. Nach Werkzahl sortiert käme Hermann
Brenner mit 3.240 Arbeiten; das misst ein Lebenswerk, nicht unser Feld.

Statt einer Rangliste darum auf jeder Profilseite „Wer hier veröffentlicht
hat", sortiert, aber **ohne Platzziffern**, mit ORCID-Verweis und dem Satz:
*„Keine Rangliste. … Wer hier fehlt, hat nicht weniger geforscht, sondern
führt keine Studie mit Ergebnis-DOI."*

### ⚠ Die Schwelle von 3 Punkten: geprüft und bestätigt

Der Verdacht war, die 353 Studien genau an der Schwelle hingen an
Allerweltswörtern wie „Lebensqualität" (244 Treffer, häufigster Auslöser).
Am **Rohtext** nachgemessen — nicht am gekürzten `kurz`-Feld, das unter
400 Zeichen abschneidet und beim ersten Versuch 111 falsche „keine
Treffer" erzeugte:

```
Woraus bestehen die 3 Punkte?
   2+1     227 Studien
   3       110 Studien   <- EIN Begriff der stärksten Klasse
   1+1+1    16 Studien   <- nur hier ist der Verdacht berechtigt
```

110 der 353 stehen auf einem einzigen Begriff der stärksten Klasse
(„Versorgungsforschung", „Routinedaten", „Regelversorgung"). Nur **16**
Studien ruhen ausschließlich auf 1-Punkt-Begriffen.

**Die unabhängige Gegenprobe** — nicht der Text, sondern das Fachgebiet der
Ergebnispublikationen in OpenAlex:

```
Punkte          Studien     VF-nah     Anteil
2 (ausgeschlossen)   79        26        33 %   <- Gegentest
3 (Schwelle)         52        25        48 %
4-5                  63        40        63 %
6-8                  25        17        68 %
```

Monoton steigend, und die **ausgeschlossenen** Studien schneiden deutlich
schlechter ab als die an der Schwelle. Damit ist die Schwelle eine
Messung und keine Willkür — siehe [[massstab-braucht-gegentest]].

**Entscheidung: nichts entfernt.** Die Schwelle leistet nachweislich
Arbeit. Dass die Trefferwahrscheinlichkeit an der Schwelle mit 48 % deutlich
unter den 63–68 % darüber liegt, ist eine ehrliche Eigenschaft der Daten,
kein Fehler. Offen (Peters Entscheidung): ob die Punktzahl als Maß für die
Sicherheit des Versorgungsbezugs auf der Seite sichtbar werden soll.
