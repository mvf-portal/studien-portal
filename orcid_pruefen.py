# -*- coding: utf-8 -*-
"""Wem gehoert die ORCID wirklich, und wie lautet die richtige?

DER ANLASS (02.11.2026)
-----------------------
Zehn ORCID stehen auf Autorenprofilen mit verschiedenen Nachnamen.
Holbe, van Lente und Popp tragen dieselbe, Rujescu, Maul und Lempfert
ebenfalls. Peter: „bitte richtige Orcids online suchen und eintragen."

⚠ EINE ORCID GEHOERT GENAU EINEM MENSCHEN, und ORCID sagt uns, wem. Das
ist besser als jede Namenssuche: Statt zu raten, welcher der beiden
richtig liegt, fragen wir die Kennung selbst.

Zwei Schritte je Fall:
  1. Die eingetragene ORCID bei ORCID abrufen. Der Name dort sagt, wem
     sie gehoert. Wessen Profil dazu passt, behaelt sie.
  2. Fuer die uebrigen eine Namenssuche. Die liefert Kandidaten, KEINE
     Gewissheit.

⚠ EINE NAMENSSUCHE IST EIN VORSCHLAG, KEIN BEFUND. „Prof. Dr. med."
steht nicht bei ORCID, Umlaute werden verschieden geschrieben, und
Namensvettern gibt es. Die Ausgabe nennt darum immer, wie viele
Kandidaten es gab und mit welcher Einrichtung - eintragen darf das nur
ein Mensch.

    py orcid_pruefen.py
    py orcid_pruefen.py --gegentest
"""
import json
import pathlib
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

HIER = pathlib.Path(__file__).resolve().parent
DATEN = HIER / "daten"
FREMD = HIER.parent / "mvf-archiv-transfer" / "daten"
KOPF = {"Accept": "application/json",
        "User-Agent": "MVF-Landkarte/1.0 (mailto:stegmaier@m-vf.de)"}

GRADE = re.compile(
    r"\b(prof|dr|univ|rer|nat|med|pol|cur|phil|oec|habil|h\.?c\.?|mult|"
    r"dipl|msc|msc\.|ma|mba|mph|bsc|beng|m\.sc\.|b\.sc\.|ph|phd)\b\.?",
    re.I)


