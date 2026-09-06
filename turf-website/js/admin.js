/* ============================================================
   ADMIN JS — dashboard behaviour
   ============================================================ */

(function () {
  "use strict";

  const S = window.SITE;
  const C = window.CONTENT;
  const Store = window.Store;

  const $ = (sel) => document.querySelector(sel);
  const $$ = (sel) => Array.from(document.querySelectorAll(sel));
  const esc = (str) => String(str ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const fmt = (n) => "₹" + Math.round(n).toLocaleString("en-IN");

  let currentView = "overview";
  let currentTab = "upcoming";

  function svgIcon(name, size = 18) {
    const L = window.lucide;
    if (!L || !L.icons) return "";
    const icon = L.icons[name] || L.icons["circle-check"];
    if (!icon) return "";
    const attrs = { width: size, height: size, "stroke-width": 2, "aria-hidden": "true" };
    try {
      if (typeof icon.toSvg === "function") return icon.toSvg(attrs);
      if (typeof icon === "function") return icon(attrs).outerHTML;
    } catch (e) { }
    return "";
  }
  function refreshIcons() {
    if (window.lucide && window.lucide.createIcons) { try { window.lucide.createIcons(); } catch (e) {} }
  }

  function toast(message, type = "ok") {
    const el = document.createElement("div");
    el.className = `toast ${type === "bad" ? "bad" : ""}`;
    el.innerHTML = `${svgIcon(type === "bad" ? "circle-x" : "circle-check", 18)}<span>${esc(message)}</span>`;
    $("#toast-wrap").appendChild(el);
    setTimeout(() => { el.style.opacity = "0"; el.style.transition = "opacity .4s"; setTimeout(() => el.remove(), 400); }, 3200);
  }

  /* ================= AUTH ================= */
  function isLoggedIn() {
    return sessionStorage.getItem("gza_admin") === "1";
  }
  function showScreen(login) {
    $("#login-screen").style.display = login ? "" : "none";
    $("#dash").hidden = login;
    if (!login) renderAll();
  }
  function initAuth() {
    $("#side-mark").innerHTML = svgIcon("football", 22);
    $("#side-name").textContent = S.name;
    $("#login-logo").innerHTML = svgIcon("football", 32);
    $("#topbar-date").textContent = new Date().toLocaleDateString("en-IN", { weekday: "long", day: "numeric", month: "long", year: "numeric" });

    $("#login-form").addEventListener("submit", (e) => {
      e.preventDefault();
      const pin = $("#pin-input").value.trim();
      if (pin === String(S.adminPin)) {
        sessionStorage.setItem("gza_admin", "1");
        $("#login-err").textContent = "";
        $("#pin-input").value = "";
        showScreen(false);
        toast("Welcome back, " + S.name + "!");
      } else {
        $("#login-err").textContent = "Incorrect PIN. Please try again.";
      }
    });

    $("#logout").addEventListener("click", () => {
      sessionStorage.removeItem("gza_admin");
      showScreen(true);
    });

    showScreen(!isLoggedIn());
  }

  /* ================= NAV ================= */
  function initNav() {
    $$(".nav-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        $$(".nav-btn").forEach((b) => b.classList.remove("active"));
        btn.classList.add("active");
        currentView = btn.dataset.view;
        const titles = { overview: "Overview", bookings: "Bookings", slots: "Slot Manager", pricing: "Pricing", settings: "Settings" };
        $("#view-title").textContent = titles[currentView];
        $$(".view").forEach((v) => (v.hidden = true));
        $("#view-" + currentView).hidden = false;
        if (currentView === "overview") renderOverview();
        if (currentView === "bookings") renderBookings();
        if (currentView === "slots") initSlotManager();
        if (currentView === "pricing") renderPricing();
        window.scrollTo({ top: 0 });
      });
    });
  }

  /* ================= OVERVIEW ================= */
  function renderOverview() {
    const st = Store.stats();
    $("#stat-today-bookings").textContent = st.todayBookings;
    $("#stat-today-revenue").textContent = fmt(st.todayRevenue);
    $("#stat-available").textContent = st.availableSlots;
    $("#stat-customers").textContent = st.totalCustomers;

    const today = Store.todayISO();
    const list = Store.getBookings()
      .filter((b) => b.date === today && b.status !== "cancelled")
      .sort((a, b) => a.hour - b.hour);
    $("#today-count").textContent = list.length;
    $("#today-list").innerHTML = list.length ? renderRows(list, true) : empty("No bookings today yet.");

    const upcoming = Store.getBookings()
      .filter((b) => b.date > today && b.status !== "cancelled")
      .sort((a, b) => (a.date + a.hour).localeCompare(b.date + b.hour))
      .slice(0, 8);
    $("#upcoming-count").textContent = Store.getBookings().filter((b) => b.date > today && b.status !== "cancelled").length;
    $("#upcoming-list").innerHTML = upcoming.length ? renderRows(upcoming) : empty("No upcoming bookings.");
    bindRowActions();
  }

  /* ================= BOOKINGS LIST ================= */
  function renderBookings() {
    const today = Store.todayISO();
    const all = Store.getBookings().sort((a, b) => (b.date + b.hour).localeCompare(a.date + a.hour));
    let filtered;
    if (currentTab === "upcoming") filtered = all.filter((b) => b.date >= today && b.status !== "cancelled");
    else if (currentTab === "today") filtered = all.filter((b) => b.date === today);
    else if (currentTab === "history") filtered = all.filter((b) => b.date < today || b.status === "cancelled" || b.status === "completed");
    else filtered = all;

    $("#all-list").innerHTML = filtered.length ? renderRows(filtered) : empty("No bookings in this view.");
    bindRowActions();
  }

  function renderRows(list, compact = false) {
    return list.map((b) => {
      const time = `${Store.hourLabel(b.hour)} – ${Store.hourLabel(b.hour + b.duration)}`;
      const badges = `
        <span class="badge ${b.status}">${b.status}</span>
        <span class="badge ${b.payment}">${b.payment === "paid" ? "Paid" : b.payment === "cod" ? "On arrival" : "Unpaid"}</span>`;
      const actions = `
        <div class="bk-actions">
          ${b.status === "pending" ? `<button class="btn btn-primary btn-sm" data-act="confirm" data-id="${b.id}">Confirm</button>` : ""}
          ${b.status !== "cancelled" ? `<button class="btn btn-outline btn-sm" data-act="complete" data-id="${b.id}">Complete</button>` : ""}
          ${b.status !== "cancelled" ? `<button class="btn btn-danger btn-sm" data-act="cancel" data-id="${b.id}">Cancel</button>` : ""}
        </div>`;
      const info = `
        <div class="bk-main">
          <strong>${esc(b.name)} · ${esc(b.sport)}</strong>
          <small>${Store.prettyDate(b.date)} · ${time} · ${b.duration}h ${b.phone ? "· " + esc(b.phone) : ""} ${b.paymentId ? "· " + esc(b.paymentId.slice(0, 12)) : ""}</small>
        </div>`;
      const amt = `<div class="bk-amt"><strong>${fmt(b.total)}</strong><small>${b.coupon ? "Coupon " + esc(b.coupon) : "No coupon"}</small></div>`;
      return `<div class="booking-row"><div style="display:flex;flex-direction:column;gap:.3rem;">${badges}</div>${info}${amt}${actions}</div>`;
    }).join("");
  }

  function empty(text) {
    return `<div class="empty">${svgIcon("calendar", 34)}<p>${esc(text)}</p></div>`;
  }

  function bindRowActions() {
    $$("[data-act]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const id = btn.dataset.id;
        const act = btn.dataset.act;
        if (act === "confirm") {
          Store.updateBooking(id, { status: "confirmed" });
          toast("Booking confirmed");
        } else if (act === "complete") {
          Store.updateBooking(id, { status: "completed" });
          toast("Marked as completed");
        } else if (act === "cancel") {
          Store.updateBooking(id, { status: "cancelled" });
          toast("Booking cancelled", "bad");
        }
        if (currentView === "overview") renderOverview(); else renderBookings();
      });
    });
  }

  /* ================= SLOT MANAGER ================= */
  function initSlotManager() {
    if (!window._smBound) {
      $("#sm-sport").innerHTML = C.sports.map((s) => `<option value="${esc(s.name)}">${s.emoji} ${esc(s.name)}</option>`).join("");
      const today = Store.todayISO();
      const d = $("#sm-date");
      d.min = today;
      if (!d.value) d.value = today;
      $("#sm-sport").addEventListener("change", () => renderSlotGrid());
      $("#sm-date").addEventListener("change", () => renderSlotGrid());
      window._smBound = true;
    }
    renderSlotGrid();
  }

  function renderSlotGrid() {
    const sport = $("#sm-sport").value;
    const date = $("#sm-date").value;
    const blocks = Store.getBlocks();
    const grid = $("#sm-grid");
    const hours = [];
    for (let h = 6; h < 23; h++) hours.push(h);

    grid.innerHTML = hours.map((h) => {
      const booking = Store.getBookings().find((b) => b.sport === sport && b.date === date && b.status !== "cancelled" && h >= b.hour && h < b.hour + b.duration);
      const block = (blocks[date] || {})[h];
      let cls = "free", label = "Free";
      if (block === "blocked") { cls = "blocked"; label = "Blocked"; }
      else if (block === "maintenance") { cls = "maintenance"; label = "Maint."; }
      else if (booking) { cls = "blocked"; label = "Booked"; }
      return `<button class="sm-slot ${cls}" data-h="${h}" ${booking ? "disabled" : ""}>
        ${Store.hourLabel(h)} – ${Store.hourLabel(h + 1)}<small>${label}</small></button>`;
    }).join("");

    $$(".sm-slot:not([disabled])").forEach((el) => {
      el.addEventListener("click", () => {
        const h = +el.dataset.h;
        const blocks2 = Store.getBlocks();
        const dateMap = blocks2[date] || {};
        const cur = dateMap[h] || "free";
        const next = cur === "free" ? "blocked" : cur === "blocked" ? "maintenance" : null;
        if (next === null) delete dateMap[h];
        else dateMap[h] = next;
        blocks2[date] = dateMap;
        Store.setBlocks(blocks2);
        renderSlotGrid();
      });
    });
  }

  /* ================= PRICING ================= */
  function renderPricing() {
    const overrides = Store.getPricing();
    const rows = C.sports.map((s) => `
      <div class="price-row" data-sport="${esc(s.name)}">
        <div class="pname">${s.emoji} ${esc(s.name)}<small>Default ${fmt(s.price)}/hr</small></div>
        <div><input type="number" min="50" step="10" data-price value="${overrides[s.name] ?? s.price}" /></div>
        <div class="default-price">Price/hr</div>
      </div>`).join("");
    $("#price-rows").innerHTML = rows;

    $("#save-pricing").onclick = () => {
      const newPricing = {};
      $$("#price-rows .price-row").forEach((row) => {
        const val = parseInt(row.querySelector("[data-price]").value, 10);
        if (val > 0) newPricing[row.dataset.sport] = val;
      });
      Store.setPricing(newPricing);
      $("#pricing-status").textContent = "Pricing updated. Changes apply to new bookings immediately.";
      toast("Pricing saved");
    };
    $("#reset-pricing").onclick = () => {
      Store.setPricing({});
      renderPricing();
      $("#pricing-status").textContent = "Pricing reset to defaults.";
      toast("Pricing reset");
    };
  }

  /* ================= SETTINGS ================= */
  function initSettings() {
    $("#save-pin").addEventListener("click", () => {
      const pin = $("#new-pin").value.trim();
      if (!/^\d{4,6}$/.test(pin)) {
        $("#pin-status").textContent = "PIN must be 4–6 digits.";
        return;
      }
      S.adminPin = pin;
      $("#pin-status").textContent = "PIN updated for this session. Edit js/config.js to make it permanent.";
      $("#new-pin").value = "";
      toast("PIN updated");
    });
  }

  /* ================= TABS ================= */
  function initTabs() {
    $$("#booking-tabs .tab").forEach((tab) => {
      tab.addEventListener("click", () => {
        $$("#booking-tabs .tab").forEach((t) => t.classList.remove("active"));
        tab.classList.add("active");
        currentTab = tab.dataset.tab;
        renderBookings();
      });
    });
  }

  function renderAll() {
    renderOverview();
    renderBookings();
    renderSlotGrid();
    renderPricing();
    refreshIcons();
  }

  function initPWA() {
    if ("serviceWorker" in navigator) {
      window.addEventListener("load", () => navigator.serviceWorker.register("sw.js", { scope: "./" }).catch(() => {}), { once: true });
    }
  }

  function boot() {
    initAuth();
    initNav();
    initTabs();
    initSettings();
    initPWA();
    refreshIcons();
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot);
  else boot();
})();
