(() => {
  const catalog = document.getElementById("catalogContainer");
  const featured = document.getElementById("featuredCourseSection");
  const chips = document.getElementById("categoryChipsContainer");
  const chipsSection = document.getElementById("categoryChipsSection");
  const search = document.getElementById("courseSearchInput");
  const level = document.getElementById("levelFilter");
  const duration = document.getElementById("durationFilter");
  const certificate = document.getElementById("certificateFilter");
  const sort = document.getElementById("sortFilter");
  const notice = document.getElementById("courseCatalogueNotice");
  const pagination = document.getElementById("coursePagination");
  const pageSummary = document.getElementById("coursePageSummary");
  const previous = document.getElementById("previousCoursesPage");
  const next = document.getElementById("nextCoursesPage");
  const categoryIcons = {
    ai: "smart_toy",
    technology: "devices",
    communication: "record_voice_over",
    business: "rocket_launch",
    finance: "account_balance_wallet",
    workplace: "verified_user",
    leadership: "diversity_3",
  };
  let activeCategory = "all";
  let currentPage = 1;
  let requestSequence = 0;
  let searchTimer;

  function showNotice(message, isError) {
    notice.textContent = message;
    notice.classList.remove("hidden");
    notice.classList.toggle("text-rose-600", Boolean(isError));
    notice.classList.toggle("text-on-surface-variant", !isError);
  }

  function durationLabel(minutes) {
    if (minutes < 60) return `${minutes} min`;
    const hours = minutes / 60;
    return `${Number.isInteger(hours) ? hours : hours.toFixed(1)} hrs`;
  }

  function courseUrl(course) {
    const detailUrl = "../skillbridge_course_details_learning_experience/code.html";
    return `${detailUrl}?course=${encodeURIComponent(course.id)}`;
  }

  function updateFeatured(course) {
    if (!course) {
      featured.hidden = true;
      featured.dataset.apiReady = "true";
      return;
    }

    featured.hidden = false;
    featured.dataset.apiReady = "true";
    featured.innerHTML = `
      <div class="bg-surface-container-low rounded-3xl p-6 sm:p-8 md:p-10 shadow-sm border border-surface-container-highest/60 relative overflow-hidden flex flex-col xl:flex-row gap-8 items-stretch justify-between">
        <div class="flex-1 flex flex-col justify-between max-w-2xl">
          <div>
            <span class="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-amber-100 text-amber-900 border border-amber-300/80 font-label-sm text-label-sm font-bold">FEATURED COURSE</span>
            <h2 class="font-headline-xl text-headline-xl text-slate-900 font-bold tracking-tight my-4 leading-tight"></h2>
            <p class="font-body-md text-body-md text-slate-700 mb-6 leading-relaxed"></p>
            <div class="flex flex-wrap items-center gap-4 text-slate-700 font-label-sm text-label-sm mb-4">
              <span class="font-medium"></span>
              <span class="font-medium"></span>
              <span class="font-medium"></span>
            </div>
          </div>
          <a class="inline-flex w-fit items-center gap-2 px-6 py-3 rounded-full bg-secondary text-on-secondary font-label-md text-label-md shadow-md hover:bg-secondary-container transition" href="">
            <span>View Course</span><span class="material-symbols-outlined text-sm">arrow_forward</span>
          </a>
        </div>
      </div>`;
    featured.querySelector("h2").textContent = course.title;
    featured.querySelector("p").textContent = course.description;
    const details = featured.querySelectorAll(".flex.flex-wrap.items-center.gap-4 span");
    details[0].textContent = durationLabel(course.estimated_duration_minutes);
    details[1].textContent = course.certificate_eligible
      ? "Certificate eligible"
      : "No certificate";
    details[2].textContent = course.category.name;
    featured.querySelector("a").href = courseUrl(course);
  }

  function createCourseCard(course) {
    const card = document.createElement("article");
    card.className =
      "course-card bg-surface-container-lowest rounded-2xl p-5 shadow-sm hover:shadow-lg transition-all flex flex-col justify-between";
    card.dataset.level = course.difficulty;
    card.dataset.duration =
      course.estimated_duration_minutes < 120
        ? "short"
        : course.estimated_duration_minutes <= 300
          ? "medium"
          : "long";
    card.dataset.title = course.title.toLowerCase();

    const content = document.createElement("div");
    const labels = document.createElement("div");
    labels.className = "flex items-center justify-between mb-3";
    const category = document.createElement("span");
    category.className =
      "font-label-sm text-label-sm px-2.5 py-1 rounded-full bg-secondary-fixed text-on-secondary-fixed";
    category.textContent = course.category.name;
    const certificateLabel = document.createElement("span");
    certificateLabel.className =
      "font-label-sm text-label-sm text-secondary font-semibold";
    certificateLabel.textContent = course.certificate_eligible ? "Certificate" : "";
    labels.append(category, certificateLabel);

    const title = document.createElement("h3");
    title.className = "font-headline-sm text-headline-sm text-on-background mb-2";
    title.textContent = course.title;
    const description = document.createElement("p");
    description.className =
      "font-body-sm text-body-sm text-on-surface-variant line-clamp-2 mb-4";
    description.textContent = course.description;
    const facts = document.createElement("div");
    facts.className =
      "flex items-center gap-3 text-label-sm font-label-sm text-on-surface-variant mb-4";
    const rating =
      Number(course.average_rating) > 0
        ? Number(course.average_rating).toFixed(1)
        : "New";
    const difficulty =
      course.difficulty === "all" ? "All levels" : course.difficulty;
    facts.textContent = `${rating}  •  ${durationLabel(course.estimated_duration_minutes)}  •  ${difficulty}`;
    content.append(labels, title, description, facts);

    const footer = document.createElement("div");
    footer.className =
      "pt-3 border-t border-transparent flex items-center justify-between";
    const instructor = document.createElement("span");
    instructor.className =
      "font-body-sm text-body-sm text-on-surface-variant truncate max-w-[130px]";
    instructor.textContent =
      course.instructors.map((entry) => entry.full_name).join(", ") ||
      "UCC SKILLSHUB";
    const link = document.createElement("a");
    link.className =
      "px-3.5 py-1.5 rounded-full bg-surface-container hover:bg-secondary hover:text-on-secondary text-secondary font-label-md text-label-md transition";
    link.href = courseUrl(course);
    link.textContent = "View Course";
    footer.append(instructor, link);
    card.append(content, footer);
    return card;
  }

  function renderCourses(results) {
    catalog.replaceChildren();
    const groups = new Map();
    results.forEach((course) => {
      const key = course.category.slug;
      if (!groups.has(key)) {
        groups.set(key, { category: course.category, courses: [] });
      }
      groups.get(key).courses.push(course);
    });

    groups.forEach(({ category, courses }) => {
      const section = document.createElement("section");
      section.className = "category-block";
      section.dataset.categoryGroup = category.slug;
      const heading = document.createElement("div");
      heading.className = "flex items-center justify-between pb-3 mb-5";
      const intro = document.createElement("div");
      intro.className = "flex items-center gap-3";
      const icon = document.createElement("div");
      icon.className =
        "w-10 h-10 rounded-xl bg-secondary-fixed text-on-secondary-fixed flex items-center justify-center";
      const iconName = document.createElement("span");
      iconName.className = "material-symbols-outlined text-xl";
      iconName.textContent = categoryIcons[category.slug] || "menu_book";
      icon.append(iconName);

      const text = document.createElement("div");
      const titleLine = document.createElement("div");
      titleLine.className = "flex items-center gap-2";
      const title = document.createElement("h2");
      title.className = "font-headline-md text-headline-md text-on-background";
      title.textContent = category.name;
      const count = document.createElement("span");
      count.className =
        "px-2 py-0.5 rounded-full bg-surface-container text-on-surface-variant font-label-sm text-label-sm";
      count.textContent = `${courses.length} shown`;
      titleLine.append(title, count);
      const description = document.createElement("p");
      description.className = "font-body-sm text-body-sm text-on-surface-variant";
      description.textContent = category.description;
      text.append(titleLine, description);
      intro.append(icon, text);
      heading.append(intro);

      const grid = document.createElement("div");
      grid.className =
        "grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-5";
      courses.forEach((course) => grid.append(createCourseCard(course)));
      section.append(heading, grid);
      catalog.append(section);
    });
    catalog.dataset.apiReady = "true";
    if (results.length === 0) {
      const empty = document.createElement("p");
      empty.className =
        "rounded-2xl bg-surface-container-lowest p-8 text-center font-body-md text-body-md text-on-surface-variant";
      empty.textContent = "No published courses match these filters.";
      catalog.append(empty);
    }
  }

  function renderCategories(categories, totalCount) {
    chips.replaceChildren();
    const allCategories = [
      { slug: "all", name: "All Courses", course_count: totalCount },
      ...categories,
    ];
    allCategories.forEach((category, index) => {
      const button = document.createElement("button");
      const selected = category.slug === activeCategory;
      button.className = `category-chip flex items-center gap-2 px-4 py-2 rounded-full font-label-md text-label-md whitespace-nowrap transition ${
        selected
          ? "active bg-secondary text-on-secondary shadow-sm"
          : "bg-surface-container-lowest text-on-surface-variant hover:bg-surface-container hover:text-on-background"
      }`;
      button.dataset.category = category.slug;
      const icon = document.createElement("span");
      icon.className = "material-symbols-outlined text-sm";
      icon.textContent =
        categoryIcons[category.slug] || (index === 0 ? "widgets" : "menu_book");
      const name = document.createElement("span");
      name.textContent = category.name;
      const count = document.createElement("span");
      count.className =
        "ml-1 px-1.5 py-0.5 rounded-full text-label-sm font-label-sm";
      count.textContent = String(category.course_count || 0);
      button.append(icon, name, count);
      button.addEventListener("click", () => {
        activeCategory = category.slug;
        currentPage = 1;
        renderCategories(categories, totalCount);
        loadCourses();
      });
      chips.append(button);
    });
    chipsSection.dataset.apiReady = "true";
  }

  async function loadSummaryMetrics() {
    try {
      const eligible = await window.skillsHubApi.get(
        "/courses/?certificate=true",
      );
      document.getElementById("eligibleCourseCount").textContent =
        String(eligible.count);
    } catch (error) {
      document.getElementById("eligibleCourseCount").textContent = "—";
      showNotice(
        `Certificate-eligible course counts are unavailable: ${error.message}`,
        true,
      );
    }

    const hasToken =
      sessionStorage.getItem("skillshubAccessToken") ||
      localStorage.getItem("skillshubAccessToken");
    if (!hasToken) return;
    try {
      let page = 1;
      const enrollments = [];
      let hasNextPage = true;
      while (hasNextPage) {
        const response = await window.skillsHubApi.get(
          `/courses/my-courses/?page=${page}`,
        );
        if (Array.isArray(response)) {
          enrollments.push(...response);
          hasNextPage = false;
        } else {
          enrollments.push(...response.results);
          hasNextPage = Boolean(response.next);
          page += 1;
        }
      }
      document.getElementById("activeCourseCount").textContent = String(
        enrollments.filter((entry) => entry.status === "in_progress").length,
      );
      document.getElementById("completedCourseCount").textContent = String(
        enrollments.filter((entry) => entry.status === "completed").length,
      );
    } catch (error) {
      document.getElementById("activeCourseCount").textContent = "—";
      document.getElementById("completedCourseCount").textContent = "—";
      showNotice(
        `Your course enrollment counts are unavailable: ${error.message}`,
        true,
      );
    }
  }

  async function loadCourses() {
    const sequence = ++requestSequence;
    catalog.setAttribute("aria-busy", "true");
    showNotice("Loading courses…", false);
    const params = new URLSearchParams({ page: String(currentPage) });
    if (search.value.trim()) params.set("search", search.value.trim());
    if (activeCategory !== "all") params.set("category", activeCategory);
    if (level.value !== "all") params.set("difficulty", level.value);
    if (duration.value !== "all") params.set("duration", duration.value);
    if (certificate.value !== "all") {
      params.set("certificate", certificate.value);
    }
    const sortValue = {
      popular: "popular",
      rated: "rated",
      newest: "newest",
      duration: "duration",
    }[sort.value] || "newest";
    params.set("sort", sortValue);

    try {
      const response = await window.skillsHubApi.get(`/courses/?${params}`);
      if (sequence !== requestSequence) return;
      renderCourses(response.results);
      document.getElementById("liveCourseCount").textContent =
        String(response.count);
      updateFeatured(currentPage === 1 ? response.results[0] : null);
      const hasPages = Boolean(response.previous || response.next);
      pagination.classList.toggle("hidden", !hasPages);
      pagination.classList.toggle("flex", hasPages);
      pageSummary.textContent = response.count
        ? `Showing ${(currentPage - 1) * 12 + 1}–${Math.min(
            currentPage * 12,
            response.count,
          )} of ${response.count} courses`
        : "";
      previous.disabled = !response.previous;
      next.disabled = !response.next;
      notice.classList.add("hidden");

      try {
        const categoryResponse = await window.skillsHubApi.get(
          "/courses/categories/",
        );
        if (sequence !== requestSequence) return;
        const categories = Array.isArray(categoryResponse)
          ? categoryResponse
          : categoryResponse.results;
        renderCategories(categories, response.count);
      } catch (error) {
        if (sequence !== requestSequence) return;
        chips.replaceChildren();
        chipsSection.dataset.apiReady = "false";
        showNotice(
          `Courses loaded, but categories are unavailable: ${error.message}`,
          true,
        );
      }
      return true;
    } catch (error) {
      if (sequence !== requestSequence) return;
      catalog.replaceChildren();
      chips.replaceChildren();
      chipsSection.dataset.apiReady = "false";
      catalog.dataset.apiReady = "true";
      updateFeatured(null);
      pagination.classList.add("hidden");
      showNotice(
        error.message || "Unable to load courses. Please try again.",
        true,
      );
      return false;
    } finally {
      if (sequence === requestSequence) {
        catalog.setAttribute("aria-busy", "false");
      }
    }
  }

  search.addEventListener("input", () => {
    window.clearTimeout(searchTimer);
    searchTimer = window.setTimeout(() => {
      currentPage = 1;
      loadCourses();
    }, 250);
  });
  [level, duration, certificate, sort].forEach((control) => {
    control.addEventListener("change", () => {
      currentPage = 1;
      loadCourses();
    });
  });
  previous.addEventListener("click", () => {
    if (currentPage > 1) {
      currentPage -= 1;
      loadCourses();
    }
  });
  next.addEventListener("click", () => {
    currentPage += 1;
    loadCourses();
  });
  window.addEventListener("keydown", (event) => {
    if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
      event.preventDefault();
      search.focus();
    }
  });

  chips.replaceChildren();
  updateFeatured(null);
  loadCourses().then((loaded) => {
    if (loaded) loadSummaryMetrics();
  });
})();
