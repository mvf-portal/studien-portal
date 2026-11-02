# -*- coding: utf-8 -*-
"""Was wird ausgeliefert, und darf es das?

WARUM DIESE DATEI
-----------------
studien.m-vf.de ist seit dem 01.11.2026 live, und GitHub Pages liefert
JEDE Datei des Repos aus, nicht nur die verlinkten. Am 02.11.2026
gemessen:

    https://studien.m-vf.de/standort-vorlage.html   HTTP 200

Diese Datei ist eine BAUVORLAGE. Wer sie aufrief, bekam eine Seite mit
{{DNVF}}, {{ENDPUNKT}}, {{ETHIK}}, {{HUBS}}, {{INNO}} und {{KENNZAHLEN}}
im Klartext. Dasselbe galt fuer vorlage.html.

⚠ EINE DATEI IM REPO IST EINE SEITE IM NETZ. Niemand hat sie verlinkt,
und sie war trotzdem oeffentlich. Verlinkung ist kein Schutz.

Geprueft wird dreierlei:
  1. Keine ausgelieferte Seite traegt unausgefuellte Platzhalter.
  2. Keine ausgelieferte Datei traegt Mailadressen (ausser den eigenen
     Hausadressen, die absichtlich dort stehen).
  3. GEGENPROBE: Eine Datei mit einem Platzhalter MUSS auffallen.

  py kontrolle_auslieferung.py
"""
import pathlib
import re
import subprocess
import sys

HIER = pathlib.Path(__file__).resolve().parent

# Unsere eigenen Adressen. Die stehen absichtlich auf den Seiten.
EIGENE = {"info@m-vf.de", "stegmaier@m-vf.de", "redaktion@m-vf.de"}

# Musteradressen, die in Formularen und Pruefaellen stehen sollen.
#
# ⚠ EINZELN AUFFUEHREN, NICHT NACH DOMAENE FREIGEBEN. "gmail.com"
# pauschal zu erlauben hiesse, dass eine echte private Adresse
# durchrutscht - genau die, die am 02.11.2026 in repositorien.py stand.
# Die beiden Freemail-Faelle pruefen, dass ein Freemailer NICHT als
# Einrichtung gilt, dafuer muss die Domaene echt sein.
MUSTER = {"name@einrichtung.de", "max.mustermann@example.org",
          "vorname.name@hochschule.de", "a@fremd.de",
          "beispiel@gmail.com", "x@web.de"}

# Die von der IETF fuer Beispiele reservierten Endungen (RFC 2606/6761).
# Was dort endet, kann niemandem gehoeren.
ERFUNDEN = (".example", ".invalid", ".test", ".localhost",
            "@example.com", "@example.org", "@example.net")

PLATZHALTER = re.compile(r"\{\{[A-Z_]+\}\}|<!--__[A-Z_]+__-->")

# ⚠ ENGE REGEL. Die erste Fassung meldete 69 Dateien, und fast alles war
# Rauschen: `world-atlas@2.0.2` ist eine Paketversion, `info@m-vf.de.`
# unsere eigene Adresse mit Satzpunkt dahinter, `name@einrichtung.de` ein
# Formularbeispiel. Eine Prüfung mit 69 Fehlalarmen wird weggesehen, und
# dann faellt der eine echte Fund nicht auf.
#
# Die Endung muss aus Buchstaben bestehen, sonst ist es keine Adresse.
MAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)*\.[A-Za-z]{2,24}\b")


def echte_fremde(text):
    """Fremde Adressen, ohne Rauschen und ohne unsere eigenen."""
    aus = set()
    for m in MAIL.findall(text):
        k = m.lower().rstrip(".,;:)")
        if k in EIGENE or k in MUSTER:
            continue
        if any(k.endswith(x) or x in k for x in ERFUNDEN):
            continue
        # Paketangaben wie world-atlas@2.0.2 haben Ziffern als Endung.
        endung = k.rsplit(".", 1)[-1]
        if not endung.isalpha():
            continue
        aus.add(k)
    return aus


