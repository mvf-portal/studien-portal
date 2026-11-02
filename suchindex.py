# -*- coding: utf-8 -*-
"""Ein Suchfeld ueber alle Bestaende.

WARUM
-----
Wer die Seite aufruft, sucht sieben verschiedene Dinge, und keines davon
heisst „Landkarte":

  a) sich selbst          e) wer foerdert
  b) seine Studien        f) wer Mitarbeitende sucht
  c) seine Institution    g) wer gerade rekrutiert
  d) woran andere forschen h) Studien zu einem Thema

Sieben davon stehen im Bestand. Ein einziges Suchfeld, das alle Bestaende
auf einmal durchsucht, beantwortet sie, ohne dass jemand vorher wissen
muss, in welchem Bestand die Antwort liegt.

WAS HINEINKOMMT, UND WAS NICHT
------------------------------
  Personen        aus drei Quellen, zusammengefuehrt
  Institutionen   die Forschungsstandorte
  Studien         aus dem Register, zeigbar
  MVF-Beitraege   aus Crossref
  Foerderer       aus dem Register

NICHT hinein kommen die 5.602 Hub-Eintraege. Unser Bestand kennt zu
ihnen nur PMID und DOI, keine Titel. Sie liessen sich verlinken, aber
nicht durchsuchen, und ein Suchfeld, das sie fuehrt, ohne sie zu finden,
waere eine Luege. Die Seite sagt das und verweist auf die Hubs selbst.

ZUSAMMENFUEHRUNG DER PERSONEN
-----------------------------
Schluessel ist Nachname plus GANZER Vorname. Blosse Initialen werden
verworfen. Der Grund steht in daten/mvf_bruecke.json: mit Initialen
faellt „Schmidt, A." mit jeder anderen Schmidt zusammen, und aus 32
belegten Doppelrollen werden scheinbar 62.

  py suchindex.py              baut daten/suchindex.json
  py suchindex.py --gegentest  prueft ohne Netz
"""
import collections
import io
import json
import pathlib
import sys
import time
import unicodedata

HIER = pathlib.Path(__file__).parent
DATEN = HIER / "daten"


def lade(name):
    p = DATEN / name
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def norm(s):
    """Fuer den Vergleich: klein, ohne Umlaute, ohne Zeichen."""
    s = (s or "").lower()
    for a, b in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")):
        s = s.replace(a, b)
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return " ".join(s.replace("-", " ").split())


# Namen, die keine Person sind. Sie stehen so in den Autorenlisten
# der Publikationen, als waeren sie eine Person.
# ⚠ Die Liste ist kurz und steht darum ausgeschrieben da. Eine Regel auf
# „Network" oder „Gruppe" wuerde auch Menschen treffen, die so heissen.
KEINE_PERSON = (
    "german deprescribing network (gerden)",
    "deutsches netzwerk versorgungsforschung e.v.",
    "fopranet-bw study group",
    "move-onko study group",
    "the diginet study group",
    "adaptation working group guidelines international network",
)


def ist_konsortium(roh):
    return (roh or "").strip().lower() in KEINE_PERSON


# Wie viele Autorennennungen der MVF-Beitraege sich einer Person
# zuordnen liessen. personen() fuellt das, bauen() schreibt es in den
# Index, und die Forschendenseite erklaert damit, warum 1.321 Profile und
# 581 Personen mit Beitrag keine Luecke sind, sondern unsere Regel.
ZUORDNUNG = {"beitraege": 0, "nennungen": 0, "zugeordnet": 0,
             "nur_initiale": 0, "ohne_vornamen": 0}


def personenschluessel(nachname, vorname):
    """Nachname plus ganzer Vorname. Eine Initiale genuegt nicht.

    ⚠ Eine einzelne Initiale fuehrt verschiedene Menschen zusammen. Lieber
    eine Person nicht finden, als zwei zu einer machen.
    """
    nach = norm(nachname)
    vor = norm((vorname or "").replace(".", " "))
    if not nach or not vor:
        return None
    erst = vor.split()[0] if vor.split() else ""
    if len(erst) < 2:
        return None
    return nach + ", " + erst


