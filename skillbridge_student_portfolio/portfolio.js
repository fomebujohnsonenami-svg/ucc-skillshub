(function () {
  const api = window.skillsHubApi;
  const proficiencyLevels = ["beginner", "intermediate", "advanced", "expert"];
  let portfolio = null;
  let activeProjectFilter = "all";

  function element(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function safeLink(value) {
    if (!value) return null;
    try {
      const url = new URL(value, window.location.href);
      return ["http:", "https:"].includes(url.protocol) ? url.href : null;
    } catch (error) {
      return null;
    }
  }

  function setText(id, value) {
    const node = document.getElementById(id);
    if (node) node.textContent = value || "";
  }

  function reveal(node) {
    if (node) node.removeAttribute("data-portfolio-loading");
  }

  function empty(id, message) {
    const node = document.getElementById(id);
    if (node) {
      reveal(node);
      node.replaceChildren(
        element("p", "py-space-md text-body-sm text-on-surface-variant", message)
      );
    }
  }

  function closePortfolioModal() {
    document.getElementById("portfolio-modal").classList.add("hidden");
  }

  function showEditor(title, description, fields, onSubmit) {
    const modal = document.getElementById("portfolio-modal");
    const slot = document.getElementById("modal-content-slot");
    const heading = element(
      "h3",
      "mb-1 font-headline-md text-headline-md font-bold text-on-surface",
      title
    );
    const intro = element(
      "p",
      "mb-space-md font-body-sm text-body-sm text-on-surface-variant",
      description
    );
    const form = element("form", "flex flex-col gap-space-sm");
    const error = element("p", "text-sm text-error");
    error.setAttribute("role", "alert");
    const controls = new Map();

    fields.forEach((field) => {
      if (field.type === "checkbox") {
        const label = element(
          "label",
          "flex items-center gap-2 text-body-sm text-on-surface"
        );
        const input = document.createElement("input");
        input.type = "checkbox";
        input.name = field.name;
        input.checked = Boolean(field.value);
        input.className = "rounded border-outline text-secondary focus:ring-secondary";
        label.append(input, document.createTextNode(field.label));
        form.append(label);
        controls.set(field.name, input);
        return;
      }

      const wrapper = element("div", "flex flex-col gap-1");
      const label = element(
        "label",
        "font-label-sm text-label-sm font-semibold text-on-surface",
        field.label
      );
      const input =
        field.type === "textarea"
          ? document.createElement("textarea")
          : field.type === "select"
            ? document.createElement("select")
            : document.createElement("input");
      input.name = field.name;
      input.required = Boolean(field.required);
      input.className =
        "w-full rounded-xl border-none bg-surface-container-low px-space-md py-2 text-body-sm text-on-surface focus:ring-2 focus:ring-secondary";
      if (field.type === "textarea") {
        input.rows = field.rows || 4;
      } else if (field.type === "select") {
        field.options.forEach((option) => {
          const item = element("option", "", option.label);
          item.value = option.value;
          input.append(item);
        });
      } else {
        input.type = field.type || "text";
        if (field.type === "url") input.placeholder = "https://";
      }
      if (field.value !== undefined) {
        if (field.type === "checkbox") input.checked = Boolean(field.value);
        else input.value = field.value;
      }
      label.htmlFor = `portfolio-field-${field.name}`;
      input.id = label.htmlFor;
      wrapper.append(label, input);
      form.append(wrapper);
      controls.set(field.name, input);
    });

    const submit = element(
      "button",
      "mt-space-sm w-full rounded-full bg-secondary py-2.5 font-semibold text-on-secondary hover:bg-secondary-container transition",
      "Save"
    );
    submit.type = "submit";
    form.append(error, submit);
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      submit.disabled = true;
      submit.textContent = "Saving…";
      error.textContent = "";
      const values = {};
      controls.forEach((input, name) => {
        values[name] =
          input.type === "checkbox" ? input.checked : input.value.trim();
      });
      try {
        await onSubmit(values);
        closePortfolioModal();
      } catch (requestError) {
        error.textContent = requestError.message || "Could not save your changes.";
        submit.disabled = false;
        submit.textContent = "Save";
      }
    });
    slot.replaceChildren(heading, intro, form);
    modal.classList.remove("hidden");
  }

  function actionButton(label, callback) {
    const button = element(
      "button",
      "rounded-full px-space-sm py-1 text-label-sm text-secondary hover:bg-surface-container",
      label
    );
    button.type = "button";
    button.addEventListener("click", callback);
    return button;
  }

  async function deleteItem(path, itemName) {
    if (!window.confirm(`Remove this ${itemName} from your portfolio?`)) return;
    await api.delete(path);
    await loadOwnerPortfolio();
  }

  function renderSocialLinks(links, owner) {
    const targets = [
      document.getElementById("portfolio-social-links"),
      document.getElementById("public-social-links"),
      document.getElementById("public-profile-links"),
    ].filter(Boolean);
    const uniqueLinks = new Map();
    (links || []).forEach((link) => {
      const href = safeLink(link.url);
      if (href) uniqueLinks.set(href, { ...link, url: href });
    });
    [
      ["GitHub", portfolio && portfolio.github_url],
      ["LinkedIn", portfolio && portfolio.linkedin_url],
    ].forEach(([label, value]) => {
      const href = safeLink(value);
      if (href && !uniqueLinks.has(href)) {
        uniqueLinks.set(href, { label, url: href });
      }
    });

    targets.forEach((target) => {
      target.replaceChildren();
      uniqueLinks.forEach((link, href) => {
        const group = element("div", "inline-flex items-center gap-1");
        const anchor = element(
          "a",
          "inline-flex items-center gap-1.5 rounded-full bg-surface-container px-space-md py-1.5 font-label-sm text-label-sm text-on-surface hover:bg-surface-variant",
          link.label || link.platform || "Website"
        );
        anchor.href = href;
        anchor.target = "_blank";
        anchor.rel = "noopener noreferrer";
        group.append(anchor);
        if (owner && target.id === "portfolio-social-links" && link.id) {
          group.append(
            actionButton("Edit", () => editSocialLink(link)),
            actionButton("Remove", () =>
              deleteItem(`/portfolio/social-links/${link.id}/`, "link")
            )
          );
        }
        target.append(group);
      });
      if (owner && target.id === "portfolio-social-links") {
        target.append(actionButton("Add link", () => editSocialLink(null)));
      }
      reveal(target);
      if (!target.childElementCount && !owner) target.classList.add("hidden");
      else target.classList.remove("hidden");
    });
  }

  function renderSkills(skills, owner) {
    const editorGrid = document.getElementById("portfolio-skills-grid");
    const publicGrid = document.getElementById("public-skills");
    reveal(editorGrid);
    reveal(publicGrid);
    editorGrid.replaceChildren();
    publicGrid.replaceChildren();
    const percentages = { beginner: 25, intermediate: 50, advanced: 75, expert: 100 };
    (skills || []).forEach((skill) => {
      const level = proficiencyLevels.includes(skill.proficiency)
        ? skill.proficiency
        : "intermediate";
      const editorCard = element(
        "article",
        "rounded-xl bg-surface-container-low p-space-md hover:bg-surface-container transition"
      );
      const top = element("div", "mb-2 flex items-start justify-between gap-2");
      const label = element("div");
      const name = element(
        "h4",
        "font-headline-sm text-headline-sm font-bold text-on-surface",
        skill.name
      );
      const category = element(
        "p",
        "text-label-sm text-label-sm text-outline",
        skill.category || "Skill"
      );
      label.append(name, category);
      top.append(label);
      if (owner) {
        const actions = element("div", "flex items-center gap-1");
        actions.append(
          actionButton("Edit", () => editSkill(skill)),
          actionButton("Remove", () =>
            deleteItem(`/portfolio/skills/${skill.id}/`, "skill")
          )
        );
        top.append(actions);
      }
      const badge = element(
        "span",
        "shrink-0 rounded-full bg-secondary-fixed px-space-sm py-0.5 font-label-sm text-label-sm font-semibold text-on-secondary-fixed-variant",
        level[0].toUpperCase() + level.slice(1)
      );
      editorCard.append(top, badge);
      const track = element(
        "div",
        "mt-space-sm h-2 w-full overflow-hidden rounded-full bg-surface-container-high"
      );
      const fill = element("div", "h-full rounded-full bg-secondary");
      fill.style.width = `${percentages[level]}%`;
      track.append(fill);
      editorCard.append(track);
      editorGrid.append(editorCard);

      const publicSkill = element(
        "span",
        "rounded-full bg-surface-container px-space-md py-2 font-label-sm text-label-sm text-on-surface",
        skill.name
      );
      publicGrid.append(publicSkill);
    });
    if (!skills || !skills.length) {
      empty("portfolio-skills-grid", "Add skills to show them here.");
      empty("public-skills", "No skills have been added.");
    }
  }

  function createProjectCard(project, owner) {
    const card = element(
      "article",
      "project-card group flex flex-col gap-space-md rounded-2xl bg-surface-container-low p-space-lg hover:bg-surface-container md:flex-row"
    );
    card.dataset.category = (project.category || "").toLowerCase();
    card.classList.add(project.category ? "has-category" : "no-category");
    const imageUrl = safeLink(project.image_url);
    if (imageUrl) {
      const image = element(
        "img",
        "h-40 w-full rounded-xl object-cover md:w-56"
      );
      image.src = imageUrl;
      image.alt = `Image for ${project.title}`;
      image.loading = "lazy";
      image.referrerPolicy = "no-referrer";
      card.append(image);
    }
    const content = element("div", "min-w-0 flex-1");
    const header = element("div", "mb-1 flex items-start justify-between gap-2");
    header.append(
      element(
        "h4",
        "font-headline-sm text-headline-sm font-bold text-on-surface",
        project.title
      )
    );
    if (project.category) {
      header.append(
        element(
          "span",
          "shrink-0 rounded-full bg-surface-container-highest px-space-sm py-0.5 font-label-sm text-label-sm text-on-surface",
          project.category
        )
      );
    }
    content.append(header);
    if (project.role) {
      content.append(
        element(
          "p",
          "mb-1.5 font-body-sm text-body-sm font-medium text-secondary",
          project.role
        )
      );
    }
    if (project.description) {
      content.append(
        element(
          "p",
          "mb-space-sm line-clamp-3 font-body-sm text-body-sm text-on-surface-variant",
          project.description
        )
      );
    }
    const tags = element("div", "mb-space-md flex flex-wrap gap-1.5");
    (project.skills || []).forEach((skill) =>
      tags.append(
        element(
          "span",
          "rounded-md bg-surface-container-highest px-space-sm py-0.5 font-label-sm text-label-sm text-on-surface",
          skill
        )
      )
    );
    content.append(tags);
    const links = element("div", "flex flex-wrap items-center gap-space-sm");
    [
      ["Repository", project.repository_url],
      ["Live demo", project.demo_url],
    ].forEach(([label, value]) => {
      const href = safeLink(value);
      if (!href) return;
      const link = element(
        "a",
        "rounded-full bg-surface-container-lowest px-space-md py-1.5 font-label-sm text-label-sm text-secondary hover:bg-surface-variant",
        label
      );
      link.href = href;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      links.append(link);
    });
    if (owner) {
      links.append(
        actionButton("Edit", () => editProject(project)),
        actionButton("Remove", () =>
          deleteItem(`/portfolio/projects/${project.id}/`, "project")
        )
      );
      const visibility = element(
        "span",
        "ml-auto font-label-sm text-label-sm text-outline",
        project.is_public ? "Public project" : "Private project"
      );
      links.append(visibility);
    }
    content.append(links);
    card.append(content);
    return card;
  }

  function renderProjects(projects, owner) {
    const editorGrid = document.getElementById("portfolio-projects-grid");
    const publicGrid = document.getElementById("public-projects");
    reveal(editorGrid);
    reveal(publicGrid);
    editorGrid.replaceChildren();
    publicGrid.replaceChildren();
    (projects || []).forEach((project) => {
      editorGrid.append(createProjectCard(project, owner));
      if (project.is_public !== false) {
        publicGrid.append(createProjectCard(project, false));
      }
    });
    if (!projects || !projects.length) {
      empty("portfolio-projects-grid", "Add projects to showcase your work.");
      empty("public-projects", "No projects have been shared.");
    } else if (!publicGrid.childElementCount) {
      empty("public-projects", "No projects have been shared.");
    }
    setText("portfolio-summary-project-count", String((projects || []).length));
    window.filterProjects(activeProjectFilter);
  }

  function createCertificateCard(entry, owner) {
    const certificate = entry.certificate_details || entry;
    const card = element(
      "article",
      "flex flex-col justify-between rounded-xl bg-surface-container-low p-space-md"
    );
    const details = element("div");
    details.append(
      element(
        "h4",
        "mb-1 font-headline-sm text-headline-sm font-bold text-on-surface",
        certificate.learning_item || "Earned certificate"
      ),
      element(
        "p",
        "mb-2 font-body-sm text-body-sm text-on-surface-variant",
        certificate.issuing_organization || ""
      ),
      element(
        "p",
        "font-label-sm text-label-sm text-outline",
        certificate.issue_date
          ? `Issued ${certificate.issue_date}`
          : "Issue date unavailable"
      )
    );
    const actions = element("div", "mt-space-md flex items-center justify-between");
    const verificationUrl = safeLink(certificate.verification_url);
    if (verificationUrl) {
      const verify = element(
        "a",
        "font-label-sm text-label-sm font-semibold text-secondary hover:underline",
        "Verify certificate"
      );
      verify.href = verificationUrl;
      verify.target = "_blank";
      verify.rel = "noopener noreferrer";
      actions.append(verify);
    }
    if (owner) {
      actions.append(
        actionButton("Remove", () =>
          deleteItem(`/portfolio/certificates/${entry.id}/`, "certificate")
        )
      );
    }
    card.append(details, actions);
    return card;
  }

  function renderCertificates(certificates, owner) {
    const editorGrid = document.getElementById("portfolio-certificates-grid");
    const publicGrid = document.getElementById("public-certificates");
    reveal(editorGrid);
    reveal(publicGrid);
    editorGrid.replaceChildren();
    publicGrid.replaceChildren();
    (certificates || []).forEach((entry) => {
      editorGrid.append(createCertificateCard(entry, owner));
      publicGrid.append(createCertificateCard(entry, false));
    });
    if (!certificates || !certificates.length) {
      empty("portfolio-certificates-grid", "No certificates are linked yet.");
      empty("public-certificates", "No certificates have been shared.");
    }
    setText(
      "portfolio-summary-certificate-count",
      String((certificates || []).length)
    );
  }

  function portfolioLink() {
    if (!portfolio || !portfolio.is_public) return "";
    const url = new URL(window.location.href);
    url.search = "";
    url.hash = "";
    url.searchParams.set("slug", portfolio.slug);
    return url.href;
  }

  function renderVisibility() {
    const isPublic = Boolean(portfolio && portfolio.is_public);
    const label = isPublic ? "Public portfolio" : "Private portfolio";
    setText("portfolio-visibility-label", label);
    setText("portfolio-summary-visibility", isPublic ? "Public" : "Private");
    const url = portfolioLink();
    const input = document.getElementById("portfolio-share-url");
    input.value = url;
    input.placeholder = isPublic ? "" : "Enable public visibility to create a share link";
    const copyButtons = document.querySelectorAll(
      '#portfolio-editor-actions button[onclick="copyShareLink()"], #portfolio-share-url + button'
    );
    copyButtons.forEach((button) => {
      button.disabled = !url;
      button.classList.toggle("opacity-50", !url);
    });
    const toggle = document.getElementById("portfolio-visibility-toggle");
    toggle.textContent = isPublic
      ? "Make portfolio private"
      : "Make portfolio public";
    toggle.onclick = async () => {
      toggle.disabled = true;
      try {
        portfolio = await api.patch("/portfolio/me/", {
          is_public: !portfolio.is_public,
        });
        renderOwner(portfolio);
        window.showToast(
          portfolio.is_public ? "Portfolio is now public." : "Portfolio is now private."
        );
      } catch (error) {
        window.showToast(error.message || "Could not update portfolio visibility.");
      } finally {
        toggle.disabled = false;
      }
    };
  }

  function renderProfile(data) {
    setText("portfolio-full-name", data.full_name);
    setText("portfolio-headline", data.headline);
    setText("portfolio-biography", data.biography);
    setText("portfolio-academic-inline", data.academic_programme);
    setText("portfolio-academic-programme", data.academic_programme);
    setText("portfolio-academic-programme-detail", data.academic_programme);
    setText("portfolio-location-inline", data.location);
    setText("portfolio-location", data.location);
    const photo = safeLink(data.profile_photo_url);
    document.querySelectorAll("#portfolio-main-grid img[data-profile-photo], #public-preview-container img[data-profile-photo]").forEach((image) => {
      if (photo) {
        image.src = photo;
        image.alt = `Profile photo for ${data.full_name}`;
      } else {
        image.removeAttribute("src");
        image.alt = "";
      }
    });
    document.querySelectorAll("[data-profile-name]").forEach((node) => {
      node.textContent = data.full_name || "";
    });
  }

  function updateCompleteness(data) {
    const checks = {
      profile: Boolean(
        data.headline &&
          data.biography &&
          data.academic_programme &&
          data.profile_photo_url
      ),
      skills: (data.skills || []).length > 0,
      projects: (data.projects || []).length > 0,
    };
    const percent = Math.round(
      (Object.values(checks).filter(Boolean).length / Object.keys(checks).length) *
        100
    );
    Object.entries(checks).forEach(([name, complete]) => {
      const row = document.querySelector(`[data-completeness-check="${name}"]`);
      if (!row) return;
      const icon = row.querySelector(".material-symbols-outlined");
      row.classList.toggle("text-on-surface", complete);
      row.classList.toggle("text-on-surface-variant", !complete);
      icon.textContent = complete ? "check_circle" : "radio_button_unchecked";
      icon.classList.toggle("text-secondary", complete);
      icon.classList.toggle("text-outline", !complete);
    });
    setText("portfolio-completeness", `${percent}% complete`);
    document.getElementById("portfolio-completeness-bar").style.width = `${percent}%`;
    setText(
      "portfolio-updated",
      data.updated_at ? new Date(data.updated_at).toLocaleDateString() : ""
    );
    setText(
      "portfolio-updated-banner",
      data.updated_at
        ? `Updated ${new Date(data.updated_at).toLocaleDateString()}`
        : ""
    );
    setText("portfolio-summary-skill-count", String((data.skills || []).length));
  }

  function renderOwner(data) {
    portfolio = data;
    renderProfile(data);
    renderSkills(data.skills, true);
    renderProjects(data.projects, true);
    renderCertificates(data.certificates, true);
    renderSocialLinks(data.social_links, true);
    renderVisibility();
    updateCompleteness(data);
  }

  async function loadOwnerPortfolio() {
    try {
      const data = await api.get("/portfolio/me/");
      renderOwner(data);
    } catch (error) {
      setText(
        "portfolio-completeness",
        error.status === 401
          ? "Sign in to manage your portfolio"
          : "Portfolio could not be loaded"
      );
      window.showToast(error.message || "Could not load your portfolio.");
    }
  }

  function renderPublic(data, publicPage) {
    if (publicPage) {
      portfolio = data;
      document.body.classList.add("public-portfolio");
      document.documentElement.classList.remove("public-portfolio-loading");
      document.getElementById("portfolio-health-banner").classList.add("hidden");
      document.getElementById("portfolio-editor-actions").classList.add("hidden");
      document.getElementById("portfolio-main-grid").classList.add("hidden");
    } else {
      document.getElementById("portfolio-main-grid").classList.add("hidden");
    }
    const preview = document.getElementById("public-preview-container");
    preview.classList.remove("hidden");
    preview.classList.add("flex");
    setText("public-full-name", data.full_name);
    setText("public-headline", data.headline);
    renderPublicAcademicInfo(data);
    setText("public-biography", data.biography);
    document.querySelectorAll("#public-preview-container img[data-profile-photo]").forEach((image) => {
      const photo = safeLink(data.profile_photo_url);
      if (photo) {
        image.src = photo;
        image.alt = `Profile photo for ${data.full_name}`;
      } else {
        image.removeAttribute("src");
        image.alt = "";
        image.classList.add("hidden");
      }
    });
    document.querySelectorAll("[data-profile-name]").forEach((node) => {
      node.textContent = data.full_name || "";
    });
    renderSkills(data.skills, false);
    renderProjects(data.projects, false);
    renderCertificates(data.certificates, false);
    renderSocialLinks(data.social_links, false);
    document.title = `${data.full_name || "Student"} | Portfolio`;
  }

  function showNotFound(error) {
    document.body.classList.add("public-portfolio");
    document.documentElement.classList.remove("public-portfolio-loading");
    const preview = document.getElementById("public-preview-container");
    preview.classList.remove("hidden");
    preview.classList.add("flex");
    const message = publicSlugMessage(error);
    const status = element(
      "div",
      "mx-auto max-w-xl py-space-2xl text-center",
      message
    );
    status.setAttribute("role", "status");
    preview.replaceChildren(
      status
    );
    document.getElementById("portfolio-main-grid").classList.add("hidden");
    document.getElementById("portfolio-health-banner").classList.add("hidden");
    document.getElementById("portfolio-editor-actions").classList.add("hidden");
    document.title = "Portfolio unavailable";
  }

  function publicSlugMessage(error) {
    if (!error || error.status === 404 || error.status === 403) {
      return "This portfolio is unavailable or private.";
    }
    return "This portfolio could not be loaded. Please try again later.";
  }

  function renderPublicAcademicInfo(data) {
    const info = [data.academic_programme, data.location].filter(Boolean).join(" • ");
    setText("public-academic-info", info);
  }

  function editPortfolioDetails() {
    showEditor(
      "Edit portfolio",
      "Update the information shown on your portfolio.",
      [
        { name: "headline", label: "Professional headline", value: portfolio.headline },
        { name: "biography", label: "Biography", type: "textarea", value: portfolio.biography },
        { name: "academic_programme", label: "Academic programme", value: portfolio.academic_programme },
        { name: "location", label: "Location", value: portfolio.location },
        { name: "github_url", label: "GitHub URL", type: "url", value: portfolio.github_url },
        { name: "linkedin_url", label: "LinkedIn URL", type: "url", value: portfolio.linkedin_url },
      ],
      async (values) => {
        portfolio = await api.patch("/portfolio/me/", values);
        renderOwner(portfolio);
      }
    );
  }

  function editSkill(skill) {
    showEditor(
      skill ? "Edit skill" : "Add skill",
      "Choose a proficiency level that reflects your experience.",
      [
        { name: "name", label: "Skill", required: true, value: skill ? skill.name : "" },
        {
          name: "proficiency",
          label: "Proficiency",
          type: "select",
          value: skill ? skill.proficiency : "intermediate",
          options: proficiencyLevels.map((value) => ({
            value,
            label: value[0].toUpperCase() + value.slice(1),
          })),
        },
        { name: "category", label: "Category", value: skill ? skill.category : "" },
      ],
      async (values) => {
        await (skill
          ? api.patch(`/portfolio/skills/${skill.id}/`, values)
          : api.post("/portfolio/skills/", values));
        await loadOwnerPortfolio();
      }
    );
  }

  function editProject(project) {
    showEditor(
      project ? "Edit project" : "Add project",
      "Add a project and optional repository or live demo links.",
      [
        { name: "title", label: "Project title", required: true, value: project ? project.title : "" },
        { name: "description", label: "Description", type: "textarea", required: true, value: project ? project.description : "" },
        { name: "role", label: "Your role", value: project ? project.role : "" },
        { name: "category", label: "Category", value: project ? project.category : "" },
        { name: "skills", label: "Skills (comma separated)", value: project ? (project.skills || []).join(", ") : "" },
        { name: "repository_url", label: "Repository URL", type: "url", value: project ? project.repository_url : "" },
        { name: "demo_url", label: "Live demonstration URL", type: "url", value: project ? project.demo_url : "" },
        { name: "image_url", label: "Project image URL", type: "url", value: project ? project.image_url : "" },
        { name: "is_public", label: "Show this project publicly", type: "checkbox", value: project ? project.is_public : true },
      ],
      async (values) => {
        values.skills = values.skills
          ? values.skills.split(",").map((skill) => skill.trim()).filter(Boolean)
          : [];
        await (project
          ? api.patch(`/portfolio/projects/${project.id}/`, values)
          : api.post("/portfolio/projects/", values));
        await loadOwnerPortfolio();
      }
    );
  }

  function editSocialLink(link) {
    showEditor(
      link ? "Edit professional link" : "Add professional link",
      "Add a link visitors can use to learn more about your work.",
      [
        {
          name: "platform",
          label: "Type",
          type: "select",
          value: link ? link.platform : "website",
          options: [
            { value: "website", label: "Website" },
            { value: "other", label: "Other" },
          ],
        },
        { name: "label", label: "Link label", required: true, value: link ? link.label : "" },
        { name: "url", label: "URL", type: "url", required: true, value: link ? link.url : "" },
      ],
      async (values) => {
        await (link
          ? api.patch(`/portfolio/social-links/${link.id}/`, values)
          : api.post("/portfolio/social-links/", values));
        await loadOwnerPortfolio();
      }
    );
  }

  function addCertificate() {
    const available = portfolio.available_certificates || [];
    if (!available.length) {
      window.showToast("No eligible certificates are available to showcase.");
      return;
    }
    showEditor(
      "Showcase a certificate",
      "Select an earned, active certificate from your account.",
      [
        {
          name: "certificate",
          label: "Earned certificate",
          type: "select",
          required: true,
          options: available.map((certificate) => ({
            value: String(certificate.id),
            label: `${certificate.learning_item} (${certificate.issue_date})`,
          })),
        },
      ],
      async (values) => {
        await api.post("/portfolio/certificates/", {
          certificate: Number(values.certificate),
        });
        await loadOwnerPortfolio();
      }
    );
  }

  window.openPortfolioEditor = function (type) {
    if (!portfolio) return;
    if (type === "profile") return editPortfolioDetails();
    if (type === "skill") return editSkill(null);
    if (type === "project") return editProject(null);
    if (type === "certificate") return addCertificate();
    if (type === "social") return editSocialLink(null);
  };

  window.switchViewMode = function (mode) {
    if (!portfolio) return;
    if (mode === "public") {
      const data = {
        ...portfolio,
        projects: (portfolio.projects || []).filter(
          (project) => project.is_public !== false
        ),
      };
      renderPublic(data);
      return;
    }
    document.body.classList.remove("public-portfolio");
    document.getElementById("public-preview-container").classList.add("hidden");
    document.getElementById("public-preview-container").classList.remove("flex");
    document.getElementById("portfolio-main-grid").classList.remove("hidden");
    document.getElementById("portfolio-health-banner").classList.remove("hidden");
    document.getElementById("portfolio-editor-actions").classList.remove("hidden");
    document.documentElement.classList.remove("public-portfolio-loading");
    renderOwner(portfolio);
  };

  window.filterProjects = function (category) {
    activeProjectFilter = category;
    ["all", "swe", "bi"].forEach((name) => {
      const tab = document.getElementById(`tab-${name}`);
      if (!tab) return;
      tab.className =
        name === category
          ? "px-space-md py-1 rounded-full bg-surface-container-lowest text-on-surface shadow-xs transition"
          : "px-space-md py-1 rounded-full text-on-surface-variant hover:text-on-surface transition";
    });
    document.querySelectorAll("#portfolio-projects-grid .project-card").forEach((card) => {
      const categoryText = card.dataset.category || "";
      const visible =
        category === "all" ||
        (category === "swe" && /software|web|engineering|application/.test(categoryText)) ||
        (category === "bi" && /data|analytics|business intelligence/.test(categoryText));
      card.classList.toggle("hidden", !visible);
      card.classList.toggle("flex", visible);
    });
  };

  window.copyShareLink = async function () {
    const value = portfolioLink();
    if (!value) {
      window.showToast("Make your portfolio public before sharing a link.");
      return;
    }
    try {
      await navigator.clipboard.writeText(value);
      window.showToast("Public portfolio link copied.");
    } catch (error) {
      const input = document.getElementById("portfolio-share-url");
      input.focus();
      input.select();
      window.showToast("Copy was blocked. Select the link and copy it manually.");
    }
  };

  [
    "portfolio-social-links",
    "portfolio-skills-grid",
    "portfolio-projects-grid",
    "portfolio-certificates-grid",
    "public-social-links",
    "public-profile-links",
    "public-skills",
    "public-projects",
    "public-certificates",
  ].forEach((id) => {
    const container = document.getElementById(id);
    if (container) container.replaceChildren();
  });
  const publicSlug = new URLSearchParams(window.location.search).get("slug");
  window.addEventListener("skillsHubProfileUpdated", (event) => {
    if (!portfolio || publicSlug || !event.detail) return;
    portfolio.full_name = event.detail.full_name || portfolio.full_name;
    portfolio.profile_photo_url =
      event.detail.profile_photo_url || portfolio.profile_photo_url;
    renderProfile(portfolio);
  });
  if (publicSlug) {
    window.skillsHubProfile.ready.then(() =>
      api
        .get(`/portfolio/public/${encodeURIComponent(publicSlug)}/`)
        .then((data) => renderPublic(data, true))
        .catch((error) => {
          console.error("Could not load the public portfolio.", error);
          showNotFound(error);
        })
    );
  } else {
    loadOwnerPortfolio();
  }
})();
