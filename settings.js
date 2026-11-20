(function () {
  const api = window.skillsHubApi;
  const dialog = document.querySelector("[data-settings-dialog]");

  function applyTheme(theme) {
    const isDark =
      theme === "dark" ||
      (theme === "system" &&
        window.matchMedia("(prefers-color-scheme: dark)").matches);
    document.documentElement.classList.toggle("dark", isDark);
    document.documentElement.dataset.theme = isDark ? "dark" : "light";
    document.documentElement.style.colorScheme = isDark ? "dark" : "light";
    let style = document.getElementById("skillshub-theme-styles");
    if (!style) {
      style = document.createElement("style");
      style.id = "skillshub-theme-styles";
      style.textContent =
        'html[data-theme="dark"] body{background:#0f172a!important;color:#e2e8f0!important}' +
        'html[data-theme="dark"] body [class~="bg-white"],html[data-theme="dark"] body [class~="bg-surface-container-lowest"],html[data-theme="dark"] body [class~="bg-surface-container-low"],html[data-theme="dark"] body [class~="bg-surface-container"],html[data-theme="dark"] body [class~="bg-surface-container-high"],html[data-theme="dark"] body [class~="bg-slate-50"],html[data-theme="dark"] body [class~="bg-slate-100"],html[data-theme="dark"] body [class~="bg-background"],html[data-theme="dark"] body [class~="bg-brand-bgMain"]{background-color:#1e293b!important}' +
        'html[data-theme="dark"] body [class~="text-slate-800"],html[data-theme="dark"] body [class~="text-slate-900"],html[data-theme="dark"] body [class~="text-on-surface"],html[data-theme="dark"] body [class~="text-brand-bgMain"]{color:#e2e8f0!important}' +
        'html[data-theme="dark"] body [class~="text-slate-600"],html[data-theme="dark"] body [class~="text-slate-500"],html[data-theme="dark"] body [class~="text-on-surface-variant"],html[data-theme="dark"] body [class~="text-slate-400"]{color:#cbd5e1!important}' +
        'html[data-theme="dark"] body [class~="border-slate-100"],html[data-theme="dark"] body [class~="border-slate-200"],html[data-theme="dark"] body [class~="border-brand-borderMuted"]{border-color:#334155!important}' +
        'html[data-theme="dark"] body input,html[data-theme="dark"] body textarea,html[data-theme="dark"] body select{background-color:#0f172a!important;color:#e2e8f0!important;border-color:#475569!important}';
      document.head.appendChild(style);
    }
  }

  if (!api) return;
  if (!dialog) {
    if (
      sessionStorage.getItem("skillshubAccessToken") ||
      localStorage.getItem("skillshubAccessToken")
    ) {
      api
        .get("/settings/")
        .then((settings) => applyTheme(settings.theme || "system"))
        .catch((error) =>
          console.error("Could not load the saved theme preference.", error)
        );
    }
    return;
  }

  const form = dialog.querySelector("[data-settings-form]");
  const statusMessage = dialog.querySelector("[data-settings-status]");
  const preferences = Array.from(
    dialog.querySelectorAll("[data-notification-preference]")
  );

  function setStatus(message, isError) {
    statusMessage.textContent = message;
    statusMessage.classList.toggle("text-rose-700", Boolean(isError));
    statusMessage.classList.toggle("text-emerald-700", !isError);
    statusMessage.classList.remove("hidden");
  }

  function fill(settings) {
    Object.entries(settings).forEach(([key, value]) => {
      const field = form.elements.namedItem(key);
      if (field && field.type !== "checkbox" && value !== null) {
        field.value = value;
      }
    });
    preferences.forEach((checkbox) => {
      checkbox.checked =
        settings.notification_preferences?.[checkbox.dataset.notificationPreference] !==
        false;
    });
    dialog.querySelectorAll("[data-student-setting]").forEach((container) => {
      const isStudent = settings.role === "student";
      container.hidden = !isStudent;
      container.classList.toggle("hidden", !isStudent);
      container.querySelectorAll("input, textarea, select").forEach((field) => {
        field.disabled = !isStudent;
      });
    });
    dialog.querySelectorAll("[data-biography-setting]").forEach((container) => {
      const canEdit = ["student", "lecturer"].includes(settings.role);
      container.hidden = !canEdit;
      container.classList.toggle("hidden", !canEdit);
      container.querySelectorAll("textarea").forEach((field) => {
        field.disabled = !canEdit;
      });
    });
    dialog.querySelector("[data-pending-email]").textContent = settings.pending_email
      ? `Verification pending for ${settings.pending_email}`
      : "";
    applyTheme(settings.theme || "system");
  }

  async function loadSettings() {
    try {
      const settings = await api.get("/settings/");
      fill(settings);
    } catch (error) {
      setStatus(error.message, true);
    }
  }

  async function openDialog() {
    dialog.hidden = false;
    dialog.classList.remove("hidden");
    dialog.classList.add("flex");
    document.body.classList.add("overflow-hidden");
    await loadSettings();
  }

  function closeDialog() {
    dialog.hidden = true;
    dialog.classList.add("hidden");
    dialog.classList.remove("flex");
    document.body.classList.remove("overflow-hidden");
    if (window.location.hash === "#settings") {
      history.replaceState(null, "", window.location.pathname + window.location.search);
    }
  }

  document.querySelectorAll('a[href="#settings"]').forEach((link) => {
    link.addEventListener("click", (event) => {
      event.preventDefault();
      history.replaceState(null, "", `${window.location.pathname}#settings`);
      openDialog();
    });
  });
  dialog.querySelectorAll("[data-settings-close]").forEach((button) => {
    button.addEventListener("click", closeDialog);
  });
  dialog.addEventListener("click", (event) => {
    if (event.target === dialog) closeDialog();
  });
  if (window.location.hash === "#settings") openDialog();

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const data = new FormData(form);
    const changes = {
      first_name: data.get("first_name"),
      last_name: data.get("last_name"),
      username: data.get("username"),
      phone_number: data.get("phone_number"),
      academic_programme: data.get("academic_programme"),
      academic_level: data.get("academic_level"),
      biography: data.get("biography"),
      profile_visibility: data.get("profile_visibility"),
      theme: data.get("theme"),
      notification_preferences: Object.fromEntries(
        preferences.map((checkbox) => [
          checkbox.dataset.notificationPreference,
          checkbox.checked,
        ])
      ),
    };
    [
      "academic_programme",
      "academic_level",
      "profile_visibility",
      "biography",
    ].forEach((key) => {
      if (form.elements.namedItem(key).disabled) delete changes[key];
    });
    try {
      const settings = await api.patch("/settings/", changes);
      fill(settings);
      setStatus("Settings saved.", false);
      if (window.skillsHubProfile?.refresh) {
        window.skillsHubProfile.refresh().catch((error) =>
          console.error("Could not refresh the updated profile display.", error)
        );
      }
      window.dispatchEvent(new Event("skillsHubNotificationsChanged"));
    } catch (error) {
      setStatus(error.message, true);
    }
  });

  dialog.querySelector("[data-email-change-form]").addEventListener("submit", async (event) => {
    event.preventDefault();
    const emailForm = event.currentTarget;
    const emailStatus = dialog.querySelector("[data-email-change-status]");
    const data = new FormData(emailForm);
    try {
      const result = await api.post("/settings/email-change/", {
        new_email: data.get("new_email"),
        current_password: data.get("current_password"),
      });
      emailStatus.textContent = result.message;
      emailStatus.classList.remove("hidden", "text-rose-700");
      dialog
        .querySelector("[data-email-confirm-form]")
        .classList.remove("hidden");
      await loadSettings();
    } catch (error) {
      emailStatus.textContent = error.message;
      emailStatus.classList.remove("hidden");
      emailStatus.classList.add("text-rose-700");
    }
  });

  dialog.querySelector("[data-email-confirm-form]").addEventListener("submit", async (event) => {
    event.preventDefault();
    const emailStatus = dialog.querySelector("[data-email-change-status]");
    const code = new FormData(event.currentTarget).get("code");
    try {
      await api.post("/settings/email-change/confirm/", { code });
      emailStatus.textContent = "Email updated. Sign in again after your current session expires.";
      emailStatus.classList.remove("hidden", "text-rose-700");
      await loadSettings();
    } catch (error) {
      emailStatus.textContent = error.message;
      emailStatus.classList.remove("hidden");
      emailStatus.classList.add("text-rose-700");
    }
  });

  dialog.querySelector("[data-profile-photo-form]").addEventListener("submit", async (event) => {
    event.preventDefault();
    const photo = event.currentTarget.elements.namedItem("profile_photo").files[0];
    if (!photo) {
      setStatus("Choose a profile photo first.", true);
      return;
    }
    const body = new FormData();
    body.append("profile_photo", photo);
    try {
      await api.post("/users/me/profile-photo/", body);
      await loadSettings();
      if (window.skillsHubProfile?.refresh) {
        await window.skillsHubProfile.refresh();
      }
      setStatus("Profile photo updated.", false);
    } catch (error) {
      setStatus(error.message, true);
    }
  });

  dialog.querySelector("[data-change-password-form]").addEventListener("submit", async (event) => {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    try {
      await api.post("/auth/change-password/", {
        current_password: data.get("current_password"),
        new_password: data.get("new_password"),
      });
      event.currentTarget.reset();
      setStatus("Password changed. Sign in again to continue.", false);
      api.clearTokens();
    } catch (error) {
      setStatus(error.message, true);
    }
  });

  const themeField = form.elements.namedItem("theme");
  themeField.addEventListener("change", () => applyTheme(themeField.value));
  window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => {
    if (themeField.value === "system") applyTheme("system");
  });
})();
