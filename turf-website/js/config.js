/* ============================================================
   TURF BOOKING WEBSITE — CLIENT CONFIG
   ------------------------------------------------------------
   Every business-specific value lives in THIS file (and content.js).
   To set up a new client:
     1. Duplicate the entire "turf-website" folder.
     2. Edit the values below.
     3. Replace images in /assets or keep the stock Unsplash images.
     4. Deploy the folder to any static host (Vercel, Netlify, cPanel).
   ============================================================ */

window.SITE = {
  /* ---------- Business identity ---------- */
  name: "GreenZone Arena",
  tagline: "Premium Turf & Sports Arena",
  legalName: "GreenZone Arena Sports LLP",

  /* ---------- Contact ---------- */
  phoneDisplay: "+91 98765 43210",
  phoneIntl: "919876543210",               // digits only, country code first
  whatsappNumber: "919876543210",          // digits only, country code first
  email: "bookings@greenzonearena.in",
  instagram: "https://instagram.com/greenzonearena",
  facebook: "https://facebook.com/greenzonearena",
  googleReviewsUrl: "https://www.google.com/maps", // replace with real GBP link

  /* ---------- Location ---------- */
  addressLine1: "No. 24, Second Main Road, Kotturpuram",
  addressLine2: "Chennai, Tamil Nadu 600085",
  city: "Chennai",
  state: "Tamil Nadu",
  pinCode: "600085",
  landmark: "Opposite Kotturpuram Metro Station",
  // For the embedded map. Use the place name or a comma lat,lng.
  mapQuery: "GreenZone Arena, Kotturpuram, Chennai",
  mapEmbedUrl:
    "https://www.google.com/maps?q=Kotturpuram%2C%20Chennai%2C%20Tamil%20Nadu&t=&z=15&ie=UTF8&iwloc=&output=embed",

  /* ---------- Hours ---------- */
  openingTime: "6:00 AM",
  closingTime: "11:00 PM",

  /* ---------- Hero ---------- */
  heroHeadline: "Book Your Turf. Play Your Game.",
  heroSubtext:
    "Premium sports facilities. Easy online booking. Your game starts here.",
  heroImage:
    "https://images.unsplash.com/photo-1577223625816-7546f13df25d?q=80&w=2000&auto=format&fit=crop",
  heroImageAlt:
    "Floodlit football turf at GreenZone Arena, Chennai at night",

  /* ---------- Turf details ---------- */
  turf: {
    name: "Premium Football Turf",
    type: "5-a-side Football Turf",
    size: "35m × 25m",
    capacity: "10–14 players",
    pricePerHour: 1000,
    description:
      "World-class FIFA-grade artificial turf with shock-absorbing infill, professional LED floodlights and side netting. Perfect for football, cricket and fitness sessions.",
  },

  /* ---------- Pricing plan ---------- */
  pricing: [
    {
      name: "Morning",
      time: "6 AM – 4 PM",
      price: 800,
      perks: ["Best value pricing", "Cooler temperatures", "Floodlights on request"],
      popular: false,
    },
    {
      name: "Evening",
      time: "4 PM – 10 PM",
      price: 1200,
      perks: ["Premium floodlight arena", "Peak playing hours", "Reserve up to 48 hrs ahead"],
      popular: true,
    },
    {
      name: "Weekend",
      time: "All day",
      price: 1500,
      perks: ["Full-day flexibility", "Groups & leagues welcome", "Free equipment rental"],
      popular: false,
    },
  ],

  /* ---------- Coupon codes ---------- */
  coupons: [
    { code: "FIRST20", discountPercent: 20, label: "20% off your first booking" },
    { code: "TEAM10", discountPercent: 10, label: "10% off group bookings" },
  ],

  /* ---------- Security / admin ---------- */
  adminPin: "1234", // change this before handing the site to a client

  /* ---------- Payments (Razorpay) ---------- */
  razorpay: {
    enabled: true,
    // TEST key — replace with your live Key ID from https://dashboard.razorpay.com
    keyId: "rzp_test_xxxxxxxxxxxxxxxx",
    currency: "INR",
    name: "GreenZone Arena",
    description: "Turf Booking",
    themeColor: "#16a34a",
    // NOTE: for production, validate payments on your server/webhook.
    // See README "Going live with payments".
  },

  /* ---------- SEO ---------- */
  seo: {
    title: "GreenZone Arena | Book Football, Cricket & Badminton Turf in Chennai",
    description:
      "Book a premium football, cricket, badminton or basketball turf in Chennai online. Real-time slot availability, UPI & card payments, instant confirmation. Floodlit arena, parking & clean facilities.",
    keywords:
      "turf booking in Chennai, football turf near me, cricket turf Chennai, book football turf Chennai, badminton court Chennai, sports arena Chennai",
    ogImage:
      "https://images.unsplash.com/photo-1577223625816-7546f13df25d?q=80&w=1200&auto=format&fit=crop",
  },
};
