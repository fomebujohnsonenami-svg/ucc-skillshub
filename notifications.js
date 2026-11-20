(function () {
  const api = window.skillsHubApi;
  const triggers = Array.from(
    document.querySelectorAll('button[aria-label="Notifications"]')
  );
  if (!api || !triggers.length) return;

  function hasSession() {
    return Boolean(
      sessionStorage.getItem("skillshubAccessToken") ||
        localStorage.getItem("skillshubAccessToken")
    );
  }

  function updateBadge(button, count) {
    let badge = button.querySelector("[data-notification-count]");
    if (!badge) {
      badge = document.createElement("span");
      badge.dataset.notificationCount = "";
      const oldIndicator = button.querySelector("span.absolute");
      if (oldIndicator) oldIndicator.remove();
      button.appendChild(badge);
    }
    badge.className =
      "absolute -top-1 -right-1 min-w-5 h-5 px-1 rounded-full bg-rose-500 text-white text-[10px] font-bold flex items-center justify-center ring-2 ring-white";
    badge.textContent = count > 99 ? "99+" : String(count);
    badge.hidden = count < 1;
    badge.classList.toggle("hidden", count < 1);
    button.setAttribute("aria-label", `Notifications${count ? ` (${count} unread)` : ""}`);
    document
      .querySelectorAll("[data-notification-count]")
      .forEach((counter) => {
        if (counter !== badge && !counter.closest("button")) {
          counter.textContent = count > 99 ? "99+" : String(count);
          counter.hidden = count < 1;
          counter.classList.toggle("hidden", count < 1);
        }
      });
  }

  function createPanel(wrapper) {
    const panel = document.createElement("section");
    panel.className =
      "absolute right-0 top-full mt-3 w-[min(24rem,calc(100vw-2rem))] max-h-[75vh] overflow-hidden rounded-2xl border border-slate-200 bg-white text-slate-800 shadow-xl z-50";
    panel.hidden = true;
    panel.setAttribute("aria-label", "Notifications");
    panel.innerHTML =
      '<div class="flex items-center justify-between border-b border-slate-100 px-4 py-3">' +
      '<h2 class="font-bold">Notifications</h2>' +
      '<button class="text-xs font-semibold text-indigo-700 hover:underline" data-mark-all type="button">Mark all read</button>' +
      "</div>" +
      '<div class="max-h-[60vh] overflow-y-auto p-2" data-notification-items></div>' +
      '<p class="hidden px-4 py-3 text-sm text-rose-700" data-notification-error role="alert"></p>';
    wrapper.appendChild(panel);
    return panel;
  }

  function renderItems(panel, items) {
    const container = panel.querySelector("[data-notification-items]");
    container.replaceChildren();
    if (!items.length) {
      const empty = document.createElement("p");
      empty.className = "px-3 py-6 text-center text-sm text-slate-500";
      empty.textContent = "You are all caught up.";
      container.appendChild(empty);
      return;
    }
    items.forEach((item) => {
      const row = document.createElement("article");
      row.className =
        "mb-1 rounded-xl p-3 " +
        (item.is_read ? "bg-white" : "bg-indigo-50");
      const heading = document.createElement("h3");
      heading.className = "text-sm font-bold";
      heading.textContent = item.title;
      const message = document.createElement("p");
      message.className = "mt-1 text-sm text-slate-600";
      message.textContent = item.message;
      const created = document.createElement("time");
      created.className = "mt-2 block text-[11px] text-slate-400";
      created.dateTime = item.created_at;
      created.textContent = new Date(item.created_at).toLocaleString();
      const actions = document.createElement("div");
      actions.className = "mt-2 flex gap-3";
      if (!item.is_read) {
        const markRead = document.createElement("button");
        markRead.className = "text-xs font-semibold text-indigo-700";
        markRead.type = "button";
        markRead.textContent = "Mark read";
        markRead.addEventListener("click", async () => {
          await runAction(panel, () => api.patch(`/notifications/${item.id}/read/`));
        });
        actions.appendChild(markRead);
      }
      const remove = document.createElement("button");
      remove.className = "text-xs font-semibold text-slate-500";
      remove.type = "button";
      remove.textContent = "Delete";
      remove.addEventListener("click", async () => {
        await runAction(panel, () => api.delete(`/notifications/${item.id}/`));
      });
      actions.appendChild(remove);
      row.append(heading, message, created, actions);
      container.appendChild(row);
    });
  }

  async function load(panel, button) {
    if (!hasSession()) {
      panel.querySelector("[data-notification-error]").textContent =
        "Sign in to view notifications.";
      panel.querySelector("[data-notification-error]").classList.remove("hidden");
      return;
    }
    const error = panel.querySelector("[data-notification-error]");
    error.classList.add("hidden");
    try {
      const response = await api.get("/notifications/?page_size=20");
      updateBadge(button, response.unread_count || 0);
      renderItems(panel, response.results || []);
    } catch (requestError) {
      error.textContent = requestError.message;
      error.classList.remove("hidden");
    }
  }

  async function runAction(panel, action) {
    const button = panel.closest("[data-notification-wrapper]").querySelector(
      'button[aria-label^="Notifications"]'
    );
    try {
      await action();
      await load(panel, button);
    } catch (requestError) {
      const error = panel.querySelector("[data-notification-error]");
      error.textContent = requestError.message;
      error.classList.remove("hidden");
    }
  }

  const panels = [];
  triggers.forEach((button) => {
    const wrapper = document.createElement("div");
    wrapper.className = "relative";
    wrapper.dataset.notificationWrapper = "";
    button.parentNode.insertBefore(wrapper, button);
    wrapper.appendChild(button);
    button.setAttribute("aria-expanded", "false");
    updateBadge(button, 0);
    const panel = createPanel(wrapper);
    panels.push({ button, panel });

    button.addEventListener("click", async () => {
      const opening = panel.hidden;
      panels.forEach(({ button: otherButton, panel: otherPanel }) => {
        otherPanel.hidden = true;
        otherButton.setAttribute("aria-expanded", "false");
      });
      panel.hidden = !opening;
      button.setAttribute("aria-expanded", String(opening));
      if (opening) await load(panel, button);
    });
    panel.querySelector("[data-mark-all]").addEventListener("click", async () => {
      await runAction(panel, () => api.post("/notifications/mark-all-read/"));
    });
  });

  document.querySelectorAll('a[href="#notifications"]').forEach((link) => {
    link.addEventListener("click", (event) => {
      const first = panels[0];
      if (!first) return;
      event.preventDefault();
      first.button.click();
    });
  });

  document.addEventListener("click", (event) => {
    panels.forEach(({ button, panel }) => {
      if (!panel.closest("[data-notification-wrapper]").contains(event.target)) {
        panel.hidden = true;
        button.setAttribute("aria-expanded", "false");
      }
    });
  });

  window.addEventListener("skillsHubNotificationsChanged", () => {
    panels.forEach(({ button, panel }) => load(panel, button));
  });

  panels.forEach(({ button, panel }) => load(panel, button));
})();
