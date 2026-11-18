(() => {
  const params = new URLSearchParams(window.location.search);
  const courseId = params.get("course");
  const lessonParam = params.get("lesson");
  const overviewRoot = document.getElementById("view-overview");
  const notice = document.getElementById("coursePageNotice");
  const accessButton = document.getElementById("courseAccessButton");
  const accessLabel = document.getElementById("courseAccessButtonLabel");
  const classroomTab = document.getElementById("tab-btn-classroom");
  const modulesContainer = document.querySelector("#curriculum .space-y-4");
  const objectivesContainer = document.getElementById("courseObjectives");
  const prerequisitesContainer = document.getElementById("coursePrerequisites");
  const reviewsSection = document.getElementById("courseReviewsSection");
  const classroomContent = document.getElementById("apiLessonContent");
  const markCompleteButton = document.getElementById("btn-mark-complete");
  let course;
  let enrollment;
  let currentLesson;
  let reviewSubmitted = false;
  Array.from(overviewRoot.children).forEach((child) => {
    if (child !== notice) child.style.display = "none";
  });
  document.getElementById("legacyClassroomContent").style.display = "none";
  showNotice("Loading course details…", false);

  function showNotice(message, isError) {
    notice.textContent = message;
    notice.classList.remove("hidden");
    notice.classList.toggle("text-rose-700", Boolean(isError));
    notice.classList.toggle("text-on-surface-variant", !isError);
  }

  function hasAccessToken() {
    return Boolean(
      sessionStorage.getItem("skillshubAccessToken") ||
        localStorage.getItem("skillshubAccessToken"),
    );
  }

  function formatDuration(minutes) {
    if (minutes < 60) return `${minutes} minutes`;
    const hours = minutes / 60;
    return `${Number.isInteger(hours) ? hours : hours.toFixed(1)} hours`;
  }

  function setText(selector, value) {
    const element = document.querySelector(selector);
    if (element) element.textContent = value;
  }

  function renderCourseOverview() {
    const overview = document.getElementById("view-overview");
    const title = overview.querySelector("h1");
    const summary = overview.querySelector(".relative.z-10.grid p.font-body-md");
    title.textContent = course.title;
    summary.textContent = course.description;
    document.title = `${course.title} | UCC SKILLSHUB`;
    document.getElementById("courseCertificateBadge").textContent =
      course.certificate_eligible
      ? "UCC SKILLSHUB Certificate Eligible"
      : "UCC SKILLSHUB Course";
    setText("#courseDifficulty", course.difficulty);
    setText(
      "#courseAverageRating",
      Number(course.average_rating)
        ? Number(course.average_rating).toFixed(1)
        : "New",
    );
    setText("#courseReviewCount", ` (${course.review_count} reviews)`);
    setText("#courseDuration", formatDuration(
      course.estimated_duration_minutes,
    ));
    setText("#courseLessonCount", `${course.lesson_count} Lessons`);
    setText("#courseEnrollmentCount", `${course.enrollment_count} Enrolled`);
    setText("#courseCertificateStatus", course.certificate_eligible
      ? "Certificate Eligible"
      : "No Certificate");

    const previewImage = document.getElementById("courseThumbnail");
    if (course.thumbnail_url) {
      previewImage.src = course.thumbnail_url;
      previewImage.alt = `${course.title} course thumbnail`;
      previewImage.classList.remove("hidden");
    } else {
      previewImage.classList.add("hidden");
    }
    const instructor = course.instructors.map((item) => item.full_name).join(", ");
    setText("#courseInstructorNames", instructor || "UCC SKILLSHUB");

    const objectives = Array.isArray(course.learning_objectives)
      ? course.learning_objectives
      : [];
    objectivesContainer.replaceChildren();
    if (objectives.length) {
      objectives.forEach((objective) => {
        const item = document.createElement("div");
        item.className =
          "flex items-start gap-3 p-3.5 rounded-xl bg-surface-container-low";
        const icon = document.createElement("span");
        icon.className =
          "material-symbols-outlined text-secondary text-[22px] shrink-0";
        icon.textContent = "check_circle";
        const text = document.createElement("p");
        text.className = "font-body-sm text-body-sm text-on-surface-variant";
        text.textContent = objective;
        item.append(icon, text);
        objectivesContainer.append(item);
      });
    } else {
      objectivesContainer.closest(".p-6.md\\:p-8").style.display = "none";
    }

    const prerequisites = Array.isArray(course.prerequisites)
      ? course.prerequisites
      : [];
    prerequisitesContainer.replaceChildren();
    prerequisites.forEach((prerequisite) => {
      const item = document.createElement("li");
      item.textContent = prerequisite;
      prerequisitesContainer.append(item);
    });
    document
      .getElementById("coursePrerequisitesCard")
      .style.display = prerequisites.length ? "" : "none";

    document.getElementById("courseInstructorCard").style.display = "none";
    document.getElementById("courseSidebar").style.display = "none";
    document
      .getElementById("courseMainColumn")
      .classList.replace("lg:col-span-8", "lg:col-span-12");
    document.getElementById("downloadSyllabusLink").classList.add("hidden");
    document.getElementById("curriculumSummary").textContent =
      `${course.modules.length} modules • ${course.lesson_count} lessons`;
    const crumbTitle = document.querySelector(
      "main .mb-6 span.text-on-surface.font-headline-sm",
    );
    if (crumbTitle) crumbTitle.textContent = course.title;
    renderCurriculum();
    renderReviews();
    updateEnrollmentControls();
    Array.from(overviewRoot.children).forEach((child) => {
      if (child !== notice) child.style.display = "";
    });
    notice.classList.add("hidden");
  }

  function renderCurriculum() {
    modulesContainer.replaceChildren();
    const lessonCount = course.modules.reduce(
      (total, module) => total + module.lessons.length,
      0,
    );
    if (!lessonCount) {
      const empty = document.createElement("p");
      empty.className =
        "rounded-xl bg-surface-container-low p-4 text-sm text-on-surface-variant";
      empty.textContent = "This course curriculum is being prepared.";
      modulesContainer.append(empty);
      return;
    }

    course.modules.forEach((module, index) => {
      const details = document.createElement("details");
      details.className = "rounded-xl bg-surface-container-low overflow-hidden";
      const summary = document.createElement("summary");
      summary.className =
        "cursor-pointer list-none p-4 font-semibold text-on-surface hover:bg-surface-container";
      const completed = module.lessons.filter(
        (lesson) => lesson.is_completed,
      ).length;
      summary.textContent = `Module ${index + 1}: ${module.title} — ${completed}/${module.lessons.length} lessons complete`;
      const list = document.createElement("div");
      list.className = "p-3 pt-0 space-y-2";
      module.lessons.forEach((lesson) => {
        const row = document.createElement("button");
        row.type = "button";
        row.className =
          "flex w-full items-center justify-between gap-3 rounded-lg bg-surface-container-lowest px-3 py-2 text-left text-sm text-on-surface transition hover:bg-secondary/10 disabled:cursor-not-allowed disabled:opacity-60";
        row.disabled = !enrollment && !lesson.is_preview;
        const name = document.createElement("span");
        name.textContent = `${lesson.is_completed ? "✓ " : ""}${lesson.title}`;
        const length = document.createElement("span");
        length.className = "shrink-0 text-xs text-on-surface-variant";
        length.textContent = lesson.is_preview
          ? `${lesson.duration_minutes} min • Preview`
          : `${lesson.duration_minutes} min`;
        row.append(name, length);
        row.addEventListener("click", () => loadLesson(lesson.id));
        list.append(row);
      });
      details.append(summary, list);
      modulesContainer.append(details);
    });
  }

  function renderReviews() {
    reviewsSection.replaceChildren();
    const heading = document.createElement("h2");
    heading.className =
      "font-headline-md text-headline-md text-on-surface font-bold mb-6";
    heading.textContent = "Student Feedback & Ratings";
    reviewsSection.append(heading);

    if (course.reviews.length) {
      const reviewList = document.createElement("div");
      reviewList.className = "grid grid-cols-1 md:grid-cols-2 gap-4";
      course.reviews.forEach((review) => {
        const card = document.createElement("article");
        card.className = "rounded-xl bg-surface-container-low p-4";
        const rating = document.createElement("p");
        rating.className = "mb-2 font-semibold text-secondary";
        rating.textContent = `${review.rating}/5`;
        const content = document.createElement("p");
        content.className = "mb-3 text-sm text-on-surface-variant";
        content.textContent = review.content;
        const author = document.createElement("p");
        author.className = "text-xs font-semibold text-on-surface";
        author.textContent = review.student_name;
        card.append(rating, content, author);
        reviewList.append(card);
      });
      reviewsSection.append(reviewList);
    } else {
      const empty = document.createElement("p");
      empty.className = "mb-4 text-sm text-on-surface-variant";
      empty.textContent = "There are no reviews for this course yet.";
      reviewsSection.append(empty);
    }

    if (enrollment && hasAccessToken() && !reviewSubmitted) addReviewForm();
  }

  function addReviewForm() {
    const form = document.createElement("form");
    form.className = "mt-6 grid gap-3";
    const label = document.createElement("label");
    label.className = "grid gap-1 text-sm font-medium text-on-surface";
    label.textContent = "Your rating";
    const select = document.createElement("select");
    select.name = "rating";
    select.required = true;
    select.className = "rounded-lg border border-outline-variant bg-white p-2";
    for (let rating = 5; rating >= 1; rating -= 1) {
      const option = document.createElement("option");
      option.value = String(rating);
      option.textContent = `${rating} star${rating > 1 ? "s" : ""}`;
      select.append(option);
    }
    label.append(select);
    const content = document.createElement("textarea");
    content.name = "content";
    content.required = true;
    content.maxLength = 2000;
    content.rows = 3;
    content.placeholder = "Share your experience with this course";
    content.className =
      "rounded-lg border border-outline-variant bg-white p-3 text-sm";
    const submit = document.createElement("button");
    submit.type = "submit";
    submit.className =
      "w-fit rounded-full bg-secondary px-5 py-2 text-sm font-semibold text-on-secondary";
    submit.textContent = "Submit Review";
    const status = document.createElement("p");
    status.className = "text-sm text-on-surface-variant";
    status.setAttribute("role", "status");
    form.append(label, content, submit, status);
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      submit.disabled = true;
      try {
        await window.skillsHubApi.post(`/courses/${course.id}/reviews/`, {
          rating: Number(select.value),
          content: content.value,
        });
        reviewSubmitted = true;
        status.textContent = "Review submitted.";
        const updated = await window.skillsHubApi.get(`/courses/${course.id}/`);
        course = updated;
        setText(
          "#courseAverageRating",
          Number(course.average_rating)
            ? Number(course.average_rating).toFixed(1)
            : "New",
        );
        setText("#courseReviewCount", ` (${course.review_count} reviews)`);
        renderReviews();
      } catch (error) {
        status.textContent = error.message || "Unable to submit your review.";
        submit.disabled = false;
      }
    });
    reviewsSection.append(form);
  }

  function updateEnrollmentControls() {
    const enrolled = Boolean(enrollment);
    accessButton.disabled = false;
    accessLabel.textContent = enrolled
      ? enrollment.last_accessed_lesson
        ? "Resume Learning"
        : "Start Learning"
      : "Enroll in this Course";
    classroomTab.disabled = !enrolled;
    classroomTab.classList.toggle("opacity-50", !enrolled);
    const total = enrollment ? enrollment.total_lessons : course.lesson_count;
    const completed = enrollment ? enrollment.completed_lessons : 0;
    const percentage = enrollment ? enrollment.progress_percentage : 0;
    setText("#classroom-progress-text", `${completed} of ${total} Lessons Finished`);
    setText("#classroom-progress-percent", `${percentage}%`);
    const progress = document.getElementById("classroom-progress-fill");
    progress.style.width = `${percentage}%`;
    setText(
      "#classroom-progress-text",
      `${completed} of ${total} Lessons Finished`,
    );
  }

  async function enrollOrResume() {
    if (!hasAccessToken()) {
      showNotice(
        "Sign in with an active student account to enroll and access lessons.",
        true,
      );
      return;
    }
    accessButton.disabled = true;
    try {
      if (!enrollment) {
        enrollment = await window.skillsHubApi.post(
          `/courses/${course.id}/enroll/`,
        );
        const rows = await window.skillsHubApi.get("/courses/my-courses/");
        const enrollments = Array.isArray(rows) ? rows : rows.results;
        enrollment =
          enrollments.find((entry) => entry.course.id === course.id) ||
          enrollment;
      }
      renderCurriculum();
      updateEnrollmentControls();
      showNotice("", false);
      const firstLesson = course.modules.flatMap((module) => module.lessons)[0];
      const lessonId =
        lessonParam ||
        enrollment.last_accessed_lesson ||
        (firstLesson && firstLesson.id);
      if (lessonId) await loadLesson(lessonId);
      else showNotice("This course has no published lessons yet.", false);
      switchMainView("classroom");
    } catch (error) {
      showNotice(error.message || "Unable to enroll in this course.", true);
    } finally {
      accessButton.disabled = false;
    }
  }

  async function loadLesson(lessonId) {
    classroomContent.textContent = "Loading lesson…";
    switchMainView("classroom");
    try {
      currentLesson = await window.skillsHubApi.get(`/lessons/${lessonId}/`);
      renderLesson();
    } catch (error) {
      classroomContent.textContent =
        error.message || "Unable to load this lesson.";
    }
  }

  function renderLesson() {
    classroomContent.replaceChildren();
    const heading = document.createElement("h2");
    heading.className =
      "mb-2 font-headline-md text-headline-md font-bold text-on-surface";
    heading.textContent = currentLesson.title;
    const module = document.createElement("p");
    module.className = "mb-5 text-sm text-on-surface-variant";
    module.textContent = `${currentLesson.module_title} • ${currentLesson.duration_minutes} min`;
    const description = document.createElement("p");
    description.className = "mb-4 text-sm text-on-surface-variant";
    description.textContent = currentLesson.description;
    const content = document.createElement("div");
    content.className =
      "mb-6 whitespace-pre-wrap rounded-xl bg-surface-container-low p-5 text-sm leading-7 text-on-surface";
    if (currentLesson.content_type === "text") {
      content.textContent = currentLesson.content;
    } else if (currentLesson.content_type === "video") {
      content.textContent = "This lesson includes a video.";
      const video = document.createElement("a");
      video.className =
        "ml-2 font-semibold text-secondary underline";
      video.href = currentLesson.video_url;
      video.target = "_blank";
      video.rel = "noopener noreferrer";
      video.textContent = "Open video";
      content.append(video);
    } else {
      content.textContent = "Download the lesson resources below.";
    }

    const resources = document.createElement("div");
    resources.className = "mb-6 grid gap-2";
    currentLesson.resources.forEach((resource) => {
      const link = document.createElement("a");
      link.className =
        "rounded-lg bg-surface-container-low px-4 py-3 text-sm font-semibold text-secondary hover:underline";
      link.href = resource.download_url;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      link.textContent = `${resource.title} (${resource.file_size} bytes)`;
      resources.append(link);
    });

    const controls = document.createElement("div");
    controls.className = "flex flex-wrap justify-between gap-3";
    const previous = document.createElement("button");
    previous.type = "button";
    previous.className =
      "rounded-full bg-surface-container px-5 py-2 text-sm font-semibold text-on-surface disabled:opacity-50";
    previous.textContent = "Previous Lesson";
    previous.disabled = !currentLesson.previous_lesson_id;
    previous.addEventListener("click", () =>
      loadLesson(currentLesson.previous_lesson_id),
    );
    const next = document.createElement("button");
    next.type = "button";
    next.className =
      "rounded-full bg-secondary px-5 py-2 text-sm font-semibold text-on-secondary disabled:opacity-50";
    next.textContent = "Next Lesson";
    next.disabled = !currentLesson.next_lesson_id;
    next.addEventListener("click", () =>
      loadLesson(currentLesson.next_lesson_id),
    );
    controls.append(previous, next);
    classroomContent.append(heading, module, description, content, resources, controls);
    setText("#active-lesson-heading", currentLesson.title);
    setText(
      "#classroom-progress-text",
      `${enrollment.completed_lessons} of ${enrollment.total_lessons} Lessons Finished`,
    );
    markCompleteButton.disabled = currentLesson.is_completed;
    setText(
      "#mark-text",
      currentLesson.is_completed ? "Completed" : "Mark Complete",
    );
    document.getElementById("legacyClassroomContent").style.display = "none";
  }

  async function completeLesson() {
    if (!currentLesson) return;
    markCompleteButton.disabled = true;
    try {
      enrollment = await window.skillsHubApi.post(
        `/lessons/${currentLesson.id}/complete/`,
      );
      currentLesson.is_completed = true;
      course.modules.forEach((module) => {
        module.lessons.forEach((lesson) => {
          if (lesson.id === currentLesson.id) lesson.is_completed = true;
        });
      });
      const percent = enrollment.progress_percentage;
      setText("#classroom-progress-percent", `${percent}%`);
      setText(
        "#classroom-progress-text",
        `${enrollment.completed_lessons} of ${enrollment.total_lessons} Lessons Finished`,
      );
      document.getElementById("classroom-progress-fill").style.width =
        `${percent}%`;
      setText("#mark-text", "Completed");
      renderCurriculum();
    } catch (error) {
      showNotice(error.message || "Unable to mark this lesson complete.", true);
      markCompleteButton.disabled = false;
    }
  }

  async function loadCourse() {
    if (!courseId || !/^\d+$/.test(courseId)) {
      showNotice("Select a course from the catalogue to view its details.", true);
      accessButton.disabled = true;
      accessLabel.textContent = "Course unavailable";
      return;
    }
    try {
      course = await window.skillsHubApi.get(`/courses/${courseId}/`);
      if (hasAccessToken()) {
        try {
          const rows = await window.skillsHubApi.get("/courses/my-courses/");
          const enrollments = Array.isArray(rows) ? rows : rows.results;
          enrollment =
            enrollments.find((entry) => entry.course.id === course.id) || null;
        } catch (error) {
          if (error.status !== 401 && error.status !== 403) throw error;
        }
      }
      renderCourseOverview();
      document.getElementById("legacyClassroomContent").style.display = "none";
      if (lessonParam && enrollment) {
        await loadLesson(lessonParam);
      }
    } catch (error) {
      showNotice(error.message || "Unable to load this course.", true);
      accessButton.disabled = true;
      accessLabel.textContent = "Course unavailable";
    }
  }

  accessButton.addEventListener("click", enrollOrResume);
  markCompleteButton.addEventListener("click", completeLesson);
  document
    .getElementById("expandCourseModules")
    .addEventListener("click", () => {
      modulesContainer.querySelectorAll("details").forEach((module) => {
        module.open = true;
      });
    });

  window.courseLearning = { loadLesson };
  loadCourse();
})();
