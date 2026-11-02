# -*- coding: utf-8 -*-
"""Kommt jedes Formularfeld beim Endpunkt auch an?

WARUM DIESE DATEI
-----------------
Am 02.11.2026 ging eine Probe-Einsendung an studien.php. Die Antwort war
`{"ok":true}`, und beim Abholen stand in `angaben` genau ein Feld:
`einrichtung`. Name, Bemerkung und die Formularkennung waren weg.

⚠ DER ENDPUNKT ANTWORTET "OK" FUER FELDER, DIE ER VERWIRFT. Seine
Feldliste FELDER ist eine Weissliste, und was nicht darin steht, fliegt
still weg. Wer nur auf die Antwort sieht, haelt das Formular fuer
dicht - und die Leute tippen ihren Namen in ein Feld, das niemand
jemals liest.

Diese Pruefung vergleicht die Feldnamen der gebauten Seiten gegen die
Weissliste im PHP und nennt beide Richtungen: Felder, die wir senden und
die verworfen werden, und Felder der Liste, die kein Formular mehr
benutzt.

  py teile/kontrolle_felder.py
"""
import pathlib
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
W = pathlib.Path(__file__).resolve().parent.parent
PHP = (pathlib.Path(
    r"C:\Users\Stegmaier\Documents\Claude-Daten\knowledge-hubs"
    r"\mvf-server\studien\studien.php"))

# Felder, die das Skript selbst setzt oder die nicht in angaben gehoeren.
EIGEN = {"email", "art", "was", "standort", "ror", "quelle"}
# name-Attribute, die keine Formularfelder sind.
KEIN_FELD = {"viewport", "description", "claude:viewport-fit-sides"}


def weissliste():
    t = PHP.read_text(encoding="utf-8", errors="replace")
    m = re.search(r"const FELDER = \[(.*?)\];", t, re.S)
    if not m:
        raise SystemExit("FELDER im PHP nicht gefunden: %s" % PHP)
    return set(re.findall(r"'([a-z0-9_]+)'\s*=>", m.group(1)))


def felder_der_seite(datei):
    t = (W / datei).read_text(encoding="utf-8")
    roh = set(re.findall(r'<(?:input|textarea|select)[^>]*\bname="([^"]+)"',
                         t))
    return {f for f in roh if f not in KEIN_FELD}


def fassung_lokal():
    """Die Kennung, die in der Datei neben uns steht."""
    t = PHP.read_text(encoding="utf-8", errors="replace")
    m = re.search(r"const FASSUNG = '([^']+)'", t)
    return m.group(1) if m else ""