# ⚠ AUCH DIE VERDREHTEN SCHREIBWEISEN. Im Bestand steht neben „et al.
# Schrappe" auch „et. al Schrappe" - mit dem Punkt hinter „et". Die eine
# Fassung wurde abgefangen, die andere wurde zur Person „Et Schrappe".
VORSATZ_WEG = ("et al.", "et. al.", "et. al", "et al", "et.al.", "et.al",
               "u. a.", "u.a.", "and others")

# Zeichenfolgen, die als Vorname auftauchen, aber keiner sind.
KEIN_NAME = {"et", "et al", "u", "u a", "ua", "and", "others",
             "and others", "ua."}


def scheinperson(vor):
    """Ist dieser „Vorname" gar keiner?

    ⚠ "et al. Kostev" wurde zu einer Person namens „Et Kostev" mit drei
    Beitraegen. Solche Scheineintraege stehen nicht nur falsch in der
    Liste, sie machen echte Namen kuenstlich mehrdeutig: „E. Neugebauer"
    hatte drei Kandidaten, zwei davon Schrott.
    """
    v = (vor or "").strip().lower().rstrip(".")
    if not v:
        return True
    if v in KEIN_NAME:
        return True
    # „E.a.m." und aehnliches: nur Initialen mit Punkten.
    kern = v.replace(".", "").replace(" ", "")
    return len(kern) < 2


def teile_namen(roh):
    """„Mueller, Anna" und „Anna Mueller" auf Nachname und Vorname bringen."""
    n = (roh or "").strip()
    if not n:
        return "", ""
    # Vorsaetze, die keine Namen sind, vor der Zerlegung weg.
    for x in VORSATZ_WEG:
        if n.lower().startswith(x):
            n = n[len(x):].strip(" .,")
        if n.lower().endswith(x):
            n = n[:-len(x)].strip(" .,")
    if not n:
        return "", ""
    # Nachgestellte Grade stoeren die Zerlegung.
    for grad in (" MPH", " MSc", " PhD", " MD", " M.Sc.", " M.A."):
        if n.endswith(grad):
            n = n[: -len(grad)].strip().rstrip(",")
    if "," in n:
        a, b = n.split(",", 1)
        return a.strip(), b.strip()
    t = n.split()
    if len(t) < 2:
        return n, ""
    return t[-1], " ".join(t[:-1])


# ---------------------------------------------------------------- Personen

