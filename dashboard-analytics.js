(function () {
  const api = window.skillsHubApi;
  const authenticated = Boolean(
    sessionStorage.getItem("skillshubAccessToken") ||
      localStorage.getItem("skillshubAccessToken")
  );

  const pathwayContainer = document.querySelector("[data-dashboard-pathway-list]");
  if (pathwayContainer) {
    pathwayContainer.replaceChildren();
    const empty = document.createElement("p");
    empty.className = "col-span-full text-sm text-slate-500";
    empty.textContent = authenticated
      ? "Loading pathway progress…"
      : "Sign in to view pathway progress.";
    pathwayContainer.appendChild(empty);
  }
  const skillContainer = document.querySelector("[data-dashboard-skills]");
  if (skillContainer) {
    skillContainer.replaceChildren();
    const empty = document.createElement("p");
    empty.className = "text-xs text-slate-500";
    empty.textContent = authenticated
      ? "Loading completed-pathway skills…"
      : "Sign in to view completed-pathway skills.";
    skillContainer.appendChild(empty);
  }
  const achievementContainer = document.querySelector(
    "[data-dashboard-achievement-list]"
  );
  if (achievementContainer) {
    achievementContainer.replaceChildren();
    const empty = document.createElement("p");
    empty.className = "col-span-3 text-xs text-slate-500";
    empty.textContent = authenticated
      ? "Loading earned achievements…"
      : "Sign in to view earned achievements.";
    achievementContainer.appendChild(empty);
  }
  const courseTitle = document.querySelector("[data-dashboard-course-title]");
  if (courseTitle) {
    courseTitle.textContent = authenticated
      ? "Loading your courses…"
      : "Sign in to view course progress";
  }
  const opportunityContainer = document.querySelector(
    "[data-dashboard-opportunity-list]"
  );
  if (opportunityContainer) {
    opportunityContainer.replaceChildren();
    const empty = document.createElement("p");
    empty.className = "text-xs text-slate-500";
    empty.textContent = authenticated
      ? "Loading current opportunities…"
      : "Sign in to view current opportunities.";
    opportunityContainer.appendChild(empty);
  }

  if (!authenticated) return;
  if (!api) {
    if (courseTitle) courseTitle.textContent = "Course progress is unavailable.";
    [
      [pathwayContainer, "Pathway progress is unavailable."],
      [skillContainer, "Completed-pathway skills are unavailable."],
      [achievementContainer, "Earned achievements are unavailable."],
      [opportunityContainer, "Current opportunities are unavailable."],
    ].forEach(([container, message]) => {
      if (!container) return;
      const empty = document.createElement("p");
      empty.className = "col-span-full text-xs text-slate-500";
      empty.textContent = message;
      container.replaceChildren(empty);
    });
    return;
  }

  function setText(selector, value) {
    const element = document.querySelector(selector);
    if (element) element.textContent = value;
  }

  function renderPathways(pathways) {
    const container = document.querySelector("[data-dashboard-pathway-list]");
    if (!container) return;
    container.replaceChildren();
    if (!pathways.length) {
      const empty = document.createElement("p");
      empty.className = "col-span-full text-sm text-slate-500";
      empty.textContent = "No enrolled skill pathways yet.";
      container.appendChild(empty);
      return;
    }
    pathways.slice(0, 4).forEach((pathway) => {
      const card = document.createElement("article");
      card.className =
        "rounded-2xl border border-brand-borderMuted bg-white p-4 shadow-sm";
      const title = document.createElement("h3");
      title.className = "text-xs font-bold text-slate-800";
      title.textContent = pathway.name;
      const details = document.createElement("p");
      details.className = "mt-1 text-[11px] text-slate-500";
      details.textContent = `${pathway.completed_steps} of ${pathway.total_steps} steps • ${pathway.progress_percentage}%`;
      const track = document.createElement("div");
      track.className = "mt-3 h-1.5 overflow-hidden rounded-full bg-slate-100";
      const fill = document.createElement("div");
      fill.className = "h-full rounded-full bg-brand-purple";
      fill.style.width = `${pathway.progress_percentage}%`;
      track.appendChild(fill);
      card.append(title, details, track);
      container.appendChild(card);
    });
  }

  function renderCourse(courses) {
    const card = document.querySelector("[data-dashboard-course-card]");
    if (!card) return;
    const enrollment = courses.find((course) => course.status === "in_progress");
    const title = card.querySelector("[data-dashboard-course-title]");
    const status = card.querySelector("[data-dashboard-course-status]");
    const description = card.querySelector("[data-dashboard-course-description]");
    const progress = card.querySelector("[data-dashboard-course-progress]");
    if (!enrollment) {
      title.textContent = "No courses in progress";
      status.textContent = "";
      description.textContent = courses.length
        ? "Your enrolled courses are complete."
        : "Enroll in a course to see learning progress here.";
      progress.style.width = "0%";
      return;
    }
    title.textContent = enrollment.title;
    status.textContent = `In progress • ${enrollment.progress_percentage}%`;
    description.textContent = `${enrollment.completed_lessons} of ${enrollment.total_lessons} lessons completed.`;
    progress.style.width = `${enrollment.progress_percentage}%`;
  }

  function renderSkills(skills) {
    const container = document.querySelector("[data-dashboard-skills]");
    if (!container) return;
    container.replaceChildren();
    if (!skills.length) {
      const empty = document.createElement("p");
      empty.className = "text-xs text-slate-500";
      empty.textContent = "Skills are listed after a required-skill pathway is completed.";
      container.appendChild(empty);
      return;
    }
    skills.slice(0, 8).forEach((skill) => {
      const pill = document.createElement("span");
      pill.className =
        "rounded-full border border-emerald-100 bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-700";
      pill.textContent = skill.name;
      container.appendChild(pill);
    });
  }

  function renderAchievements(response) {
    const container = document.querySelector("[data-dashboard-achievement-list]");
    if (!container) return;
    container.replaceChildren();
    const awards = response.results || response;
    if (!Array.isArray(awards) || !awards.length) {
      const empty = document.createElement("p");
      empty.className = "col-span-3 text-xs text-slate-500";
      empty.textContent = "Earned achievements will appear here.";
      container.appendChild(empty);
      return;
    }
    awards.slice(0, 3).forEach((award) => {
      const achievement = award.achievement || award;
      const item = document.createElement("div");
      item.className = "flex flex-col items-center text-center";
      const badge = document.createElement("div");
      badge.className =
        "flex h-14 w-14 items-center justify-center overflow-hidden rounded-full bg-indigo-100 text-xl text-indigo-700";
      if (achievement.badge_image) {
        const image = document.createElement("img");
        image.src = achievement.badge_image;
        image.alt = "";
        image.className = "h-full w-full object-cover";
        badge.appendChild(image);
      } else {
        badge.textContent = "★";
      }
      const name = document.createElement("span");
      name.className = "mt-2 text-[11px] font-bold text-slate-800";
      name.textContent = achievement.name;
      item.append(badge, name);
      container.appendChild(item);
    });
  }

  function renderOpportunities(response) {
    if (!opportunityContainer) return;
    opportunityContainer.replaceChildren();
    const opportunities = Array.isArray(response)
      ? response
      : response && Array.isArray(response.results)
        ? response.results
        : [];
    if (!opportunities.length) {
      const empty = document.createElement("p");
      empty.className = "text-xs text-slate-500";
      empty.textContent = "No current opportunities are available.";
      opportunityContainer.appendChild(empty);
      return;
    }
    opportunities.slice(0, 2).forEach((opportunity) => {
      const item = document.createElement("article");
      item.className = "border-b border-slate-100 pb-3 last:border-0 last:pb-0";
      const title = document.createElement("h3");
      title.className = "text-xs font-bold text-slate-800";
      title.textContent = opportunity.title;
      const organization = document.createElement("p");
      organization.className = "mt-0.5 text-[11px] text-slate-500";
      organization.textContent = opportunity.organization;
      const description = document.createElement("p");
      description.className = "mt-1 text-xs text-slate-600";
      description.textContent = opportunity.description || "";
      item.append(title, organization, description);
      opportunityContainer.appendChild(item);
    });
  }

  async function loadOpportunities() {
    try {
      renderOpportunities(await api.get("/opportunities/?page_size=2"));
    } catch (error) {
      if (opportunityContainer) {
        const unavailable = document.createElement("p");
        unavailable.className = "text-xs text-slate-500";
        unavailable.textContent = "Current opportunities are unavailable.";
        opportunityContainer.replaceChildren(unavailable);
      }
      console.error("Could not load current opportunities.", error);
    }
  }

  async function loadDashboard() {
    try {
      const [dashboard, progress, achievements] = await Promise.all([
        api.get("/analytics/student-dashboard/"),
        api.get("/analytics/student-progress/"),
        api.get("/achievements/my-achievements/"),
      ]);
      [
        "enrolled_courses",
        "completed_courses",
        "certificates_earned",
        "projects_submitted",
      ].forEach((key) => {
        const element = document.querySelector(
          `[data-dashboard-metric="${key}"]`
        );
        if (element) {
          element.textContent =
            dashboard[key] === null ? "Not tracked" : String(dashboard[key]);
        }
      });
      renderCourse(progress.courses || []);
      renderPathways(dashboard.pathway_progress || []);
      renderSkills(dashboard.skills_acquired || []);
      renderAchievements(achievements);
    } catch (error) {
      document
        .querySelectorAll("[data-dashboard-metric]")
        .forEach((element) => (element.textContent = "Unavailable"));
      [
        [pathwayContainer, "Pathway progress is unavailable."],
        [skillContainer, "Completed-pathway skills are unavailable."],
        [achievementContainer, "Earned achievements are unavailable."],
        [opportunityContainer, "Current opportunities are unavailable."],
      ].forEach(([container, message]) => {
        if (!container) return;
        const empty = document.createElement("p");
        empty.className = "col-span-full text-xs text-slate-500";
        empty.textContent = message;
        container.replaceChildren(empty);
      });
      if (courseTitle) courseTitle.textContent = "Course progress is unavailable.";
      console.error("Could not load student dashboard analytics.", error);
    }
  }

  loadOpportunities();
  loadDashboard();
})();
