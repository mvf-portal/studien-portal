/* Karte und Rangliste der Forschungsstandorte.
 *
 * ⚠ NICHT NEU ERFINDEN: Die Mercator-Rechnung in `karteBauen` ist teuer
 * erkauft. Laenge in Grad und Breite in Mercator-Bogenmass zu mischen
 * macht aus Deutschland einen waagerechten Strich. BEIDE Achsen im
 * Bogenmass, so wie es hier steht.
 *
 * Herausgeloest aus der alten Einseitenfassung (`vorlage.html`), damit
 * `standorte.html` die Karte traegt, ohne den ganzen Studienteil
 * mitzuschleppen. Die Funktionen sind unveraendert uebernommen, nur die
 * Datenanbindung oben ist neu.
 */
(function () {
  "use strict";
  var el = document.getElementById("daten");
  if (!el) { return; }
  var D = JSON.parse(el.textContent);
  var Z = D.zaehlung || {};
  var ORTE = (D.standorte && D.standorte.standorte) || [];
  var S = D.studien || [];

  function esc(s){ return String(s==null?"":s).replace(/[&<>"]/g, function(c){
    return {"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;"}[c]; }); }
  function zahl(n){ return Number(n||0).toLocaleString("de-DE"); }
  function id(x){ return document.getElementById(x); }

  /* Zustand der Ortliste. Stand in der alten Einseitenfassung ausserhalb
     der Funktionen und muss hier mitkommen, sonst wirft `zeichneOrte`. */
  var ogezeigt = 60, ogefiltert = ORTE;
  var ogewaehlt = { traeger: "", fach: "" };

  var mehr = id("omehr");
  if (mehr) {
    mehr.addEventListener("click", function () {
      ogezeigt += 60;
      zeichneOrte();
    });
  }

  function karteBauen(){
    var ziel = id("karte");
    if (!ziel) { return; }
    var ringe = D.kontur || [];
    var orte = ((D.standorte || {}).standorte || [])
                 .filter(function(s){ return s.lat && s.lon; });
    if (!ringe.length) {
      ziel.innerHTML = "<p class='kartenhinweis'>Der Umriss fehlt, die "
        + "Karte bleibt aus. (daten/kontur.json, erzeugt mit kontur.py)</p>";
      return;
    }

    var B = 640, H = 820, R = 18;          /* Zeichenflaeche und Rand */
    /* BEIDE Achsen im Bogenmass. Nimmt man die Laenge in Grad und die
       Breite in Mercator-Einheiten (die sind im Bogenmass), unterscheiden
       sich die Spannweiten um den Faktor 57 - und Deutschland wird zu
       einem waagerechten Strich. Genau so ist es beim ersten Versuch
       herausgekommen. */
    function mx(lon){ return lon * Math.PI / 180; }
    function my(lat){ return Math.log(Math.tan(Math.PI/4 + lat*Math.PI/360)); }

    var lo = [], la = [];
    ringe.forEach(function(r){ r.forEach(function(p){
      lo.push(mx(p[0])); la.push(my(p[1])); }); });
    var lo0 = Math.min.apply(null, lo), lo1 = Math.max.apply(null, lo),
        la0 = Math.min.apply(null, la), la1 = Math.max.apply(null, la);
    var sx = (B - 2*R) / (lo1 - lo0), sy = (H - 2*R) / (la1 - la0),
        s  = Math.min(sx, sy);
    var vx = R + ((B - 2*R) - (lo1 - lo0)*s) / 2,
        vy = R + ((H - 2*R) - (la1 - la0)*s) / 2;
    function X(lon){ return vx + (mx(lon) - lo0) * s; }
    function Y(lat){ return vy + (la1 - my(lat)) * s; }

    var d = ringe.map(function(r){
      return "M" + r.map(function(p){
        return X(p[0]).toFixed(1) + " " + Y(p[1]).toFixed(1);
      }).join("L") + "Z";
    }).join(" ");

    /* Flaeche nach Studienzahl, nicht Radius: Ein Kreis mit doppeltem
       Radius sieht VIERMAL so gross aus und uebertreibt den Unterschied. */
    var max = Math.max.apply(null, orte.map(function(o){ return o.studien; }));
    function rad(n){ return 4 + 16 * Math.sqrt(n / max); }

    orte.sort(function(a, b){ return b.studien - a.studien; });
    var punkte = orte.map(function(o){
      var x = X(o.lon), y = Y(o.lat), r = rad(o.studien);
      var stadt = o.koordinate === "ort";
      return '<a href="standort/' + o.datei + '" class="kpunkt'
        + (stadt ? ' nurstadt' : '') + '">'
        + '<title>' + esc(o.name) + ', ' + o.studien + ' Studien'
        + (o.ort ? ', ' + esc(o.ort) : '')
        + (stadt ? ' (Lage der Stadt, nicht der Einrichtung)' : '')
        + '</title>'
        + '<circle cx="' + x.toFixed(1) + '" cy="' + y.toFixed(1)
        + '" r="' + r.toFixed(1) + '"/></a>';
    }).join("");

    /* Die groessten beschriften - mehr wird zur Buchstabenwolke. */
    var namen = orte.slice(0, 8).map(function(o){
      var x = X(o.lon), y = Y(o.lat), r = rad(o.studien);
      var rechts = x < B * 0.55;
      return '<text class="kname" x="' + (x + (rechts ? r+5 : -(r+5))).toFixed(1)
        + '" y="' + (y + 3.5).toFixed(1) + '"'
        + (rechts ? '' : ' text-anchor="end"') + '>'
        + esc(o.ort || o.name) + '</text>';
    }).join("");

    var ohne = ((D.standorte || {}).standorte || []).length - orte.length;
    var nurStadt = orte.filter(function(o){
      return o.koordinate === "ort"; }).length;
    ziel.innerHTML =
      '<svg viewBox="0 0 ' + B + ' ' + H + '" class="ksvg" role="img" '
      + 'aria-label="Karte der Forschungsstandorte">'
      + '<path class="kland" d="' + d + '"/>' + punkte + namen + '</svg>'
      + "<p class='kartenhinweis'>Kreisfläche nach Zahl der Studien. "
      + "Anklicken führt zum Standortprofil. Ortsangabe aus ROR und "
      + "OpenAlex, geprüft gegen den Ort im Register."
      + (nurStadt > 0 ? " <b>" + nurStadt + " Kreise sind hohl</b>: Dort "
           + "ließ sich die Einrichtung nicht zweifelsfrei zuordnen, "
           + "meist weil die Kennung zur Mutterorganisation in einer anderen "
           + "Stadt gehört. Gezeigt wird dann der Ort aus dem Register, "
           + "nicht die Lage der Einrichtung." : "")
      + (ohne > 0 ? " " + ohne + " Standort"
           + (ohne === 1 ? " ist" : "e sind") + " gar nicht eingezeichnet."
         : "")
      + "</p>";
  }

  function toplisteBauen(){
    var ziel = id("topliste");
    if (!ziel) { return; }
    var orte = ((D.standorte || {}).standorte || []).slice();
    if (!orte.length) { return; }
    orte.sort(function(a, b){
      return b.studien - a.studien || (a.name || "").localeCompare(b.name || "");
    });
    var N = 15, max = orte[0].studien;
    var zeilen = orte.slice(0, N).map(function(o, i){
      var breite = (100 * o.studien / max).toFixed(1);
      return '<li>'
        + '<span class="tplatz">' + (i + 1) + '</span>'
        + '<a class="tname" href="standort/' + o.datei + '">' + esc(o.name)
        + '</a>'
        + '<span class="tort">' + esc(o.ort || "") + '</span>'
        + '<span class="tbalken"><i style="width:' + breite + '%"></i></span>'
        + '<span class="tzahl">' + o.studien + '</span>'
        + '</li>';
    }).join("");
    ziel.innerHTML =
      "<h2>Die Standorte mit den meisten Studien</h2>"
      + '<ol class="tliste">' + zeilen + "</ol>"
      + "<p class='kartenhinweis' style='text-align:left'>"
      + "Gezählt sind die " + zahl(D.vf_gesamt) + " Studien, die wir "
      + "wiedergeben dürfen. <b>Das misst nicht das Lebenswerk, sondern "
      + "wer zuletzt registriert hat</b>, denn die Lizenz des Registers "
      + "hängt am Datum, ältere und abgeschlossene Forschung fehlt "
      + "deshalb. Eine Einrichtung kann hier klein aussehen und trotzdem "
      + "seit Jahrzehnten führend sein.</p>";
  }

  function ortkarte(o){
    /* Jede Angabe in ein eigenes <span>, sonst greift der Abstand des
       Rasters nicht und die Zeile laeuft zusammen. */
    var z = ["<span><b>" + zahl(o.studien) + "</b> Studien</span>"];
    if (o.rekrutiert) z.push('<span class="g"><b>' + zahl(o.rekrutiert) +
      "</b> rekrutieren</span>");
    if (o.zentren) z.push("<span>" + zahl(o.zentren) + " Studienzentren</span>");
    if (o.ror) z.push("<span>im Innofonds-Radar</span>");
    var fach = (o.faecher || []).length
      ? '<span class="fa">' + esc(o.faecher.join(" · ")) + "</span>"
      : '<span class="fa leer">Fach im Register nicht genannt</span>';
    return '<a class="ortkarte" href="standort/' + esc(o.datei) + '">' +
      '<span class="nm">' + esc(o.name) + "</span>" +
      '<span class="wo">' + esc([o.ort, o.land].filter(Boolean).join(" · ")) + "</span>" +
      '<span class="ta">' + esc(o.traegerart || "") + "</span>" + fach +
      '<span class="zz">' + z.join("") + "</span></a>";
  }

  function zeichneOrte(){
    /* ⚠ Das eigene Suchfeld der alten Einseitenfassung gibt es hier nicht
       mehr. Gesucht wird oben, ueber ALLE Bestaende. Ohne diese Pruefung
       wirft die Zeile und die ganze Ortliste bleibt leer. */
    var feld = id("suche");
    var q = feld ? feld.value.trim().toLowerCase() : "";
    ogefiltert = ORTE.filter(function(o){
      if (ogewaehlt.traeger && o.traegerart !== ogewaehlt.traeger) return false;
      if (ogewaehlt.fach) {
        if (ogewaehlt.fach === "__offen__") {
          if ((o.faecher || []).length) return false;
        } else if ((o.faecher || []).indexOf(ogewaehlt.fach) < 0) return false;
      }
      if (!q) return true;
      return ((o.name + " " + o.ort + " " + o.land + " " +
               (o.traegerart || "") + " " + (o.faecher || []).join(" ") + " " +
               (o.schreibweisen || []).join(" ")).toLowerCase().indexOf(q) >= 0);
    });
    id("ortliste").innerHTML = ogefiltert.slice(0, ogezeigt).map(ortkarte).join("") ||
      '<div class="studie" style="text-align:center;color:var(--ink-faint)">Kein Standort gefunden.</div>';
    id("otreffer").textContent = zahl(ogefiltert.length) + " von " +
      zahl(ORTE.length) + " Forschungsstandorten";
    id("omehr").hidden = ogezeigt >= ogefiltert.length;
    /* ⚠ Den Filterkasten der alten Einseitenfassung gibt es hier nicht.
       Ohne diese Pruefung wirft die Zeile NACH dem Zeichnen, die Liste
       steht dann zwar da, aber der Fehler verdeckt jeden echten. */
    var anzeige = id("ofaktiv");
    if (anzeige) {
      var t = [];
      if (ogewaehlt.traeger) t.push(ogewaehlt.traeger);
      if (ogewaehlt.fach) t.push(ogewaehlt.fach === "__offen__"
        ? "Fach nicht genannt" : ogewaehlt.fach);
      anzeige.textContent = t.length ? t.join(" · ") : "alle Standorte";
    }
  }
  /* Start */
  try { karteBauen(); } catch (e) { console.error("Karte:", e); }
  try { toplisteBauen(); } catch (e) { console.error("Rangliste:", e); }
  try { zeichneOrte(); } catch (e) { console.error("Ortliste:", e); }
})();
