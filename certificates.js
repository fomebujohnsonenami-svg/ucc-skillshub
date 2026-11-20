(function () {
  const api = window.skillsHubApi;
  const featured = document.getElementById("certificate-featured");
  const badgeGrid = document.getElementById("achievement-grid");
  if (!api || !featured || !badgeGrid) return;

  const verificationModal = document.getElementById("verify-modal");
  const verificationInput = document.getElementById("credential-input");
  const verificationResult = document.getElementById("verification-result");
  const verificationSubmit = document.getElementById("verify-submit");
  const verificationFeedback = document.createElement("p");
  verificationFeedback.className = "mb-space-md text-body-sm text-error";
  verificationFeedback.setAttribute("role", "status");
  verificationSubmit.before(verificationFeedback);

  function showMessage(parent, message, isError) {
    const notice = document.createElement("p");
    notice.className = isError
      ? "rounded-xl bg-rose-50 p-space-md text-body-sm text-rose-700"
      : "rounded-xl bg-surface-container-low p-space-md text-body-sm text-on-surface-variant";
    notice.textContent = message;
    parent.replaceChildren(notice);
  }

  async function getAllPages(path) {
    const items = [];
    let page = 1;
    let next = true;
    while (next) {
      const response = await api.get(`${path}?page=${page}`);
      if (Array.isArray(response)) {
        items.push(...response);
        next = false;
      } else {
        items.push(...(response.results || []));
        next = Boolean(response.next);
        page += 1;
      }
    }
    return items;
  }

  function makeButton(label, icon, handler) {
    const button = document.createElement("button");
    button.type = "button";
    button.className =
      "inline-flex items-center gap-space-xs rounded-full bg-surface-container-low px-space-md py-2.5 font-label-md text-label-md text-on-surface transition hover:bg-surface-container";
    const symbol = document.createElement("span");
    symbol.className = "material-symbols-outlined text-[18px]";
    symbol.textContent = icon;
    const text = document.createElement("span");
    text.textContent = label;
    button.append(symbol, text);
    button.addEventListener("click", handler);
    return button;
  }

  function renderCertificate(certificate) {
    const card = document.createElement("article");
    card.className =
      "rounded-xl border border-surface-container bg-surface-container-lowest p-space-lg shadow-sm";

    const heading = document.createElement("h3");
    heading.className = "font-headline-sm text-headline-sm text-on-surface";
    heading.textContent = certificate.learning_item.name;
    const summary = document.createElement("p");
    summary.className = "mt-1 font-body-sm text-body-sm text-on-surface-variant";
    summary.textContent = `${certificate.certificate_type === "course" ? "Course" : "Pathway"} certificate · ${certificate.issuing_organization}`;
    const serial = document.createElement("p");
    serial.className = "mt-2 font-label-sm text-label-sm text-outline";
    serial.textContent = `Issued ${certificate.issue_date} · ${certificate.certificate_id}`;
    const actions = document.createElement("div");
    actions.className = "mt-space-md flex flex-wrap gap-space-sm";
    const detail = document.createElement("div");
    detail.className =
      "mt-space-md hidden rounded-lg bg-surface-container-low p-space-md text-body-sm text-on-surface-variant";
    const feedback = document.createElement("p");
    feedback.className = "mt-space-sm font-body-sm text-body-sm text-rose-700";

    actions.append(
      makeButton("View details", "description", async () => {
        if (!detail.classList.contains("hidden")) {
          detail.classList.add("hidden");
          return;
        }
        detail.classList.remove("hidden");
        if (detail.dataset.loaded) return;
        detail.textContent = "Loading certificate details…";
        try {
          const details = await api.get(`/certificates/${certificate.id}/`);
          detail.textContent = `Completed ${details.completion_info.completed_at || "as recorded"} · Issued by ${details.issuing_organization} · Certificate ID ${details.certificate_id}.`;
          detail.dataset.loaded = "true";
        } catch (error) {
          detail.textContent =
            error.message || "Unable to load certificate details.";
        }
      }),
      makeButton("Download PDF", "download", async (event) => {
        const button = event.currentTarget;
        button.disabled = true;
        try {
          const file = await api.download(
            `/certificates/${certificate.id}/download/`,
          );
          const url = URL.createObjectURL(file);
          const link = document.createElement("a");
          link.href = url;
          link.download = `${certificate.certificate_id}.pdf`;
          link.click();
          URL.revokeObjectURL(url);
        } catch (error) {
          feedback.textContent =
            error.message || "Unable to download this certificate.";
        } finally {
          button.disabled = false;
        }
      }),
      makeButton("Copy link", "content_copy", async () => {
        try {
          await navigator.clipboard.writeText(certificate.verification_url);
          feedback.textContent = "Verification link copied.";
        } catch (error) {
          feedback.textContent = "Clipboard access is unavailable in this browser.";
        }
      }),
      makeButton("Share", "share", async () => {
        try {
          if (navigator.share) {
            await navigator.share({
              title: certificate.learning_item.name,
              url: certificate.verification_url,
            });
          } else {
            await navigator.clipboard.writeText(certificate.verification_url);
            feedback.textContent = "Verification link copied.";
          }
        } catch (error) {
          if (error.name !== "AbortError") {
            feedback.textContent = "Unable to share this verification link.";
          }
        }
      }),
    );
    card.append(heading, summary, serial, actions, detail, feedback);
    return card;
  }

  function renderAchievement(achievement) {
    const card = document.createElement("article");
    card.className = achievement.earned
      ? "flex flex-col items-center rounded-xl bg-surface-container-low p-space-md text-center"
      : "flex flex-col items-center rounded-xl bg-surface-container-low/60 p-space-md text-center opacity-75";
    const icon = document.createElement("div");
    icon.className = achievement.earned
      ? "mb-3 flex h-16 w-16 items-center justify-center rounded-full bg-secondary text-on-secondary shadow-md"
      : "mb-3 flex h-16 w-16 items-center justify-center rounded-full bg-surface-container text-outline shadow-inner";
    if (achievement.earned && achievement.badge_image) {
      const image = document.createElement("img");
      image.className = "h-12 w-12 object-contain";
      image.src = new URL(achievement.badge_image, api.baseUrl).href;
      image.alt = `${achievement.name} badge`;
      icon.append(image);
    } else {
      const symbol = document.createElement("span");
      symbol.className = "material-symbols-outlined text-[32px]";
      symbol.textContent = achievement.earned ? "workspace_premium" : "lock";
      icon.append(symbol);
    }
    const name = document.createElement("h4");
    name.className = "font-headline-sm text-[14px] font-bold leading-tight text-on-surface";
    name.textContent = achievement.name;
    const description = document.createElement("p");
    description.className = "mt-1 font-label-sm text-[11px] text-on-surface-variant";
    description.textContent = achievement.earned
      ? `Unlocked ${new Date(achievement.awarded_at).toLocaleDateString()}`
      : achievement.description;
    card.append(icon, name, description);
    return card;
  }

  async function load() {
    featured.replaceChildren();
    badgeGrid.replaceChildren();
    try {
      const [certificates, achievements, enrollments] = await Promise.all([
        getAllPages("/certificates/"),
        getAllPages("/achievements/"),
        getAllPages("/courses/my-courses/"),
      ]);
      const earned = achievements.filter((achievement) => achievement.earned);
      featured.classList.remove("hidden");
      badgeGrid.classList.remove("hidden");
      document.getElementById("certificate-count").textContent =
        String(certificates.length);
      document.getElementById("completed-course-count").textContent = String(
        enrollments.filter((enrollment) => enrollment.status === "completed").length,
      );
      document.getElementById("pathway-certificate-count").textContent = String(
        certificates.filter((certificate) => certificate.certificate_type === "pathway").length,
      );
      document.getElementById("achievement-count").textContent = String(earned.length);
      document.getElementById("achievement-total").textContent =
        `/ ${achievements.length}`;
      document.getElementById("achievement-progress-label").textContent =
        `${earned.length} of ${achievements.length} unlocked`;
      document.getElementById("achievement-progress-bar").style.width =
        `${achievements.length ? (earned.length / achievements.length) * 100 : 0}%`;

      if (certificates.length) {
        const title = document.createElement("h2");
        title.className = "mb-space-md font-headline-lg text-headline-lg text-on-surface";
        title.textContent = "Your certificates";
        const grid = document.createElement("div");
        grid.className = "grid grid-cols-1 gap-space-md md:grid-cols-2";
        certificates.forEach((certificate) => grid.append(renderCertificate(certificate)));
        featured.append(title, grid);
      } else {
        showMessage(featured, "You have not earned any certificates yet. Complete an eligible course or skill pathway to receive one.", false);
      }
      if (achievements.length) {
        achievements.forEach((achievement) =>
          badgeGrid.append(renderAchievement(achievement)),
        );
      } else {
        showMessage(badgeGrid, "No achievements are available yet.", false);
      }
    } catch (error) {
      featured.classList.remove("hidden");
      badgeGrid.classList.remove("hidden");
      showMessage(
        featured,
        error.status === 401 || error.status === 403
          ? "Sign in with an active student account to view certificates and achievements."
          : error.message || "Unable to load certificates and achievements.",
        true,
      );
      showMessage(badgeGrid, "Achievements could not be loaded.", true);
    }
  }

  function verificationToken(value) {
    const input = value.trim().replace(/\/+$/, "");
    const token = input.split("/").pop();
    return token || input;
  }

  verificationSubmit.addEventListener("click", async () => {
    const token = verificationToken(verificationInput.value);
    verificationFeedback.textContent = "";
    verificationResult.classList.add("hidden");
    if (!token) {
      verificationFeedback.textContent = "Enter a verification token or link.";
      return;
    }
    verificationSubmit.disabled = true;
    try {
      const certificate = await api.get(
        `/certificates/verify/${encodeURIComponent(token)}/`,
      );
      document.getElementById("verification-recipient").textContent =
        certificate.recipient;
      document.getElementById("verification-item").textContent =
        certificate.learning_item;
      const state = document.getElementById("verification-status");
      state.textContent = certificate.valid ? "Valid" : "Revoked";
      state.className = certificate.valid
        ? "font-semibold text-emerald-700"
        : "font-semibold text-rose-700";
      verificationResult.classList.remove("hidden");
    } catch (error) {
      verificationFeedback.textContent =
        error.status === 404
          ? "No certificate was found for this verification token."
          : error.message || "Unable to verify this certificate.";
    } finally {
      verificationSubmit.disabled = false;
    }
  });

  if (verificationModal) {
    verificationModal.addEventListener("click", (event) => {
      if (event.target === verificationModal) verificationFeedback.textContent = "";
    });
  }

  load();
})();
