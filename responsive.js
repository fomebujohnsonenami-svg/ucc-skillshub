(function () {
  const sidebar = document.querySelector(
    '[data-purpose="main-sidebar"], [data-purpose="primary-sidebar"], [data-purpose="sidebar"]'
  );
  if (!sidebar) return;

  const breakpoint = window.matchMedia("(max-width: 1023.98px)");
  const body = document.body;
  body.classList.add("has-responsive-sidebar");

  if (!sidebar.id) sidebar.id = "primary-navigation";

  const toggle = document.createElement("button");
  toggle.className = "responsive-menu-toggle";
  toggle.type = "button";
  toggle.setAttribute("aria-controls", sidebar.id);
  toggle.setAttribute("aria-expanded", "false");
  toggle.setAttribute("aria-label", "Open navigation menu");

  const icon = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  icon.setAttribute("viewBox", "0 0 24 24");
  icon.setAttribute("width", "22");
  icon.setAttribute("height", "22");
  icon.setAttribute("aria-hidden", "true");
  icon.setAttribute("fill", "none");
  icon.setAttribute("stroke", "currentColor");
  icon.setAttribute("stroke-width", "2");
  icon.setAttribute("stroke-linecap", "round");
  icon.append(
    ...[
      [4, 6, 20, 6],
      [4, 12, 20, 12],
      [4, 18, 20, 18],
    ].map((line) => {
      const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
      path.setAttribute("d", `M${line[0]} ${line[1]}h${line[2] - line[0]}`);
      return path;
    })
  );
  toggle.append(icon);

  const backdrop = document.createElement("button");
  backdrop.className = "responsive-nav-backdrop";
  backdrop.type = "button";
  backdrop.tabIndex = -1;
  backdrop.setAttribute("aria-label", "Close navigation menu");
  body.append(toggle, backdrop);

  function closeMenu(returnFocus) {
    body.removeAttribute("data-responsive-nav-open");
    toggle.setAttribute("aria-expanded", "false");
    toggle.setAttribute("aria-label", "Open navigation menu");
    backdrop.tabIndex = -1;
    if (breakpoint.matches) {
      sidebar.inert = true;
      sidebar.setAttribute("aria-hidden", "true");
    }
    if (returnFocus) toggle.focus();
  }

  function openMenu() {
    body.setAttribute("data-responsive-nav-open", "true");
    toggle.setAttribute("aria-expanded", "true");
    toggle.setAttribute("aria-label", "Close navigation menu");
    backdrop.tabIndex = 0;
    sidebar.inert = false;
    sidebar.removeAttribute("aria-hidden");
    const firstLink = sidebar.querySelector("a");
    if (firstLink) firstLink.focus();
  }

  function syncBreakpoint() {
    if (breakpoint.matches) {
      if (body.getAttribute("data-responsive-nav-open") !== "true") {
        closeMenu(false);
      }
    } else {
      body.removeAttribute("data-responsive-nav-open");
      toggle.setAttribute("aria-expanded", "false");
      toggle.setAttribute("aria-label", "Open navigation menu");
      sidebar.inert = false;
      sidebar.removeAttribute("aria-hidden");
    }
  }

  toggle.addEventListener("click", () => {
    if (body.getAttribute("data-responsive-nav-open") === "true") {
      closeMenu(true);
    } else {
      openMenu();
    }
  });
  backdrop.addEventListener("click", () => closeMenu(true));
  sidebar.querySelectorAll("a").forEach((link) => {
    link.addEventListener("click", () => {
      if (breakpoint.matches) closeMenu(false);
    });
  });
  document.addEventListener("keydown", (event) => {
    if (
      event.key === "Escape" &&
      body.getAttribute("data-responsive-nav-open") === "true"
    ) {
      closeMenu(true);
    }
  });

  if (breakpoint.addEventListener) {
    breakpoint.addEventListener("change", syncBreakpoint);
  } else {
    breakpoint.addListener(syncBreakpoint);
  }
  syncBreakpoint();
})();