def personen():
    """Drei Quellen auf einen Schluessel bringen."""
    leute = {}

    uebergangen = []

    def eintrag(k, name):
        if k not in leute:
            nach, vor = teile_namen(name)
            leute[k] = {"name": (vor + " " + nach).strip(),
                        "studien": [], "mvf": [], "dkvf": 0, "rors": set()}
        return leute[k]

    db = (lade("doi_bezug.json") or {}).get("arbeiten", {})
    for doi, a in db.items():
        for p in (a.get("personen") or []):
            if ist_konsortium(p.get("name")):
                uebergangen.append(p.get("name"))
                continue
            nach, vor = teile_namen(p.get("name"))
            k = personenschluessel(nach, vor)
            if not k:
                continue
            e = eintrag(k, p.get("name"))
            if doi not in e["studien"]:
                e["studien"].append(doi)
            for r in (p.get("rors") or []):
                e["rors"].add(r)

    for z in ZUORDNUNG:
        ZUORDNUNG[z] = 0
    for b in (lade("mvf_beitraege.json") or {}).get("beitraege", {}).items():
        doi, dat = b
        if dat.get("autoren"):
            ZUORDNUNG["beitraege"] += 1
        for a in (dat.get("autoren") or []):
            if ist_konsortium(a):
                uebergangen.append(a)
                continue
            ZUORDNUNG["nennungen"] += 1
            nach, vor = teile_namen(a)
            k = personenschluessel(nach, vor)
            if not k:
                # Getrennt zaehlen: Eine Initiale ist unsere Regel, ein
                # fehlender Name ist eine Luecke in der Quelle.
                ZUORDNUNG["ohne_vornamen" if not vor
                          else "nur_initiale"] += 1
                continue
            ZUORDNUNG["zugeordnet"] += 1
            e = eintrag(k, a)
            if doi not in e["mvf"]:
                e["mvf"].append(doi)

    for p in (lade("dkvf.json") or {}).get("personen", []):
        if ist_konsortium(p.get("name")):
            uebergangen.append(p.get("name"))
            continue
        nach, vor = teile_namen(p.get("name"))
        k = personenschluessel(nach, vor)
        if not k:
            continue
        eintrag(k, p.get("name"))["dkvf"] += 1

    if uebergangen:
        print("  uebergangen, weil kein Mensch: %d Nennungen, %d Namen"
              % (len(uebergangen), len(set(uebergangen))))

    # ------------------------------------------- Initialen aufloesen
    #
    # Erst jetzt, wenn alle Menschen mit vollem Vornamen stehen. Das
    # Register sind SIE, nicht eine Datei von aussen.
    reg = {}

    # Zweites Register, nur nach Nachname. Es traegt die Faelle, in denen
    # ueberhaupt kein Vorname dasteht: „et al. Schrappe" kommt zwoelfmal
    # vor und meint selbstverstaendlich Matthias Schrappe - aber nur,
    # wenn es genau einen Schrappe gibt.
    nur_nachname = {}

    def anmelden(k):
        nach, _, vor = k.partition(", ")
        if not nach or not vor or scheinperson(vor):
            return
        reg.setdefault((nach, vor[0]), set()).add(k)
        nur_nachname.setdefault(nach, set()).add(k)

    for k in leute:
        anmelden(k)

    # ⚠ DIE AUTORENPROFILE GEHOEREN INS REGISTER. Ohne sie kannte der
    # Lauf nur, wer schon mit vollem Vornamen belegt war - Matthias
    # Schrappe blieb bei 12 Beitraegen, obwohl er ein Profil hat. Mit
    # ihnen sind es die 645 aus der Messung statt 449.
    #
    # Das ist wechselseitig: personen.py liest suchindex.json, wir lesen
    # personen.json. Es laeuft fest, weil hier NIE eine Person entsteht,
    # sondern nur ein DOI an eine bestehende gehaengt wird. Die Kette
    # laeuft ohnehin zweimal, und der dritte Lauf aendert nichts mehr.
    for k in (lade("personen.json") or {}).get("personen", {}):
        if k not in leute:
            anmelden(k)
    nur_profil = {k for ks in reg.values() for k in ks} - set(leute)

    geloest = offen = 0
    for doi, dat in (lade("mvf_beitraege.json") or {}).get(
            "beitraege", {}).items():
        for a in (dat.get("autoren") or []):
            if ist_konsortium(a):
                continue
            nach, vor = teile_namen(a)
            if personenschluessel(nach, vor):
                continue                     # steht schon zugeordnet
            n, v = norm(nach), norm(vor)
            # ⚠ HIER NICHT scheinperson() BENUTZEN. Die Funktion weist
            # eine blosse Initiale ab, damit sie kein eigener Mensch
            # wird - und genau solche Initialen sollen hier aufgeloest
            # werden. Mit scheinperson() loeste der Lauf 13 statt 645.
            # Abzuweisen ist auf dieser Seite nur, was gar kein Name ist.
            if not n and not v:
                continue
            if v.rstrip(".") in KEIN_NAME:
                v = ""
            if not n:
                # Nur ein Vorname und kein Nachname: nicht aufloesbar.
                continue
            if v:
                kand = reg.get((n, v[0]))
            else:
                # Gar kein Vorname, etwa „et al. Schrappe". Auffloesbar,
                # wenn der Nachname im Bestand nur einmal vorkommt.
                kand = nur_nachname.get(n)
            # ⚠ NUR BEI GENAU EINEM KANDIDATEN. Zwei heisst offen lassen:
            # lieber eine Person nicht finden, als zwei zu einer machen.
            if not kand or len(kand) != 1:
                offen += 1
                continue
            k = next(iter(kand))
            if k in nur_profil and k not in leute:
                # Die Person kennen wir nur aus den Autorenprofilen. Sie
                # bekommt hier ihren ersten Beleg, aber den Namen nehmen
                # wir aus dem Profil, nicht aus der Initialen-Nennung.
                echt = (lade("personen.json") or {}).get(
                    "personen", {}).get(k, {}).get("name") or a
                eintrag(k, echt)
            e = leute[k]
            if doi not in e["mvf"]:
                e["mvf"].append(doi)
                ZUORDNUNG["zugeordnet"] += 1
                ZUORDNUNG["nur_initiale"] = max(
                    0, ZUORDNUNG["nur_initiale"] - 1)
            geloest += 1
    ZUORDNUNG["initiale_geloest"] = geloest
    ZUORDNUNG["initiale_offen"] = offen
    print("  Initialen im geschlossenen Bestand: %d geloest, %d bleiben offen"
          % (geloest, offen))
    return leute


