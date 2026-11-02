/* Die Eintragsseite: zwei Formulare, ein Absendeweg.
 *
 * WARUM DIESE SEITE
 * -----------------
 * Drei Seiten verwiesen auf „Zum Formular" und meinten
 * standort-vorlage.html. Das ist eine Vorlage mit 17 Platzhaltern. Wer
 * klickte, sah „{{NAME}}" als Ueberschrift.
 *
 * WARUM ZWEI FORMULARE
 * --------------------
 * 2.265 von 2.430 Einrichtungen haben keine Profilseite, 4.056 von 5.395
 * Personen kein Profil bei MVF. Fuer beide Gruppen ist die Selbstauskunft
 * der einzige Weg in den Bestand, und eine Einrichtung traegt andere
 * Angaben ein als ein Mensch.
 *
 * ⚠ DER NAME KOMMT AUS DER ADRESSZEILE, NICHT AUS DEM BESTAND.
 * Jede Zeile auf institutionen.html und forschende.html, die kein Ziel
 * hat, verweist hierher mit ?art=…&name=…. Der Name wird darum wie Text
 * behandelt und nur in Formularfelder gesetzt, nie in die Seite
 * geschrieben, wo er Auszeichnung mitbringen koennte.
 */
(function () {
  "use strict";

  /* Derselbe Weg wie auf den Standortseiten und den Innofonds-Pruefseiten:
     POST an einen Endpunkt auf dem MVF-Server. Solange er fehlt, sagt die
     Seite das und oeffnet eine vorbereitete E-Mail. Eine Seite, die um
     Eintraege BITTET, darf die Leute nicht mit einem Fehler stehen
     lassen. */
  /* ⚠ KEINE EIGENE ADRESSE HIER. Diese Datei geht nicht durch
     eine Vorlage, also kann sie keinen Platzhalter tragen. Den
     Wert setzt seiten.py als window.ENDPUNKT in die Seite, und
     die eine Quelle bleibt standorte.py. Vorher stand hier eine
     zweite leere Konstante - die haette beim Scharfstellen still
     leer bleiben koennen. */
  var ENDPUNKT = window.ENDPUNKT || "";

  function abfrage(name) {
    var m = new RegExp("[?&]" + name + "=([^&]*)").exec(
      window.location.search || "");
    if (!m) { return ""; }
    try { return decodeURIComponent(m[1].replace(/\+/g, " ")); }
    catch (e) { return ""; }
  }

  var art = abfrage("art") === "person" ? "person" : "einrichtung";
  var name = abfrage("name").slice(0, 200);

  /* Den gemeinten Teil aufmachen und den Namen eintragen. */
  function vorbereiten() {
    var teil = document.getElementById("teil-" + art);
    if (teil) { teil.open = true; }
    if (!name) { return; }
    var feld = document.getElementById(
      art === "person" ? "person-name" : "einrichtung-name");
    if (feld) { feld.value = name; }
    var sage = document.getElementById("gemeint");
    if (sage) {
      /* textContent, nicht innerHTML: Der Name kommt aus der Adresszeile. */
      sage.textContent = name;
      /* ⚠ NICHT parentNode: Das ist der <p>, der Kasten ist der Grossvater.
         Mit parentNode blieb der Kasten verborgen, obwohl der Name drin
         stand. */
      var kasten = sage.closest(".hinweiskasten");
      if (kasten) { kasten.hidden = false; }
    }
  }

  /* Umschalten zwischen den beiden Teilen, ohne die Seite neu zu laden. */
  function umschalten() {
    Array.prototype.forEach.call(
      document.querySelectorAll("[data-oeffnet]"), function (a) {
        a.addEventListener("click", function (ev) {
          ev.preventDefault();
          var ziel = document.getElementById(a.getAttribute("data-oeffnet"));
          if (!ziel) { return; }
          ziel.open = true;
          ziel.scrollIntoView({ behavior: "smooth", block: "start" });
        });
      });
  }

  function absenden(f, betreff, was) {
    var st = f.querySelector(".stand");
    f.addEventListener("submit", function (ev) {
      ev.preventDefault();
      var d = new FormData(f), o = { was: was };
      d.forEach(function (v, k) { o[k] = v; });
      if (!o.email || o.email.indexOf("@") < 1) {
        st.className = "stand fehl";
        st.textContent = "Bitte eine dienstliche E-Mail-Adresse angeben.";
        return;
      }
      if (!ENDPUNKT) {
        var zeilen = [];
        Object.keys(o).forEach(function (k) {
          if (k === "email" || k === "was") { return; }
          var v = (o[k] == null ? "" : String(o[k])).trim();
          if (v) { zeilen.push(k + ": " + v); }
        });
        var UM = String.fromCharCode(10);
        var mail = "mailto:info@m-vf.de"
          + "?subject=" + encodeURIComponent(betreff)
          + "&body=" + encodeURIComponent(
            "Absender: " + (o.email || "") + UM + UM + zeilen.join(UM + UM));
        st.className = "stand";
        st.innerHTML = "Das Absenden über die Seite ist noch nicht "
          + "eingerichtet, wir richten den Zugang gerade ein. "
          + "<a href='" + mail + "'>Ihre Angaben als E-Mail öffnen</a>: "
          + "Der Text ist bereits ausgefüllt, Sie müssen nur senden.";
        return;
      }
      st.className = "stand";
      st.textContent = "wird gesendet …";
      fetch(ENDPUNKT, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(o)
      }).then(function (r) {
        if (r.ok) {
          st.className = "stand ok";
          st.textContent = "Angekommen. Wir schicken den persönlichen Link "
            + "an " + o.email + ".";
          f.querySelector("button[type=submit]").disabled = true;
        } else if (r.status === 429) {
          st.className = "stand";
          st.textContent = "Ihre vorige Einsendung ist angekommen. Der "
            + "Server nimmt nur eine Einsendung pro Minute an.";
        } else {
          st.className = "stand fehl";
          st.textContent = "Der Server hat abgelehnt (" + r.status
            + "). Bitte schreiben Sie an info@m-vf.de.";
        }
      }).catch(function () {
        st.className = "stand fehl";
        st.textContent = "Keine Verbindung. Bitte später erneut versuchen "
          + "oder an info@m-vf.de schreiben.";
      });
    });
  }

  vorbereiten();
  umschalten();
  var fe = document.getElementById("form");
  if (fe) { absenden(fe, "Einrichtung eintragen: " + name, "einrichtung"); }
  var fp = document.getElementById("form-person");
  if (fp) { absenden(fp, "Eigenen Eintrag pflegen: " + name, "person"); }
})();
