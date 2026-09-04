/* ============================================================
   STORE — bookings, slots and availability logic
   ------------------------------------------------------------
   Data lives in localStorage so the site works with zero backend.
   For production, replace these functions with API calls (see README).
   ============================================================ */

window.Store = (() => {
  const KEYS = {
    bookings: "gza_bookings",
    blocks: "gza_blocks",       // { "2026-08-10": { hour: "maintenance"|"blocked" } }
    pricing: "gza_pricing",     // overrides set from admin dashboard
  };

  const read = (key, fallback) => {
    try {
      const raw = localStorage.getItem(key);
      return raw ? JSON.parse(raw) : fallback;
    } catch {
      return fallback;
    }
  };
  const write = (key, value) => {
    try {
      localStorage.setItem(key, JSON.stringify(value));
    } catch (e) {
      console.warn("Storage unavailable:", e);
    }
  };

  /* ---------- helpers ---------- */
  const pad = (n) => String(n).padStart(2, "0");
  const hourLabel = (h) => {
    const ampm = h >= 12 ? "PM" : "AM";
    const h12 = h % 12 === 0 ? 12 : h % 12;
    return `${h12} ${ampm}`;
  };
  const todayISO = () => {
    const d = new Date();
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
  };

  const makeId = () => "GZA-" + Date.now().toString(36).toUpperCase() + Math.random().toString(36).slice(2, 5).toUpperCase();

  const fmtMoney = (n) => "₹" + Math.round(n).toLocaleString("en-IN");

  /* ---------- date helpers ---------- */
  function addDays(dateISO, days) {
    const d = new Date(dateISO + "T00:00:00");
    d.setDate(d.getDate() + days);
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
  }

  function nextDays(count) {
    const out = [];
    for (let i = 0; i < count; i++) out.push(addDays(todayISO(), i));
    return out;
  }

  function prettyDate(dateISO) {
    const d = new Date(dateISO + "T00:00:00");
    return d.toLocaleDateString("en-IN", { weekday: "short", day: "numeric", month: "short", year: "numeric" });
  }

  /* ---------- bookings CRUD ---------- */
  const getBookings = () => read(KEYS.bookings, []);
  const setBookings = (list) => write(KEYS.bookings, list);

  const getBlocks = () => read(KEYS.blocks, {});
  const setBlocks = (blocks) => write(KEYS.blocks, blocks);

  const getPricing = () => read(KEYS.pricing, {});
  const setPricing = (p) => write(KEYS.pricing, p);

  function addBooking(data) {
    const list = getBookings();
    const booking = {
      id: makeId(),
      createdAt: new Date().toISOString(),
      status: "pending", // pending -> confirmed -> completed | cancelled
      payment: "unpaid", // unpaid -> paid
      ...data,
    };
    list.push(booking);
    setBookings(list);
    return booking;
  }

  function updateBooking(id, patch) {
    const list = getBookings().map((b) => (b.id === id ? { ...b, ...patch } : b));
    setBookings(list);
    return list.find((b) => b.id === id);
  }

  function findBooking(id) {
    return getBookings().find((b) => b.id === id);
  }

  /* ---------- availability ---------- */
  // Returns slot status for a given sport/date/hour.
  function slotStatus(sport, date, hour) {
    const blocks = getBlocks();
    const block = (blocks[date] || {})[hour];
    if (block === "maintenance") return "maintenance";
    if (block === "blocked") return "booked"; // owner blocked it, treat as unavailable

    const clash = getBookings().some(
      (b) =>
        b.sport === sport &&
        b.date === date &&
        b.status !== "cancelled" &&
        hour >= b.hour &&
        hour < b.hour + b.duration,
    );
    return clash ? "booked" : "free";
  }

  function availableHours(sport, date) {
    const hours = [];
    for (let h = 6; h < 23; h++) hours.push(h);
    return hours.filter((h) => slotStatus(sport, date, h) === "free");
  }

  /* ---------- pricing ---------- */
  // Base price from content sports, optionally overridden per sport in admin.
  function basePrice(sportName) {
    const over = getPricing()[sportName];
    if (over != null) return over;
    const s = (window.CONTENT?.sports || []).find((x) => x.name === sportName);
    return s ? s.price : 800;
  }

  function computePrice(sportName, duration, couponCode) {
    const unit = basePrice(sportName);
    const base = unit * duration;
    let discount = 0;
    let coupon = null;

    if (couponCode) {
      const list = (window.SITE?.coupons || []).find(
        (c) => c.code.toUpperCase() === couponCode.trim().toUpperCase(),
      );
      if (list) {
        coupon = list;
        discount = Math.round((base * list.discountPercent) / 100);
      }
    }
    return { unit, base, discount, total: base - discount, coupon };
  }

  /* ---------- stats (admin) ---------- */
  function stats() {
    const list = getBookings();
    const today = todayISO();
    const todays = list.filter((b) => b.date === today && b.status !== "cancelled");
    const paidTodays = todays.filter((b) => b.payment === "paid" || b.payment === "cod");
    const revenue = paidTodays.reduce((s, b) => s + b.total, 0);

    const customers = new Set(list.map((b) => b.phone)).size;

    // available slots today = number of free slots across sports
    const sports = (window.CONTENT?.sports || []).filter((s) => s.bookable !== false);
    let available = 0;
    sports.forEach((s) => (available += availableHours(s.name, today).length));

    return {
      todayBookings: todays.length,
      todayRevenue: revenue,
      availableSlots: available,
      totalCustomers: customers,
      totalBookings: list.length,
      paidRevenue: list.filter((b) => b.payment === "paid" || b.payment === "cod").reduce((s, b) => s + b.total, 0),
    };
  }

  return {
    KEYS,
    todayISO,
    addDays,
    nextDays,
    prettyDate,
    hourLabel,
    fmtMoney,
    makeId,
    getBookings,
    setBookings,
    addBooking,
    updateBooking,
    findBooking,
    getBlocks,
    setBlocks,
    getPricing,
    setPricing,
    slotStatus,
    availableHours,
    basePrice,
    computePrice,
    stats,
  };
})();