# ----------------------------------------------------------------- bauen

def hubeintraege():
    """Die Studien der 15 Knowledge-Hubs, mit deutschem Titel.

    Eine PMID kann in mehreren Hubs stehen. Sie wird einmal aufgenommen
    und nennt alle Hubs, in denen sie vorkommt. Sonst stuende dieselbe
    Arbeit bis zu fuenfzehnmal in der Trefferliste.
    """
    # py -I haengt den Skriptordner nicht an sys.path, darum hier.
    if str(HIER) not in sys.path:
        sys.path.insert(0, str(HIER))
    import hubbezug

    wurzel = HIER.parent
    gesammelt = {}
    for ordner, (kuerzel, name, url) in hubbezug.PORTALE.items():
        p = wurzel / ordner / "studien-archiv.json"
        if not p.exists():
            print("  Hub-Archiv fehlt: %s" % ordner)
            continue
        for e in json.loads(p.read_text(encoding="utf-8")):
            pmid = str(e.get("pmid") or "").strip()
            titel = (e.get("title") or "").strip()
            if not pmid or not titel:
                continue
            g = gesammelt.setdefault(pmid, {
                "titel": titel, "journal": (e.get("journal") or "").strip(),
                "jahr": str(e.get("year") or "").strip(),
                "autor": (e.get("author") or "").strip(),
                "kurz": (e.get("sum") or "").strip(),
                "hubs": [], "url": "",
            })
            if name not in [h[0] for h in g["hubs"]]:
                g["hubs"].append((name, url))
            if not g["url"]:
                g["url"] = url + "/neue-studien.html#studie-" + pmid
    return gesammelt


