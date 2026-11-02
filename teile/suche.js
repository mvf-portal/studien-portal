/* Ein Suchfeld ueber alle Bestaende.
 *
 * WARUM
 * Wer die Seite aufruft, sucht sieben verschiedene Dinge: sich selbst,
 * seine Studien, seine Institution, woran andere forschen, wer foerdert,
 * wer rekrutiert, Studien zu einem Thema. Keines davon heisst
 * „Landkarte". Ein Feld, das alle Bestaende auf einmal durchsucht,
 * beantwortet sie, ohne dass man vorher wissen muss, wo die Antwort
 * liegt.
 *
 * WAS ES NICHT FINDET, und das sagt es auch
 * Die Hub-Eintraege fehlen: zu ihnen liegen nur PMID und DOI vor, keine
 * Titel. Stellenanzeigen fehlen: dazu gibt es keine offene Quelle. Beides
 * steht unter den Treffern, nicht im Kleingedruckten.
 */
(function () {
  "use strict";

  var ART = {
    person:      { wort: "Forschende",    reihe: 1 },
    institution: { wort: "Institutionen", reihe: 2 },
    studie:      { wort: "Studien",       reihe: 3 },
    mvf:         { wort: "MVF-Beiträge",  reihe: 4 },
    hub:         { wort: "In den Hubs",   reihe: 5 },
    foerderer:   { wort: "Förderer",      reihe: 6 }
  };

  var index = null, laedt = false, feld, kasten, offen = false, wahl = -1;

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
    });
  }

  function zahl(n) { return Number(n || 0).toLocaleString("de-DE"); }

  /* Dieselbe Regel wie im Python-Bauskript: klein, ohne Umlaute. Weicht
   * sie ab, findet die Suche „Mühlensiepen" nicht. */
  function norm(s) {
    s = String(s || "").toLowerCase();
    s = s.replace(/ä/g, "ae").replace(/ö/g, "oe").replace(/ü/g, "ue")
         .replace(/ß/g, "ss");
    s = s.normalize("NFKD").replace(/[̀-ͯ]/g, "");
    return s.replace(/-/g, " ").replace(/\s+/g, " ").trim();
  }

  /* Der Kern kommt sofort, die Hubs gleich danach. Die zweite Datei
   * ist mehr als doppelt so gross wie der Kern, und auf den meisten
   * Seiten tippt niemand. Sie darf den ersten Tastendruck nicht
   * aufhalten. */
  function nachladen() {
    if (!index || index.hubsDa || index.hubsLaedt) { return; }
    index.hubsLaedt = true;
    fetch(WURZEL + (index.nachladen || "daten/suchindex-hubs.json"))
      .then(function (a) { return a.json(); })
      .then(function (d) {
        var zu = (d && d.eintraege) || [];
        for (var i = 0; i < zu.length; i++) { index.eintraege.push(zu[i]); }
        index.hubsDa = true;
        index.hubsLaedt = false;
        /* Wer schon getippt hat, bekommt die Hub-Treffer nachgereicht. */
        if (offen && feld && norm(feld.value).length >= 2) { malen(feld.value); }
      })
      .catch(function () { index.hubsLaedt = false; });
  }

  function laden() {
    if (index || laedt) {
      if (index) { nachladen(); }
      return Promise.resolve(index);
    }
    laedt = true;
    return fetch(WURZEL + "daten/suchindex.json")
      .then(function (a) { return a.json(); })
      .then(function (d) { index = d; laedt = false; nachladen(); return d; })
      .catch(function () { laedt = false; return null; });
  }

  /* Rang: Ein Treffer im Namen wiegt schwerer als einer im Volltext, und
   * ein Namensanfang schwerer als ein Treffer in der Mitte. Ohne das
   * steht „Hoffmann" hinter zwanzig Abstracts, die ihn nur erwaehnen. */
  function rang(e, q) {
    var n = norm(e.n);
    if (n === q) { return 0; }
    if (n.indexOf(q) === 0) { return 1; }
    /* Nachname zuerst: „sundmacher" soll „Leonie Sundmacher" finden. */
    if (n.split(" ").some(function (w) { return w.indexOf(q) === 0; })) { return 2; }
    if (n.indexOf(q) >= 0) { return 3; }
    if ((e.s || "").indexOf(q) >= 0) { return 4; }
    return 9;
  }

  function suchen(roh) {
    var q = norm(roh);
    if (!index || q.length < 2) { return null; }
    var topf = {};
    Object.keys(ART).forEach(function (k) { topf[k] = []; });
    for (var i = 0; i < index.eintraege.length; i++) {
      var e = index.eintraege[i];
      var r = rang(e, q);
      if (r < 9 && topf[e.t]) { topf[e.t].push([r, e]); }
    }
    Object.keys(topf).forEach(function (k) {
      topf[k].sort(function (a, b) {
        if (a[0] !== b[0]) { return a[0] - b[0]; }
        return a[1].n.localeCompare(b[1].n, "de");
      });
    });
    return topf;
  }

  function zusatz(e) {
    var z = e.z || {}, t = [];
    if (e.t === "person") {
      if (z.studien) { t.push(z.studien + " Studienpublikation" + (z.studien > 1 ? "en" : "")); }
      if (z.mvf) { t.push(z.mvf + " MVF-Beitrag" + (z.mvf > 1 ? "e" : "")); }
      if (z.dkvf) { t.push(z.dkvf + " DKVF-Abstract" + (z.dkvf > 1 ? "s" : "")); }
      if (z.haeuser && z.haeuser.length) { t.push(z.haeuser[0]); }
    } else if (e.t === "institution") {
      t.push(zahl(z.studien) + " Studien");
      if (z.rekrutiert) { t.push(z.rekrutiert + " rekrutieren"); }
      if (e.o) { t.push(e.o); }
    } else if (e.t === "studie") {
      if (z.rekrutiert) { t.push("rekrutiert gerade"); }
      else if (z.status) { t.push(z.status); }
      if (e.o) { t.push(e.o); }
      if (z.jahr) { t.push("registriert " + z.jahr); }
    } else if (e.t === "mvf") {
      if (z.heft) { t.push("Heft " + z.heft); }
      if (z.jahr) { t.push(String(z.jahr)); }
      if (z.autoren && z.autoren.length) { t.push(z.autoren.slice(0, 2).join(", ")); }
    } else if (e.t === "hub") {
      if (z.hubs && z.hubs.length) { t.push(z.hubs.join(", ")); }
      if (z.journal) { t.push(z.journal); }
      if (z.jahr) { t.push(String(z.jahr)); }
    } else if (e.t === "foerderer") {
      t.push(zahl(z.studien) + " Studien gefördert");
    }
    return t.join(" · ");
  }

  function zeile(e, i) {
    var u = /^https?:/.test(e.u) ? e.u : WURZEL + e.u;
    var neu = /^https?:/.test(e.u) ? ' target="_blank" rel="noopener"' : "";
    var titel = e.t === "studie" && (e.z || {}).titel && e.n !== e.z.titel
      ? '<span class="st">' + esc(e.z.titel.slice(0, 110)) + "</span>" : "";
    return '<a class="str" href="' + esc(u) + '"' + neu
      + ' data-i="' + i + '" role="option"><span class="sn">' + esc(e.n)
      + "</span>" + titel + '<span class="sz">' + esc(zusatz(e)) + "</span></a>";
  }

  function malen(roh) {
    var topf = suchen(roh);
    if (!topf) {
      kasten.innerHTML = "";
      kasten.hidden = true;
      offen = false;
      return;
    }
    var h = [], gesamt = 0, i = 0;
    Object.keys(ART).sort(function (a, b) {
      return ART[a].reihe - ART[b].reihe;
    }).forEach(function (k) {
      var tr = topf[k];
      gesamt += tr.length;
      if (!tr.length) { return; }
      h.push('<div class="sgrp"><div class="sk">' + ART[k].wort
        + ' <span>' + zahl(tr.length) + "</span></div>");
      tr.slice(0, 6).forEach(function (p) { h.push(zeile(p[1], i++)); });
      if (tr.length > 6) {
        h.push('<div class="smehr">und ' + zahl(tr.length - 6)
          + " weitere " + ART[k].wort + "</div>");
      }
      h.push("</div>");
    });
    if (!gesamt) {
      h.push('<div class="sleer"><b>Kein Treffer für „' + esc(roh)
        + "“.</b><p>Gesucht wird in Namen von Forschenden, Institutionen, "
        + "Studientiteln, Indikationen, MVF-Beiträgen, Förderern und in "
        + "den Studien der 15 Knowledge-Hubs.</p></div>");
    }
    h.push('<div class="sfuss">Durchsucht werden ' + zahl(index.eintraege.length)
      + " Einträge, die Studien der 15 Knowledge-Hubs eingeschlossen. "
      + "<b>Nicht enthalten:</b> Stellenanzeigen, für die es keine offene "
      + "Quelle gibt, und 588 Studien, deren Lizenz uns die Wiedergabe "
      + "verbietet.</div>");
    kasten.innerHTML = h.join("");
    kasten.hidden = false;
    offen = true;
    wahl = -1;
  }

  function markieren() {
    var alle = kasten.querySelectorAll(".str");
    for (var i = 0; i < alle.length; i++) {
      alle[i].classList.toggle("an", i === wahl);
      if (i === wahl) { alle[i].scrollIntoView({ block: "nearest" }); }
    }
  }

  function tasten(ev) {
    var alle = kasten.querySelectorAll(".str");
    if (ev.key === "Escape") {
      kasten.hidden = true; offen = false; return;
    }
    if (!offen || !alle.length) { return; }
    if (ev.key === "ArrowDown") {
      ev.preventDefault(); wahl = (wahl + 1) % alle.length; markieren();
    } else if (ev.key === "ArrowUp") {
      ev.preventDefault();
      wahl = (wahl - 1 + alle.length) % alle.length; markieren();
    } else if (ev.key === "Enter" && wahl >= 0) {
      ev.preventDefault(); alle[wahl].click();
    }
  }

  function start() {
    feld = document.getElementById("allesuche");
    kasten = document.getElementById("allesuche-treffer");
    if (!feld || !kasten) { return; }

    var warte = null;
    function reagieren() {
      clearTimeout(warte);
      warte = setTimeout(function () {
        if (norm(feld.value).length < 2) { malen(feld.value); return; }
        laden().then(function (d) {
          if (!d) {
            kasten.innerHTML = '<div class="sleer"><b>Der Suchindex ließ '
              + "sich nicht laden.</b><p>Die Seiten selbst funktionieren "
              + "weiter.</p></div>";
            kasten.hidden = false;
            return;
          }
          malen(feld.value);
        });
      }, 120);
    }
    feld.addEventListener("input", reagieren);
    feld.addEventListener("focus", function () { laden(); });
    feld.addEventListener("keydown", tasten);
    document.addEventListener("click", function (ev) {
      if (!kasten.contains(ev.target) && ev.target !== feld) {
        kasten.hidden = true; offen = false;
      }
    });
    /* Mit ?q= in der Adresse laesst sich ein Treffer verlinken. */
    var q = new URLSearchParams(location.search).get("q");
    if (q) { feld.value = q; reagieren(); }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start);
  } else { start(); }
})();
