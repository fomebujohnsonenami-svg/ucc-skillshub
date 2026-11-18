(function () {
  const api = window.skillsHubApi;
  const cards = document.getElementById("dashboardPathwayCards");
  const notice = document.getElementById("dashboardPathwayNotice");
  if (!api || !cards || !notice) return;

  function showNotice(message) {
    notice.textContent = message;
    notice.classList.remove("hidden");
  }

  function renderEnrollment(enrollment) {
    const link = document.createElement("a");
    link.className =
      "flex h-36 flex-col justify-between rounded-2xl border border-slate-100 bg-white p-4 shadow-sm transition-shadow hover:shadow-md";
    link.href = `../skillbridge_skill_pathways_career_roadmaps/code.html?pathway=${encodeURIComponent(enrollment.pathway.id)}`;

    const header = document.createElement("div");
    header.className = "flex items-center gap-3";
    const icon = document.createElement("span");
    icon.className =
      "flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-xl bg-indigo-50 text-indigo-600";
    icon.textContent = "↗";
    const title = document.createElement("h4");
    title.className = "text-xs font-bold leading-tight text-slate-800";
    title.textContent = enrollment.pathway.name;
    header.append(icon, title);

    const footer = document.createElement("div");
    footer.className = "mt-2 space-y-1.5";
    const label = document.createElement("div");
    label.className = "text-[11px] font-medium text-slate-400";
    label.textContent = `${enrollment.completed_steps} of ${enrollment.total_steps} steps · ${enrollment.progress_percentage}%`;
    const track = document.createElement("div");
    track.className = "h-1.5 w-full overflow-hidden rounded-full bg-slate-100";
    const bar = document.createElement("div");
    bar.className = "h-full rounded-full bg-indigo-600";
    bar.style.width = `${enrollment.progress_percentage}%`;
    track.append(bar);
    footer.append(label, track);
    link.append(header, footer);
    return link;
  }

  async function load() {
    cards.replaceChildren();
    cards.dataset.apiReady = "true";
    const hasToken =
      sessionStorage.getItem("skillshubAccessToken") ||
      localStorage.getItem("skillshubAccessToken");
    if (!hasToken) {
      showNotice("Sign in to see your enrolled pathways.");
      return;
    }

    notice.classList.add("hidden");
    try {
      const data = await api.get("/pathways/my-pathways/");
      const enrollments = Array.isArray(data) ? data : data.results || [];
      if (!enrollments.length) {
        showNotice("You have not enrolled in a pathway yet. Browse the pathway catalogue to get started.");
        return;
      }
      enrollments.forEach((enrollment) => cards.append(renderEnrollment(enrollment)));
    } catch (error) {
      showNotice(`Your pathways could not be loaded. ${error.message}`);
    }
  }

  load();
})();
