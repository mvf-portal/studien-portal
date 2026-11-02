/* Eine Steuerung fuer die langen Listen: Sortierung, Filter, Mengengrenze.
 *
 * WARUM
 * -----
 * Peter Stegmaier hat am 01.11.2026 zwei Dinge gefragt, die dieselbe
 * Ursache haben: „wie sind die sortiert? alfabetisch? filter möglich?"
 * und „nicht klickbar, warum?".
 *
 * Die Seiten waren nach Studien und Projekten absteigend sortiert, und
 * das stand nirgends. Sie zeigten 40 je Abschnitt, und die uebrigen 2.390
 * Einrichtungen waren nur ueber die Suche erreichbar. Eine Rangliste, die
 * ihre Regel nicht nennt, ist eine Behauptung.
 *
 * WIE
 * ---
 * Die Seite liefert ALLE Zeilen aus. Ohne JavaScript ist die Liste lang,
 * aber vollstaendig und richtig sortiert. Mit JavaScript blendet diese
 * Datei ueber die Mengengrenze hinaus aus, sortiert um und filtert.
 *
 * ⚠ NICHT AUF NACHLADEN UMSTELLEN. Die Zeilen tragen die Sprungmarken, zu
 * denen die Suche verlinkt (forschende.html#sundmacher-leonie). Was erst
 * JavaScript baut, ist beim Sprung noch nicht da.
 *
 * ⚠ DIE STANDZEILE MUSS SAGEN, WAS FEHLT. Getrennt nach Filter und
 * Mengengrenze. Eine Auswahl, die ihre Auslassung verschweigt, laesst die
 * Lesenden glauben, sie saehen alles.
 */
