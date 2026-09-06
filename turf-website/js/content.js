/* ============================================================
   CONTENT DATA — Sports, Facilities, Offers, Gallery, Reviews
   Edit these arrays to match each client's business.
   ============================================================ */

window.CONTENT = {
  /* ---------- Sports ---------- */
  sports: [
    {
      name: "Football",
      emoji: "⚽",
      desc: "5-a-side and 7-a-side on FIFA-grade artificial turf with pro floodlights.",
      price: 800,
      img: "https://images.unsplash.com/photo-1579952363873-27f3bade9f55?q=80&w=800&auto=format&fit=crop",
      alt: "Football players on a green turf pitch",
      bookable: true,
    },
    {
      name: "Cricket",
      emoji: "🏏",
      desc: "Hard-hitting nets and match practice with professional bowling machine.",
      price: 900,
      img: "https://images.unsplash.com/photo-1531415074968-036ba1b575da?q=80&w=800&auto=format&fit=crop",
      alt: "Cricket bat and stumps on a pitch",
      bookable: true,
    },
    {
      name: "Badminton",
      emoji: "🏸",
      desc: "Indoor synthetic courts with proper net height and cushioned flooring.",
      price: 400,
      img: "https://images.unsplash.com/photo-1626224583764-f87db24ac4ea?q=80&w=800&auto=format&fit=crop",
      alt: "Badminton rackets and shuttlecock on court",
      bookable: true,
    },
    {
      name: "Basketball",
      emoji: "🏀",
      desc: "Regulation-height hoops with grippy outdoor surface, day and night.",
      price: 600,
      img: "https://images.unsplash.com/photo-1546519638-68e109498ffc?q=80&w=800&auto=format&fit=crop",
      alt: "Basketball court with hoop",
      bookable: true,
    },
    {
      name: "Volleyball",
      emoji: "🏐",
      desc: "Beach-sand and indoor variants available for casual and league play.",
      price: 500,
      img: "https://images.unsplash.com/photo-1612872087720-bb876e2e67d1?q=80&w=800&auto=format&fit=crop",
      alt: "Volleyball net on a sports court",
      bookable: true,
    },
    {
      name: "Tennis",
      emoji: "🎾",
      desc: "Padded acrylic hard courts with net and practice wall for training.",
      price: 700,
      img: "https://images.unsplash.com/photo-1595435934249-5df7ed86e1c0?q=80&w=800&auto=format&fit=crop",
      alt: "Tennis court with net",
      bookable: true,
    },
  ],

  /* ---------- Facilities (icon = lucide name) ---------- */
  facilities: [
    { icon: "floodlight", title: "Floodlights", desc: "Professional LED lighting for night play" },
    { icon: "parking", title: "Free Parking", desc: "Dedicated 40+ vehicle parking area" },
    { icon: "shirt", title: "Changing Room", desc: "Clean changing rooms for men & women" },
    { icon: "shower", title: "Washrooms", desc: "Clean, well-maintained washrooms" },
    { icon: "droplet", title: "Drinking Water", desc: "RO water points around the arena" },
    { icon: "sofa", title: "Seating Area", desc: "Viewing gallery for friends & family" },
    { icon: "cctv", title: "CCTV Security", desc: "24×7 monitored arena" },
    { icon: "wifi", title: "Wi-Fi", desc: "High-speed Wi-Fi in the lounge" },
    { icon: "football", title: "Equipment Rental", desc: "Balls, bats, rackets & more" },
    { icon: "medkit", title: "First Aid", desc: "On-site first aid & medical kit" },
  ],

  /* ---------- Offers ---------- */
  offers: [
    {
      tag: "FIRST GAME OFFER",
      title: "20% OFF your first booking",
      desc: "New here? Use code FIRST20 at checkout and enjoy your first game at a discount.",
      validity: "Valid for all new customers",
      code: "FIRST20",
    },
    {
      tag: "WEEKEND OFFER",
      title: "Special weekend pricing",
      desc: "Lock in weekend slots early and save ₹300 per hour on group bookings.",
      validity: "Valid Sat & Sun, 9 AM – 5 PM",
      code: "TEAM10",
    },
    {
      tag: "GROUP BOOKING",
      title: "Book more, save more",
      desc: "Reserve 3+ hours for your league, team or event and get extra time on the house.",
      validity: "For bookings of 3+ hours",
      code: null,
    },
  ],

  /* ---------- Gallery ---------- */
  gallery: [
    {
      src: "https://images.unsplash.com/photo-1577223625816-7546f13df25d?q=80&w=1200&auto=format&fit=crop",
      alt: "Floodlit turf arena at night",
      tag: "Night Arena",
    },
    {
      src: "https://images.unsplash.com/photo-1522778119026-d647f0596c20?q=80&w=1200&auto=format&fit=crop",
      alt: "Green football pitch in daylight",
      tag: "Main Turf",
    },
    {
      src: "https://images.unsplash.com/photo-1553778263-73a83bab9b0c?q=80&w=1200&auto=format&fit=crop",
      alt: "Footballers in a training match",
      tag: "Match Day",
    },
    {
      src: "https://images.unsplash.com/photo-1546519638-68e109498ffc?q=80&w=1200&auto=format&fit=crop",
      alt: "Basketball court under open sky",
      tag: "Basketball Court",
    },
    {
      src: "https://images.unsplash.com/photo-1460409028349-5eb5dd09d5a2?q=80&w=1200&auto=format&fit=crop",
      alt: "Evening sports floodlight glow",
      tag: "Floodlights",
    },
    {
      src: "https://images.unsplash.com/photo-1571019613454-1cb2f99b2d8b?q=80&w=1200&auto=format&fit=crop",
      alt: "Players training with coach",
      tag: "Training",
    },
  ],

  /* ---------- Reviews ---------- */
  reviews: [
    {
      name: "Arun Kumar",
      rating: 5,
      text: "Great turf, excellent lighting and very clean facilities. Booking online was super easy.",
      date: "2 weeks ago",
    },
    {
      name: "Priya S.",
      rating: 5,
      text: "Best turf in the area. The floodlights are amazing for evening matches. Highly recommend!",
      date: "1 month ago",
    },
    {
      name: "Rahul Menon",
      rating: 4,
      text: "Nice playing surface and friendly staff. Parking was easy and the changing rooms are clean.",
      date: "1 month ago",
    },
    {
      name: "Sneha R.",
      rating: 5,
      text: "Booked a cricket slot through WhatsApp. Instant confirmation and great coordination.",
      date: "2 months ago",
    },
    {
      name: "Vignesh T.",
      rating: 5,
      text: "Affordable pricing for a premium turf. Our weekend league plays here every week.",
      date: "3 months ago",
    },
    {
      name: "Karthik B.",
      rating: 4,
      text: "Good equipment rental and the first-aid kit gives peace of mind. Solid experience.",
      date: "3 months ago",
    },
  ],
  averageRating: 4.8,
  reviewCount: 214,

  /* ---------- About ---------- */
  about: {
    heading: "Chennai's most-played turf arena",
    paragraphs: [
      "GreenZone Arena was built for one simple reason — to give Chennai's players a world-class surface they can book in minutes. From FIFA-grade artificial turf to professional LED floodlights, every detail is designed for serious play.",
      "Whether it's a friendly 5-a-side, a corporate tournament or an early-morning fitness session, our team keeps the arena spotless and ready. You focus on the game; we handle the rest.",
    ],
    highlights: [
      "Premium FIFA-grade playing surface",
      "Professional LED floodlighting",
      "Easy online & WhatsApp booking",
      "Convenient central location with parking",
      "Clean, well-maintained facilities",
      "Honest, affordable pricing",
    ],
  },

  /* ---------- Footer ---------- */
  footerNote:
    "GreenZone Arena is a premium multi-sport arena in Chennai. Book football, cricket, badminton, basketball, volleyball and tennis turfs online — pay with UPI or card — and get instant confirmation.",
};