def bauen():
    eintraege = []
    zaehlung = collections.Counter()

    if str(HIER) not in sys.path:
        sys.path.insert(0, str(HIER))
    from personen import ankername

    # Institutionen zuerst, ihre ROR-Kennungen brauchen die Personen.
    st = (lade("standorte.json") or {}).get("standorte", [])
    ror_name = {}
    for s in st:
        if s.get("ror"):
            ror_name[s["ror"]] = s["name"]
        such = " ".join([s.get("name", ""), s.get("ort", ""),
                         s.get("traegerart", "") or "",
                         " ".join(s.get("schreibweisen") or []),
                         " ".join(s.get("faecher") or [])])
        eintraege.append({
            "t": "institution", "n": s.get("name", ""),
            "o": s.get("ort", ""), "u": "standort/" + (s.get("datei") or ""),
            "z": {"studien": s.get("studien", 0),
                  "rekrutiert": s.get("rekrutiert", 0),
                  "ror": s.get("ror") or ""},
            "s": norm(such),
        })
    zaehlung["institution"] = len(st)

    bereits = set()
    # ⚠ REDAKTION IST KEINE FORSCHUNG. Regel und Begruendung in
    # zuschnitt.py. Wer hier steht, kommt weder in die Liste noch in die
    # Suche - beides muss gleich entscheiden, sonst zeigt ein Suchlink
    # auf eine Zeile, die es nicht gibt.
    from zuschnitt import REDAKTION
    for k, p in sorted(personen().items()):
        if k in REDAKTION:
            continue
        haus = sorted({ror_name[r] for r in p["rors"] if r in ror_name})
        such = " ".join([p["name"]] + haus)
        eintraege.append({
            "t": "person", "n": p["name"],
            "o": haus[0] if haus else "",
            "k": k,
            "u": "forschende.html#" + ankername(k),
            "z": {"studien": len(p["studien"]), "mvf": len(p["mvf"]),
                  "dkvf": p["dkvf"], "haeuser": haus},
            "s": norm(such),
        })
        zaehlung["person"] += 1
        bereits.add(k)

    # ------------------------------------------------- die uebrigen 780
    #
    # personen.py kennt drei Quellen mehr als wir: die ausgelieferten
    # Autorenprofile auf m-vf.de, die Autorenboxen aus den Beitrags-PDFs
    # und 84 von Hand gepflegte Paare. Wer dort steht, aber bei uns keinen
    # gezaehlten Beleg hat, fehlte bis zum 02.11.2026 in der Suche - und
    # stand trotzdem in der Liste.
    #
    # ⚠ DIE SEITE VERSPRICHT "EINE SUCHE UEBER ALLES". Ein Name, der auf
    # ihr steht und den sie nicht findet, bricht das Versprechen an genau
    # der Stelle, an der jemand nach sich selbst sucht.
    P = lade("personen.json") or {}
    nachgetragen = 0
    verworfen = 0
    for k, p in sorted((P.get("personen") or {}).items()):
        if k in bereits:
            continue
        # ⚠ SCHEINPERSONEN DUERFEN HIER NICHT WIEDER HEREIN. Sonst halten
        # sie sich selbst am Leben: personen.py schreibt „Et Kostev" nach
        # personen.json, wir tragen sie von dort in den Suchindex nach,
        # und personen.py liest sie im naechsten Lauf wieder daraus. Die
        # wechselseitige Kette traegt dann den Fehler mit.
        if k in REDAKTION:
            continue
        _, _, vor_k = k.partition(", ")
        if scheinperson(vor_k):
            verworfen += 1
            continue
        haus = [p.get("einrichtung")] if p.get("einrichtung") else []
        eintraege.append({
            "t": "person", "n": p.get("name") or k,
            "o": haus[0] if haus else "",
            "k": k,
            "u": "forschende.html#" + (p.get("anker") or ankername(k)),
            "z": {"studien": 0, "mvf": p.get("mvf") or 0,
                  "dkvf": p.get("dkvf") or 0, "haeuser": haus},
            "s": norm(" ".join([p.get("name") or k] + haus)),
        })
        zaehlung["person"] += 1
        nachgetragen += 1
    if nachgetragen or verworfen:
        print("  aus personen.json nachgetragen: %d, als Scheinperson "
              "abgewiesen: %d" % (nachgetragen, verworfen))

    L = lade("landkarte.json") or {}
    for x in L.get("studien", []):
        orte = [o.get("ort", "") for o in (x.get("orte") or []) if o.get("ort")]
        such = " ".join([x.get("titel") or "", x.get("akronym") or "",
                         x.get("indikation") or "", x.get("id") or "",
                         (x.get("sponsor") or {}).get("name") or "",
                         " ".join(sorted(set(orte))),
                         " ".join(x.get("foerderung") or [])])
        eintraege.append({
            "t": "studie", "n": (x.get("akronym") or "").strip()
                                or (x.get("titel") or "")[:90],
            "o": sorted(set(orte))[0] if orte else "",
            "u": "studien.html#" + (x.get("id") or ""),
            "z": {"id": x.get("id"), "status": x.get("status_de"),
                  "rekrutiert": x.get("status") == "RECRUITING",
                  "jahr": (x.get("registriert") or "")[:4],
                  "titel": x.get("titel") or ""},
            "s": norm(such),
        })
        zaehlung["studie"] += 1

    # Unsere EIGENEN Schlagwoerter, von Hand vergeben. Sie beantworten
    # „Studien zu meinem Thema" besser als jede fremde Klassifikation:
    # 1.755 verschiedene auf 414 Beitraegen, im Schnitt 5,9 je Beitrag.
    # OpenAlex liefert dagegen nur 80 von 936 Fachgebieten und drosselt
    # jede weitere Anfrage mit HTTP 429.
    SW = (lade("mvf_schlagworte.json") or {}).get("schlagworte", {})
    for doi, b in sorted((lade("mvf_beitraege.json") or {})
                         .get("beitraege", {}).items()):
        worte = SW.get(doi) or []
        such = " ".join([b.get("titel") or "", b.get("abstract") or "",
                         " ".join(b.get("autoren") or []),
                         " ".join(worte)])
        eintraege.append({
            "t": "mvf", "n": b.get("titel") or doi,
            "o": "", "u": "https://doi.org/" + doi,
            "z": {"jahr": b.get("jahr"), "heft": b.get("heft") or "",
                  "autoren": (b.get("autoren") or [])[:4],
                  "worte": worte[:6]},
            # Die Schlagwoerter VORN, damit sie die Laengengrenze von 600
            # Zeichen ueberleben. Ein langes Abstract wuerde sie sonst
            # hinausdraengen, und dann faende die Suche sie nie.
            "s": norm(" ".join(worte) + " " + such)[:800],
        })
        zaehlung["mvf"] += 1

    fo = lade("foerderer.json") or {}
    for f in fo.get("liste", []):
        name = f.get("name") if isinstance(f, dict) else str(f)
        anz = f.get("studien", f.get("anzahl", 0)) if isinstance(f, dict) else 0
        if isinstance(anz, list):
            anz = len(anz)
        eintraege.append({
            "t": "foerderer", "n": name, "o": "",
            "u": "studien.html#geber-" + norm(name).replace(" ", "-")[:50],
            "z": {"studien": anz}, "s": norm(name),
        })
        zaehlung["foerderer"] += 1

    # Die Hubs: 15 Archive, deutsche Titel und Zusammenfassungen.
    hubliste = []
    for pmid, g in sorted(hubeintraege().items()):
        namen = [n for n, _ in g["hubs"]]
        # ⚠ OHNE DIE ZUSAMMENFASSUNG. Mit ihr waechst der Index, den
        # JEDE Seite laedt, von 420 KB auf 1,4 MB gzip. Die Hub-Titel
        # sind bei uns selbst geschriebene deutsche Saetze und tragen
        # die Suche allein, die Zusammenfassung steht im Hub.
        such = " ".join([g["titel"], g["journal"], g["autor"],
                         " ".join(namen)])
        hubliste.append({
            "t": "hub", "n": g["titel"],
            "o": namen[0] if namen else "",
            "u": g["url"] or ("https://pubmed.ncbi.nlm.nih.gov/%s/" % pmid),
            "z": {"pmid": pmid, "jahr": g["jahr"], "journal": g["journal"],
                  "autor": g["autor"], "hubs": namen},
            "s": norm(such)[:400],
        })
        zaehlung["hub"] += 1

    raus = {
        "stand": time.strftime("%Y-%m-%d"),
        "hinweis": ("Ein Index ueber sechs Bestaende, die Studien der 15 "
                    "Knowledge-Hubs eingeschlossen. Gesucht wird in Titel, "
                    "Zusammenfassung, Namen, Orten und Schlagworten."),
        "nicht_enthalten": [
            {"was": "Stellenanzeigen", "anzahl": 0,
             "grund": "keine offene Quelle, kommt nur ueber die "
                      "Selbstauskunft der Einrichtungen"},
            {"was": "Studien ohne CC BY 4.0", "anzahl": 588,
             "grund": "die Lizenz des Registers erlaubt die Wiedergabe "
                      "nicht, nur die Zahl"},
        ],
        "zaehlung": dict(zaehlung),
        "zuordnung": dict(ZUORDNUNG),
        "eintraege": eintraege,
    }
    raus["nachladen"] = "daten/suchindex-hubs.json"
    ziel = DATEN / "suchindex.json"
    ziel.write_text(json.dumps(raus, ensure_ascii=False, separators=(",", ":")),
                    encoding="utf-8")

    zweit = DATEN / "suchindex-hubs.json"
    zweit.write_text(json.dumps(
        {"stand": raus["stand"], "eintraege": hubliste},
        ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print("-> %s  (%s KB)"
          % (zweit.relative_to(HIER),
             format(zweit.stat().st_size // 1024, ",d").replace(",", ".")))
    return raus, ziel


# -------------------------------------------------------------- Gegentest

def gegentest():
    ok = True
    print("Personenschluessel, ganzer Vorname verlangt:")
    for nach, vor, soll in (("Schmidt", "Annika", "schmidt, annika"),
                            ("Schmidt", "A.", None),
                            ("Schmidt", "A", None),
                            ("Mühlensiepen", "Felix", "muehlensiepen, felix"),
                            ("Poß-Doering", "Regina", "poss doering, regina"),
                            ("", "Anna", None),
                            ("Mayer", "", None)):
        ist = personenschluessel(nach, vor)
        gut = ist == soll
        ok = ok and gut
        print(f"  {'ok ' if gut else 'FEHLER'} {nach!r:<16} {vor!r:<10} -> {ist!r}")

    print("\nNamen zerlegen:")
    for roh, soll in (("Mueller, Anna", ("Mueller", "Anna")),
                      ("Anna Mueller", ("Mueller", "Anna")),
                      ("Anna Maria Mueller", ("Mueller", "Anna Maria")),
                      # Der nachgestellte Grad fliegt heraus, und das ist
                      # richtig: gesucht wird der Mensch, nicht sein Titel.
                      ("Mueller, Anna MPH", ("Mueller", "Anna")),
                      ("Mueller, Anna PhD", ("Mueller", "Anna")),
                      ("Mueller", ("Mueller", "")),
                      ("", ("", ""))):
        ist = teile_namen(roh)
        gut = ist == soll
        ok = ok and gut
        print(f"  {'ok ' if gut else 'FEHLER'} {roh!r:<24} -> {ist}")

    print("\nZwei Schmidt bleiben zwei:")
    a = personenschluessel("Schmidt", "Annika")
    b = personenschluessel("Schmidt", "Andreas")
    gut = a != b and a and b
    ok = ok and gut
    print(f"  {'ok ' if gut else 'FEHLER'} {a!r} != {b!r}")

    print("\n" + ("Gegentest bestanden." if ok else "GEGENTEST GESCHEITERT."))
    return ok


def main():
    if "--gegentest" in sys.argv:
        return 0 if gegentest() else 1
    raus, ziel = bauen()
    print("Suchindex gebaut")
    for art, n in sorted(raus["zaehlung"].items(), key=lambda x: -x[1]):
        print(f"   {art:<14} {n:6d}")
    print(f"   {'gesamt':<14} {len(raus['eintraege']):6d}")
    print("\nabsichtlich nicht enthalten:")
    for n in raus["nicht_enthalten"]:
        print(f"   {n['was']:<18} {n['anzahl']:6d}  {n['grund']}")
    kb = ziel.stat().st_size / 1024
    print(f"\n-> daten/suchindex.json  ({kb:,.0f} KB)")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