(function () {
  "use strict";

  function zahl(n) {
    return String(n).replace(/\B(?=(\d{3})+(?!\d))/g, ".");
  }

  function norm(s) {
    s = (s || "").toLowerCase();
    s = s.replace(/ä/g, "ae").replace(/ö/g, "oe").replace(/ü/g, "ue")
         .replace(/ß/g, "ss");
    return s.normalize ? s.normalize("NFKD").replace(/[̀-ͯ]/g, "")
                       : s;
  }

  function aufbauen(raum) {
    var steuer = raum.querySelector(".steuer");
    if (!steuer) { return; }
    var stand = steuer.querySelector(".steuer-stand");
    var sortfeld = steuer.querySelector("[data-sort]");
    var suchfeld = steuer.querySelector("[data-such]");
    var filterfelder = Array.prototype.slice.call(
      steuer.querySelectorAll("[data-filter]"));

    /* Jeder Abschnitt fuer sich: Die Traegerarten bleiben getrennt, und
       eine Hochschule rutscht nicht zwischen die Unternehmen. */
    var teile = Array.prototype.slice.call(
      raum.querySelectorAll("[data-teil]")).map(function (t) {
        var kasten = t.querySelector(".haeuser");
        return {
          abschnitt: t,
          kasten: kasten,
          zeilen: kasten ? Array.prototype.slice.call(
            kasten.querySelectorAll(".haus")) : [],
          grenze: parseInt(t.getAttribute("data-grenze") || "40", 10),
          alle: false,
          knopf: null,
          fuss: t.querySelector(".teil-stand")
        };
      }).filter(function (t) { return t.kasten; });

    if (!teile.length) { return; }

    function schluessel(zeile, art) {
      if (art === "name") { return zeile.getAttribute("data-n") || ""; }
      return -parseFloat(zeile.getAttribute("data-" + art) || "0");
    }

    function sortieren(art) {
      teile.forEach(function (t) {
        var kopie = t.zeilen.slice();
        /* Stabil sortieren: Bei gleichem Wert bleibt die Reihenfolge, die
           der Bau geliefert hat. Sonst springen Zeilen bei jedem Umschalten
           grundlos umher. */
        kopie.forEach(function (z, i) { z.__i = i; });
        kopie.sort(function (a, b) {
          var x = schluessel(a, art), y = schluessel(b, art);
          if (x < y) { return -1; }
          if (x > y) { return 1; }
          return a.__i - b.__i;
        });
        var f = document.createDocumentFragment();
        kopie.forEach(function (z) { f.appendChild(z); });
        t.kasten.appendChild(f);
        t.zeilen = kopie;
      });
    }

    function passt(zeile, suche, filter) {
      for (var k in filter) {
        if (!filter[k]) { continue; }
        var wert = " " + (zeile.getAttribute("data-" + k) || "") + " ";
        if (wert.indexOf(" " + filter[k] + " ") < 0) { return false; }
      }
      if (suche) {
        var s = zeile.getAttribute("data-such") || "";
        if (s.indexOf(suche) < 0) { return false; }
      }
      return true;
    }

    function malen() {
      var suche = norm(suchfeld ? suchfeld.value.trim() : "");
      var filter = {};
      filterfelder.forEach(function (f) {
        filter[f.getAttribute("data-filter")] = f.value || "";
      });

      var ganz = 0, gefiltert = 0, gezeigt = 0, gekappt = 0, sichtbar = 0;
      teile.forEach(function (t) {
        var n = 0, zeigt = 0;
        t.zeilen.forEach(function (z) {
          ganz += 1;
          if (!passt(z, suche, filter)) {
            z.hidden = true;
            gefiltert += 1;
            return;
          }
          n += 1;
          if (!t.alle && n > t.grenze) {
            z.hidden = true;
            gekappt += 1;
            return;
          }
          z.hidden = false;
          zeigt += 1;
        });
        gezeigt += zeigt;
        sichtbar += n;

        /* Ein Abschnitt ohne Treffer verschwindet samt Ueberschrift.
           Eine leere Ueberschrift sieht nach einem Fehler aus. */
        t.abschnitt.hidden = (n === 0);
        if (t.fuss) {
          if (n > zeigt) {
            t.fuss.hidden = false;
            t.fuss.innerHTML = "Gezeigt sind " + zahl(zeigt) + " von "
              + zahl(n) + ". <button type=\"button\" class=\"alle\">Alle "
              + zahl(n) + " zeigen</button>";
            t.fuss.querySelector("button").addEventListener(
              "click", function () { t.alle = true; malen(); });
          } else if (t.alle && n > t.grenze) {
            t.fuss.hidden = false;
            t.fuss.innerHTML = "Alle " + zahl(n) + " gezeigt. "
              + "<button type=\"button\" class=\"alle\">Wieder auf "
              + zahl(t.grenze) + " kürzen</button>";
            t.fuss.querySelector("button").addEventListener(
              "click", function () { t.alle = false; malen(); });
          } else {
            t.fuss.hidden = true;
            t.fuss.textContent = "";
          }
        }
      });

      if (stand) {
        var s = ["<b>" + zahl(gezeigt) + "</b> von " + zahl(ganz)
                 + " gezeigt"];
        /* Getrennt sagen, WARUM etwas fehlt. „1.200 ausgeblendet" laesst
           offen, ob der Filter oder die Mengengrenze es war. */
        if (gefiltert) {
          s.push(zahl(gefiltert) + " durch die Auswahl ausgeblendet");
        }
        if (gekappt) {
          s.push(zahl(gekappt) + " durch die Mengengrenze, über die Knöpfe "
                 + "in den Abschnitten erreichbar");
        }
        if (!gefiltert && !gekappt) { s.push("nichts ausgeblendet"); }
        stand.innerHTML = s.join(" &middot; ");
      }
      return sichtbar;
    }

    /* Eine Sprungmarke muss ankommen, auch wenn die Zeile gekappt war.
       Sonst springt der Browser auf eine Zeile mit hidden und zeigt den
       Seitenanfang. */
    /* ⚠ scrollIntoView ALLEIN REICHT NICHT, und zwar aus zwei Gruenden.
     * Erstens deckt malen() unmittelbar davor bis zu 5.345 Zeilen auf, und
     * die Seite wird dabei von 15.000 auf 985.000 Pixel hoch. Zweitens
     * holt der Browser seinen eigenen Sprung auf die Sprungmarke spaeter
     * nach und ueberschreibt unseren.
     * Gemessen am 01.11.2026: Der Sprung auf #betzler-felix landete
     * 115.283 Pixel unter der Zeile, am Ende der Seite.
     * Darum rechnen wir die Stelle selbst aus und fahren sie dreimal an:
     * nach dem Umbruch, nach dem Laden und noch einmal spaeter. Der letzte
     * gewinnt. */
    function hin(ziel) {
      function fahre() {
        /* block "start" achtet auf scroll-margin-top, und das haelt die
           Zeile unter der klebenden Steuerleiste frei. */
        ziel.scrollIntoView({block: "start"});
      }
      requestAnimationFrame(function () {
        requestAnimationFrame(fahre);
      });
      window.addEventListener("load", fahre);
      setTimeout(fahre, 350);
    }

    function zurAnkerzeile() {
      var h = (window.location.hash || "").slice(1);
      if (!h) { return; }
      var ziel = document.getElementById(decodeURIComponent(h));
      if (!ziel || !ziel.classList.contains("haus")) { return; }
      if (!ziel.hidden) {
        ziel.classList.add("gesucht");
        return hin(ziel);
      }
      teile.forEach(function (t) {
        if (t.zeilen.indexOf(ziel) >= 0) { t.alle = true; }
      });
      if (suchfeld) { suchfeld.value = ""; }
      filterfelder.forEach(function (f) { f.value = ""; });
      malen();
      ziel.classList.add("gesucht");
      hin(ziel);
    }

    if (sortfeld) {
      sortfeld.addEventListener("change", function () {
        sortieren(sortfeld.value);
        malen();
      });
    }
    if (suchfeld) {
      var warte = null;
      suchfeld.addEventListener("input", function () {
        clearTimeout(warte);
        warte = setTimeout(malen, 120);
      });
    }
    filterfelder.forEach(function (f) {
      f.addEventListener("change", function () {
        teile.forEach(function (t) { t.alle = false; });
        malen();
      });
    });

    /* Die Voreinstellungen aus den frueheren Abschnittsueberschriften:
       „In beiden Welten" war eine eigene Liste, jetzt ist es ein Knopf.

       ⚠ IM GANZEN DOKUMENT SUCHEN, nicht in raum. Die Knoepfe stehen im
       Hinweiskasten UEBER der Liste, also ausserhalb von .listenraum.
       Mit raum.querySelectorAll fand liste.js null Knoepfe, und alle vier
       taten nichts. */
    Array.prototype.forEach.call(
      document.querySelectorAll("[data-stellt]"), function (a) {
        a.addEventListener("click", function (ev) {
          ev.preventDefault();
          var wunsch = JSON.parse(a.getAttribute("data-stellt"));
          Object.keys(wunsch).forEach(function (k) {
            if (k === "sort" && sortfeld) { sortfeld.value = wunsch[k]; }
            else {
              filterfelder.forEach(function (f) {
                if (f.getAttribute("data-filter") === k) {
                  f.value = wunsch[k];
                }
              });
            }
          });
          if (suchfeld) { suchfeld.value = ""; }
          teile.forEach(function (t) { t.alle = false; });
          if (sortfeld) { sortieren(sortfeld.value); }
          malen();
          steuer.scrollIntoView({behavior: "smooth", block: "start"});
        });
      });

    steuer.hidden = false;
    if (sortfeld) { sortieren(sortfeld.value); }
    malen();
    zurAnkerzeile();
    window.addEventListener("hashchange", zurAnkerzeile);
  }

  Array.prototype.forEach.call(
    document.querySelectorAll(".listenraum"), aufbauen);
})();
