(function () {
  const baseUrl = (
    window.SKILLSHUB_API_BASE_URL || "http://127.0.0.1:8000/api/v1"
  ).replace(/\/+$/, "");
  const tokenKeys = ["skillshubAccessToken", "skillshubRefreshToken", "skillshubUser"];

  function getValue(key) {
    return sessionStorage.getItem(key) || localStorage.getItem(key);
  }

  function setValue(key, value, persistent) {
    const destination = persistent ? localStorage : sessionStorage;
    const other = persistent ? sessionStorage : localStorage;
    destination.setItem(key, value);
    other.removeItem(key);
  }

  function clearTokens() {
    tokenKeys.forEach((key) => {
      sessionStorage.removeItem(key);
      localStorage.removeItem(key);
    });
  }

  function errorMessage(data) {
    if (typeof data === "string") return data;
    if (!data || typeof data !== "object") return "The request could not be completed.";
    const messages = [];
    Object.entries(data).forEach(([key, value]) => {
      if (Array.isArray(value)) messages.push(`${key}: ${value.map(String).join(" ")}`);
      else if (typeof value === "string") messages.push(`${key}: ${value}`);
      else if (value && typeof value === "object") messages.push(errorMessage(value));
    });
    return messages.join(" ") || "The request could not be completed.";
  }

  async function request(path, options, retry) {
    const requestOptions = options || {};
    const headers = new Headers(requestOptions.headers || {});
    const access = getValue("skillshubAccessToken");
    if (access) headers.set("Authorization", `Bearer ${access}`);
    if (
      requestOptions.body &&
      !(requestOptions.body instanceof FormData) &&
      !headers.has("Content-Type")
    ) {
      headers.set("Content-Type", "application/json");
    }

    let response = await fetch(`${baseUrl}${path}`, {
      ...requestOptions,
      headers,
    });
    if (response.status === 401 && retry !== false && path !== "/auth/token/refresh/") {
      const refresh = getValue("skillshubRefreshToken");
      if (refresh) {
        const refreshed = await fetch(`${baseUrl}/auth/token/refresh/`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ refresh }),
        });
        if (refreshed.ok) {
          const tokens = await refreshed.json();
          const persistent = localStorage.getItem("skillshubRefreshToken") !== null;
          setValue("skillshubAccessToken", tokens.access, persistent);
          if (tokens.refresh) {
            setValue("skillshubRefreshToken", tokens.refresh, persistent);
          }
          return request(path, requestOptions, false);
        }
        clearTokens();
      }
    }

    const data =
      response.status === 204 || response.status === 205
        ? null
        : await response.json().catch(() => null);
    if (!response.ok) {
      const error = new Error(errorMessage(data));
      error.status = response.status;
      error.data = data;
      throw error;
    }
    return data;
  }

  window.skillsHubApi = {
    baseUrl,
    clearTokens,
    get(path) {
      return request(path, { method: "GET" });
    },
    post(path, body) {
      return request(path, {
        method: "POST",
        body: body instanceof FormData ? body : JSON.stringify(body || {}),
      });
    },
    patch(path, body) {
      return request(path, {
        method: "PATCH",
        body: body instanceof FormData ? body : JSON.stringify(body || {}),
      });
    },
  };
})();
