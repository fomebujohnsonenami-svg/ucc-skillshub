(function () {
  const sidebar = document.querySelector(
    '[data-purpose="main-sidebar"], [data-purpose="primary-sidebar"], [data-purpose="sidebar"]'
  );
  if (!sidebar) return;

  const breakpoint = window.matchMedia("(max-width: 1023.98px)");
  const body = document.body;
  body.classList.add("has-responsive-sidebar");

  if (!sidebar.id) sidebar.id = "primary-navigation";

  const toggle = document.createElement("button");
  toggle.className = "responsive-menu-toggle";
  toggle.type = "button";
  toggle.setAttribute("aria-controls", sidebar.id);
  toggle.setAttribute("aria-expanded", "false");
  toggle.setAttribute("aria-label", "Open navigation menu");

  const icon = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  icon.setAttribute("viewBox", "0 0 24 24");
  icon.setAttribute("width", "22");
  icon.setAttribute("height", "22");
  icon.setAttribute("aria-hidden", "true");
  icon.setAttribute("fill", "none");
  icon.setAttribute("stroke", "currentColor");
  icon.setAttribute("stroke-width", "2");
  icon.setAttribute("stroke-linecap", "round");
  icon.append(
    ...[
      [4, 6, 20, 6],
      [4, 12, 20, 12],
      [4, 18, 20, 18],
    ].map((line) => {
      const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
      path.setAttribute("d", `M${line[0]} ${line[1]}h${line[2] - line[0]}`);
      return path;
    })
  );
  toggle.append(icon);

  const backdrop = document.createElement("button");
  backdrop.className = "responsive-nav-backdrop";
  backdrop.type = "button";
  backdrop.tabIndex = -1;
  backdrop.setAttribute("aria-label", "Close navigation menu");
  body.append(toggle, backdrop);

  function closeMenu(returnFocus) {
    body.removeAttribute("data-responsive-nav-open");
    toggle.setAttribute("aria-expanded", "false");
    toggle.setAttribute("aria-label", "Open navigation menu");
    backdrop.tabIndex = -1;
    if (breakpoint.matches) {
      sidebar.inert = true;
      sidebar.setAttribute("aria-hidden", "true");
    }
    if (returnFocus) toggle.focus();
  }

  function openMenu() {
    body.setAttribute("data-responsive-nav-open", "true");
    toggle.setAttribute("aria-expanded", "true");
    toggle.setAttribute("aria-label", "Close navigation menu");
    backdrop.tabIndex = 0;
    sidebar.inert = false;
    sidebar.removeAttribute("aria-hidden");
    const firstLink = sidebar.querySelector("a");
    if (firstLink) firstLink.focus();
  }

  function syncBreakpoint() {
    if (breakpoint.matches) {
      if (body.getAttribute("data-responsive-nav-open") !== "true") {
        closeMenu(false);
      }
    } else {
      body.removeAttribute("data-responsive-nav-open");
      toggle.setAttribute("aria-expanded", "false");
      toggle.setAttribute("aria-label", "Open navigation menu");
      sidebar.inert = false;
      sidebar.removeAttribute("aria-hidden");
    }
  }

  toggle.addEventListener("click", () => {
    if (body.getAttribute("data-responsive-nav-open") === "true") {
      closeMenu(true);
    } else {
      openMenu();
    }
  });
  backdrop.addEventListener("click", () => closeMenu(true));
  sidebar.querySelectorAll("a").forEach((link) => {
    link.addEventListener("click", () => {
      if (breakpoint.matches) closeMenu(false);
    });
  });
  document.addEventListener("keydown", (event) => {
    if (
      event.key === "Escape" &&
      body.getAttribute("data-responsive-nav-open") === "true"
    ) {
      closeMenu(true);
    }
  });

  if (breakpoint.addEventListener) {
    breakpoint.addEventListener("change", syncBreakpoint);
  } else {
    breakpoint.addListener(syncBreakpoint);
  }
  syncBreakpoint();
})();