def fassung_server():
    """Die Kennung, die der Server von sich selbst meldet.

    Rueckgabe: (kennung, grund). Bei leerer Kennung sagt der Grund, warum
    - nicht erreichbar, oder eine Fassung ohne Kennung (also alt).
    """
    import json
    import urllib.error
    import urllib.request
    adr = ("https://www.monitor-versorgungsforschung.de/studien/"
           "studien.php")
    rumpf = json.dumps({"art": "probe"}).encode("utf-8")
    # ⚠ OHNE EIGENE KENNUNG ANTWORTET CLOUDFLARE MIT 403. Mit der
    # Vorgabe von urllib ("Python-urllib/3.x") kam 403 Forbidden, waehrend
    # dasselbe curl 200 bekam - und die Pruefung las das als "kein Netz".
    bitte = urllib.request.Request(
        adr, data=rumpf,
        headers={"Content-Type": "application/json",
                 "Origin": "https://studien.m-vf.de",
                 "User-Agent": "MVF-Landkarte-Kontrolle/1.0 "
                               "(+https://studien.m-vf.de)"})
    try:
        with urllib.request.urlopen(bitte, timeout=25) as a:
            d = json.loads(a.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        # Eine Antwort IST eine Antwort. 403 heisst nicht "kein Netz",
        # sondern "abgewiesen" - das darf die Pruefung nicht verschlucken.
        return "", "abgewiesen mit HTTP %s" % e.code
    except (urllib.error.URLError, OSError, ValueError) as e:
        return "", "nicht erreichbar (%s)" % e
    if not d.get("ok"):
        return "", "Probe nicht ok: %r" % d
    f = d.get("fassung") or ""
    return f, "" if f else "Antwort ohne Kennung, also vor dem 02.11.2026"


def endpunkt_gesetzt():
    """Sendet eintragen.html ueberhaupt an den Server?"""
    s = (W / "standorte.py").read_text(encoding="utf-8")
    m = re.search(r'ENDPUNKT_EINTRAGEN = "([^"]*)"', s)
    return bool(m and m.group(1))


def verworfene(datei, erlaubt):
    """Welche Felder dieser Seite wirft der Endpunkt weg?

    ⚠ DIE EIGENTLICHE PRUEFUNG STEHT HIER UND NUR HIER. Vorher lag sie
    im Rumpf von main(), und die Gegenprobe baute sich daneben eine
    eigene, vereinfachte Fassung - sie fragte `"einrichtung" not in
    probe`, was durch die Konstruktion immer wahr ist. Die Gegenprobe
    pruefte also sich selbst und nie den Code, der im Ernstfall laeuft.

    Gefunden am 02.11.2026, nachdem zwei Nachbarsitzungen genau diese
    Gattung bei sich entdeckt hatten: eine Pruefung mit gutem Namen, die
    etwas anderes misst, als ihr Name sagt.
    """
    unsere = felder_der_seite(datei)
    return unsere, sorted(f for f in unsere
                          if f not in erlaubt and f not in EIGEN)


def main():
    erlaubt = weissliste()
    ok = True
    seiten = ["eintragen.html", "landkarte.html"]
    seiten += sorted(p.name for p in (W / "standort").glob("*.html"))[:1]

    for datei in seiten:
        if not (W / datei).exists():
            continue
        unsere, verworfen = verworfene(datei, erlaubt)
        gut = not verworfen
        ok = ok and gut
        print("%s %-22s %d Felder, %d verworfen"
              % ("ok " if gut else "FEHLER", datei, len(unsere),
                 len(verworfen)))
        for f in verworfen:
            print("      verworfen:", f)

    # Die andere Richtung. Kein Fehler, aber es sagt, wo die Liste
    # gewachsen ist, ohne dass ein Formular nachkam.
    alle = set()
    for datei in seiten:
        if (W / datei).exists():
            alle |= felder_der_seite(datei)
    ungenutzt = sorted(f for f in erlaubt if f not in alle and f not in EIGEN)
    print("   Hinweis: %d Felder der Weissliste benutzt kein Formular%s"
          % (len(ungenutzt), (": " + ", ".join(ungenutzt))
             if ungenutzt else ""))

    # ----------------------------------------------------- GEGENPROBE
    #
    # ⚠ SIE MUSS DIESELBE FUNKTION AUFRUFEN WIE DER ERNSTFALL. Sonst
    # prueft sie ihre eigene Hilfskonstruktion. Also: einer echten Seite
    # ein Feld aus der Weissliste nehmen und verlangen, dass
    # verworfene() es meldet.
    traeger = next((d for d in seiten
                    if (W / d).exists()
                    and "einrichtung" in felder_der_seite(d)), "")
    if not traeger:
        ok = False
        print("FEHLER GEGENPROBE: keine Seite mit 'einrichtung' gefunden")
    else:
        _, ohne = verworfene(traeger, erlaubt - {"einrichtung"})
        merkt_es = "einrichtung" in ohne
        _, mit = verworfene(traeger, erlaubt)
        still = "einrichtung" not in mit
        gut = merkt_es and still
        ok = ok and gut
        print("%s GEGENPROBE an %s: ohne 'einrichtung' meldet die Pruefung "
              "es (%s), mit 'einrichtung' schweigt sie (%s)"
              % ("ok " if gut else "FEHLER", traeger,
                 "ja" if merkt_es else "NEIN", "ja" if still else "NEIN"))

    # ------------------------------------------- Der Server, nicht die Datei
    lok = fassung_lokal()
    srv, grund = fassung_server()
    sendet = endpunkt_gesetzt()
    gleich = bool(srv) and srv == lok
    print("   Fassung hier %r, auf dem Server %r%s"
          % (lok, srv, (" (" + grund + ")") if grund else ""))
    if gleich:
        print("ok  Server traegt dieselbe Fassung")
    elif not srv and "nicht erreichbar" in grund:
        print("   Hinweis: ohne Netz nicht entscheidbar, kein Fehler")
    elif sendet:
        ok = False
        print("FEHLER Server ist hinter der Datei, aber eintragen.html "
              "sendet dorthin")
        print("       -> ENDPUNKT_EINTRAGEN in standorte.py leeren, bis "
              "eingespielt ist")
    else:
        print("   Hinweis: Server ist hinter der Datei. eintragen.html "
              "sendet nicht dorthin,")
        print("            sondern oeffnet die vorbereitete E-Mail. Kein "
              "Feld geht verloren.")
        print("            ENDPUNKT_EINTRAGEN scharf stellen, sobald die "
              "Fassungen gleich sind.")

    print("\n" + ("Felder bestanden." if ok else "FELDER GESCHEITERT."))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