/* Shared working account controls for dashboard sidebars. */
(function(){
const api=window.skillsHubApi,side=document.querySelector('[data-purpose="sidebar"],[data-purpose="main-sidebar"],[data-purpose="primary-sidebar"]');
if(!api||!side)return;
const modal=document.createElement("div");
modal.style.cssText="display:none;position:fixed;inset:0;z-index:1000;background:#0f172a99;align-items:center;justify-content:center;padding:16px";
modal.innerHTML='<div role="dialog" aria-modal="true" style="width:min(100%,520px);max-height:90vh;overflow:auto;background:white;color:#172033;border-radius:18px;padding:24px"><div style="display:flex;justify-content:space-between;align-items:center"><h2 style="font-size:22px;font-weight:800" data-heading></h2><button type="button" data-close aria-label="Close" style="font-size:28px">×</button></div><div data-body style="margin-top:16px"></div></div>';
document.body.append(modal);
const area=modal.querySelector("[data-body]");
function close(){modal.style.display="none"}
function open(title){modal.querySelector("[data-heading]").textContent=title;modal.style.display="flex";area.textContent="Loading…"}
modal.querySelector("[data-close]").onclick=close;
modal.onclick=e=>{if(e.target===modal)close()};
document.addEventListener("keydown",e=>{if(e.key==="Escape")close()});
function field(form,name,label,value){const wrap=document.createElement("label");wrap.style.cssText="display:block;margin:12px 0;font-size:14px;font-weight:600";wrap.textContent=label;const input=document.createElement("input");input.name=name;input.value=value||"";input.style.cssText="display:block;width:100%;border:1px solid #cbd5e1;border-radius:9px;padding:10px;margin-top:5px";wrap.append(input);form.append(wrap)}
async function settings(){
open("Account settings");
try{
const data=await api.get("/settings/"),form=document.createElement("form");
area.replaceChildren(form);
[["first_name","First name"],["last_name","Last name"],["username","Username"],["phone_number","Phone number"]].forEach(([key,label])=>field(form,key,label,data[key]));
const theme=document.createElement("select");theme.name="theme";theme.style.cssText="display:block;width:100%;padding:10px;margin:12px 0;border:1px solid #cbd5e1;border-radius:9px";
["system","light","dark"].forEach(value=>{const opt=document.createElement("option");opt.value=value;opt.textContent=value[0].toUpperCase()+value.slice(1);theme.append(opt)});theme.value=data.theme||"system";form.append(theme);
const status=document.createElement("p");status.setAttribute("role","status");form.append(status);
const save=document.createElement("button");save.type="submit";save.textContent="Save changes";save.style.cssText="background:#5136ca;color:white;padding:10px 20px;border-radius:10px;margin-top:12px";form.append(save);
form.onsubmit=async e=>{e.preventDefault();status.textContent="Saving…";try{await api.patch("/settings/",Object.fromEntries(new FormData(form)));status.textContent="Saved successfully.";if(window.skillsHubProfile?.refresh)await window.skillsHubProfile.refresh()}catch(err){status.textContent=err.message}};
}catch(err){area.textContent="Could not load settings: "+err.message}
}
async function notifications(){
open("Notifications");
try{
const data=await api.get("/notifications/?page_size=20");area.replaceChildren();
const items=data.results||[];
const status=document.createElement("p");status.textContent=items.length?items.length+" recent notifications":"You are all caught up.";area.append(status);
if(items.length){const all=document.createElement("button");all.textContent="Mark all read";all.style.cssText="color:#5136ca;font-weight:700;margin:12px 0";all.onclick=async()=>{try{await api.post("/notifications/mark-all-read/");await notifications()}catch(err){status.textContent=err.message}};area.append(all)}
items.forEach(item=>{const box=document.createElement("article");box.style.cssText="border:1px solid #e2e8f0;padding:12px;border-radius:10px;margin:8px 0";const title=document.createElement("strong");title.textContent=item.title;const msg=document.createElement("p");msg.textContent=item.message;box.append(title,msg);if(!item.is_read){const read=document.createElement("button");read.textContent="Mark read";read.style.cssText="color:#5136ca;display:block;margin-top:8px";read.onclick=async()=>{try{await api.patch("/notifications/"+encodeURIComponent(item.id)+"/read/");await notifications()}catch(err){status.textContent=err.message}};box.append(read)}area.append(box)})
}catch(err){area.textContent="Could not load notifications: "+err.message}
}
async function logout(){
if(!confirm("Sign out of UCC Skillshub?"))return;
const refresh=sessionStorage.getItem("skillshubRefreshToken")||localStorage.getItem("skillshubRefreshToken");
try{if(refresh)await api.post("/auth/logout/",{refresh})}catch(err){console.warn("Remote sign-out failed",err)}
finally{api.clearTokens();window.location.assign("../ucc_skillshub_sign_in/code.html")}
}
side.querySelectorAll("a").forEach(link=>{
const label=link.textContent.trim().replace(/\s+\d+$/,"").toLowerCase();
if(["settings","notifications","logout"].includes(label)){
link.href="#"+label;
link.addEventListener("click",event=>{event.preventDefault();event.stopImmediatePropagation();if(label==="settings")settings();else if(label==="notifications")notifications();else logout()},true)
}
});
})();
