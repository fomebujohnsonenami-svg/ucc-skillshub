(() => {
  const section = document.getElementById("continueLearningSection");
  if (!section) return;
  const list = document.getElementById("continueLearningList");
  const notice = document.getElementById("continueLearningNotice");
  const template = list.firstElementChild.cloneNode(true);
  const catalogUrl = "../ucc_skillshub_courses_catalogue/code.html";

  function showMessage(message, isError) {
    notice.replaceChildren();
    notice.classList.remove("hidden");
    notice.classList.toggle("text-rose-700", Boolean(isError));
    const text = document.createElement("span");
    text.textContent = message;
    notice.append(text);
  }

  function renderEnrollment(enrollment) {
    const card = template.cloneNode(true);
    card.removeAttribute("id");
    const course = enrollment.course;
    const progress = enrollment.progress_percentage;
    const heading = card.querySelector("h3");
    heading.textContent = course.title;
    const status = card.querySelector("h3 + span");
    status.textContent =
      enrollment.status === "completed"
        ? "Completed"
        : `In Progress • ${progress}%`;
    const description = card.querySelector(
      ".flex-1.w-full.space-y-3 > p",
    );
    description.textContent = course.description;
    card.querySelector('[style*="width: 68%"]').style.width = `${progress}%`;

    const button = card.querySelector("button");
    const link = document.createElement("a");
    link.className = button.className;
    link.append(...Array.from(button.childNodes));
    link.firstChild.textContent =
      enrollment.status === "completed" ? "Review Course" : "Continue";
    const lessonQuery = enrollment.last_accessed_lesson
      ? `&lesson=${encodeURIComponent(enrollment.last_accessed_lesson)}`
      : "";
    link.href = `../skillbridge_course_details_learning_experience/code.html?course=${encodeURIComponent(course.id)}${lessonQuery}`;
    button.replaceWith(link);
    return card;
  }

  showMessage("Loading your courses…", false);
  async function loadCourses() {
    try {
      const enrollments = [];
      let page = 1;
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
      const completed = enrollments.filter(
        (enrollment) => enrollment.status === "completed",
      ).length;
      document.getElementById("enrolledCourseCount").textContent =
        String(enrollments.length);
      document.getElementById("completedCourseCount").textContent =
        String(completed);
      list.replaceChildren(...enrollments.map(renderEnrollment));
      list.dataset.apiReady = "true";
      if (!enrollments.length) {
        notice.replaceChildren();
        const message = document.createElement("span");
        message.textContent =
          "You are not enrolled in any courses yet. ";
        const link = document.createElement("a");
        link.className = "font-bold text-indigo-600 hover:underline";
        link.href = catalogUrl;
        link.textContent = "Browse the course catalogue";
        notice.append(message, link);
        notice.classList.remove("hidden");
      } else {
        notice.classList.add("hidden");
      }
    } catch (error) {
      list.replaceChildren();
      list.dataset.apiReady = "true";
      showMessage(
        error.status === 401 || error.status === 403
          ? "Sign in with an active student account to see your courses."
          : error.message || "Unable to load your courses. Please try again.",
        true,
      );
    }
  }

  loadCourses();
})();
