(function () {
  const api = window.skillsHubApi;
  const profileImages = Array.from(
    document.querySelectorAll('img[data-profile-photo], img[alt*="Prince Egah"]')
  );
  const profileNames = new Set();
  const profileGreetings = Array.from(
    document.querySelectorAll("[data-profile-greeting]")
  );
  const profileEmails = Array.from(
    document.querySelectorAll("[data-profile-email]")
  );
  const profileInitials = Array.from(
    document.querySelectorAll("[data-profile-initials]")
  );
  const profileEmailLinks = Array.from(
    document.querySelectorAll("[data-profile-email-link]")
  );

  profileImages.forEach((image) => {
    image.dataset.profilePhoto = "";
    image.removeAttribute("src");
    image.alt = "";

    let container = image.parentElement;
    for (let depth = 0; container && depth < 6; depth += 1) {
      const matches = Array.from(
        container.querySelectorAll("h1, h2, h3, h4, span, p")
      ).filter(
        (element) =>
          element.children.length === 0 &&
          element.textContent.trim() === "Prince Egah"
      );
      if (matches.length) {
        matches.forEach((element) => {
          element.dataset.profileName = "";
          profileNames.add(element);
        });
        break;
      }
      container = container.parentElement;
    }
  });

  function getStoredValue(key) {
    return sessionStorage.getItem(key) || localStorage.getItem(key);
  }

  function hasSession() {
    return Boolean(
      getStoredValue("skillshubAccessToken") ||
        getStoredValue("skillshubRefreshToken")
    );
  }

  function getFullName(user) {
    return [user.first_name, user.last_name].filter(Boolean).join(" ").trim();
  }

  function saveUser(user) {
    const persistent = localStorage.getItem("skillshubRefreshToken") !== null;
    const destination = persistent ? localStorage : sessionStorage;
    const other = persistent ? sessionStorage : localStorage;
    const cachedUser = { ...user };
    delete cachedUser.profile_photo_url;
    destination.setItem("skillshubUser", JSON.stringify(cachedUser));
    other.removeItem("skillshubUser");
  }

  let currentUser = null;

  function render(user) {
    currentUser = user;
    const fullName = getFullName(user);
    profileNames.forEach((element) => {
      element.textContent = fullName;
    });
    document.querySelectorAll("[data-profile-name]").forEach((element) => {
      element.textContent = fullName;
    });
    profileGreetings.forEach((element) => {
      element.textContent = user.first_name
        ? `Welcome back, ${user.first_name}!`
        : "Welcome back!";
    });
    profileEmails.forEach((element) => {
      element.textContent = user.email || "";
    });
    profileEmailLinks.forEach((element) => {
      if (user.email) {
        element.href = `mailto:${user.email}`;
      } else {
        element.removeAttribute("href");
      }
    });
    const initials = [user.first_name, user.last_name]
      .filter(Boolean)
      .map((name) => name.charAt(0).toUpperCase())
      .join("");
    profileInitials.forEach((element) => {
      element.textContent = initials;
    });
    document.querySelectorAll("[data-profile-photo]").forEach((image) => {
      if (user.profile_photo_url) {
        image.src = user.profile_photo_url;
        image.alt = fullName ? `Profile photo for ${fullName}` : "Profile photo";
        image.removeAttribute("aria-hidden");
      } else {
        image.removeAttribute("src");
        image.alt = "";
        image.setAttribute("aria-hidden", "true");
      }
    });
  }

  function clearProfile() {
    currentUser = null;
    profileNames.forEach((element) => {
      element.textContent = "";
    });
    profileGreetings.forEach((element) => {
      element.textContent = "Welcome to UCC SKILLSHUB!";
    });
    profileEmails.forEach((element) => {
      element.textContent = "";
    });
    profileEmailLinks.forEach((element) => {
      element.removeAttribute("href");
    });
    profileInitials.forEach((element) => {
      element.textContent = "";
    });
    document.querySelectorAll("[data-profile-name]").forEach((element) => {
      element.textContent = "";
    });
    document.querySelectorAll("[data-profile-photo]").forEach((image) => {
      image.removeAttribute("src");
      image.alt = "";
      image.setAttribute("aria-hidden", "true");
    });
  }

  function readCachedUser() {
    const stored = getStoredValue("skillshubUser");
    if (!stored) return null;
    try {
      const user = JSON.parse(stored);
      if (!user || typeof user !== "object") return null;
      delete user.profile_photo_url;
      return user;
    } catch (error) {
      console.error("Could not read the cached SkillsHub profile.", error);
      sessionStorage.removeItem("skillshubUser");
      localStorage.removeItem("skillshubUser");
      return null;
    }
  }

  async function loadProfile() {
    if (!hasSession()) {
      clearProfile();
      return;
    }
    const cachedUser = readCachedUser();
    if (cachedUser) render(cachedUser);
    if (!api) {
      console.error("The SkillsHub API client is unavailable.");
      return;
    }
    try {
      const user = await api.get("/users/me/");
      render(user);
      saveUser(user);
    } catch (error) {
      if (error.status === 401) {
        api.clearTokens();
        clearProfile();
      }
      console.error("Could not load the signed-in profile.", error);
    }
  }

  const ready = loadProfile();

  window.skillsHubProfile = {
    get currentUser() {
      return currentUser;
    },
    get ready() {
      return ready;
    },
    isAuthenticated: hasSession,
    async updateProfile(changes) {
      if (!hasSession()) throw new Error("Sign in to update your profile.");
      const user = await api.patch("/users/me/", changes);
      render(user);
      saveUser(user);
      return user;
    },
    async uploadProfilePhoto(file) {
      if (!hasSession()) throw new Error("Sign in to upload a profile photo.");
      const formData = new FormData();
      formData.append("profile_photo", file);
      const result = await api.post("/users/me/profile-photo/", formData);
      render({ ...currentUser, profile_photo_url: result.profile_photo_url });
      saveUser(currentUser);
      return result;
    },
  };
})();
