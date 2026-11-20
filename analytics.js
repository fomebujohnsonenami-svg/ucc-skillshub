(function () {
  const api = window.skillsHubApi;
  const authenticated = Boolean(
    sessionStorage.getItem("skillshubAccessToken") ||
      localStorage.getItem("skillshubAccessToken")
  );
  if (!api || !authenticated) return;

  function setText(selector, value) {
    const element = document.querySelector(selector);
    if (element) element.textContent = value;
  }

  function renderActivity(activity) {
    const chart = document.querySelector("[data-analytics-week-chart]");
    if (!chart) return;
    chart.replaceChildren();
    const latest = activity.slice(-7);
    const maximum = Math.max(1, ...latest.map((day) => day.total));
    latest.forEach((day) => {
      const date = new Date(`${day.date}T00:00:00`);
      const column = document.createElement("div");
      column.className =
        "group flex h-full flex-col items-center justify-end relative";
      const tooltip = document.createElement("span");
      tooltip.className =
        "absolute -top-8 rounded bg-primary-container px-2 py-1 text-[10px] text-on-primary opacity-0 group-hover:opacity-100";
      tooltip.textContent = `${day.total} recorded actions`;
      const bar = document.createElement("div");
      bar.className =
        "w-full max-w-[42px] rounded-t-lg bg-secondary-fixed group-hover:bg-secondary-container";
      bar.style.height = `${Math.max(2, (day.total / maximum) * 100)}%`;
      bar.setAttribute("aria-label", `${day.total} recorded actions`);
      const weekday = document.createElement("span");
      weekday.className = "mt-2 text-xs text-on-surface-variant";
      weekday.textContent = date.toLocaleDateString(undefined, {
        weekday: "short",
      });
      const count = document.createElement("span");
      count.className = "text-[10px] text-outline";
      count.textContent = String(day.total);
      column.append(tooltip, bar, weekday, count);
      chart.appendChild(column);
    });
    chart.hidden = false;
    chart.classList.remove("hidden");
  }

  function renderCourseProgress(courses) {
    const container = document.querySelector("[data-analytics-course-progress]");
    if (!container) return;
    container.replaceChildren();
    const activeCourses = courses.filter(
      (course) => course.status === "in_progress"
    );
    if (!activeCourses.length) {
      const empty = document.createElement("p");
      empty.className = "text-sm text-on-surface-variant";
      empty.textContent = "No courses are currently in progress.";
      container.appendChild(empty);
      container.hidden = false;
      container.classList.remove("hidden");
      return;
    }
    activeCourses.slice(0, 4).forEach((course) => {
      const card = document.createElement("article");
      card.className =
        "rounded-xl bg-surface-container-lowest p-space-sm";
      const heading = document.createElement("div");
      heading.className = "mb-1 flex items-center justify-between gap-2";
      const title = document.createElement("span");
      title.className =
        "font-label-md text-label-md font-semibold text-on-surface";
      title.textContent = course.title;
      const percentage = document.createElement("span");
      percentage.className = "font-label-sm text-label-sm font-bold text-secondary";
      percentage.textContent = `${course.progress_percentage}%`;
      heading.append(title, percentage);
      const track = document.createElement("div");
      track.className = "h-2 w-full rounded-full bg-surface-container";
      const fill = document.createElement("div");
      fill.className = "h-full rounded-full bg-secondary";
      fill.style.width = `${course.progress_percentage}%`;
      track.appendChild(fill);
      const detail = document.createElement("span");
      detail.className = "mt-1 block text-xs text-outline";
      detail.textContent = `${course.completed_lessons} of ${course.total_lessons} lessons completed`;
      card.append(heading, track, detail);
      container.appendChild(card);
    });
    container.hidden = false;
    container.classList.remove("hidden");
  }

  function renderSkills(skills) {
    const container = document.querySelector("[data-analytics-skills-grid]");
    if (!container) return;
    container.replaceChildren();
    if (!skills.length) {
      const empty = document.createElement("p");
      empty.className = "text-sm text-on-surface-variant";
      empty.textContent =
        "No pathway skills are recorded yet. Complete a pathway to see its required skills here.";
      container.appendChild(empty);
      container.hidden = false;
      container.classList.remove("hidden");
      return;
    }
    skills.forEach((skill) => {
      const card = document.createElement("article");
      card.className =
        "rounded-2xl bg-surface-container-lowest p-space-lg shadow-sm";
      const title = document.createElement("h3");
      title.className = "font-headline-sm text-headline-sm text-on-surface";
      title.textContent = skill.name;
      const category = document.createElement("p");
      category.className = "mt-2 text-sm text-on-surface-variant";
      category.textContent = skill.category_name;
      card.append(title, category);
      container.appendChild(card);
    });
    container.hidden = false;
    container.classList.remove("hidden");
  }

  function renderNotifications(notifications) {
    const container = document.querySelector("[data-analytics-notifications]");
    if (!container) return;
    container.replaceChildren();
    if (!notifications.length) {
      const empty = document.createElement("p");
      empty.className = "text-sm text-on-surface-variant";
      empty.textContent = "No recent notifications.";
      container.appendChild(empty);
      container.hidden = false;
      container.classList.remove("hidden");
      return;
    }
    notifications.slice(0, 8).forEach((notification) => {
      const item = document.createElement("article");
      item.className =
        "relative rounded-xl bg-surface-container-low p-space-md";
      const heading = document.createElement("div");
      heading.className = "mb-1 flex items-start justify-between gap-3";
      const title = document.createElement("h3");
      title.className = "font-label-md text-label-md font-bold text-on-surface";
      title.textContent = notification.title;
      const created = document.createElement("time");
      created.className = "shrink-0 text-[11px] text-outline";
      created.dateTime = notification.created_at;
      created.textContent = new Date(notification.created_at).toLocaleDateString();
      const message = document.createElement("p");
      message.className = "text-sm text-on-surface-variant";
      message.textContent = notification.message;
      heading.append(title, created);
      item.append(heading, message);
      container.appendChild(item);
    });
    container.hidden = false;
    container.classList.remove("hidden");
  }

  async function loadAnalytics() {
    try {
      const [dashboard, progress, activity, notifications] = await Promise.all([
        api.get("/analytics/student-dashboard/"),
        api.get("/analytics/student-progress/"),
        api.get("/analytics/learning-activity/?days=30"),
        api.get("/notifications/?page_size=20"),
      ]);
      const courses = progress.courses || [];
      const completed = dashboard.completed_courses || 0;
      const enrolled = dashboard.enrolled_courses || 0;
      const inProgress = courses.filter(
        (course) => course.status === "in_progress"
      ).length;
      const notStarted = courses.filter(
        (course) =>
          course.status === "in_progress" && course.completed_lessons === 0
      ).length;
      const activeProgress = Math.max(0, inProgress - notStarted);
      const completionRate = enrolled ? (completed / enrolled) * 100 : 0;
      const skills = dashboard.skills_acquired || [];

      setText("[data-analytics-total-activity]", String(activity.total_activity));
      setText("[data-analytics-completed-courses]", String(completed));
      setText("[data-analytics-enrolled-courses]", String(enrolled));
      setText("[data-analytics-skills-count]", String(skills.length));
      setText(
        "[data-analytics-current-streak]",
        String(dashboard.learning_streak?.current || 0)
      );
      setText(
        "[data-analytics-longest-streak]",
        String(dashboard.learning_streak?.longest || 0)
      );
      setText("[data-analytics-total-courses]", `${enrolled} Total Courses`);
      setText("[data-analytics-completion-rate]", `${completionRate.toFixed(1)}%`);
      setText("[data-analytics-course-completed]", `${completed} completed`);
      setText("[data-analytics-course-progress-count]", `${activeProgress} in progress`);
      setText("[data-analytics-course-not-started]", `${notStarted} not started`);

      const completedRing = document.querySelector("[data-analytics-completed-ring]");
      if (completedRing) {
        completedRing.setAttribute("stroke-dasharray", `${completionRate}, 100`);
      }
      const progressRing = document.querySelector("[data-analytics-progress-ring]");
      if (progressRing) {
        const progressRate = enrolled ? (activeProgress / enrolled) * 100 : 0;
        progressRing.setAttribute("stroke-dasharray", `${progressRate}, 100`);
        progressRing.setAttribute("stroke-dashoffset", `${-completionRate}`);
      }

      renderActivity(activity.activity || []);
      renderCourseProgress(courses);
      renderSkills(skills);
      renderNotifications(notifications.results || []);
      document.querySelectorAll("[data-notification-count]").forEach((badge) => {
        if (!badge.closest('button[aria-label^="Notifications"]')) {
          badge.textContent = String(notifications.unread_count || 0);
          badge.hidden = !notifications.unread_count;
          badge.classList.toggle("hidden", !notifications.unread_count);
        }
      });
    } catch (error) {
      console.error("Could not load student analytics.", error);
    }
  }

  loadAnalytics();
})();
