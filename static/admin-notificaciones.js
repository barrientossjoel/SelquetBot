/* Avisos pop-up del panel: consulta /admin/notificaciones y avisa (notificación
 * del navegador + toast + sonido) cuando entra un pedido, reserva o evento nuevo.
 * Es genérico: recorre lo que devuelve el endpoint, no conoce los tipos. */
(function () {
  'use strict';

  var ENDPOINT = '/admin/notificaciones';
  var STORAGE_KEY = 'selquet_notif_vistos';
  var INTERVALO_MS = 20000;
  var soportado = 'Notification' in window;

  var vistos = leer();

  function leer() {
    try { return JSON.parse(localStorage.getItem(STORAGE_KEY)) || null; }
    catch (e) { return null; }
  }
  function guardar() { localStorage.setItem(STORAGE_KEY, JSON.stringify(vistos)); }

  function pedirPermiso() {
    if (soportado && Notification.permission === 'default') Notification.requestPermission();
  }

  function sonar() {
    try {
      var ctx = new (window.AudioContext || window.webkitAudioContext)();
      var osc = ctx.createOscillator(), gain = ctx.createGain();
      osc.connect(gain); gain.connect(ctx.destination);
      osc.type = 'sine'; osc.frequency.value = 880; gain.gain.value = 0.08;
      osc.start();
      setTimeout(function () { osc.stop(); ctx.close(); }, 220);
    } catch (e) { /* sin audio, no pasa nada */ }
  }

  function toast(titulo, cuerpo) {
    var cont = document.getElementById('notif-toasts');
    if (!cont) {
      cont = document.createElement('div');
      cont.id = 'notif-toasts';
      document.body.appendChild(cont);
    }
    var el = document.createElement('div');
    el.className = 'notif-toast';
    var b = document.createElement('b'); b.textContent = titulo;
    var s = document.createElement('span'); s.textContent = cuerpo || '';
    el.appendChild(b); el.appendChild(s);
    el.addEventListener('click', function () { el.remove(); });
    cont.appendChild(el);
    setTimeout(function () { el.remove(); }, 12000);
  }

  function avisar(titulo, cuerpo) {
    if (soportado && Notification.permission === 'granted') {
      try {
        var n = new Notification(titulo, {
          body: cuerpo || '', icon: '/static/selquet-logo.svg', tag: 'selquet-' + Date.now(),
        });
        n.onclick = function () { window.focus(); };
      } catch (e) { /* algunos navegadores restringen; el toast alcanza */ }
    }
    toast(titulo, cuerpo);
    sonar();
  }

  function chequear() {
    fetch(ENDPOINT, { cache: 'no-store' })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (data) {
        if (!data) return;
        if (vistos === null) {                 // primera vez: fijar línea base, sin avisar
          vistos = {};
          for (var k in data) vistos[k] = data[k].max_id;
          guardar();
          return;
        }
        var cambio = false;
        for (var clave in data) {
          var info = data[clave];
          if (info.max_id > (vistos[clave] || 0)) {
            avisar(info.titulo, info.label);
            vistos[clave] = info.max_id;
            cambio = true;
          }
        }
        if (cambio) guardar();
      })
      .catch(function () { /* red caída: reintenta en el próximo ciclo */ });
  }

  document.addEventListener('click', pedirPermiso, { once: true });
  var btn = document.getElementById('btn-avisos');
  if (btn) btn.addEventListener('click', pedirPermiso);
  pedirPermiso();
  chequear();
  setInterval(chequear, INTERVALO_MS);
})();
