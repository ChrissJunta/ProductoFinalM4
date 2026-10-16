"use strict";
// CONTRACT-023: aviso emergente al personal cuando entra un ticket por Telegram.
(() => {
  const root = document.getElementById("mesa-ticket-alerts");
  if (!root || !window.fetch) return;
  const feedUrl = root.dataset.feedUrl;
  const pollMs = Math.max(5, Number(root.dataset.pollSeconds) || 15) * 1000;
  const KEY = "mesa:lastTicketId";
  const MAX_TOASTS = 4;
  let timer = null;

  const read = () => {
    try { return sessionStorage.getItem(KEY); } catch { return null; }
  };
  const save = value => {
    try { sessionStorage.setItem(KEY, String(value)); } catch { /* sin almacenamiento */ }
  };
  const el = (tag, className, text) => {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text) node.textContent = text;
    return node;
  };

  const desktopNotice = ticket => {
    if (!document.hidden || !("Notification" in window)) return;
    if (Notification.permission !== "granted") return;
    const notice = new Notification(`Nuevo ticket por ${ticket.channel}`, {
      body: `${ticket.code} · ${ticket.subject}`,
      tag: ticket.code,
    });
    notice.onclick = () => { window.focus(); window.location.href = ticket.url; };
  };

  const show = ticket => {
    const toast = el("div", "mesa-toast");
    toast.setAttribute("role", "alert");
    const head = el("div", "mesa-toast-head");
    head.append(el("strong", "", `Nuevo ticket por ${ticket.channel}`));
    const close = el("button", "btn-close", "");
    close.type = "button";
    close.setAttribute("aria-label", "Cerrar aviso");
    close.addEventListener("click", () => toast.remove());
    head.append(close);
    toast.append(head);
    toast.append(el("p", "mesa-toast-subject", `${ticket.code} · ${ticket.subject}`));
    toast.append(el("p", "mesa-toast-meta", `${ticket.user} · prioridad ${ticket.priority}`));
    const actions = el("div", "mesa-toast-actions");
    const open = el("a", "btn btn-sm btn-primary", "Abrir ticket");
    open.href = ticket.url;
    actions.append(open);
    if ("Notification" in window && Notification.permission === "default") {
      const enable = el("button", "btn btn-sm btn-outline-primary", "Avisarme fuera de la pestaña");
      enable.type = "button";
      enable.addEventListener("click", () => {
        Notification.requestPermission().finally(() => enable.remove());
      });
      actions.append(enable);
    }
    toast.append(actions);
    root.prepend(toast);
    while (root.children.length > MAX_TOASTS) root.lastElementChild.remove();
    desktopNotice(ticket);
  };

  const poll = async () => {
    const after = read();
    const url = after === null ? feedUrl : `${feedUrl}?after=${encodeURIComponent(after)}`;
    try {
      const response = await fetch(url, {
        credentials: "same-origin",
        headers: { Accept: "application/json", "X-Mesa-Background": "1" },
      });
      const type = response.headers.get("Content-Type") || "";
      // Sesión vencida o sin permiso: se deja de consultar hasta la próxima página.
      if (!response.ok || !type.includes("application/json")) return clearInterval(timer);
      const data = await response.json();
      [...data.tickets].reverse().forEach(show);
      save(data.last_id);
    } catch {
      /* red caída: se reintenta en la siguiente vuelta */
    }
  };

  poll();
  timer = setInterval(poll, pollMs);
})();
