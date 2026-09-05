/* ============================================================
   MAIN — renders the customer site from CONFIG + CONTENT
   ============================================================ */

(function () {
  "use strict";

  const S = window.SITE;
  const C = window.CONTENT;
  const Store = window.Store;

  /* ---------- tiny helpers ---------- */
  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));
  const esc = (str) =>
    String(str ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  const waLink = (message) => `https://wa.me/${S.whatsappNumber}?text=${encodeURIComponent(message)}`;
  const defaultWaMessage = () => `Hi, I would like to book ${S.turf.name} on a date at a time slot. Please confirm availability.`;

  const fmt = (n) => "₹" + Math.round(n).toLocaleString("en-IN");

  /* ---------- lucide ---------- */
  function svgIcon(name, size = 18) {
    const L = window.lucide;
    if (!L || !L.icons) return "";
    const icon = L.icons[name] || L.icons["circle-check"];
    if (!icon) return "";
    const attrs = { width: size, height: size, "stroke-width": 2, "aria-hidden": "true" };
    try {
      if (typeof icon.toSvg === "function") return icon.toSvg(attrs);
      if (typeof icon === "function") return icon(attrs).outerHTML;
    } catch {
      return "";
    }
    return "";
  }
  function refreshIcons() {
    if (window.lucide && window.lucide.createIcons) {
      try { window.lucide.createIcons(); } catch (e) { /* noop */ }
    }
  }

  /* ---------- toast ---------- */
  function toast(message, type = "ok") {
    const wrap = $("#toast-wrap");
    if (!wrap) return;
    const el = document.createElement("div");
    el.className = `toast ${type}`;
    el.innerHTML = `${svgIcon(type === "ok" ? "circle-check" : "circle-x", 18)}<span>${esc(message)}</span>`;
    wrap.appendChild(el);
    setTimeout(() => {
      el.style.opacity = "0";
      el.style.transition = "opacity .4s";
      setTimeout(() => el.remove(), 400);
    }, 3600);
  }

  /* ---------- apply SITE config to static markup ---------- */
  function applyConfig() {
    const q = S.mapQuery;
    const address = `${S.addressLine1}, ${S.addressLine2}`;
    const dirUrl = `https://www.google.com/maps/dir/?api=1&destination=${encodeURIComponent(q)}`;

    // SEO
    const title = $("#seo-title");
    if (title) title.textContent = S.seo.title;
    const md = document.querySelector('meta[name="description"]');
    if (md) md.setAttribute("content", S.seo.description);
    const mk = document.querySelector('meta[name="keywords"]');
    if (mk) mk.setAttribute("content", S.seo.keywords);

    // Brand
    ["#brand-text", "#footer-mark"].forEach((sel) => {
      const el = $(sel);
      if (el) el.innerHTML = svgIcon("football", 24);
    });
    const brandName = $("#brand-text");
    if (brandName) brandName.innerHTML = `${esc(S.name)}<small>${esc(S.tagline)}</small>`;

    // Hero
    const chip = $(".hero-chip");
    if (chip) chip.innerHTML = `<span class="dot"></span> Open today · ${S.openingTime} – ${S.closingTime}`;
    const heroImg = $(".hero-bg img");
    if (heroImg) { heroImg.src = S.heroImage; heroImg.alt = S.heroImageAlt; }
    const heroH1 = $(".hero h1");
    if (heroH1) {
      if (S.heroHeadline.includes("<br")) {
        const parts = S.heroHeadline.split(/<br\s*\/?>/i);
        heroH1.innerHTML = `${esc(parts[0])}<br /><span>${esc(parts[1])}</span>`;
      } else if (S.heroHeadline.includes(". ")) {
        const idx = S.heroHeadline.lastIndexOf(". ");
        heroH1.innerHTML = `${esc(S.heroHeadline.slice(0, idx + 1))} <span>${esc(S.heroHeadline.slice(idx + 2))}</span>`;
      } else {
        heroH1.innerHTML = esc(S.heroHeadline);
      }
    }
    const lead = $(".hero p.lead");
    if (lead) lead.textContent = S.heroSubtext;

    // Hero stats
    const stats = $$(".hero-stat strong");
    if (stats[0]) stats[0].textContent = S.addressLine2.split(",")[0] + ", " + S.city;
    if (stats[1]) stats[1].textContent = `${S.openingTime} – ${S.closingTime}`;
    const sportsCount = C.sports.length;
    if (stats[2]) stats[2].textContent = `${sportsCount} Sports`;
    const statSubs = $$(".hero-stat small");
    if (statSubs[0]) statSubs[0].textContent = S.landmark || "Central location";
    if (statSubs[1]) statSubs[1].textContent = "Open all days";
    if (statSubs[2]) statSubs[2].textContent = C.sports.map((s) => s.name).slice(0, 2).join(" · ") + " · more";

    // Turf
    const badge = $("#turf-type-badge");
    if (badge) badge.innerHTML = `${svgIcon("football", 16)} ${esc(S.turf.type)}`;
    const turfTitle = $("#turf h2");
    if (turfTitle) turfTitle.innerHTML = `${esc(S.turf.name.split(" Turf")[0] || S.turf.name)} <em>Turf</em>`;
    const tDesc = $("#turf-desc");
    if (tDesc) tDesc.textContent = S.turf.description;
    const tPrice = $("#turf-price");
    if (tPrice) tPrice.textContent = fmt(S.turf.pricePerHour);

    // Turf specs
    const specs = $("#turf-specs");
    if (specs) {
      const rows = [
        { icon: "map-pin", label: "Location", value: S.city },
        { icon: "layout-grid", label: "Turf Size", value: S.turf.size },
        { icon: "users", label: "Capacity", value: S.turf.capacity },
        { icon: "sunrise", label: "Opening", value: S.openingTime },
        { icon: "sunset", label: "Closing", value: S.closingTime },
        { icon: "trophy", label: "Sports", value: C.sports.slice(0, 3).map((s) => s.name).join(", ") + (C.sports.length > 3 ? " +" : "") },
      ];
      specs.innerHTML = rows.map((r) => `<li>${svgIcon(r.icon, 20)}<div><small>${esc(r.label)}</small><strong>${esc(r.value)}</strong></div></li>`).join("");
    }

    // Links
    const links = [
      { id: "#nav-phone", href: `tel:${S.phoneIntl}` },
      { id: "#float-call", href: `tel:${S.phoneIntl}` },
      { id: "#call-channel", href: `tel:${S.phoneIntl}` },
      { id: "#email-channel", href: `mailto:${S.email}` },
      { id: "#ig-channel", href: S.instagram },
      { id: "#wa-social", href: waLink(defaultWaMessage()) },
      { id: "#float-wa", href: waLink(defaultWaMessage()) },
      { id: "#wa-channel", href: waLink(defaultWaMessage()) },
      { id: "#cta-whatsapp", href: waLink(defaultWaMessage()) },
      { id: "#dir-whatsapp", href: waLink(defaultWaMessage()) },
    ];
    links.forEach(({ id, href }) => { const el = $(id); if (el) el.href = href; });

    const phoneTexts = [$("#nav-phone"), $("#call-channel"), $("#float-call")];
    phoneTexts.forEach((el) => { if (el && el.querySelector("small")) el.querySelector("small").textContent = S.phoneDisplay; });
    $("#nav-phone")?.setAttribute("title", `Call ${S.phoneDisplay}`);
    $("#float-call").innerHTML = svgIcon("phone", 26);
    $("#float-wa").innerHTML = `<svg viewBox="0 0 24 24" fill="currentColor"><path d="M17.5 14.4c-.3-.15-1.76-.87-2.03-.97-.27-.1-.47-.15-.67.15-.2.3-.77.96-.94 1.16-.17.2-.35.22-.65.07-.3-.15-1.26-.46-2.4-1.48a9 9 0 0 1-1.66-2.07c-.17-.3-.02-.46.13-.61.13-.13.3-.35.45-.52.15-.17.2-.3.3-.5.1-.2.05-.37-.02-.52-.08-.15-.67-1.62-.92-2.22-.24-.58-.49-.5-.67-.51h-.57c-.2 0-.52.07-.8.37-.27.3-1.04 1.02-1.04 2.5 0 1.47 1.07 2.9 1.22 3.1.15.2 2.1 3.2 5.1 4.49.71.3 1.27.49 1.7.63.72.23 1.37.2 1.88.12.58-.09 1.76-.72 2-1.42.25-.7.25-1.29.18-1.42-.07-.13-.27-.2-.57-.35Z"/><path d="M12.05 2a9.97 9.97 0 0 0-8.5 15.33L2 22l4.83-1.52A9.97 9.97 0 1 0 12.05 2Zm0 18.17a8.15 8.15 0 0 1-4.16-1.14l-.3-.18-2.87.9.9-2.8-.19-.3a8.15 8.15 0 1 1 6.62 3.52Z"/></svg>`;

    // Directions
    const dirBtn = $$("#location .field-row .btn")[0];
    if (dirBtn) dirBtn.href = dirUrl;
    if (dirBtn) dirBtn.setAttribute("target", "_blank");
    const mapIframe = $(".map-frame iframe");
    if (mapIframe) mapIframe.src = S.mapEmbedUrl;

    // Addresses in location card + footer
    const addrCells = $$(".info-row strong");
    if (addrCells[0]) addrCells[0].textContent = S.addressLine1;
    const addrSubs = $$(".info-row .sub");
    if (addrSubs[0]) addrSubs[0].textContent = `${S.addressLine2} · ${S.landmark || ""}`;
    if (addrSubs[1]) addrSubs[1].textContent = "Open all 7 days";
    if (addrSubs[2]) addrSubs[2].textContent = "Call or message anytime";
    const hoursStrong = $$(".info-row strong")[1];
    if (hoursStrong) hoursStrong.textContent = `${S.openingTime} – ${S.closingTime}`;
    const phoneStrong = $$(".info-row strong")[2];
    if (phoneStrong) phoneStrong.textContent = S.phoneDisplay;
    const footContact = $$(".footer-contact li span");
    if (footContact[0]) footContact[0].textContent = `${S.addressLine1}, ${S.addressLine2}`;
    if (footContact[1]) footContact[1].textContent = S.phoneDisplay;
    if (footContact[2]) footContact[2].textContent = S.email;
    if (footContact[3]) footContact[3].textContent = `Open ${S.openingTime} – ${S.closingTime}`;

    // email/ig channel sub texts
    const chEmail = $("#email-channel small"); if (chEmail) chEmail.textContent = S.email;
    const chIg = $("#ig-channel small"); if (chIg) chIg.textContent = S.instagram.replace("https://instagram.com/", "@");

    // Google reviews button
    const gBtn = $("#g-review-btn");
    if (gBtn) gBtn.href = S.googleReviewsUrl;
    if (gBtn) gBtn.setAttribute("target", "_blank");

    // Footer note + year
    const note = $(".footer-about p");
    if (note) note.textContent = C.footerNote;
    const yr = $("#year"); if (yr) yr.textContent = new Date().getFullYear();
  }

  /* ---------- navbar ---------- */
  function buildNav() {
    const navItems = [
      { label: "Home", href: "#home" },
      { label: "Sports", href: "#sports" },
      { label: "Facilities", href: "#facilities" },
      { label: "Pricing", href: "#pricing" },
      { label: "Gallery", href: "#gallery" },
      { label: "Reviews", href: "#reviews" },
      { label: "About", href: "#about" },
      { label: "Contact", href: "#contact" },
    ];
    $("#nav-links").innerHTML = navItems.map((n) => `<li><a href="${n.href}">${n.label}</a></li>`).join("");
    $("#mobile-nav").innerHTML =
      navItems.map((n) => `<a href="${n.href}">${n.label}<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="width:18px;height:18px;"><path d="m9 18 6-6-6-6"/></svg></a>`).join("") +
      `<a href="#booking" class="btn btn-primary">Book Now</a>`;
    $("#footer-links").innerHTML = navItems.map((n) => `<li><a href="${n.href}">${n.label}</a></li>`).join("");
    $("#footer-sports").innerHTML = C.sports.slice(0, 6).map((s) => `<li><a href="#booking">${s.name}</a></li>`).join("");

    const burger = $("#nav-burger");
    const mobileNav = $("#mobile-nav");
    const toggle = (force) => {
      const open = force !== undefined ? force : !mobileNav.classList.contains("open");
      mobileNav.classList.toggle("open", open);
      burger.setAttribute("aria-expanded", open);
      burger.innerHTML = open ? svgIcon("x", 22) : svgIcon("menu", 22);
      document.body.style.overflow = open ? "hidden" : "";
    };
    burger.addEventListener("click", () => toggle());
    mobileNav.addEventListener("click", (e) => { if (e.target.closest("a")) toggle(false); });
    burger.innerHTML = svgIcon("menu", 22);

    window.addEventListener("scroll", () => {
      $("#nav").classList.toggle("scrolled", window.scrollY > 30);
    }, { passive: true });
    $("#nav").classList.toggle("scrolled", window.scrollY > 30);

    // active link highlighting
    const sections = navItems.map((n) => $(n.href)).filter(Boolean);
    const links = $$("#nav-links a");
    const io = new IntersectionObserver(
      (entries) => {
        entries.forEach((en) => {
          if (en.isIntersecting) {
            links.forEach((a) => a.classList.toggle("active", a.getAttribute("href") === "#" + en.target.id));
          }
        });
      },
      { rootMargin: "-45% 0px -50% 0px" }
    );
    sections.forEach((s) => io.observe(s));
  }

  /* ---------- ticker ---------- */
  function buildTicker() {
    const items = [
      "Open Today 6:00 AM – 11:00 PM",
      "6 Sports Under One Roof",
      "Free Parking",
      "Floodlit Night Games",
      "Online Booking & Payment",
      "Instant WhatsApp Confirmation",
    ];
    const row = items.map((t) => `<span>${esc(t)}<i>●</i></span>`).join("");
    $("#ticker-track").innerHTML = row + row; // duplicate for seamless loop
  }

  /* ---------- sports ---------- */
  function buildSports() {
    $("#sports-grid").innerHTML = C.sports
      .map(
        (s, i) => `
        <article class="card sport-card reveal reveal-d${i % 3}">
          <div class="sport-img">
            <span class="sport-emoji">${s.emoji}</span>
            <img src="${s.img}" alt="${esc(s.alt)}" loading="lazy" />
          </div>
          <div class="sport-body">
            <h3>${esc(s.name)}<span class="sport-price">${fmt(s.price)}<small>/hr</small></span></h3>
            <p>${esc(s.desc)}</p>
            <a href="#booking" class="btn btn-outline btn-sm" data-sport="${esc(s.name)}">Book ${esc(s.name)}</a>
          </div>
        </article>`,
      )
      .join("");
    $$("#sports-grid [data-sport]").forEach((btn) => {
      btn.addEventListener("click", () => { selectSport(btn.dataset.sport); });
    });
  }

  /* ---------- facilities ---------- */
  function buildFacilities() {
    const iconMap = {
      floodlight: "floodlight",
      parking: "square-parking",
      shirt: "shirt",
      shower: "shower-head",
      droplet: "droplets",
      sofa: "armchair",
      cctv: "cctv",
      wifi: "wifi",
      football: "football",
      medkit: "cross",
    };
    $("#facilities-grid").innerHTML = C.facilities
      .map(
        (f, i) => `
        <div class="card facility-card reveal reveal-d${i % 4}">
          <div class="facility-icon">${svgIcon(iconMap[f.icon] || f.icon, 28)}</div>
          <h3>${esc(f.title)}</h3>
          <p>${esc(f.desc)}</p>
        </div>`,
      )
      .join("");
  }

  /* ---------- pricing ---------- */
  function buildPricing() {
    $("#pricing-grid").innerHTML = S.pricing
      .map(
        (p, i) => `
        <div class="card pricing-card reveal reveal-d${i % 3} ${p.popular ? "popular" : ""}">
          ${p.popular ? '<span class="popular-tag">Most Popular</span>' : ""}
          <h3>${esc(p.name)}</h3>
          <div class="pricing-time">${svgIcon("clock", 16)} ${esc(p.time)}</div>
          <div class="pricing-price">${fmt(p.price)}<small> / hour</small></div>
          <ul>${p.perks.map((perk) => `<li>${svgIcon("circle-check", 18)}${esc(perk)}</li>`).join("")}</ul>
          <a href="#booking" class="btn ${p.popular ? "btn-primary" : "btn-outline"}">Book This Slot</a>
        </div>`,
      )
      .join("");
  }

  /* ---------- offers ---------- */
  function buildOffers() {
    $("#offers-grid").innerHTML = C.offers
      .map(
        (o, i) => `
        <div class="offer-card reveal reveal-d${i % 3}">
          <span class="offer-tag">${esc(o.tag)}</span>
          <h3>${esc(o.title)}</h3>
          <p>${esc(o.desc)}</p>
          <div class="offer-meta">${svgIcon("calendar-check", 15)} ${esc(o.validity)}</div>
          ${o.code ? `<span class="offer-code">CODE · ${esc(o.code)}</span>` : ""}
          <a href="#booking" class="btn btn-outline btn-sm" style="margin-top: 0.8rem;">Claim Offer</a>
        </div>`,
      )
      .join("");
  }

  /* ---------- gallery + lightbox ---------- */
  let lbIndex = 0;
  function buildGallery() {
    $("#gallery-grid").innerHTML = C.gallery
      .map(
        (g, i) => `
        <div class="gallery-item reveal reveal-d${i % 4}" data-i="${i}" role="button" tabindex="0" aria-label="View photo: ${esc(g.alt)}">
          <img src="${g.src}" alt="${esc(g.alt)}" loading="lazy" />
          <span class="gallery-zoom">${svgIcon("maximize-2", 18)}</span>
          <span class="gallery-tag">${esc(g.tag)}</span>
        </div>`,
      )
      .join("");
    const open = (i) => {
      lbIndex = (i + C.gallery.length) % C.gallery.length;
      const g = C.gallery[lbIndex];
      $("#lb-img").src = g.src;
      $("#lb-img").alt = g.alt;
      $("#lb-caption").textContent = g.alt;
      $("#lightbox").classList.add("open");
      document.body.style.overflow = "hidden";
    };
    $$(".gallery-item").forEach((el) => {
      const i = +el.dataset.i;
      el.addEventListener("click", () => open(i));
      el.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); open(i); } });
    });
    $("#lb-close").addEventListener("click", () => {
      $("#lightbox").classList.remove("open");
      document.body.style.overflow = "";
    });
    $("#lb-prev").addEventListener("click", () => open(lbIndex - 1));
    $("#lb-next").addEventListener("click", () => open(lbIndex + 1));
    $("#lightbox").addEventListener("click", (e) => { if (e.target.id === "lightbox") { $("#lightbox").classList.remove("open"); document.body.style.overflow = ""; } });
    document.addEventListener("keydown", (e) => {
      if (!$("#lightbox").classList.contains("open")) return;
      if (e.key === "Escape") { $("#lb-close").click(); }
      if (e.key === "ArrowLeft") open(lbIndex - 1);
      if (e.key === "ArrowRight") open(lbIndex + 1);
    });
  }

  /* ---------- reviews ---------- */
  const starSvg = () => `<svg viewBox="0 0 24 24"><path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/></svg>`;
  function buildReviews() {
    const stars = (n) => starSvg().repeat(n);
    $("#rating-num").textContent = C.averageRating.toFixed(1);
    $("#rating-stars").innerHTML = stars(5);
    $("#rating-meta").textContent = `Based on ${C.reviewCount} reviews`;
    $("#reviews-grid").innerHTML = C.reviews
      .map(
        (r, i) => `
        <div class="card review-card reveal reveal-d${i % 3}">
          <div class="stars-row">${stars(r.rating)}</div>
          <p>“${esc(r.text)}”</p>
          <div class="review-author">
            <span class="avatar">${esc(r.name.trim()[0])}</span>
            <div><strong>${esc(r.name)}</strong><small>${esc(r.date)}</small></div>
            <span class="verified-badge">${svgIcon("badge-check", 13)} Verified</span>
          </div>
        </div>`,
      )
      .join("");
  }

  /* ---------- about ---------- */
  function buildAbout() {
    $("#about-p1").textContent = C.about.paragraphs[0];
    $("#about-p2").textContent = C.about.paragraphs[1] || "";
    $("#about-highlights").innerHTML = C.about.highlights
      .map((h) => `<li>${svgIcon("circle-check", 20)}${esc(h)}</li>`)
      .join("");
  }

  /* ---------- booking widget ---------- */
  const state = {
    sport: null,
    date: null,
    duration: 1,
    hour: null,
    coupon: null,
    price: null,
  };

  function selectedSport() { return C.sports.find((s) => s.name === state.sport); }

  function selectSport(name) {
    const sport = C.sports.find((s) => s.name === name);
    if (!sport) return;
    state.sport = sport.name;
    $("#bk-sport").value = sport.name;
    renderSlots();
    document.getElementById("booking").scrollIntoView({ behavior: "smooth" });
  }

  function initBooking() {
    // sport select
    $("#bk-sport").innerHTML = C.sports
      .map((s) => `<option value="${esc(s.name)}">${s.emoji} ${esc(s.name)} — ${fmt(s.price)}/hr</option>`)
      .join("");
    $("#bk-sport").value = C.sports[0].name;
    state.sport = C.sports[0].name;

    // date input
    const dateInput = $("#bk-date");
    const today = Store.todayISO();
    dateInput.min = today;
    dateInput.max = Store.addDays(today, 30);
    dateInput.value = today;
    state.date = today;

    // duration chips
    $$("#bk-duration .chip").forEach((chip) => {
      chip.addEventListener("click", () => {
        $$("#bk-duration .chip").forEach((c) => c.classList.remove("active"));
        chip.classList.add("active");
        state.duration = +chip.dataset.hours;
        state.hour = null;
        renderSlots();
      });
    });
    $("#bk-duration .chip").classList.add("active");

    // events
    $("#bk-sport").addEventListener("change", (e) => {
      state.sport = e.target.value;
      state.hour = null;
      state.coupon = null;
      $("#coupon-input").value = "";
      $("#coupon-msg").textContent = "";
      renderSlots();
    });
    dateInput.addEventListener("change", (e) => {
      state.date = e.target.value;
      state.hour = null;
      renderSlots();
    });

    // coupon
    $("#coupon-apply").addEventListener("click", () => {
      const code = $("#coupon-input").value;
      if (!code) return;
      const found = S.coupons.find((c) => c.code.toUpperCase() === code.trim().toUpperCase());
      const msg = $("#coupon-msg");
      if (found) {
        state.coupon = found.code;
        msg.textContent = `✓ ${found.label} applied`;
        msg.className = "coupon-msg ok";
      } else {
        state.coupon = null;
        msg.textContent = "✗ Invalid coupon code";
        msg.className = "coupon-msg bad";
      }
      renderSummary();
    });

    renderSlots();
    renderSummary();
  }

  function renderSlots() {
    if (!state.sport || !state.date) return;
    const hours = [];
    const dur = state.duration;
    for (let h = 6; h <= 23 - dur; h++) hours.push(h);

    const container = $("#bk-slots");
    if (!hours.length) {
      container.innerHTML = `<p style="grid-column:1/-1;color:var(--text-dim);">No slots left for this day.</p>`;
      return;
    }
    container.innerHTML = hours
      .map((h) => {
        const status = Store.slotStatus(state.sport, state.date, h);
        const cls = status === "free" ? "free" : status;
        const timeLabel = `${Store.hourLabel(h)} – ${Store.hourLabel(h + dur)}`;
        return `<button class="slot ${cls}${state.hour === h ? " selected" : ""}" data-h="${h}" ${status !== "free" ? "disabled" : ""}>
          ${timeLabel}${status === "free" ? "<small>Available</small>" : status === "booked" ? "<small>Booked</small>" : "<small>Maintenance</small>"}
        </button>`;
      })
      .join("");
    $$("#bk-slots .slot.free").forEach((el) => {
      el.addEventListener("click", () => {
        $$("#bk-slots .slot").forEach((s) => s.classList.remove("selected"));
        el.classList.add("selected");
        state.hour = +el.dataset.h;
        renderSummary();
      });
    });
  }

  function renderSummary() {
    const sport = selectedSport();
    if (!sport) return;
    const price = Store.computePrice(state.sport, state.duration, state.coupon);
    state.price = price;

    $("#sum-sport").textContent = sport.emoji + " " + sport.name;
    $("#sum-date").textContent = Store.prettyDate(state.date);
    $("#sum-time").textContent = state.hour != null ? `${Store.hourLabel(state.hour)} – ${Store.hourLabel(state.hour + state.duration)}` : "—";
    $("#sum-duration").textContent = state.duration + (state.duration > 1 ? " hours" : " hour");
    $("#sum-price").textContent = fmt(price.base);
    $("#sum-discount").textContent = price.discount ? `- ${fmt(price.discount)}` : "₹0";
    $("#sum-total").textContent = fmt(price.total);

    const proceed = $("#bk-proceed");
    proceed.disabled = state.hour == null;
  }

  /* ---------- booking wizard modal ---------- */
  let pending = null; // holds booking draft during wizard

  function openModal(step) {
    const modal = $("#booking-modal");
    modal.classList.add("open");
    document.body.style.overflow = "hidden";
    setStep(step);
  }
  function closeModal() {
    $("#booking-modal").classList.remove("open");
    document.body.style.overflow = "";
  }
  function setStep(n) {
    $$("#bm-steps .step").forEach((s, i) => s.classList.toggle("active", i <= n));
    renderStep(n);
  }

  function renderStep(n) {
    const body = $("#bm-body");
    $("#bm-title").textContent = ["Your details", "Review booking", "Secure payment", "Booking confirmed"][n];

    if (n === 0) {
      body.innerHTML = `
        <div class="field-row">
          <div class="field"><label for="bm-name">Full name</label><input id="bm-name" placeholder="Player name" /></div>
          <div class="field"><label for="bm-phone">Phone (WhatsApp)</label><input id="bm-phone" type="tel" placeholder="+91 98765 43210" /></div>
        </div>
        <div class="field"><label for="bm-email">Email</label><input id="bm-email" type="email" placeholder="you@email.com" /></div>
        <div class="field"><label for="bm-notes">Notes (optional)</label><textarea id="bm-notes" rows="2" placeholder="Anything we should know?"></textarea></div>
        <button class="btn btn-primary btn-block" id="bm-next0">Continue to Review</button>
        <p class="pay-note">No account needed. Your slot is held while you complete booking.</p>`;
      $("#bm-phone").addEventListener("input", (e) => { e.target.value = e.target.value.replace(/[^\d+\s-]/g, ""); });
      $("#bm-next0").addEventListener("click", () => {
        const name = $("#bm-name").value.trim();
        const phone = $("#bm-phone").value.replace(/\D/g, "");
        const email = $("#bm-email").value.trim();
        if (name.length < 2) return toast("Please enter your name", "bad");
        if (phone.length < 10) return toast("Please enter a valid phone number", "bad");
        if (email && !/^\S+@\S+\.\S+$/.test(email)) return toast("Please enter a valid email", "bad");
        pending = { ...pending, name, phone, email: email || "—", notes: $("#bm-notes").value.trim() };
        setStep(1);
      });
      const nameEl = $("#bm-name");
      if (nameEl) setTimeout(() => nameEl.focus(), 60);
    }

    if (n === 1) {
      const p = pending.price;
      body.innerHTML = `
        <div class="confirm-details">
          <div class="summary-line"><small>Sport</small><strong>${esc(pending.sport)}</strong></div>
          <div class="summary-line"><small>Date</small><strong>${Store.prettyDate(pending.date)}</strong></div>
          <div class="summary-line"><small>Time</small><strong>${Store.hourLabel(pending.hour)} – ${Store.hourLabel(pending.hour + pending.duration)}</strong></div>
          <div class="summary-line"><small>Duration</small><strong>${pending.duration} hour${pending.duration > 1 ? "s" : ""}</strong></div>
          <div class="summary-line"><small>Amount</small><strong>${fmt(p.base)}</strong></div>
          ${p.discount ? `<div class="summary-line discount-line"><small>Discount</small><strong>- ${fmt(p.discount)}</strong></div>` : ""}
          <div class="summary-line summary-total"><small>Total</small><strong>${fmt(p.total)}</strong></div>
        </div>
        <div class="field-row">
          <button class="btn btn-outline" id="bm-back1">Back</button>
          <button class="btn btn-primary" id="bm-pay">Pay ${fmt(p.total)}</button>
        </div>
        <p class="pay-note">Secure payment via Razorpay · UPI, Cards, Netbanking & Wallets</p>`;
      $("#bm-back1").addEventListener("click", () => setStep(0));
      $("#bm-pay").addEventListener("click", () => {
        if (window.location.protocol === "file:" && !S.razorpay.keyId.startsWith("rzp_live")) {
          toast("Razorpay needs https — running in demo mode", "bad");
          setStep(2);
          return;
        }
        setStep(2);
        startPayment();
      });
    }

    if (n === 2) {
      body.innerHTML = `
        <div class="pay-methods"><span>UPI</span><span>Credit / Debit Card</span><span>Net Banking</span><span>Wallets</span></div>
        <div style="text-align:center; padding: 1.6rem 0;">
          <div class="confirm-icon" style="width:64px;height:64px;margin-bottom:1rem;">${svgIcon("lock", 30)}</div>
          <p style="color:var(--text-dim); margin-bottom:1.4rem;">A secure payment window will open to pay <strong style="color:var(--text)">${fmt(pending.price.total)}</strong>.<br />If it doesn't open automatically, tap the button below.</p>
        </div>
        <button class="btn btn-primary btn-block" id="bm-payagain">Open Payment ${fmt(pending.price.total)}</button>
        <p class="pay-note" id="bm-paystatus">Waiting for payment…</p>`;
      $("#bm-payagain").addEventListener("click", () => startPayment());
    }

    if (n === 3) {
      confirmBooking();
    }
  }

  /* ---------- payment (Razorpay) ---------- */
  let paymentBusy = false;
  function startPayment() {
    if (paymentBusy) return;
    const cfg = S.razorpay;
    const total = pending.price.total;
    const statusEl = $("#bm-paystatus");

    // Demo mode when no live key is configured
    if (!cfg.keyId || cfg.keyId.startsWith("rzp_test_xxxxxxxx")) {
      paymentBusy = true;
      if (statusEl) statusEl.textContent = "Demo mode: payment simulated…";
      setTimeout(() => {
        paymentBusy = false;
        completeBooking("cod");
        toast("Demo booking created (no real payment)");
      }, 900);
      return;
    }

    if (typeof window.Razorpay === "undefined") {
      // fallback if checkout script blocked
      setTimeout(() => {
        paymentBusy = false;
        completeBooking("cod");
        toast("Payment script unavailable — booking confirmed on arrival");
      }, 600);
      return;
    }

    paymentBusy = true;
    const rzp = new window.Razorpay({
      key: cfg.keyId,
      amount: total * 100,
      currency: cfg.currency,
      name: cfg.name,
      description: `${pending.sport} · ${pending.date} · ${Store.hourLabel(pending.hour)}`,
      image: undefined,
      prefill: { name: pending.name, email: pending.email, contact: pending.phone },
      theme: { color: cfg.themeColor },
      handler: function (response) {
        paymentBusy = false;
        completeBooking("paid", response.razorpay_payment_id);
        toast("Payment successful 🎉");
      },
      modal: {
        ondismiss: function () {
          paymentBusy = false;
          if (statusEl) statusEl.textContent = "Payment cancelled. You can retry.";
          toast("Payment cancelled", "bad");
        },
      },
    });
    rzp.open();
  }

  function completeBooking(payment, paymentId) {
    const data = {
      sport: pending.sport,
      date: pending.date,
      hour: pending.hour,
      duration: pending.duration,
      name: pending.name,
      phone: pending.phone,
      email: pending.email,
      notes: pending.notes,
      unit: pending.price.unit,
      base: pending.price.base,
      discount: pending.price.discount,
      total: pending.price.total,
      coupon: pending.price.coupon ? pending.price.coupon.code : null,
      status: "confirmed",
      payment,
      paymentId: paymentId || null,
    };
    const booking = Store.addBooking(data);
    pending.bookingId = booking.id;
    pending.paid = payment === "paid";
    renderStep(3);
    refreshAvailability();
  }

  /* ---------- confirmation ---------- */
  function confirmBooking() {
    const b = pending;
    const body = $("#bm-body");
    const details = `
      <div style="text-align:center;">
        <div class="confirm-icon">${b.paid ? svgIcon("badge-check", 40) : svgIcon("clock", 40)}</div>
        <h3 style="font-size:1.5rem;">Booking Confirmed!</h3>
        <p style="color:var(--text-dim); font-size:0.92rem; margin:0.3rem 0 0.6rem;">${b.paid ? "Payment received. See you on the turf!" : "Pay on arrival. See you on the turf!"}</p>
        <span class="booking-id-pill">${svgIcon("ticket", 15)} ${b.bookingId}</span>
      </div>
      <div class="confirm-details">
        <div class="summary-line"><small>Turf</small><strong>${esc(S.turf.name)}</strong></div>
        <div class="summary-line"><small>Sport</small><strong>${esc(b.sport)}</strong></div>
        <div class="summary-line"><small>Date</small><strong>${Store.prettyDate(b.date)}</strong></div>
        <div class="summary-line"><small>Time</small><strong>${Store.hourLabel(b.hour)} – ${Store.hourLabel(b.hour + b.duration)}</strong></div>
        <div class="summary-line"><small>Amount</small><strong>${fmt(b.price.total)}</strong></div>
        <div class="summary-line"><small>Payment</small><strong>${b.paid ? "Paid · Online" : "Pay on Arrival"}</strong></div>
      </div>
      <div class="confirm-actions">
        <button class="btn btn-primary" id="bm-invoice">${svgIcon("download", 18)} Download Invoice</button>
        <a class="btn btn-wa" id="bm-wa" target="_blank" rel="noopener">${svgIcon("message-circle", 18)} Share on WhatsApp</a>
        <button class="btn btn-outline" id="bm-done" style="grid-column:1/-1;">Book Another Slot</button>
      </div>`;
    body.innerHTML = details;

    const shareMsg = `Hi ${S.name}!\nI just booked a slot online.\n\nBooking ID: ${b.bookingId}\nSport: ${b.sport}\nDate: ${Store.prettyDate(b.date)}\nTime: ${Store.hourLabel(b.hour)} – ${Store.hourLabel(b.hour + b.duration)}\nAmount: ${fmt(b.price.total)}\nPayment: ${b.paid ? "Paid online" : "Pay on arrival"}\n\nPlease confirm. Thank you!`;
    $("#bm-wa").href = waLink(shareMsg);

    $("#bm-invoice").addEventListener("click", () => downloadInvoice(b));
    $("#bm-done").addEventListener("click", () => {
      closeModal();
      state.hour = null;
      state.coupon = null;
      $("#coupon-input").value = "";
      $("#coupon-msg").textContent = "";
      renderSlots();
      renderSummary();
    });
  }

  function downloadInvoice(b) {
    const rows = [
      ["Turf", S.turf.name],
      ["Sport", b.sport],
      ["Date", Store.prettyDate(b.date)],
      ["Time", `${Store.hourLabel(b.hour)} – ${Store.hourLabel(b.hour + b.duration)}`],
      ["Duration", `${b.duration} hour${b.duration > 1 ? "s" : ""}`],
      ["Booking ID", b.bookingId],
      ["Name", b.name],
      ["Phone", b.phone],
      ["Email", b.email],
      ["Amount", fmt(b.price.base)],
      ["Discount", b.price.discount ? `- ${fmt(b.price.discount)}` : "₹0"],
      ["Total", fmt(b.price.total)],
      ["Payment", b.paid ? "Paid online" : "Pay on arrival"],
    ];
    const html = `<!doctype html><html><head><meta charset="utf-8"><title>Invoice ${b.bookingId}</title>
      <style>body{font-family:Arial,sans-serif;max-width:640px;margin:2rem auto;padding:0 1rem;color:#111}
      h1{font-size:1.5rem}.head{display:flex;justify-content:space-between;border-bottom:2px solid #16a34a;padding-bottom:1rem;margin-bottom:1.5rem}
      table{width:100%;border-collapse:collapse}td{padding:.55rem .2rem;border-bottom:1px solid #eee}td:last-child{text-align:right;font-weight:600}
      .tot td{font-size:1.05rem;font-weight:700;color:#16a34a}.muted{color:#777;font-size:.85rem}</style></head><body>
      <div class="head"><div><h1>${esc(S.name)}</h1><div class="muted">${esc(S.addressLine1)}, ${esc(S.addressLine2)}</div><div class="muted">${esc(S.phoneDisplay)} · ${esc(S.email)}</div></div>
      <div><h1>Invoice</h1><div class="muted">${b.bookingId}</div><div class="muted">${new Date().toLocaleDateString("en-IN")}</div></div></div>
      <table>${rows.map((r) => `<tr><td>${esc(r[0])}</td><td>${esc(r[1])}</td></tr>`).join("")}
      <tr class="tot"><td>PAYABLE</td><td>${fmt(b.price.total)}</td></tr></table>
      <p class="muted" style="margin-top:1.5rem">Thank you for booking with ${esc(S.name)}. Present this invoice at the reception.</p>
      </body></html>`;
    const blob = new Blob([html], { type: "text/html" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `Invoice-${b.bookingId}.html`;
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 2000);
  }

  function refreshAvailability() {
    renderSlots();
    renderSummary();
  }

  /* ---------- modal open from summary ---------- */
  function initWizard() {
    $("#bk-proceed").addEventListener("click", () => {
      if (state.hour == null) return toast("Please pick an available slot", "bad");
      if (Store.slotStatus(state.sport, state.date, state.hour) !== "free") {
        return toast("That slot was just taken. Pick another.", "bad");
      }
      pending = {
        sport: state.sport,
        date: state.date,
        hour: state.hour,
        duration: state.duration,
        price: Store.computePrice(state.sport, state.duration, state.coupon),
      };
      openModal(0);
    });
    $("#bm-close").addEventListener("click", closeModal);
    $("#booking-modal").addEventListener("click", (e) => {
      if (e.target.id === "booking-modal") closeModal();
    });
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && $("#booking-modal").classList.contains("open")) closeModal();
    });
  }

  /* ---------- contact form ---------- */
  function initContact() {
    $("#contact-form").addEventListener("submit", (e) => {
      e.preventDefault();
      const name = $("#cf-name").value.trim();
      const phone = $("#cf-phone").value.trim();
      const email = $("#cf-email").value.trim();
      const message = $("#cf-message").value.trim();
      const msg = $("#cf-msg");

      if (!name || !phone || !message) {
        msg.textContent = "Please fill in name, phone and message.";
        msg.className = "form-msg show bad";
        return;
      }
      const text = `Hi ${S.name}!\n\nName: ${name}\nPhone: ${phone}\nEmail: ${email}\n\n${message}`;
      msg.textContent = "Opening WhatsApp with your message…";
      msg.className = "form-msg show ok";
      window.open(waLink(text), "_blank");
      e.target.reset();
      setTimeout(() => msg.classList.remove("show"), 5000);
    });
  }

  /* ---------- reveal on scroll ---------- */
  function initReveal() {
    const io = new IntersectionObserver(
      (entries) => entries.forEach((en) => { if (en.isIntersecting) { en.target.classList.add("visible"); io.unobserve(en.target); } }),
      { threshold: 0.12 }
    );
    $$(".reveal").forEach((el) => io.observe(el));
  }

  /* ---------- PWA: offline, install prompt ---------- */
  let deferredPrompt = null;

  function installBanner(title) {
    const existing = $("#install-banner");
    if (existing) existing.remove();
    const el = document.createElement("div");
    el.className = "install-banner";
    el.id = "install-banner";
    el.innerHTML = `
      <span class="install-logo">${svgIcon("football", 22)}</span>
      <div style="flex:1;"><strong style="display:block;">Install GreenZone Arena</strong><small style="color:var(--text-dim);">${esc(title)}</small></div>
      <button class="btn btn-primary btn-sm" id="install-do">Install</button>
      <button class="install-close" id="install-dismiss" aria-label="Dismiss"></button>`;
    document.body.appendChild(el);
    $("#install-dismiss").innerHTML = svgIcon("x", 16);
    $("#install-dismiss").addEventListener("click", () => {
      el.remove();
      if (el.dataset.installable) {
        try { localStorage.setItem("gza_ios_hint", "1"); } catch (e) {}
      }
    });
    $("#install-do").addEventListener("click", async () => {
      if (deferredPrompt) {
        deferredPrompt.prompt();
        const { outcome } = await deferredPrompt.userChoice;
        if (outcome === "accepted") el.remove();
        deferredPrompt = null;
        try { localStorage.setItem("gza_ios_hint", "1"); } catch (e) {}
      } else {
        try { localStorage.setItem("gza_ios_hint", "1"); } catch (e) {}
        toast("On iPhone, tap Share → Add to Home Screen");
      }
    });
    return el;
  }

  function initPWA() {
    if ("serviceWorker" in navigator) {
      window.addEventListener(
        "load",
        () => navigator.serviceWorker.register("sw.js", { scope: "./" }).catch(() => {}),
        { once: true },
      );
    }

    const isIOS = /iphone|ipad|ipod/i.test(navigator.userAgent) && !window.MSStream && !window.navigator.standalone;

    const bookingNear = () => {
      const b = document.getElementById("booking");
      return b && b.getBoundingClientRect().top < window.innerHeight * 0.8;
    };

    // Android / Chrome — hold the install prompt, show a banner as user reaches booking
    if (window.matchMedia && window.matchMedia("(display-mode: browser)").matches) {
      window.addEventListener("beforeinstallprompt", (e) => {
        e.preventDefault();
        deferredPrompt = e;
        const show = () => {
          if (!deferredPrompt || !bookingNear()) return;
          window.removeEventListener("scroll", show);
          const banner = installBanner("Open instantly from your home screen");
          banner.dataset.installable = "1";
          deferredPrompt = null;
        };
        window.addEventListener("scroll", show, { passive: true });
        show();
      });
    }

    // iOS — no install prompt event; guide to Add to Home Screen once
    if (isIOS) {
      const shown = (() => { try { return localStorage.getItem("gza_ios_hint") === "1"; } catch (e) { return false; } })();
      const show = () => {
        if (shown || window.navigator.standalone || !bookingNear()) return;
        window.removeEventListener("scroll", show);
        const banner = installBanner("Tap Share, then “Add to Home Screen”");
        banner.dataset.installable = "1";
      };
      window.addEventListener("scroll", show, { passive: true });
    }

    window.addEventListener("appinstalled", () => {
      const b = $("#install-banner");
      if (b) b.remove();
      toast("Installed! Find GreenZone on your home screen 🎉");
    });
  }

  /* ---------- boot ---------- */
  function boot() {
    applyConfig();
    buildNav();
    buildTicker();
    buildSports();
    buildFacilities();
    buildPricing();
    buildOffers();
    buildGallery();
    buildReviews();
    buildAbout();
    initBooking();
    initWizard();
    initContact();
    initReveal();
    initPWA();
    refreshIcons();
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot);
  else boot();
})();
