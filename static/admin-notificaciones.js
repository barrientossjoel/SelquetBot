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
    pedido:  function (id) { return '/admin/takeaway?focus=pedido-' + id; },
    reserva: function (id) { return '/admin/reservas?focus=reserva-' + id; },
    evento:  function (id) { return '/admin/reservas?tab=corporativas&focus=evento-' + id; },
  };
  var VISTA_DE_TIPO = { pedido: 'pedidos' };  // solo Takeaway se refresca en vivo

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

  // ── sonido ──
  // Un AudioContext único, desbloqueado en el primer gesto del usuario (política
  // de autoplay). Cada aviso son 3 beeps para que se note (molesta a propósito).
  var audioCtx = null;
  function desbloquearAudio() {
    if (!audioCtx) { try { audioCtx = new (window.AudioContext || window.webkitAudioContext)(); } catch (e) { audioCtx = null; } }
    if (audioCtx && audioCtx.state === 'suspended') audioCtx.resume();
  }
  function beep(freq, cuando, dur) {
    var osc = audioCtx.createOscillator(), gain = audioCtx.createGain();
    osc.connect(gain); gain.connect(audioCtx.destination);
    osc.type = 'square';   // onda cuadrada: más fuerte y "molesta" que la sine
    osc.frequency.value = freq;
    gain.gain.setValueAtTime(0.0001, cuando);
    gain.gain.exponentialRampToValueAtTime(0.38, cuando + 0.01);
    gain.gain.setValueAtTime(0.38, cuando + dur - 0.02);
    gain.gain.exponentialRampToValueAtTime(0.0001, cuando + dur);
    osc.start(cuando); osc.stop(cuando + dur);
  }
  function sonar() {
    desbloquearAudio();
    if (!audioCtx) return;
    var t = audioCtx.currentTime;
    // Alarma de ~2,2s: 3 repeticiones de dos tonos alternados (tipo sirena).
    for (var i = 0; i < 3; i++) {
      var b = t + i * 0.75;
      beep(988, b, 0.2);
      beep(1319, b + 0.24, 0.28);
    }
  }

  // Notificación del navegador que aparece aunque estén en otra pestaña y queda
  // fija hasta que la cierran (requireInteraction). Mismo tag → no se acumulan.
  function notificarPersistente(msg) {
    if (!(soportado && Notification.permission === 'granted')) return;
    try {
      var n = new Notification('SELQUET · ¡Atención!', {
        body: msg, icon: '/static/selquet-logo.svg',
        tag: 'selquet-pendientes', renotify: true, requireInteraction: true,
      });
      n.onclick = function () { window.focus(); n.close(); };
    } catch (e) { /* sin notificación */ }
  }
  function mensajePendientes(d) {
    var p = [];
    if (d.pedidos) p.push(d.pedidos + ' pedido' + (d.pedidos > 1 ? 's' : ''));
    if (d.reservas) p.push(d.reservas + ' reserva' + (d.reservas > 1 ? 's' : ''));
    if (d.corporativas) p.push(d.corporativas + ' corporativa' + (d.corporativas > 1 ? 's' : ''));
    return '🔴 ' + p.join(' · ') + ' sin atender. ¡Respondé!';
  }

  // ── alerta persistente: titila el título y suena mientras haya pendientes ──
  var tituloBase = document.title;
  var pendientes = 0;
  var ciclos = 0;

  setInterval(function () {   // titileo del título de la pestaña
    if (pendientes > 0) {
      document.title = (document.title === tituloBase)
        ? '🔴 (' + pendientes + ') sin atender'
        : tituloBase;
    } else if (document.title !== tituloBase) {
      document.title = tituloBase;
    }
  }, 1000);

  function chequearPendientes() {
    fetch('/admin/pendientes/activos', { cache: 'no-store' })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (d) {
        if (!d) return;
        var antes = pendientes;
        pendientes = d.total || 0;
        // Suena y avisa si aparece algo nuevo, y sigue insistiendo (cada ~3 ciclos)
        // mientras queden pendientes sin atender.
        if (pendientes > 0 && (pendientes > antes || ciclos % 3 === 0)) {
          sonar();
          notificarPersistente(mensajePendientes(d));
        }
        ciclos++;
      })
      .catch(function () { /* red caída: reintenta */ });
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
  function refrescar(cont) {
    var url = cont.getAttribute('data-fragment-url');
    if (!url) return;
    fetch(url, { cache: 'no-store' })
      .then(function (r) { return r.ok ? r.text() : null; })
      .then(function (html) { if (html != null) cont.innerHTML = html; });
  }
  function quizasRefrescar(nuevas) {
    var cont = document.getElementById('op-tabla');
    if (!cont) return;
    var vista = cont.getAttribute('data-vista');
    if (nuevas.some(function (n) { return VISTA_DE_TIPO[n.tipo] === vista; })) refrescar(cont);
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
    // Desbloquear el audio en el primer gesto (política de autoplay del navegador).
    document.addEventListener('click', desbloquearAudio, { once: true });
    document.addEventListener('keydown', desbloquearAudio, { once: true });
    pedirPermiso();
    focoInicial();
    verificar();
    setInterval(verificar, POLLING_MS);
    chequearPendientes();
    setInterval(chequearPendientes, POLLING_MS);
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