def hole(url, versuche=3):
    for i in range(versuche):
        try:
            with urllib.request.urlopen(
                    urllib.request.Request(url, headers=KOPF),
                    timeout=30) as a:
                return a.getcode(), json.loads(a.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            return e.code, None
        except (urllib.error.URLError, OSError, ValueError):
            if i == versuche - 1:
                return 0, None
            time.sleep(2 * (i + 1))
    return 0, None


def blank(name):
    """Grade und Titel weg, damit nur der Name bleibt."""
    s = GRADE.sub(" ", name or "")
    s = re.sub(r"[.,]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def wem_gehoert(orcid):
    """Der Name, der bei ORCID zu dieser Kennung steht."""
    code, d = hole("https://pub.orcid.org/v3.0/%s/person" % orcid)
    if code != 200 or not d:
        return None, "HTTP %s" % code
    n = (d.get("name") or {})
    vor = ((n.get("given-names") or {}) or {}).get("value") or ""
    nach = ((n.get("family-name") or {}) or {}).get("value") or ""
    kredit = ((n.get("credit-name") or {}) or {}).get("value") or ""
    voll = (kredit or (vor + " " + nach)).strip()
    return voll or None, ""


def suche(name):
    """Kandidaten zu einem Namen. Liefert eine Liste, keine Gewissheit."""
    rein = blank(name)
    teile = rein.split()
    if len(teile) < 2:
        return []
    q = 'given-names:"%s" AND family-name:"%s"' % (teile[0], teile[-1])
    code, d = hole("https://pub.orcid.org/v3.0/expanded-search/?q=%s&rows=5"
                   % urllib.parse.quote(q))
    if code != 200 or not d:
        return []
    aus = []
    for r in (d.get("expanded-result") or []):
        aus.append({
            "orcid": r.get("orcid-id"),
            "name": " ".join(x for x in (r.get("given-names"),
                                         r.get("family-names")) if x),
            "haeuser": (r.get("institution-name") or [])[:3]})
    return aus


def gegentest():
    print("GEGENTEST")
    ok = True
    for ein, soll in (("Prof. Dr. med. Dr. phil. Eva Winkler", "Eva Winkler"),
                      ("Dr. rer. nat. Kai Uwe Blau", "Kai Uwe Blau"),
                      ("Evert Jan van Lente", "Evert Jan van Lente"),
                      ("Alexander Tamdjidi BEng", "Alexander Tamdjidi")):
        ist = blank(ein)
        gut = ist == soll
        ok = ok and gut
        print("   %s %-40r -> %r" % ("ok " if gut else "FEHLER", ein, ist))

    # ⚠ DIE ABFRAGE MUSS WIRKLICH ANTWORTEN. Eine Pruefung ohne Netz
    # darf nicht gruen melden.
    name, grund = wem_gehoert("0000-0002-1825-0097")   # Josiah Carberry
    gut = bool(name)
    ok = ok and gut
    print("   %s ORCID-Abruf antwortet: %r %s"
          % ("ok " if gut else "FEHLER", name, grund))
    print("\n" + ("Gegentest bestanden." if ok else "GEGENTEST GESCHEITERT."))
    return 0 if ok else 1


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if "--gegentest" in sys.argv:
        return gegentest()

    sys.path.insert(0, str(HIER))
    from suchindex import norm

    W = json.loads((FREMD / "wp_autoren.json").read_text(
        encoding="utf-8"))["autoren"]
    nach_orcid = {}
    for sl, v in W.items():
        o = (v.get("orcid") or "").strip()
        if o:
            nach_orcid.setdefault(o, []).append(sl)
    strittig = {o: s for o, s in nach_orcid.items()
                if len(s) > 1
                and len({norm(W[x].get("nachname") or "").split()[0]
                         if norm(W[x].get("nachname") or "").split() else ""
                         for x in s}) > 1}

    print("Strittige ORCID: %d, betroffene Profile: %d"
          % (len(strittig), sum(len(s) for s in strittig.values())))
    print()
    aus = []
    for o in sorted(strittig):
        slugs = strittig[o]
        inhaber, grund = wem_gehoert(o)
        print("=" * 68)
        print("%s  steht auf %d Profilen" % (o, len(slugs)))
        print("   ORCID sagt, sie gehoert: %s%s"
              % (inhaber or "(nicht abrufbar)",
                 "  [%s]" % grund if grund else ""))
        fall = {"orcid": o, "gehoert": inhaber, "profile": []}
        for sl in slugs:
            name = W[sl].get("name") or sl
            passt = (inhaber and norm(blank(name)).split()[-1:] ==
                     norm(inhaber).split()[-1:])
            print("   %-6s %-34s %s"
                  % ("BEHAELT" if passt else "falsch", sl[:34], name[:34]))
            eintrag = {"slug": sl, "id": W[sl].get("id"), "name": name,
                       "behaelt": bool(passt), "vorschlag": []}
            if not passt:
                for k in suche(name):
                    eintrag["vorschlag"].append(k)
                    print("        Vorschlag %s  %-26s %s"
                          % (k["orcid"], (k["name"] or "")[:26],
                             ", ".join(k["haeuser"])[:40]))
                if not eintrag["vorschlag"]:
                    print("        kein Treffer bei ORCID")
            fall["profile"].append(eintrag)
            time.sleep(0.4)
        aus.append(fall)

    ziel = DATEN / "orcid_strittig.json"
    ziel.write_text(json.dumps(
        {"stand": time.strftime("%Y-%m-%d"),
         "hinweis": ("Je strittiger ORCID: wem sie laut ORCID gehoert, "
                     "welches Profil sie behaelt, und Suchvorschlaege "
                     "fuer die uebrigen. ⚠ Vorschlaege sind Kandidaten "
                     "aus einer Namenssuche, kein Befund. Eintragen "
                     "darf das nur ein Mensch."),
         "faelle": aus}, ensure_ascii=False, indent=1), encoding="utf-8")
    print("\n-> %s" % ziel)
    return 0


if __name__ == "__main__":
    sys.exit(main())
