/* Avisos del panel SELQUET.
 * Polling al servidor de novedades (pedidos/reservas/eventos) → notificación del
 * NAVEGADOR (con fallback a toast). Al hacer click lleva al registro y lo enfoca.
 * Si la tabla de esa vista está abierta, la refresca sin recargar la página. */
(function () {
  'use strict';

  var ENDPOINT = '/admin/notificaciones/pendientes';
  var POLLING_MS = 8000;
  var soportado = 'Notification' in window;

  var EMOJI = { pedido: '🛒', reserva: '🍽️', evento: '🎉' };
  var RUTA = {
    pedido:  function (id) { return '/admin/operacion?vista=pedidos&focus=pedido-' + id; },
    reserva: function (id) { return '/admin/operacion?vista=reservas&focus=reserva-' + id; },
    evento:  function (id) { return '/admin/eventos?focus=evento-' + id; },
  };
  var VISTA_DE_TIPO = { pedido: 'pedidos', reserva: 'reservas' };  // eventos viven en otra página

  // ── permisos ──
  function pedirPermiso() { if (soportado && Notification.permission === 'default') Notification.requestPermission().then(actualizarBtn); }
  function actualizarBtn() {
    var btn = document.getElementById('btn-avisos');
    if (!btn) return;
    if (!soportado) { btn.style.display = 'none'; return; }
    if (Notification.permission === 'granted') { btn.textContent = '🔔 Avisos activados'; btn.classList.add('on'); }
    else if (Notification.permission === 'denied') { btn.textContent = '🔔 Avisos bloqueados'; }
    else { btn.textContent = '🔔 Activar avisos'; }
  }

  // ── ir al registro y enfocarlo ──
  function enfocar(anchor) {
    var el = document.getElementById(anchor);
    if (!el) return false;
    el.scrollIntoView({ behavior: 'smooth', block: 'center' });
    el.classList.add('destacado');
    setTimeout(function () { el.classList.remove('destacado'); }, 3000);
    return true;
  }
  function irA(tipo, refId) {
    if (refId == null) return;
    if (enfocar(tipo + '-' + refId)) return;      // ya está en esta página → solo foco
    if (RUTA[tipo]) window.location.href = RUTA[tipo](refId);
  }

  // ── avisos ──
  function sonar() {
    try {
      var ctx = new (window.AudioContext || window.webkitAudioContext)();
      var osc = ctx.createOscillator(), gain = ctx.createGain();
      osc.connect(gain); gain.connect(ctx.destination);
      osc.type = 'sine'; osc.frequency.value = 880; gain.gain.value = 0.07;
      osc.start(); setTimeout(function () { osc.stop(); ctx.close(); }, 200);
    } catch (e) { /* sin audio */ }
  }

  function toast(n) {
    var cont = document.getElementById('notif-toasts');
    if (!cont) { cont = document.createElement('div'); cont.id = 'notif-toasts'; document.body.appendChild(cont); }
    var el = document.createElement('div');
    el.className = 'notif-toast';
    var e = document.createElement('span'); e.className = 'notif-toast-emoji'; e.textContent = EMOJI[n.tipo] || '🔔';
    var s = document.createElement('span'); s.textContent = n.mensaje;
    el.appendChild(e); el.appendChild(s);
    el.addEventListener('click', function () { irA(n.tipo, n.ref_id); el.remove(); });
    cont.appendChild(el);
    sonar();
    setTimeout(function () { el.remove(); }, 10000);
  }

  function avisar(n) {
    if (soportado && Notification.permission === 'granted') {
      try {
        var notif = new Notification(n.mensaje, { icon: '/static/selquet-logo.svg', tag: 'selquet-' + (n.id || '') });
        notif.onclick = function () { window.focus(); irA(n.tipo, n.ref_id); notif.close(); };
        return;
      } catch (e) { /* cae al toast */ }
    }
    toast(n);   // fallback si no hay permiso o el navegador no soporta
  }

  // ── refresco de la tabla abierta (sin recargar) ──
  function refrescar(cont, vista) {
    var qs = 'vista=' + encodeURIComponent(vista);
    var fecha = new URLSearchParams(window.location.search).get('fecha');
    if (fecha) qs += '&fecha=' + encodeURIComponent(fecha);
    fetch('/admin/operacion/tabla?' + qs, { cache: 'no-store' })
      .then(function (r) { return r.ok ? r.text() : null; })
      .then(function (html) { if (html != null) cont.innerHTML = html; });
  }
  function quizasRefrescar(nuevas) {
    var cont = document.getElementById('op-tabla');
    if (!cont) return;
    var vista = cont.getAttribute('data-vista');
    if (nuevas.some(function (n) { return VISTA_DE_TIPO[n.tipo] === vista; })) refrescar(cont, vista);
  }

  // ── polling ──
  function verificar() {
    fetch(ENDPOINT, { cache: 'no-store' })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (data) {
        var nuevas = data && data.notificaciones;
        if (!nuevas || !nuevas.length) return;
        nuevas.forEach(avisar);
        quizasRefrescar(nuevas);
      })
      .catch(function () { /* red caída: reintenta en el próximo ciclo */ });
  }

  function focoInicial() {
    var f = new URLSearchParams(window.location.search).get('focus');
    if (f) setTimeout(function () { enfocar(f); }, 250);
  }

  function init() {
    actualizarBtn();
    var btn = document.getElementById('btn-avisos');
    if (btn) btn.addEventListener('click', pedirPermiso);
    document.addEventListener('click', pedirPermiso, { once: true });
    pedirPermiso();
    focoInicial();
    verificar();
    setInterval(verificar, POLLING_MS);
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
