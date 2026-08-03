/* Notificaciones del panel SELQUET (mismo patrón que ocr_web).
 * Campana con badge + dropdown (persistido en localStorage) + toasts, y polling
 * al servidor de las novedades pendientes (pedidos, reservas, eventos). */
(function () {
  'use strict';

  var CONFIG = {
    ENDPOINT: '/admin/notificaciones/pendientes',
    POLLING_MS: 8000,
    MAX: 20,
    STORAGE_KEY: 'selquet_notifs',
  };

  var EMOJI = { pedido: '🛒', reserva: '🍽️', evento: '🎉' };

  var notifs = [];

  // ── persistencia ──
  function cargar() { try { notifs = JSON.parse(localStorage.getItem(CONFIG.STORAGE_KEY)) || []; } catch (e) { notifs = []; } }
  function guardar() { localStorage.setItem(CONFIG.STORAGE_KEY, JSON.stringify(notifs)); }

  // ── alta de una notificación ──
  function agregar(mensaje, tipo) {
    notifs.unshift({
      mensaje: mensaje,
      emoji: EMOJI[tipo] || '🔔',
      hora: new Date().toLocaleTimeString('es-AR', { hour: '2-digit', minute: '2-digit' }),
    });
    if (notifs.length > CONFIG.MAX) notifs.pop();
    guardar();
    actualizarBadge();
    animarCampana();
    render();
  }

  // ── UI ──
  function actualizarBadge() {
    var badge = document.getElementById('notif-badge');
    if (!badge) return;
    badge.textContent = notifs.length > 9 ? '9+' : notifs.length;
    badge.style.display = notifs.length > 0 ? 'flex' : 'none';
  }

  function animarCampana() {
    var btn = document.querySelector('.notif-btn');
    if (!btn) return;
    btn.classList.add('notif-shake');
    setTimeout(function () { btn.classList.remove('notif-shake'); }, 500);
  }

  function render() {
    var lista = document.getElementById('notif-list');
    if (!lista) return;
    if (notifs.length === 0) {
      lista.innerHTML = '<div class="notif-empty">Sin notificaciones</div>';
      return;
    }
    lista.innerHTML = notifs.map(function (n) {
      return '<div class="notif-item"><span class="notif-emoji">' + n.emoji + '</span>' +
             '<div class="notif-content"><span class="notif-msg"></span>' +
             '<span class="notif-time">' + n.hora + '</span></div></div>';
    }).join('');
    // texto por separado para no inyectar HTML del mensaje
    var items = lista.querySelectorAll('.notif-msg');
    notifs.forEach(function (n, i) { if (items[i]) items[i].textContent = n.mensaje; });
  }

  function toggle(event) {
    if (event) event.stopPropagation();
    var dd = document.getElementById('notif-dropdown');
    if (dd) { dd.classList.toggle('active'); if (dd.classList.contains('active')) render(); }
  }

  function limpiar() { notifs = []; guardar(); actualizarBadge(); render(); }

  function toast(mensaje, emoji) {
    var cont = document.getElementById('notif-toasts');
    if (!cont) { cont = document.createElement('div'); cont.id = 'notif-toasts'; document.body.appendChild(cont); }
    var el = document.createElement('div');
    el.className = 'notif-toast';
    var e = document.createElement('span'); e.className = 'notif-toast-emoji'; e.textContent = emoji || '🔔';
    var s = document.createElement('span'); s.textContent = mensaje;
    el.appendChild(e); el.appendChild(s);
    el.addEventListener('click', function () { el.remove(); });
    cont.appendChild(el);
    setTimeout(function () { el.remove(); }, 10000);
  }

  function sonar() {
    try {
      var ctx = new (window.AudioContext || window.webkitAudioContext)();
      var osc = ctx.createOscillator(), gain = ctx.createGain();
      osc.connect(gain); gain.connect(ctx.destination);
      osc.type = 'sine'; osc.frequency.value = 880; gain.gain.value = 0.07;
      osc.start(); setTimeout(function () { osc.stop(); ctx.close(); }, 200);
    } catch (e) { /* sin audio */ }
  }

  // ── polling al servidor ──
  function verificar() {
    fetch(CONFIG.ENDPOINT, { cache: 'no-store' })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (data) {
        if (!data || !data.notificaciones || !data.notificaciones.length) return;
        data.notificaciones.forEach(function (n) {
          var emoji = EMOJI[n.tipo] || '🔔';
          toast(n.mensaje, emoji);
          agregar(n.mensaje, n.tipo);
        });
        sonar();
      })
      .catch(function () { /* red caída: reintenta en el próximo ciclo */ });
  }

  function bindEventos() {
    document.addEventListener('click', function (e) {
      var wrap = document.querySelector('.notif-wrapper');
      var dd = document.getElementById('notif-dropdown');
      if (wrap && dd && !wrap.contains(e.target)) dd.classList.remove('active');
    });
  }

  function init() {
    cargar();
    actualizarBadge();
    render();
    bindEventos();
    verificar();
    setInterval(verificar, CONFIG.POLLING_MS);
  }

  window.Notificaciones = { toggle: toggle, limpiar: limpiar };

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
