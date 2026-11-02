# -*- coding: utf-8 -*-
"""Dublette Autorenprofile auf m-vf.de, aus drei Richtungen gesucht.

DER ANLASS
----------
Peter ist heute nacheinander ueber einzelne Faelle gestolpert: Pieloth,
Haeussler, Marschall, Gilbers, Giulini, Blau. Jedes Mal eine Meldung,
jedes Mal eine Einzelpruefung. Diese Datei sucht sie alle auf einmal.

DREI SUCHEN, WEIL JEDE ETWAS ANDERES FINDET
-------------------------------------------
1. ORCID. Zwei Profile mit derselben ORCID sind dieselbe Person, ohne
   Wenn und Aber. Das ist kein Verdacht, das ist ein Beleg.
   Gefunden hat das den Fall Blau.

2. Unser Personenschluessel: Nachname plus ERSTER Vorname. Faengt
   „Kai" gegen „Kai Uwe" und „Axel" gegen „Axel C.".

3. Nachname-Kern: der erste Teil eines zusammengesetzten Nachnamens.
   Faengt „Giulini" gegen „Giulini-Limbach", also den Fall
   Maedchenname gegen Ehename, den Suche 2 nicht sehen kann.

⚠ EIN VERDACHT IST KEIN BEFUND. Zwei Menschen koennen denselben Namen
tragen. Die Ausgabe nennt deshalb je Paar, WELCHE Suche angeschlagen
hat und wie viele Beitraege an jedem Profil haengen - erst das macht
entscheidbar, welches Profil bleibt und ob etwas umzuhaengen ist.

⚠ UMHAENGEN HEISST ERSETZEN, NICHT SETZEN. Das Feld author_id ist eine
LISTE. Beitrag #78748 traegt drei Autor:innen; wer die Liste auf das
Zielprofil setzt, statt die eine Kennung darin zu ersetzen, nimmt den
Beitrag seinen uebrigen Autor:innen weg. Die Ausgabe nennt darum je
Beitrag die VOLLSTAENDIGE Liste.

    py wp_dubletten.py
    py wp_dubletten.py --gegentest
"""
import collections
import json
import pathlib
import sys
import time

HIER = pathlib.Path(__file__).resolve().parent
DATEN = HIER / "daten"
FREMD = HIER.parent / "mvf-archiv-transfer" / "daten"


def lade(p, was):
    p = pathlib.Path(p)
    if not p.exists():
        raise SystemExit("ABBRUCH: %s fehlt (%s)" % (p, was))
    return json.loads(p.read_text(encoding="utf-8"))


def kern(nachname, norm):
    """Der erste Teil eines zusammengesetzten Nachnamens.

    „Giulini-Limbach" -> „giulini". Trennt an Bindestrich und
    Leerzeichen, nicht an Apostrophen: „N'Doye" ist ein Name, kein Paar.
    """
    n = norm(nachname or "").replace("-", " ")
    return n.split()[0] if n.split() else ""


def gegentest():
    sys.path.insert(0, str(HIER))
    from suchindex import norm
    print("GEGENTEST")
    ok = True
    # ⚠ DER APOSTROPH BLEIBT. norm() ersetzt nur, was weder Buchstabe
    # noch Ziffer noch Leerzeichen ist - der Apostroph gehoert dazu und
    # ueberlebt. „N'Doye" ist EIN Nachname, kein zusammengesetzter, und
    # „n'doye" ist deshalb der richtige Kern. Meine erste Erwartung hier
    # lautete „ndoye" und war falsch, nicht die Funktion.
    faelle = [("Giulini-Limbach", "giulini"), ("Giulini", "giulini"),
              ("Mueller", "mueller"), ("von Kutzleben", "von"),
              ("N'Doye", "n'doye"), ("Niepraschk-von Dollen", "niepraschk"),
              ("", "")]
    for ein, soll in faelle:
        ist = kern(ein, norm)
        gut = ist == soll
        ok = ok and gut
        print("   %s %-18r -> %-10r" % ("ok " if gut else "FEHLER", ein, ist))
    print("   HINWEIS: „von Kutzleben\" wird zu „von\". Namenszusaetze "
          "sind\n            kein Kern, darum werden sie unten "
          "uebersprungen.")
    print("\n" + ("Gegentest bestanden." if ok else "GEGENTEST GESCHEITERT."))
    return 0 if ok else 1


