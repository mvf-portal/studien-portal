# -*- coding: utf-8 -*-
"""Kommt jeder Link der Suche auch an? Gemessen an den gebauten Seiten.

WARUM DIESE DATEI
-----------------
Die Suche verweist auf Sprungmarken: forschende.html#sundmacher-leonie.
Bis zum 01.11.2026 gab die Forschendenseite 90 Zeilen aus und keine
einzige Sprungmarke. Jeder dieser Links fuehrte auf den Seitenanfang, und
niemand hat es gemerkt, weil nichts es nachgemessen hat.

⚠ EIN LINK, DER NICHT ANKOMMT, SIEHT AUS WIE EIN LINK, DER ANKOMMT.
Darum laeuft diese Pruefung gegen die FERTIGEN Dateien, nicht gegen die
Daten. Wer sie gegen die Daten laufen laesst, prueft seine eigene
Absicht.

  py kontrolle_anker.py

Prueft:
  1. Jeder Personenlink der Suche hat sein id-Ziel in forschende.html.
  2. Jeder Institutionslink der Suche hat seine Datei in standort/.
  3. Keine Sprungmarke kommt zweimal vor. Zwei gleiche ids heissen, dass
     ein Link immer auf dieselbe von beiden Zeilen springt.
  4. Jede Zeile hat ein Ziel: eine Profilseite oder das Formular.
  5. GEGENPROBE: Eine erfundene Sprungmarke darf NICHT gefunden werden.
"""
import collections
import html
import json
import pathlib
import re
import sys

HIER = pathlib.Path(__file__).resolve().parent
DATEN = HIER / "daten"


def lade(name):
    p = DATEN / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def ids(datei):
    """Die Sprungmarken einer Seite, entmaskiert.

    ⚠ ENTMASKIEREN NICHT VERGESSEN. Im Quelltext steht
    id="n&#x27;doye-ramatoulaye", im Browser ist die Marke
    n'doye-ramatoulaye. Wer die rohen Zeichen vergleicht, meldet einen
    Fehler, den es nicht gibt - und uebersieht beim naechsten Mal einen,
    den es gibt.
    """
    t = (HIER / datei).read_text(encoding="utf-8")
    roh = re.findall(r'<div class="haus(?:[^"]*)" id="([^"]+)"', t)
    return [html.unescape(x) for x in roh], t


def zeilen_von(t):
    """Die Zeilen einer Liste, jede ganz.

    ⚠ NICHT MIT (.*?)</div></div> SCHNEIDEN. Das endet an der ersten
    doppelten Klammer, und die steht VOR dem Link zum Formular am
    Zeilenende. Die Pruefung meldete darum 4.074 Zeilen ohne Ziel, die
    alle eines haben.
    """
    stuecke = t.split('<div class="haus')[1:]
    return [s.split('<div class="haus')[0] for s in stuecke]


def main():
    ok = True
    S = lade("suchindex.json")
    eintraege = S.get("eintraege") or []

    # ----------------------------------------------- 1. Personenlinks
    anker, roh_f = ids("forschende.html")
    menge = set(anker)
    links = [e["u"] for e in eintraege if e["t"] == "person"]
    fehlt = [u for u in links
             if u.split("#")[-1] not in menge]
    gut = not fehlt
    ok = ok and gut
    print("1. Personenlinks der Suche, die ankommen")
    print("   %s %d von %d" % ("ok " if gut else "FEHLER",
                               len(links) - len(fehlt), len(links)))
    for u in fehlt[:5]:
        print("      kein Ziel:", u)

    # ----------------------------------------------- 2. Institutionen
    links_i = [e["u"] for e in eintraege if e["t"] == "institution"]
    fehlt_i = [u for u in links_i if not (HIER / u).exists()]
    gut = not fehlt_i
    ok = ok and gut
    print("2. Institutionslinks der Suche, die eine Datei haben")
    print("   %s %d von %d" % ("ok " if gut else "FEHLER",
                               len(links_i) - len(fehlt_i), len(links_i)))
    for u in fehlt_i[:5]:
        print("      fehlt:", u)

    # ----------------------------------------------- 3. Doppelte ids
    print("3. Keine Sprungmarke zweimal")
    for datei in ("forschende.html", "institutionen.html"):
        a, _ = ids(datei)
        doppelt = [k for k, n in collections.Counter(a).items() if n > 1]
        leer = sum(1 for x in a if not x.strip())
        gut = not doppelt and not leer
        ok = ok and gut
        print("   %s %-20s %d Zeilen, %d doppelt, %d ohne Marke"
              % ("ok " if gut else "FEHLER", datei, len(a), len(doppelt), leer))
        for k in doppelt[:4]:
            print("      doppelt:", k)

    # ----------------------------------------------- 4. Jede Zeile ein Ziel
    print("4. Jede Zeile hat ein Ziel")
    for datei, erwartet in (("forschende.html", None),
                            ("institutionen.html", None)):
        _, t = ids(datei)
        zeilen = zeilen_von(t)
        # Entweder ein Link im Namen (Profil, Standortseite) oder der Weg
        # zum Formular am Zeilenende.
        ohne = [z for z in zeilen
                if "<a " not in z]
        gut = not ohne
        ok = ok and gut
        print("   %s %-20s %d von %d Zeilen mit Ziel"
              % ("ok " if gut else "FEHLER", datei,
                 len(zeilen) - len(ohne), len(zeilen)))
        for z in ohne[:3]:
            print("      ohne Ziel:", re.sub(r"\s+", " ", z)[:90])

    # ----------------------------------------------- 5. Gegenprobe
    #
    # ⚠ EINE PRUEFUNG, DIE NIE FEHLSCHLAEGT, PRUEFT NICHTS. Darum nehmen
    # wir einer Zeile die Sprungmarke weg - nur im Speicher - und
    # verlangen, dass die Pruefung das meldet. Tut sie es nicht, ist sie
    # kaputt, und ihr „bestanden" ist wertlos.
    print("5. GEGENPROBE: eine Fassung ohne Sprungmarke muss durchfallen")
    opfer = next((u.split("#")[-1] for u in links), "")
    kaputt = {a for a in menge if a != opfer}
    merkt_es = any(u.split("#")[-1] not in kaputt for u in links)
    gut = bool(opfer) and merkt_es
    ok = ok and gut
    print("   %s Marke %r entfernt, Pruefung meldet es: %s"
          % ("ok " if gut else "FEHLER", opfer, "ja" if merkt_es else "NEIN"))

    erfunden = "gibt-es-nicht-zarnekow-wilhelmine"
    gut = erfunden not in menge
    ok = ok and gut
    print("   %s eine erfundene Marke %r wird nicht gefunden"
          % ("ok " if gut else "FEHLER", erfunden))

    print("\n" + ("Kontrolle bestanden." if ok else "KONTROLLE GESCHEITERT."))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