def ausgeliefert():
    """Jede Datei, die GitHub Pages veroeffentlichen wuerde.

    ⚠ NICHT DAS DATEISYSTEM FRAGEN, SONDERN GIT. Ausgeliefert wird, was
    im Repo steht - nicht, was hier herumliegt. Ein Arbeitsbaum voller
    ungetrackter Dateien taeuscht in beide Richtungen.

    Dateien und Ordner mit fuehrendem Unterstrich laesst Jekyll weg. Das
    gilt nur, solange keine .nojekyll danebenliegt.
    """
    roh = subprocess.run(["git", "ls-files"], cwd=HIER,
                         capture_output=True, text=True, check=True).stdout
    jekyll_aus = (HIER / ".nojekyll").exists()
    aus = []
    for z in roh.splitlines():
        if not z.strip():
            continue
        teile = pathlib.PurePosixPath(z).parts
        if not jekyll_aus and any(t.startswith("_") for t in teile):
            continue
        aus.append(z)
    return aus, jekyll_aus


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    dateien, jekyll_aus = ausgeliefert()
    print("Im Repo und damit ausgeliefert: %d Dateien" % len(dateien))
    if jekyll_aus:
        print("⚠ .nojekyll liegt vor: Dateien mit _ WERDEN ausgeliefert.")
    else:
        print("   Jekyll laeuft, Dateien mit fuehrendem _ bleiben draussen.")
    ok = True

    # ------------------------------------------- 1. Platzhalter
    print("\n1. Keine ausgelieferte Seite mit unausgefuellten Platzhaltern")
    schlimm = []
    for z in dateien:
        if not z.endswith((".html", ".htm")):
            continue
        p = HIER / z
        if not p.exists():
            continue
        t = p.read_text(encoding="utf-8", errors="replace")
        fund = sorted(set(PLATZHALTER.findall(t)))
        if fund:
            schlimm.append((z, fund))
    ok = ok and not schlimm
    print("   %s %d von %d Seiten sauber"
          % ("ok " if not schlimm else "FEHLER",
             sum(1 for z in dateien if z.endswith(".html")) - len(schlimm),
             sum(1 for z in dateien if z.endswith(".html"))))
    for z, fund in schlimm:
        print("      %s  %s" % (z, " ".join(fund[:5])))

    # ------------------------------------------- 2. Fremde Mailadressen
    print("\n2. Keine fremden Mailadressen in ausgelieferten Dateien")
    # ⚠ GENAU EINE AUSNAHME, UND SIE IST DIESE DATEI. Die Gegenprobe
    # unten MUSS Adressen enthalten, die wie echte aussehen, sonst prueft
    # sie nichts. Jede weitere Ausnahme waere ein Loch: Wer hier einen
    # zweiten Namen eintraegt, schaltet die Pruefung fuer eine Datei ab.
    EIGENE_DATEI = pathlib.Path(__file__).name
    ausnahmen = {EIGENE_DATEI}
    if ausnahmen != {EIGENE_DATEI}:
        raise SystemExit("Nur diese Datei darf ausgenommen sein.")

    treffer = []
    for z in dateien:
        if pathlib.PurePosixPath(z).name in ausnahmen:
            continue
        p = HIER / z
        if not p.exists() or p.stat().st_size > 20_000_000:
            continue
        try:
            t = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        fremd = echte_fremde(t)
        if fremd:
            treffer.append((z, sorted(fremd)))
    ok = ok and not treffer
    print("   %s %d Dateien mit fremden Adressen"
          % ("ok " if not treffer else "FEHLER", len(treffer)))
    for z, fremd in treffer[:5]:
        print("      %s  %d Adressen, z. B. %s"
              % (z, len(fremd), ", ".join(fremd[:2])))

    # ------------------------------------------- 3. Tote interne Verweise
    #
    # ⚠ EIN KNOPF AUF JEDER SEITE IST EIN FEHLER AUF JEDER SEITE. Die
    # Netzleiste der 15 Themen-Hubs verweist auf „newsletter.html"
    # daneben. Dieses Angebot hat keine, und der Knopf fuehrte auf allen
    # Seiten ins Leere, auch auf der laengst veroeffentlichten
    # landkarte.html. Aufgefallen ist es erst beim Durchzaehlen der
    # Verweise, nicht beim Ansehen der Seite.
    print("\n3. Keine toten internen Verweise")
    tot = {}
    for z in dateien:
        if not z.endswith(".html"):
            continue
        p = HIER / z
        if not p.exists():
            continue
        t = p.read_text(encoding="utf-8", errors="replace")
        for ziel in set(re.findall(
                r'href="([^"#?:]+\.html)(?:[#?][^"]*)?"', t)):
            if ziel.startswith(("http", "//")):
                continue
            if (p.parent / ziel).exists() or (HIER / ziel).exists():
                continue
            tot.setdefault(ziel, set()).add(z)
    ok = ok and not tot
    print("   %s %d Seiten geprueft, %d tote Ziele"
          % ("ok " if not tot else "FEHLER",
             sum(1 for z in dateien if z.endswith(".html")), len(tot)))
    for ziel, wo in sorted(tot.items()):
        print("      %-24s auf %d Seiten, z. B. %s"
              % (ziel, len(wo), sorted(wo)[0]))

    # ------------------------------------------- 4. Gegenprobe
    #
    # ⚠ SIE MUSS DIESELBE PRUEFUNG AUFRUFEN WIE DER ERNSTFALL, nicht eine
    # vereinfachte Fassung daneben. Genau dieser Fehler steckte am
    # 02.11.2026 in teile/kontrolle_felder.py.
    print("\n4. GEGENPROBE")
    kaputt = "<html>{{NAME}} und <!--__INHALT__--></html>"
    gefunden = sorted(set(PLATZHALTER.findall(kaputt)))
    gut = gefunden == ["(nichts)"] or len(gefunden) == 2
    ok = ok and gut
    print("   %s eine Seite mit Platzhaltern wird erkannt: %s"
          % ("ok " if gut else "FEHLER", " ".join(gefunden) or "NEIN"))
    sauber = PLATZHALTER.findall("<html><p>Alles ausgefuellt.</p></html>")
    gut2 = not sauber
    ok = ok and gut2
    print("   %s eine saubere Seite loest keinen Fehlalarm aus"
          % ("ok " if gut2 else "FEHLER"))
    # Beide Richtungen und das bekannte Rauschen, mit derselben Funktion.
    fremd_probe = echte_fremde(
        "echte.person@uni-irgendwo.de info@m-vf.de. world-atlas@2.0.2 "
        "name@einrichtung.de vorname.name@institut.example "
        "beispiel@gmail.com privat@gmail.com")
    gut3 = fremd_probe == {"echte.person@uni-irgendwo.de",
                           "privat@gmail.com"}
    ok = ok and gut3
    print("   %s echte Adressen erkannt (auch eine private bei einem\n"
          "       Freemailer), eigene, Muster, .example und Paketversion "
          "nicht:\n       %s"
          % ("ok " if gut3 else "FEHLER", sorted(fremd_probe)))

    print("\n" + ("Auslieferung bestanden."
                 if ok else "AUSLIEFERUNG GESCHEITERT."))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
