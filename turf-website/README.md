# Turf Booking Website — Client Template

A premium, dark-themed, mobile-first turf booking website for Indian sports/turf
businesses. Built with **zero build step** — plain HTML, CSS and vanilla JS — so it
can be duplicated and customized for every client in minutes, then deployed to any
static host (Vercel, Netlify, cPanel, GitHub Pages).

---

## Quick start

```bash
# Option A — no install needed
# Just open index.html in a browser (booking works, payments run in demo mode)

# Option B — run a local server (recommended for full Razorpay flow)
npx serve turf-website
# then open http://localhost:3000
```

| Page | URL |
|---|---|
| Customer website | `/` (`index.html`) |
| Owner dashboard | `/admin.html` — default PIN: `1234` |

---

## Project structure

```
turf-website/
├── index.html          Customer website (all sections + booking wizard)
├── admin.html          Owner dashboard (bookings, slots, pricing, revenue)
├── css/
│   ├── style.css       Customer site styles (dark premium sports theme)
│   └── admin.css       Dashboard styles
├── js/
│   ├── config.js       ★ ALL business settings (phone, address, pricing, PIN…)
│   ├── content.js      ★ ALL content collections (sports, facilities, offers, gallery, reviews)
│   ├── store.js        Bookings/slots logic (localStorage)
│   ├── main.js         Customer site behaviour
│   └── admin.js        Dashboard behaviour
├── robots.txt
└── sitemap.xml
```

---

## Onboarding a new client (the important part)

1. **Duplicate** the whole `turf-website` folder and rename it for the client.
2. Open **`js/config.js`** and change every value:
   - `name`, `tagline`, `phoneDisplay`, `phoneIntl`, `whatsappNumber`, `email`
   - `addressLine1/2`, `city`, `mapQuery`, `mapEmbedUrl`, `googleReviewsUrl`
   - `openingTime`, `closingTime`, hero headline/subtext/images
   - `turf` details, `pricing`, `coupons`, `adminPin`
   - `seo.title`, `seo.description`, `seo.keywords`, `seo.ogImage`
3. Open **`js/content.js`** and update:
   - `sports` (name, description, price, image)
   - `facilities`, `offers`, `gallery`, `reviews`, `about`, `footerNote`
4. Replace images: keep the stock Unsplash URLs or drop client photos in
   `assets/` and swap the URLs.
5. Deploy. Done.

> Because every business value lives in `config.js`/`content.js`, nothing is
> hard-coded elsewhere — `index.html` is intentionally generic.

---

## Going live with payments (Razorpay)

1. Create a Razorpay account → **Settings → API Keys**.
2. Put your **Live Key ID** in `js/config.js` → `razorpay.keyId`.
3. Set up a **webhook** at your backend for `payment.captured` to record payments
   server-side (optional for demo, required for multi-device accuracy).
4. Replace `razorpay_test_*` keys with live keys when the client is ready.

**Demo mode:** when the key is a test placeholder, the site auto-completes the
payment step with "Pay on arrival" so you can demo the whole flow without a key.

> Payments work over `https://` or `localhost`. From `file://` the wizard falls
> back to demo mode automatically.

---

## Bookings, data & the "database"

Bookings and slot blocks live in the browser via **localStorage** (keys `gza_*`).
This is perfect for:

- Demo / proposal pitches to clients
- Single-owner turf running on one phone or laptop
- Static hosting with no server

**For production (recommended upgrade):** connect `store.js` to a backend.
Each `Store.*` function is a thin wrapper — swap `localStorage` reads/writes for
API calls. Suggested schema:

```sql
bookings(
  id text primary key,        -- GZA-XXXX
  sport text, date text, hour int, duration int,
  name text, phone text, email text, notes text,
  unit int, base int, discount int, total int, coupon text,
  status text,                -- pending | confirmed | completed | cancelled
  payment text,               -- unpaid | paid | cod
  payment_id text, created_at timestamp
)
slots( sport, date, hour, state )   -- state: free | blocked | maintenance
```

Free options: **Supabase** (Postgres, generous free tier, easy row-level security)
or a tiny **Node/Express + SQLite** API. Notifications (WhatsApp/Email/SMS) can be
added via Twilio, Gupshup or Razorpay's built-in order/email receipts.

---

## Customizing the design

All theme tokens (colors, radius, fonts) are CSS variables at the top of
`css/style.css`. To re-brand per client:

```css
:root {
  --primary: #22c55e;       /* main accent */
  --primary-strong: #16a34a;
  --accent: #a3e635;        /* secondary accent */
  --bg: #060b10;            /* page background */
  --font-display: "Space Grotesk", sans-serif;
}
```

Swap `Space Grotesk`/`Inter` for another Google Font by editing the `<link>` in
`index.html` and the variables above.

---

## Security notes

- The admin PIN (`adminPin` in config) protects the dashboard in the browser only.
  Anyone with the source can read it. For a real client, move authentication
  server-side (e.g., Supabase Auth) and gate the admin API.
- Never commit Razorpay **Secret Key** — only the Key ID goes in client code.
  Payment verification must happen on your server via webhook.
- `robots.txt` blocks nothing but keep `/admin.html` linked only privately.

---

## Packages (what you can sell)

| Basic | Standard | Premium |
|---|---|---|
| Home, About, Sports, Facilities | + Online booking & live slots | + Razorpay payments |
| Gallery, Pricing, Contact | + Customer details & confirmation | + Invoice download & WhatsApp share |
| Google Maps, WhatsApp, Call | + Offers, Reviews | + Admin dashboard & revenue analytics |
| Responsive, SEO | + Admin booking management | + Coupons, slot blocking, notifications |

All three are already implemented in this template — disable features you don't
sell by removing the matching `<section>` in `index.html`.

---

## SEO checklist before launch

- [ ] Replace `greenzonearena.example.com` in `sitemap.xml`, `robots.txt`, JSON-LD `url` and `og:url` with the real domain
- [ ] Add real keywords in `config.js` → `seo`
- [ ] Set the real Google Business Profile link (`googleReviewsUrl`)
- [ ] Submit `sitemap.xml` in Google Search Console
- [ ] Replace placeholder images with real client photos + descriptive alt text

---

© Built for freelance turf/sports clients. Deploy per client, edit `config.js`, ship.
