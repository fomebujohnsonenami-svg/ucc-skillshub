(function () {
  const api = window.skillsHubApi;
  if (!api) return;

  const grid = document.getElementById("pathways-grid");
  const filters = document.getElementById("filter-pill-container");
  const searchInput = document.getElementById("pathwaySearchInput");
  const difficultyFilter = document.getElementById("pathwayDifficultyFilter");
  const notice = document.getElementById("pathwayStatusNotice");
  const detail = document.getElementById("pathway-detail-section");
  const pagination = document.getElementById("pathwayPagination");
  const pageSummary = document.getElementById("pathwayPageSummary");
  const pageSize = 12;
  let page = 1;
  let category = "all";
  let search = "";
  let difficulty = "all";
  let selectedPathway = null;
  let enrollments = [];
  let progress = null;
  let searchTimer;

  function element(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function setNotice(message, visible) {
    notice.textContent = message || "";
    notice.hidden = !visible;
  }

  function resultList(data) {
    return Array.isArray(data) ? data : data && Array.isArray(data.results) ? data.results : [];
  }

  function enrolledPathway(id) {
    return enrollments.find((enrollment) => enrollment.pathway.id === id) || null;
  }

  function cardFor(pathway) {
    const button = element(
      "button",
      "group relative flex w-full flex-col justify-between rounded-2xl bg-surface-container-lowest p-space-lg text-left shadow-sm transition-all duration-300 hover:shadow-xl focus:outline-none focus:ring-2 focus:ring-secondary"
    );
    button.type = "button";
    button.setAttribute("aria-label", `View ${pathway.name} pathway`);
    const upper = element("div", "flex flex-col gap-space-md");
    const row = element("div", "flex items-center justify-between");
    const icon = element(
      "span",
      "material-symbols-outlined flex h-12 w-12 items-center justify-center rounded-xl bg-surface-container text-[26px] text-secondary group-hover:bg-secondary group-hover:text-on-secondary transition",
      "route"
    );
    const duration = element(
      "span",
      "rounded-full bg-surface-container-low px-2.5 py-1 font-label-sm text-label-sm text-on-surface-variant",
      `${pathway.estimated_duration_weeks} weeks`
    );
    row.append(icon, duration);

    const title = element(
      "h3",
      "font-headline-md text-headline-md font-bold text-on-surface transition group-hover:text-secondary",
      pathway.name
    );
    const description = element(
      "p",
      "mt-1 line-clamp-3 font-body-sm text-body-sm text-on-surface-variant",
      pathway.description
    );
    const meta = element(
      "p",
      "mt-2 font-label-sm text-label-sm text-on-surface-variant",
      `${pathway.category ? pathway.category.name : "General"} · ${pathway.difficulty} · ${pathway.step_count} steps`
    );
    const skills = element("div", "mt-3 flex flex-wrap gap-1.5");
    (pathway.required_skills || []).slice(0, 4).forEach((skill) => {
      skills.append(
        element(
          "span",
          "rounded-full bg-surface-container-low px-2.5 py-1 font-label-sm text-label-sm text-on-surface-variant",
          skill.name
        )
      );
    });
    upper.append(row, title, description, meta, skills);

    const footer = element(
      "div",
      "mt-space-lg flex items-center justify-between border-t border-surface-container-high/60 pt-space-sm font-label-md text-label-md"
    );
    const currentEnrollment = enrolledPathway(pathway.id);
    footer.append(
      element(
        "span",
        "text-on-surface-variant",
        currentEnrollment
          ? `${currentEnrollment.progress_percentage}% complete`
          : `${pathway.recommended_course_count || 0} recommended courses`
      ),
      element(
        "span",
        "text-secondary",
        currentEnrollment ? "Continue pathway →" : "View pathway →"
      )
    );
    button.append(upper, footer);
    button.addEventListener("click", () => openPathway(pathway.id, true));
    return button;
  }

  function renderPathways(data) {
    const pathways = resultList(data);
    grid.replaceChildren();
    pathways.forEach((pathway) => grid.append(cardFor(pathway)));
    grid.dataset.apiReady = "true";
    document.getElementById("pathwayTrackCount").textContent = data.count;
    document.getElementById("visible-count").textContent = data.count;
    if (!pathways.length) {
      grid.append(
        element(
          "p",
          "col-span-full rounded-xl bg-surface-container-lowest p-space-lg font-body-md text-body-md text-on-surface-variant",
          "No published pathways match these filters yet."
        )
      );
    }

    const hasPrevious = Boolean(data.previous);
    const hasNext = Boolean(data.next);
    pagination.classList.toggle("hidden", !(hasPrevious || hasNext));
    pagination.classList.add("flex");
    document.getElementById("previousPathwaysPage").disabled = !hasPrevious;
    document.getElementById("nextPathwaysPage").disabled = !hasNext;
    const start = pathways.length ? (page - 1) * pageSize + 1 : 0;
    const end = pathways.length ? start + pathways.length - 1 : 0;
    pageSummary.textContent = `${start}–${end} of ${data.count} pathways`;
  }

  async function loadPathways() {
    setNotice("Loading pathways…", true);
    const params = new URLSearchParams({ page: String(page) });
    if (search) params.set("search", search);
    if (category !== "all") params.set("category", category);
    if (difficulty !== "all") params.set("difficulty", difficulty);
    try {
      const data = await api.get(`/pathways/?${params.toString()}`);
      renderPathways(data);
      setNotice("", false);
    } catch (error) {
      setNotice(`Pathways could not be loaded. ${error.message}`, true);
    }
  }

  function setFilterActive(activeButton) {
    filters.querySelectorAll("button").forEach((button) => {
      const active = button === activeButton;
      button.className = active
        ? "filter-tab flex items-center gap-1.5 rounded-full bg-secondary px-5 py-2 font-label-md text-label-md text-on-secondary shadow-md transition"
        : "filter-tab flex items-center gap-1.5 rounded-full bg-surface-container-low px-5 py-2 font-label-md text-label-md text-on-surface transition hover:bg-surface-container-high";
      button.setAttribute("aria-selected", String(active));
    });
  }

  async function loadCategories() {
    try {
      const data = await api.get("/pathway-categories/");
      const categories = resultList(data);
      filters.replaceChildren();
      const items = [{ slug: "all", name: "All Pathways", pathway_count: data.count || 0 }, ...categories];
      items.forEach((item, index) => {
        const button = element(
          "button",
          index === 0
            ? "filter-tab flex items-center gap-1.5 rounded-full bg-secondary px-5 py-2 font-label-md text-label-md text-on-secondary shadow-md transition"
            : "filter-tab flex items-center gap-1.5 rounded-full bg-surface-container-low px-5 py-2 font-label-md text-label-md text-on-surface transition hover:bg-surface-container-high"
        );
        button.type = "button";
        button.dataset.filter = item.slug;
        button.setAttribute("role", "tab");
        button.setAttribute("aria-selected", String(index === 0));
        button.append(
          element("span", "", item.name),
          element(
            "span",
            "rounded-full bg-surface-container px-1.5 py-0.5 font-label-sm text-label-sm font-bold text-on-surface-variant",
            item.pathway_count || 0
          )
        );
        button.addEventListener("click", () => {
          category = item.slug;
          page = 1;
          setFilterActive(button);
          loadPathways();
        });
        filters.append(button);
      });
      filters.dataset.apiReady = "true";
    } catch (error) {
      setNotice(`Pathway categories could not be loaded. ${error.message}`, true);
    }
  }

  async function loadEnrollments() {
    if (
      !sessionStorage.getItem("skillshubAccessToken") &&
      !localStorage.getItem("skillshubAccessToken")
    ) {
      enrollments = [];
      return;
    }
    try {
      const data = await api.get("/pathways/my-pathways/");
      enrollments = resultList(data);
    } catch (error) {
      if (error.status !== 403) throw error;
      enrollments = [];
    }
  }

  function renderSkills(pathway) {
    const container = document.getElementById("pathwayRequiredSkills");
    const skills = pathway.required_skills || [];
    container.replaceChildren();
    document.getElementById("pathwaySkillCount").textContent =
      `${skills.length} Key Competencies`;
    skills.forEach((skill) => {
      container.append(
        element(
          "span",
          "inline-flex items-center gap-1.5 rounded-full bg-secondary-fixed px-3 py-1 font-label-sm text-label-sm text-on-secondary-fixed",
          skill.name
        )
      );
    });
    if (!skills.length) {
      container.append(element("p", "font-body-sm text-body-sm text-on-surface-variant", "No required skills listed."));
    }
  }

  function renderCourses(pathway) {
    const container = document.getElementById("pathwayRecommendedCourses");
    const courses = pathway.recommended_courses || [];
    container.replaceChildren();
    courses.forEach((course) => {
      const link = element(
        "a",
        "group flex items-center gap-space-sm rounded-xl p-2.5 transition hover:bg-surface-container-low"
      );
      link.href = "../ucc_skillshub_courses_catalogue/code.html";
      const image = document.createElement("img");
      image.className = "h-12 w-16 flex-shrink-0 rounded-lg bg-surface-container object-cover";
      image.alt = "";
      if (course.thumbnail_url) image.src = course.thumbnail_url;
      const info = element("span", "min-w-0 flex-1");
      info.append(
        element("span", "block truncate font-headline-sm text-headline-sm text-on-surface group-hover:text-secondary", course.title),
        element("span", "font-label-sm text-label-sm text-on-surface-variant", `${course.difficulty || "Course"} · ${course.estimated_duration_minutes || 0} minutes`)
      );
      link.append(image, info);
      container.append(link);
    });
    if (!courses.length) {
      container.append(element("p", "font-body-sm text-body-sm text-on-surface-variant", "No recommended courses listed."));
    }
  }

  function renderRoadmap(pathway) {
    const container = document.getElementById("pathwayRoadmap");
    container.replaceChildren();
    const steps = pathway.steps || [];
    const completed = steps.filter((step) => step.is_completed).length;
    steps.forEach((step, index) => {
      const article = element("article", "relative");
      article.id = `pathway-step-${step.id}`;
      const marker = element(
        "span",
        `absolute -left-6 top-5 flex h-7 w-7 items-center justify-center rounded-full text-white ring-4 ring-background ${step.is_completed ? "bg-emerald-500" : "bg-secondary"}`
      );
      marker.textContent = step.is_completed ? "✓" : String(index + 1).padStart(2, "0");
      const card = element("div", "rounded-2xl bg-surface-container-lowest p-space-md shadow-sm");
      const heading = element("div", "flex flex-wrap items-center justify-between gap-2");
      heading.append(
        element(
          "span",
          `rounded-full px-2.5 py-0.5 font-label-sm text-label-sm font-bold uppercase ${step.is_completed ? "bg-emerald-50 text-emerald-700" : "bg-secondary-fixed text-on-secondary-fixed"}`,
          `Stage ${String(index + 1).padStart(2, "0")} · ${step.is_completed ? "Completed" : "In progress"}`
        ),
        element("span", "font-label-sm text-label-sm text-on-surface-variant", `Estimated: ${step.estimated_duration_weeks} weeks`)
      );
      card.append(
        heading,
        element("h4", "mt-2 font-headline-sm text-headline-sm font-bold text-on-surface", step.title),
        element("p", "mt-1 font-body-sm text-body-sm text-on-surface-variant", step.description || "")
      );
      if (step.recommended_course) {
        const courseLink = element("a", "mt-3 inline-block font-label-sm text-label-sm font-semibold text-secondary hover:underline", `Recommended course: ${step.recommended_course.title}`);
        courseLink.href = "../ucc_skillshub_courses_catalogue/code.html";
        card.append(courseLink);
      }
      if (step.project_title) {
        card.append(
          element("p", "mt-3 font-label-sm text-label-sm font-semibold text-on-surface", `Project: ${step.project_title}`),
          element("p", "font-body-sm text-body-sm text-on-surface-variant", step.project_description || "")
        );
      }
      const completeButton = element(
        "button",
        `mt-4 rounded-full px-4 py-2 font-label-md text-label-md ${step.is_completed ? "bg-emerald-50 text-emerald-700" : "bg-secondary text-on-secondary"} disabled:cursor-not-allowed disabled:opacity-60`,
        step.is_completed ? "Completed" : enrolledPathway(pathway.id) ? "Mark step complete" : "Enroll to track this step"
      );
      completeButton.type = "button";
      completeButton.disabled = step.is_completed || !enrolledPathway(pathway.id);
      if (!completeButton.disabled) {
        completeButton.addEventListener("click", () => completeStep(step.id, completeButton));
      }
      card.append(completeButton);
      article.append(marker, card);
      container.append(article);
    });
    if (!steps.length) {
      container.append(element("p", "rounded-xl bg-surface-container-lowest p-space-md font-body-sm text-body-sm text-on-surface-variant", "This pathway has no published steps yet."));
    }
    document.getElementById("pathwayProgressSummary").textContent = `${completed}/${steps.length} Completed`;
    const percentage = steps.length ? Math.round((completed * 100) / steps.length) : 0;
    document.getElementById("featuredProgressRing").setAttribute("stroke-dasharray", `${percentage}, 100`);
    document.getElementById("featuredProgressPercent").textContent = `${percentage}%`;
  }

  function renderProjects(pathway) {
    const projects = (pathway.steps || []).filter((step) => step.project_title);
    const container = document.getElementById("pathwayProjects");
    container.replaceChildren();
    document.getElementById("pathwayProjectCount").textContent = `${projects.length} Projects`;
    projects.forEach((project, index) => {
      const item = element("div", "flex flex-col gap-1.5 rounded-xl bg-surface-container-low p-space-sm");
      item.append(
        element("span", "font-label-md text-label-md font-bold text-on-surface", `${index + 1}. ${project.project_title}`),
        element("p", "font-body-sm text-body-sm text-on-surface-variant", project.project_description || "")
      );
      container.append(item);
    });
    if (!projects.length) {
      container.append(element("p", "font-body-sm text-body-sm text-on-surface-variant", "No practical projects listed."));
    }
  }

  function renderDetail(pathway) {
    selectedPathway = pathway;
    const enrollment = enrolledPathway(pathway.id);
    const currentProgress = progress && progress.pathway.id === pathway.id ? progress : null;
    const completionSteps = currentProgress ? currentProgress.steps : null;
    if (completionSteps) {
      pathway.steps = completionSteps;
    }
    detail.dataset.loaded = "true";
    document.getElementById("pathwayDetailBreadcrumb").textContent = pathway.name;
    document.getElementById("pathwayDetailTitle").textContent = pathway.name;
    document.getElementById("pathwayDetailDescription").textContent = pathway.description;
    document.getElementById("pathwayDetailStatus").textContent = enrollment
      ? `${enrollment.progress_percentage}% complete`
      : `${pathway.difficulty} · ${pathway.category.name}`;
    document.getElementById("pathwayStepMetric").textContent = `${pathway.steps.length} steps`;
    document.getElementById("pathwayProjectMetric").textContent =
      `${pathway.steps.filter((step) => step.project_title).length} projects`;
    document.getElementById("pathwayDurationMetric").textContent =
      `${pathway.estimated_duration_weeks} weeks`;
    document.getElementById("pathwayEnrollmentMetric").textContent =
      `${pathway.enrollment_count} learners`;
    document.getElementById("pathwayEnrollLabel").textContent = enrollment
      ? enrollment.status === "completed" ? "Pathway completed" : "Continue pathway"
      : "Enroll in pathway";
    const hasToken =
      sessionStorage.getItem("skillshubAccessToken") ||
      localStorage.getItem("skillshubAccessToken");
    document.getElementById("pathwayEnrollButton").disabled =
      (!enrollment && !hasToken) || Boolean(enrollment && enrollment.status === "completed");
    if (!enrollment && !sessionStorage.getItem("skillshubAccessToken") && !localStorage.getItem("skillshubAccessToken")) {
      document.getElementById("pathwayEnrollLabel").textContent = "Sign in to enroll";
    }
    document.getElementById("featuredPathwayTitle").textContent = enrollment ? pathway.name : "No active pathway yet";
    document.getElementById("featuredPathwaySummary").textContent =
      enrollment ? `${enrollment.completed_steps} of ${enrollment.total_steps} steps completed` : "Choose a career pathway below";
    document.getElementById("featuredPathwayNext").textContent =
      enrollment ? "Resume your learning roadmap" : "Enroll to begin your roadmap";
    document.getElementById("featuredPathwayStatus").textContent =
      enrollment ? "Progress is calculated from completed steps" : "Pathway progress is based on completed steps";
    renderSkills(pathway);
    renderCourses(pathway);
    renderProjects(pathway);
    renderRoadmap(pathway);
  }

  async function openPathway(id, scroll) {
    setNotice("Loading pathway details…", true);
    progress = null;
    try {
      const pathway = await api.get(`/pathways/${id}/`);
      let enrollment = enrolledPathway(pathway.id);
      if (enrollment) {
        try {
          progress = await api.get(`/pathways/${pathway.id}/progress/`);
        } catch (error) {
          if (error.status !== 404) throw error;
          enrollments = enrollments.filter((item) => item.pathway.id !== pathway.id);
          enrollment = null;
        }
      }
      renderDetail(pathway);
      setNotice("", false);
      const url = new URL(window.location.href);
      url.searchParams.set("pathway", String(id));
      window.history.replaceState({}, "", url);
      if (scroll) detail.scrollIntoView({ behavior: "smooth", block: "start" });
    } catch (error) {
      setNotice(`Pathway details could not be loaded. ${error.message}`, true);
    }
  }

  async function completeStep(stepId, button) {
    button.disabled = true;
    button.textContent = "Saving…";
    try {
      progress = await api.post(`/pathway-steps/${stepId}/complete/`);
      const enrollment = enrolledPathway(selectedPathway.id);
      if (enrollment) {
        enrollment.status = progress.status;
        enrollment.completed_steps = progress.completed_steps;
        enrollment.total_steps = progress.total_steps;
        enrollment.progress_percentage = progress.progress_percentage;
      }
      renderDetail(selectedPathway);
      await loadPathways();
    } catch (error) {
      button.disabled = false;
      button.textContent = "Mark step complete";
      setNotice(`Step completion could not be saved. ${error.message}`, true);
    }
  }

  document.getElementById("pathwayEnrollButton").addEventListener("click", async () => {
    if (!selectedPathway) return;
    const existingEnrollment = enrolledPathway(selectedPathway.id);
    if (existingEnrollment) {
      const targetStep =
        selectedPathway.steps.find((step) => !step.is_completed) ||
        selectedPathway.steps[selectedPathway.steps.length - 1];
      if (targetStep) {
        document
          .getElementById(`pathway-step-${targetStep.id}`)
          .scrollIntoView({ behavior: "smooth", block: "center" });
      }
      return;
    }
    const button = document.getElementById("pathwayEnrollButton");
    button.disabled = true;
    document.getElementById("pathwayEnrollLabel").textContent = "Enrolling…";
    try {
      await api.post(`/pathways/${selectedPathway.id}/enroll/`);
      await loadEnrollments();
      await openPathway(selectedPathway.id, false);
      await loadPathways();
    } catch (error) {
      button.disabled = false;
      setNotice(`Enrollment could not be completed. ${error.message}`, true);
    }
  });

  searchInput.addEventListener("input", () => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => {
      search = searchInput.value.trim();
      page = 1;
      loadPathways();
    }, 250);
  });
  difficultyFilter.addEventListener("change", () => {
    difficulty = difficultyFilter.value;
    page = 1;
    loadPathways();
  });
  document.getElementById("previousPathwaysPage").addEventListener("click", () => {
    if (page > 1) {
      page -= 1;
      loadPathways();
    }
  });
  document.getElementById("nextPathwaysPage").addEventListener("click", () => {
    page += 1;
    loadPathways();
  });

  document.addEventListener("DOMContentLoaded", async () => {
    try {
      await loadEnrollments();
    } catch (error) {
      setNotice(`Your enrolled pathways could not be loaded. ${error.message}`, true);
    }
    await Promise.all([loadCategories(), loadPathways()]);
    const requestedPathway = new URLSearchParams(window.location.search).get("pathway");
    if (requestedPathway && /^\d+$/.test(requestedPathway)) {
      openPathway(requestedPathway, false);
    } else {
      detail.dataset.loaded = "false";
    }
  });
})();