# Namenszusaetze, die kein Kern sind.
ZUSATZ = {"von", "van", "de", "der", "den", "zu", "zur", "le", "la", "di",
          "da", "dos", "del", "al", "el", "ten", "ter", "op"}


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if "--gegentest" in sys.argv:
        return gegentest()

    sys.path.insert(0, str(HIER))
    from suchindex import personenschluessel, norm

    W = lade(FREMD / "wp_autoren.json", "Autorenprofile")["autoren"]
    V = lade(FREMD / "wp_autorverknuepfung.json", "Verknuepfungen")

    # Profil-Slug -> Beitraege, und Beitrag -> alle seine Autoren
    je_profil = collections.defaultdict(list)
    autoren_von = {}
    for x in V["beitraege"]:
        autoren_von[x["slug"]] = {"id": x["id"],
                                  "author_id": x.get("author_id") or [],
                                  "author_slug": x.get("author_slug") or []}
        for s in (x.get("author_slug") or []):
            je_profil[s].append(x["slug"])

    print("Autorenprofile: %d" % len(W))

    nach_orcid = collections.defaultdict(list)
    nach_schluessel = collections.defaultdict(list)
    nach_kern = collections.defaultdict(list)
    for sl, v in W.items():
        o = (v.get("orcid") or "").strip()
        if o:
            nach_orcid[o].append(sl)
        k = personenschluessel(v.get("nachname"), v.get("vorname"))
        if k:
            nach_schluessel[k].append(sl)
        kn = kern(v.get("nachname"), norm)
        vn = norm(v.get("vorname") or "").split()
        if kn and kn not in ZUSATZ and vn:
            nach_kern[(kn, vn[0])].append(sl)

    paare = {}

    def merke(slugs, grund):
        for i in range(len(slugs)):
            for j in range(i + 1, len(slugs)):
                a, b = sorted((slugs[i], slugs[j]))
                paare.setdefault((a, b), set()).add(grund)

    # ⚠ GLEICHE ORCID ALLEIN BEWEIST GAR NICHTS. Von 14 mehrfach
    # vergebenen ORCID gehoeren nur 4 zu Profilen mit gleichem
    # Nachnamen. Die uebrigen 10 sind FALSCH EINGETRAGEN: Holbe, van
    # Lente und Popp tragen dieselbe, Rujescu, Maul und Lempfert
    # ebenfalls. Eine ORCID ist die Forscherkennung einer Person, eine
    # falsche schreibt ihr fremde Arbeiten zu.
    #
    # Ein Beleg ist die ORCID erst ZUSAMMEN mit dem Namen. Der Rest ist
    # ein Fund eigener Art und wird getrennt gemeldet.
    falsch = []
    for o, s in nach_orcid.items():
        if len(s) < 2:
            continue
        if len({kern(W[x].get("nachname"), norm) for x in s}) == 1:
            merke(s, "gleiche ORCID")
        else:
            falsch.append((o, s))
    for k, s in nach_schluessel.items():
        if len(s) > 1:
            merke(s, "Nachname + erster Vorname")
    for k, s in nach_kern.items():
        if len(s) > 1:
            merke(s, "Nachnamenskern + Vorname")

    print("Verdachtspaare: %d" % len(paare))
    if falsch:
        print()
        print("⚠ FALSCH EINGETRAGENE ORCID: %d Kennungen stehen auf "
              "Profilen mit VERSCHIEDENEN Nachnamen." % len(falsch))
        for o, s in sorted(falsch, key=lambda x: -len(x[1])):
            print("   %s auf %d: %s"
                  % (o, len(s),
                     ", ".join((W[x].get("name") or x) for x in s)[:68]))
    print()
    # Belegt zuerst: ORCID schlaegt alles.
    def rang(p):
        g = paare[p]
        return (0 if "gleiche ORCID" in g else 1, p[0])

    for (a, b) in sorted(paare, key=rang):
        g = sorted(paare[(a, b)])
        na, nb = len(je_profil.get(a, [])), len(je_profil.get(b, []))
        belegt = "BELEGT" if "gleiche ORCID" in g else "Verdacht"
        print("   %-8s %s" % (belegt, " + ".join(g)))
        print("      %-34s id %-7s %2d Beitraege  %s"
              % (a[:34], W[a].get("id"), na, (W[a].get("name") or "")[:30]))
        print("      %-34s id %-7s %2d Beitraege  %s"
              % (b[:34], W[b].get("id"), nb, (W[b].get("name") or "")[:30]))

    ziel = DATEN / "wp_dubletten.json"
    aus = []
    for (a, b), g in paare.items():
        aus.append({
            "a": {"slug": a, "id": W[a].get("id"), "name": W[a].get("name"),
                  "beitraege": [{"slug": s, **autoren_von[s]}
                                for s in je_profil.get(a, [])]},
            "b": {"slug": b, "id": W[b].get("id"), "name": W[b].get("name"),
                  "beitraege": [{"slug": s, **autoren_von[s]}
                                for s in je_profil.get(b, [])]},
            "gruende": sorted(g),
            "belegt": "gleiche ORCID" in g})
    ziel.write_text(json.dumps(
        {"stand": time.strftime("%Y-%m-%d"),
         "hinweis": ("Verdachtspaare, aus drei Richtungen gesucht. "
                     "'belegt' heisst: beide Profile tragen dieselbe "
                     "ORCID. Je Beitrag steht die VOLLSTAENDIGE "
                     "author_id-Liste dabei: Umhaengen heisst eine "
                     "Kennung darin ERSETZEN, nicht die Liste setzen."),
         "paare": aus}, ensure_ascii=False, indent=1), encoding="utf-8")
    print("\n-> %s" % ziel)
    return 0


if __name__ == "__main__":
    sys.exit(main())
