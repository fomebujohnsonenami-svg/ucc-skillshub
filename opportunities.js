(function () {
  const api = window.skillsHubApi;
  const state = {
    categories: [],
    opportunities: [],
    applications: [],
    category: "",
    page: 1,
    hasMore: false,
    selectedOpportunity: null,
    loading: false,
  };

  const byId = (id) => document.getElementById(id);
  const hasAccessToken = () =>
    Boolean(
      sessionStorage.getItem("skillshubAccessToken") ||
        localStorage.getItem("skillshubAccessToken")
    );
  const listFromResponse = (response) =>
    Array.isArray(response) ? response : response && Array.isArray(response.results) ? response.results : [];

  function setText(id, value) {
    const element = byId(id);
    if (element) element.textContent = value || "";
  }

  function createElement(tag, className, text) {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text !== undefined) element.textContent = text;
    return element;
  }

  function setReady() {
    document.body.classList.add("opportunities-ready");
  }

  function currentFilters(page) {
    const parameters = new URLSearchParams();
    const search = byId("opportunity-search").value.trim();
    const location = byId("opportunity-location-filter").value;
    const opportunityType = byId("opportunity-type-filter").value;
    const arrangement = byId("opportunity-arrangement-filter").value;
    const deadlineDays = byId("opportunity-deadline-filter").value;
    const skill = byId("opportunity-skill-filter").value.trim();
    if (search) parameters.set("search", search);
    if (location) parameters.set("location", location);
    if (opportunityType) parameters.set("opportunity_type", opportunityType);
    if (arrangement) parameters.set("work_arrangement", arrangement);
    if (skill) parameters.set("skills", skill);
    if (deadlineDays) {
      const deadline = new Date();
      deadline.setDate(deadline.getDate() + Number(deadlineDays));
      parameters.set("deadline_before", deadline.toISOString().slice(0, 10));
    }
    if (state.category) parameters.set("category", state.category);
    parameters.set("page", String(page));
    return parameters.toString();
  }

  async function loadOpportunities(append) {
    if (!api || state.loading) return;
    state.loading = true;
    const list = byId("opportunity-list");
    if (!append) {
      list.replaceChildren(
        createElement(
          "p",
          "p-space-md text-body-sm text-on-surface-variant",
          "Loading opportunities..."
        )
      );
    }
    const requestedPage = append ? state.page + 1 : 1;
    try {
      const response = await api.get(
        `/opportunities/?${currentFilters(requestedPage)}`
      );
      const results = listFromResponse(response);
      state.opportunities = append
        ? state.opportunities.concat(results)
        : results;
      state.page = requestedPage;
      state.hasMore = Boolean(response && !Array.isArray(response) && response.next);
      renderOpportunities();
      if (!append) {
        state.selectedOpportunity =
          state.opportunities.find((item) => item.id === state.selectedOpportunity) ||
          state.opportunities[0] ||
          null;
        if (state.selectedOpportunity) {
          selectOpportunity(state.selectedOpportunity.id);
        } else {
          renderEmptyDetail();
        }
      }
    } catch (error) {
      if (!append) {
        state.opportunities = [];
        state.selectedOpportunity = null;
        renderFeatured(null);
      }
      list.replaceChildren(
        createElement(
          "p",
          "p-space-md text-body-sm text-error",
          `Could not load opportunities. ${error.message}`
        )
      );
      renderEmptyDetail();
      console.error("Could not load opportunities.", error);
    } finally {
      state.loading = false;
      setReady();
    }
  }

  function renderCategories() {
    const container = byId("category-tabs");
    container.replaceChildren();
    const categories = [{ slug: "", name: "All Opportunities" }].concat(
      state.categories
    );
    categories.forEach((category) => {
      const button = createElement(
        "button",
        "category-pill px-4 py-2 rounded-full font-label-md text-label-md whitespace-nowrap transition"
      );
      button.type = "button";
      button.textContent = category.name;
      button.classList.add(
        state.category === category.slug
          ? "bg-secondary"
          : "bg-surface-container-lowest"
      );
      button.classList.add(
        state.category === category.slug
          ? "text-on-secondary"
          : "text-on-surface"
      );
      button.dataset.category = category.slug;
      button.addEventListener("click", () => {
        state.category = category.slug;
        renderCategories();
        loadOpportunities(false);
      });
      container.appendChild(button);
    });
  }

  function createSkillPill(skill) {
    return createElement(
      "span",
      "px-2.5 py-0.5 rounded-full bg-surface-container-low text-on-surface font-label-sm text-label-sm",
      skill.name
    );
  }

  function renderOpportunityCard(opportunity) {
    const card = createElement(
      "article",
      "opportunity-card p-space-md bg-surface-container-lowest rounded-2xl shadow-sm hover:shadow-md transition cursor-pointer relative"
    );
    card.dataset.id = opportunity.id;
    card.tabIndex = 0;
    card.setAttribute("role", "button");
    card.setAttribute("aria-label", `${opportunity.title} at ${opportunity.organization}`);
    card.addEventListener("click", () => selectOpportunity(opportunity.id));
    card.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        selectOpportunity(opportunity.id);
      }
    });

    const headingRow = createElement(
      "div",
      "flex flex-col sm:flex-row sm:items-start justify-between gap-space-sm"
    );
    const titleArea = createElement("div", "flex items-start gap-space-sm");
    const logo = createElement(
      "div",
      "w-12 h-12 rounded-xl bg-surface-container-high text-secondary flex items-center justify-center font-headline-md text-headline-md font-bold shrink-0",
      (opportunity.organization || "?").trim().slice(0, 2).toUpperCase()
    );
    const titleInfo = createElement("div");
    titleInfo.appendChild(
      createElement(
        "h3",
        "font-headline-md text-headline-md text-on-surface",
        opportunity.title
      )
    );
    titleInfo.appendChild(
      createElement(
        "p",
        "font-label-md text-label-md text-on-surface-variant mt-0.5",
        opportunity.organization
      )
    );
    titleInfo.appendChild(
      createElement(
        "p",
        "font-label-sm text-label-sm text-on-surface-variant mt-1",
        [
          opportunity.work_arrangement,
          opportunity.location,
          opportunity.compensation,
        ]
          .filter(Boolean)
          .join(" · ")
      )
    );
    titleArea.append(logo, titleInfo);
    const category = createElement(
      "span",
      "px-2.5 py-1 rounded-full bg-surface-container font-label-sm text-label-sm text-on-surface-variant self-start",
      opportunity.category ? opportunity.category.name : ""
    );
    headingRow.append(titleArea, category);
    card.appendChild(headingRow);

    card.appendChild(
      createElement(
        "p",
        "font-body-sm text-body-sm text-on-surface-variant mt-3 line-clamp-2",
        opportunity.description
      )
    );

    const skillRow = createElement("div", "flex items-center gap-1.5 flex-wrap mt-3 pt-2");
    (opportunity.required_skills || []).forEach((skill) =>
      skillRow.appendChild(createSkillPill(skill))
    );
    if (skillRow.childElementCount) card.appendChild(skillRow);

    const footer = createElement(
      "div",
      "flex items-center justify-between mt-4 pt-3 flex-wrap gap-2"
    );
    const deadlineText = opportunity.application_deadline
      ? `Deadline: ${new Date(opportunity.application_deadline).toLocaleDateString()}`
      : "Deadline not listed";
    footer.appendChild(
      createElement(
        "span",
        "text-label-sm font-label-sm text-on-surface-variant",
        deadlineText
      )
    );
    const applyButton = createElement(
      "button",
      "px-4 py-1.5 rounded-full bg-secondary text-on-secondary font-label-md text-label-md hover:bg-secondary-container transition",
      opportunity.is_applied ? "Applied" : "View opportunity"
    );
    applyButton.type = "button";
    applyButton.disabled = Boolean(opportunity.is_applied);
    applyButton.addEventListener("click", (event) => {
      event.stopPropagation();
      if (!opportunity.is_applied) selectOpportunity(opportunity.id);
    });
    footer.appendChild(applyButton);
    card.appendChild(footer);
    return card;
  }

  function renderOpportunities() {
    const list = byId("opportunity-list");
    list.replaceChildren();
    if (!state.opportunities.length) {
      list.appendChild(
        createElement(
          "p",
          "p-space-md text-body-sm text-on-surface-variant",
          "No open opportunities match these filters."
        )
      );
    } else {
      state.opportunities.forEach((opportunity) =>
        list.appendChild(renderOpportunityCard(opportunity))
      );
    }
    if (state.hasMore) {
      const more = createElement(
        "button",
        "self-center px-5 py-2 rounded-full bg-surface-container text-on-surface font-label-md text-label-md hover:bg-surface-container-high transition",
        "Load more opportunities"
      );
      more.type = "button";
      more.addEventListener("click", () => loadOpportunities(true));
      list.appendChild(more);
    }
    setText("opportunity-count", String(state.opportunities.length));
    renderFeatured(state.opportunities[0]);
  }

  function renderFeatured(opportunity) {
    const section = byId("featured-opportunity");
    if (!opportunity) {
      section.style.display = "none";
      section.replaceChildren();
      return;
    }
    section.style.display = "";
    const card = createElement(
      "div",
      "rounded-2xl bg-surface-container-lowest p-space-lg shadow-sm relative overflow-hidden"
    );
    card.appendChild(
      createElement(
        "div",
        "absolute top-0 left-0 right-0 h-1.5 bg-gradient-to-r from-secondary via-secondary-container to-secondary-fixed-dim"
      )
    );
    const layout = createElement("div", "flex flex-col lg:flex-row gap-space-lg justify-between items-start");
    const info = createElement("div", "flex-1 flex flex-col gap-space-sm");
    info.appendChild(
      createElement(
        "span",
        "px-3 py-1 rounded-full bg-secondary-fixed text-on-secondary-fixed-variant font-label-sm text-label-sm font-bold self-start",
        opportunity.category ? opportunity.category.name : "Opportunity"
      )
    );
    info.appendChild(
      createElement(
        "h2",
        "font-headline-lg text-headline-lg text-on-surface mt-1",
        opportunity.title
      )
    );
    info.appendChild(
      createElement(
        "p",
        "font-label-md text-label-md text-on-surface-variant",
        [opportunity.organization, opportunity.location, opportunity.work_arrangement]
          .filter(Boolean)
          .join(" · ")
      )
    );
    info.appendChild(
      createElement(
        "p",
        "font-body-md text-body-md text-on-surface-variant max-w-3xl mt-1",
        opportunity.description
      )
    );
    const skillList = createElement("div", "flex items-center gap-space-xs flex-wrap pt-2");
    (opportunity.required_skills || []).forEach((skill) =>
      skillList.appendChild(createSkillPill(skill))
    );
    info.appendChild(skillList);

    const actions = createElement(
      "div",
      "w-full lg:w-72 shrink-0 bg-surface-container-low p-space-md rounded-xl flex flex-col gap-space-sm"
    );
    actions.appendChild(
      createElement(
        "p",
        "font-label-sm text-label-sm text-on-surface-variant",
        `Compensation: ${opportunity.compensation || "Not specified"}`
      )
    );
    actions.appendChild(
      createElement(
        "p",
        "font-label-sm text-label-sm text-on-surface-variant",
        opportunity.application_deadline
          ? `Application deadline: ${new Date(opportunity.application_deadline).toLocaleDateString()}`
          : "Application deadline not listed"
      )
    );
    const viewButton = createElement(
      "button",
      "w-full py-2.5 px-space-md rounded-full bg-surface-container text-on-surface font-label-md text-label-md hover:bg-surface-container-high transition",
      "View details"
    );
    viewButton.type = "button";
    viewButton.addEventListener("click", () => selectOpportunity(opportunity.id));
    actions.appendChild(viewButton);
    const applyButton = createElement(
      "button",
      "w-full py-2.5 px-space-md rounded-full bg-secondary text-on-secondary font-label-md text-label-md flex items-center justify-center gap-1 shadow-md hover:bg-secondary-container transition",
      opportunity.is_applied ? "Already applied" : "Apply"
    );
    applyButton.type = "button";
    applyButton.disabled = Boolean(opportunity.is_applied) || !opportunity.is_open;
    applyButton.addEventListener("click", () => openApplyModal(opportunity.id));
    actions.appendChild(applyButton);
    layout.append(info, actions);
    card.appendChild(layout);
    section.replaceChildren(card);
  }

  function renderTextList(container, value, emptyMessage) {
    container.replaceChildren();
    const lines = (value || "")
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter(Boolean);
    if (!lines.length) {
      container.appendChild(createElement("li", "text-on-surface-variant", emptyMessage));
      return;
    }
    lines.forEach((line) => {
      const item = createElement("li", "flex items-start gap-2");
      item.appendChild(
        createElement("span", "w-1.5 h-1.5 rounded-full bg-secondary shrink-0 mt-2")
      );
      item.appendChild(createElement("span", "", line));
      container.appendChild(item);
    });
  }

  function selectOpportunity(id) {
    const opportunity =
      typeof id === "object"
        ? id
        : state.opportunities.find((item) => item.id === Number(id));
    if (!opportunity) return;
    state.selectedOpportunity = opportunity.id;
    document.querySelectorAll(".opportunity-card").forEach((card) => {
      card.classList.toggle("ring-2", String(card.dataset.id) === String(id));
      card.classList.toggle("ring-secondary", String(card.dataset.id) === String(id));
    });
    setText("drawer-title", opportunity.title);
    setText("drawer-company", opportunity.organization);
    setText(
      "drawer-meta",
      [opportunity.category && opportunity.category.name, opportunity.location]
        .filter(Boolean)
        .join(" · ")
    );
    setText(
      "drawer-sublocation",
      [opportunity.work_arrangement, opportunity.location].filter(Boolean).join(" · ")
    );
    setText("drawer-stipend", opportunity.compensation || "Not specified");
    setText("drawer-contract", opportunity.opportunity_type || "Not specified");
    setText("drawer-arrangement", opportunity.work_arrangement || "Not specified");
    setText(
      "drawer-deadline",
      opportunity.application_deadline
        ? new Date(opportunity.application_deadline).toLocaleDateString()
        : "Not listed"
    );
    setText("drawer-description", opportunity.description);
    setText("drawer-logo", (opportunity.organization || "?").trim().slice(0, 2).toUpperCase());
    const matchBadge = byId("drawer-match-badge");
    matchBadge.textContent = opportunity.is_open
      ? "Open opportunity"
      : "Applications closed";
    const responsibilityList = byId("drawer-responsibilities");
    renderTextList(
      responsibilityList,
      [opportunity.responsibilities, opportunity.requirements]
        .filter(Boolean)
        .join("\n"),
      "No additional responsibilities or requirements listed."
    );
    const skillSection = byId("drawer-skills");
    skillSection.previousElementSibling.textContent = "Required skills";
    const skillList = skillSection;
    skillList.replaceChildren();
    (opportunity.required_skills || []).forEach((skill) =>
      skillList.appendChild(createSkillPill(skill))
    );
    if (!opportunity.required_skills || !opportunity.required_skills.length) {
      skillList.appendChild(
        createElement("span", "text-body-sm text-on-surface-variant", "No specific skills listed.")
      );
    }
    const applyButton = byId("drawer-apply-btn");
    applyButton.onclick = () => openApplyModal(opportunity.id);
    applyButton.disabled = !opportunity.is_open || Boolean(opportunity.is_applied);
    applyButton.querySelector("span:last-child").textContent = opportunity.is_applied
      ? "Already applied"
      : opportunity.is_open
        ? "Apply for this opportunity"
        : "Applications closed";
    if (opportunity.is_applied) applyButton.disabled = true;
  }

  function renderEmptyDetail() {
    setText("drawer-title", "Select an opportunity");
    setText("drawer-company", "");
    setText("drawer-meta", "");
    setText("drawer-sublocation", "");
    setText("drawer-stipend", "");
    setText("drawer-contract", "");
    setText("drawer-arrangement", "");
    setText("drawer-deadline", "");
    setText("drawer-description", "Opportunity details will appear here.");
    setText("drawer-match-badge", "");
    renderTextList(
      byId("drawer-responsibilities"),
      "",
      "No responsibilities or requirements listed."
    );
    const skillSection = byId("drawer-skills");
    skillSection.previousElementSibling.textContent = "Required skills";
    skillSection.replaceChildren(
      createElement("span", "text-body-sm text-on-surface-variant", "No skills listed.")
    );
    const applyButton = byId("drawer-apply-btn");
    applyButton.disabled = true;
    applyButton.querySelector("span:last-child").textContent = "Select an opportunity";
  }

  function initializeModal() {
    const content = byId("apply-modal").querySelector(".max-w-xl");
    content.innerHTML = `
      <div class="flex items-start justify-between gap-space-sm pb-space-sm">
        <div>
          <span class="font-label-sm text-label-sm text-secondary uppercase font-bold tracking-wider">Opportunity application</span>
          <h3 class="font-headline-xl text-headline-xl text-on-surface mt-0.5" id="modal-role-title"></h3>
          <p class="font-body-sm text-body-sm text-on-surface-variant" id="modal-org-name"></p>
        </div>
        <button class="w-8 h-8 rounded-full bg-surface-container hover:bg-surface-container-high text-on-surface flex items-center justify-center transition" type="button" id="close-application-modal" aria-label="Close">
          <span class="material-symbols-outlined text-[20px]">close</span>
        </button>
      </div>
      <form id="opportunity-application-form" class="flex flex-col gap-space-md">
        <div class="p-space-sm bg-surface-container-low rounded-xl hidden" id="application-instructions-panel">
          <span class="font-label-md text-label-md text-on-surface font-bold">Application instructions</span>
          <p class="font-body-sm text-body-sm text-on-surface-variant mt-1" id="application-instructions"></p>
        </div>
        <label class="flex flex-col gap-1.5 font-label-md text-label-md text-on-surface font-bold">
          Portfolio (optional)
          <select class="w-full p-space-sm bg-surface-container-low text-on-surface rounded-xl" id="application-portfolio" name="portfolio">
            <option value="">Do not attach a portfolio</option>
          </select>
        </label>
        <label class="flex flex-col gap-1.5 font-label-md text-label-md text-on-surface font-bold">
          Application statement
          <textarea class="w-full p-space-sm bg-surface-container-low text-on-surface font-body-sm text-body-sm rounded-xl border-none focus:outline-none focus:ring-2 focus:ring-secondary" name="statement" rows="5" maxlength="5000" required></textarea>
        </label>
        <label class="flex flex-col gap-1.5 font-label-md text-label-md text-on-surface font-bold">
          Supporting documents (optional, up to 5 files; 10 MB each)
          <input class="w-full p-space-sm bg-surface-container-low text-on-surface rounded-xl" type="file" name="attachments" multiple accept=".pdf,.doc,.docx,.rtf,.txt,.png,.jpg,.jpeg">
        </label>
        <p class="text-xs text-on-surface-variant">Only the selected portfolio and files are shared with the opportunity manager.</p>
        <p class="text-sm text-error" id="application-form-message" role="status" aria-live="polite"></p>
        <div class="flex items-center justify-end gap-2 pt-2">
          <button class="px-5 py-2.5 rounded-full bg-surface-container text-on-surface font-label-md text-label-md hover:bg-surface-container-high transition" type="button" id="cancel-application">Cancel</button>
          <button class="px-6 py-2.5 rounded-full bg-gradient-to-r from-secondary to-secondary-container text-on-secondary font-label-md text-label-md shadow-md hover:shadow-lg transition flex items-center gap-1.5" type="submit">
            <span>Submit application</span>
            <span class="material-symbols-outlined text-[16px]">send</span>
          </button>
        </div>
      </form>`;
    byId("close-application-modal").addEventListener("click", closeApplyModal);
    byId("cancel-application").addEventListener("click", closeApplyModal);
    byId("opportunity-application-form").addEventListener("submit", submitApplication);
    byId("apply-modal").addEventListener("click", (event) => {
      if (event.target === byId("apply-modal")) closeApplyModal();
    });
  }

  async function loadPortfolioOptions() {
    const select = byId("application-portfolio");
    select.replaceChildren(
      new Option("Do not attach a portfolio", "")
    );
    if (!hasAccessToken()) return;
    try {
      const portfolio = await api.get("/portfolio/me/");
      if (portfolio && portfolio.id) {
        select.add(new Option(portfolio.headline || "My portfolio", String(portfolio.id)));
      }
    } catch (error) {
      if (error.status !== 404) {
        byId("application-form-message").textContent =
          "Your portfolio could not be loaded. You can still apply without attaching it.";
      }
    }
  }

  function openApplyModal(id) {
    const opportunity = state.opportunities.find((item) => item.id === Number(id));
    if (!opportunity) return;
    if (!hasAccessToken()) {
      window.alert("Sign in with an active student account to apply.");
      return;
    }
    if (!opportunity.is_open || opportunity.is_applied) return;
    state.selectedOpportunity = opportunity.id;
    setText("modal-role-title", opportunity.title);
    setText("modal-org-name", opportunity.organization);
    setText("application-instructions", opportunity.application_instructions);
    byId("application-instructions-panel").classList.toggle(
      "hidden",
      !opportunity.application_instructions
    );
    byId("application-form-message").textContent = "";
    byId("opportunity-application-form").reset();
    loadPortfolioOptions();
    const modal = byId("apply-modal");
    modal.classList.remove("hidden");
    modal.classList.add("flex");
  }

  function closeApplyModal() {
    const modal = byId("apply-modal");
    modal.classList.add("hidden");
    modal.classList.remove("flex");
  }

  async function submitApplication(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const button = form.querySelector('button[type="submit"]');
    const message = byId("application-form-message");
    const opportunity = state.opportunities.find(
      (item) => item.id === state.selectedOpportunity
    );
    if (!opportunity) {
      message.textContent = "Select an opportunity before applying.";
      return;
    }
    const formData = new FormData(form);
    const portfolio = formData.get("portfolio");
    if (portfolio) formData.set("portfolio", portfolio);
    [...formData.getAll("attachments")].forEach((file) => {
      if (!file || !file.name) formData.delete("attachments");
    });
    button.disabled = true;
    message.textContent = "Submitting your application...";
    try {
      await api.post(`/opportunities/${opportunity.id}/apply/`, formData);
      closeApplyModal();
      window.alert("Your application has been submitted.");
      await Promise.all([loadOpportunities(false), loadApplications()]);
    } catch (error) {
      message.textContent = error.message || "Your application could not be submitted.";
    } finally {
      button.disabled = false;
    }
  }

  const applicationStatuses = [
    ["applied", "Applied", "bg-surface-tint"],
    ["under_review", "Under Review", "bg-amber-500"],
    ["shortlisted", "Shortlisted", "bg-secondary"],
    ["accepted", "Accepted", "bg-emerald-500"],
    ["rejected", "Rejected", "bg-error"],
  ];

  function renderApplications() {
    const section = byId("pipeline-section");
    const title = section.querySelector("h2");
    const count = title.parentElement.querySelector("span");
    count.textContent = String(state.applications.length);
    setText("my-applications-count", String(state.applications.length));
    section.querySelector("p").textContent = hasAccessToken()
      ? "Track the current status of applications you have submitted."
      : "Sign in with an active student account to submit applications and track their status.";
    const grid = section.querySelector(".grid");
    grid.className = "grid grid-cols-1 md:grid-cols-2 xl:grid-cols-5 gap-space-md";
    grid.replaceChildren();
    applicationStatuses.forEach(([key, label, color]) => {
      const applications = state.applications.filter((application) => application.status === key);
      const column = createElement(
        "div",
        "flex flex-col gap-space-sm bg-surface-container-low p-space-md rounded-2xl"
      );
      const heading = createElement("div", "flex items-center justify-between");
      const titleWrap = createElement("div", "flex items-center gap-2");
      titleWrap.appendChild(createElement("span", `w-2.5 h-2.5 rounded-full ${color}`));
      titleWrap.appendChild(
        createElement("span", "font-label-md text-label-md text-on-surface font-bold", label)
      );
      heading.append(titleWrap, createElement("span", "px-2 py-0.5 rounded-full bg-surface-container-highest text-on-surface-variant font-label-sm text-label-sm font-semibold", String(applications.length)));
      column.appendChild(heading);
      if (!applications.length) {
        column.appendChild(
          createElement("p", "text-sm text-on-surface-variant", "No applications")
        );
      }
      applications.forEach((application) => {
        const card = createElement(
          "article",
          "bg-surface-container-lowest p-space-md rounded-xl shadow-sm flex flex-col gap-2"
        );
        card.appendChild(
          createElement(
            "h4",
            "font-headline-sm text-headline-sm text-on-surface",
            application.opportunity.title
          )
        );
        card.appendChild(
          createElement(
            "span",
            "text-body-sm font-body-sm text-secondary font-medium",
            application.opportunity.organization
          )
        );
        card.appendChild(
          createElement(
            "span",
            "text-xs text-on-surface-variant",
            `Submitted ${new Date(application.submitted_at).toLocaleDateString()}`
          )
        );
        (application.attachments || []).forEach((attachment) => {
          if (attachment.download_url) {
            const link = createElement(
              "a",
              "text-sm text-secondary underline",
              `Download ${attachment.file_name}`
            );
            link.href = attachment.download_url;
            link.rel = "noopener noreferrer";
            link.target = "_blank";
            card.appendChild(link);
          }
        });
        column.appendChild(card);
      });
      grid.appendChild(column);
    });
  }

  async function loadApplications() {
    if (!hasAccessToken()) {
      state.applications = [];
      renderApplications();
      return;
    }
    try {
      state.applications = listFromResponse(
        await api.get("/opportunities/my-applications/")
      );
      renderApplications();
    } catch (error) {
      state.applications = [];
      renderApplications();
      if (error.status !== 401 && error.status !== 403) {
        console.error("Could not load applications.", error);
      }
    }
  }

  function renderLoadError(message) {
    byId("opportunity-list").replaceChildren(
      createElement("p", "p-space-md text-body-sm text-error", message)
    );
  }

  async function initialize() {
    initializeModal();
    const skillMatchBanner = byId("skillmatch-banner");
    if (skillMatchBanner) skillMatchBanner.remove();
    const quickFilters = byId("high-match-filter");
    if (quickFilters) quickFilters.parentElement.remove();
    renderApplications();

    byId("opportunity-search").addEventListener("input", debounce(() => {
      loadOpportunities(false);
    }, 250));
    [
      "opportunity-location-filter",
      "opportunity-type-filter",
      "opportunity-arrangement-filter",
      "opportunity-deadline-filter",
      "opportunity-skill-filter",
    ].forEach((id) =>
      byId(id).addEventListener("change", () => loadOpportunities(false))
    );

    if (!api) {
      renderLoadError("The Skillshub API client is unavailable.");
      renderEmptyDetail();
      setReady();
      return;
    }
    try {
      state.categories = listFromResponse(
        await api.get("/opportunities/categories/")
      );
      renderCategories();
      await loadOpportunities(false);
      await loadApplications();
    } catch (error) {
      renderLoadError(`Could not load opportunity categories. ${error.message}`);
      renderEmptyDetail();
      setReady();
    }
  }

  function debounce(callback, delay) {
    let timeout;
    return function () {
      window.clearTimeout(timeout);
      timeout = window.setTimeout(callback, delay);
    };
  }

  window.selectOpportunity = selectOpportunity;
  window.populateRightDrawer = selectOpportunity;
  window.openApplyModal = openApplyModal;
  window.closeApplyModal = closeApplyModal;
  window.submitApplication = submitApplication;
  initialize();
})();
