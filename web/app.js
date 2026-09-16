const ICON_ATTRS = 'viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"';
const ICONS = {
  landmark: `<svg class="icon" ${ICON_ATTRS}><polygon points="12 2 21 8 3 8"></polygon><line x1="6" y1="11" x2="6" y2="18"></line><line x1="10" y1="11" x2="10" y2="18"></line><line x1="14" y1="11" x2="14" y2="18"></line><line x1="18" y1="11" x2="18" y2="18"></line><line x1="3" y1="22" x2="21" y2="22"></line></svg>`,
  scale: `<svg class="icon" ${ICON_ATTRS}><line x1="12" y1="2" x2="12" y2="22"></line><line x1="5" y1="6" x2="19" y2="6"></line><circle cx="5" cy="11" r="3"></circle><circle cx="19" cy="11" r="3"></circle><line x1="8" y1="22" x2="16" y2="22"></line></svg>`,
  sun: `<svg class="icon" ${ICON_ATTRS}><circle cx="12" cy="12" r="4"></circle><line x1="12" y1="2" x2="12" y2="4"></line><line x1="12" y1="20" x2="12" y2="22"></line><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"></line><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"></line><line x1="2" y1="12" x2="4" y2="12"></line><line x1="20" y1="12" x2="22" y2="12"></line><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"></line><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"></line></svg>`,
  moon: `<svg class="icon" viewBox="0 0 24 24" fill="currentColor" stroke="none"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path></svg>`,
  calendar: `<svg class="icon" ${ICON_ATTRS}><rect x="3" y="4" width="18" height="18" rx="2"></rect><line x1="16" y1="2" x2="16" y2="6"></line><line x1="8" y1="2" x2="8" y2="6"></line><line x1="3" y1="10" x2="21" y2="10"></line></svg>`,
  chevronRight: `<svg class="icon" ${ICON_ATTRS}><polyline points="9 18 15 12 9 6"></polyline></svg>`,
};

const CATEGORY_LABELS = {
  f1: "F-1",
  opt: "OPT",
  stem_opt: "STEM OPT",
  h1b: "H-1B",
  green_card: "Green card",
  travel_entry: "Travel",
  general: "General",
};

const SOURCE_LABELS = {
  "federal_register:uscis_rules": "USCIS rules (Federal Register)",
  "federal_register:dhs_rules": "DHS rules (Federal Register)",
  "federal_register:ice_rules": "ICE rules (Federal Register)",
  "federal_register:state_dept_rules": "State Dept rules (Federal Register)",
  "rss:uscis_news": "USCIS news releases",
  "rss:uscis_alerts": "USCIS alerts",
  "rss:murthy_law": "Murthy Law Firm",
  "rss:citizenpath": "CitizenPath",
  "rss:american_immigration_council": "American Immigration Council",
  "rss:wr_immigration": "WR Immigration",
};

const COUNTRY_LABELS = {
  ROW: "All Chargeability Areas",
  CHINA: "China",
  INDIA: "India",
  MEXICO: "Mexico",
  PHILIPPINES: "Philippines",
};

const SECTION_LABELS = {
  family_sponsored: "Family-Sponsored",
  employment_based: "Employment-Based",
};

// Category keys are already human-readable (EB-1..EB-5, F1/F2A/F2B/F3/F4)
// as of the pd-tracker-primary bulletin source -- no relabeling needed.
const categoryDisplay = (cat) => cat;

const PAGE_SIZE = 40;
const TAB_TRUST = { feed: null, analysis: "analysis" }; // null = no trust restriction (mixed feed)

let allItems = [];
let bulletinData = null;
let currentTab = "feed";

let activeCategories = new Set();
let activeTrust = new Set();
let activeSources = new Set();
let dateRange = "all";
let actionableOnly = false;
let searchTerm = "";
let sortOrder = "newest";
let visibleCount = PAGE_SIZE;

function timeAgo(iso) {
  const diffMs = Date.now() - new Date(iso).getTime();
  const min = Math.floor(diffMs / 60000);
  if (min < 1) return "just now";
  if (min < 60) return `${min}m ago`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr}h ago`;
  const day = Math.floor(hr / 24);
  if (day < 7) return `${day}d ago`;
  return new Date(iso).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

async function loadFeed() {
  try {
    const res = await fetch(`../data/data.json?t=${Date.now()}`, { cache: "no-store" });
    const data = await res.json();
    allItems = data.items || [];
    document.getElementById("header-meta-text").textContent =
      `updated ${timeAgo(data.generated_at)} · ${data.source_count} sources`;
    renderAll();
  } catch (err) {
    document.getElementById("feed").innerHTML =
      '<div class="empty-state">Could not load data/data.json. Run scripts/ingest.py first.</div>';
  }
}

function getTabItems() {
  const trust = TAB_TRUST[currentTab];
  return trust ? allItems.filter((i) => i.source_trust === trust) : allItems;
}

function withinDateRange(isoDate) {
  if (dateRange === "all") return true;
  const days = { today: 1, week: 7, month: 30 }[dateRange];
  return Date.now() - new Date(isoDate).getTime() <= days * 86400000;
}

function getFilteredItems() {
  return getTabItems().filter((item) => {
    if (activeCategories.size && !item.categories.some((c) => activeCategories.has(c))) return false;
    if (activeTrust.size && !activeTrust.has(item.source_trust)) return false;
    if (activeSources.size && !activeSources.has(item.source)) return false;
    if (actionableOnly && !item.actionable) return false;
    if (!withinDateRange(item.published_at)) return false;
    if (searchTerm && !item.title.toLowerCase().includes(searchTerm)) return false;
    return true;
  });
}

function hasActiveFilters() {
  return (
    activeCategories.size > 0 ||
    activeTrust.size > 0 ||
    activeSources.size > 0 ||
    dateRange !== "all" ||
    actionableOnly ||
    searchTerm !== ""
  );
}

function resetFilters() {
  activeCategories = new Set();
  activeTrust = new Set();
  activeSources = new Set();
  dateRange = "all";
  actionableOnly = false;
  searchTerm = "";
  sortOrder = "newest";
  document.getElementById("search").value = "";
  document.getElementById("date-range").value = "all";
  document.getElementById("sort-order").value = "newest";
  visibleCount = PAGE_SIZE;
}

function renderAll() {
  renderStatLine();
  renderMovementBanner();
  renderCategoryPills();
  renderTrustToggles();
  renderSourceMenu();
  renderFeed();
}

function renderStatLine() {
  const items = getTabItems();
  const actionableCount = items.filter((i) => i.actionable).length;
  const thisWeek = items.filter((i) => withinDays(i.published_at, 7)).length;
  document.getElementById("stats").innerHTML =
    `<strong>${thisWeek}</strong> update${thisWeek === 1 ? "" : "s"} this week · ` +
    `<strong class="actionable-count">${actionableCount}</strong> actionable · ` +
    `${items.length} total`;
}

function renderMovementBanner() {
  const banner = document.getElementById("movement-banner");
  if (currentTab !== "feed" || !bulletinData || !bulletinData.month) {
    banner.innerHTML = "";
    return;
  }
  const eb = bulletinData.final_action?.employment_based || {};
  const movement = bulletinData.movement?.final_action?.employment_based || {};
  const highlights = [
    ["EB-2", "INDIA", "EB-2 India"],
    ["EB-3", "INDIA", "EB-3 India"],
    ["EB-2", "CHINA", "EB-2 China"],
  ];
  const moved = highlights.find(([cat, country]) => movement[cat] && movement[cat][country]);
  if (!moved) {
    banner.innerHTML = "";
    return;
  }
  const [cat, country, label] = moved;
  const delta = movement[cat][country];
  const direction = delta > 0 ? "advanced" : "moved back";
  banner.innerHTML = `${ICONS.calendar}<span>${label} ${direction} ${Math.abs(delta)} month${Math.abs(delta) === 1 ? "" : "s"} in the latest Visa Bulletin — see Visa Bulletin tab</span>${ICONS.chevronRight}`;
  banner.className = "movement-banner";
  banner.onclick = () => document.querySelector('.tab[data-tab="bulletin"]').click();
}

function withinDays(isoDate, days) {
  return Date.now() - new Date(isoDate).getTime() <= days * 86400000;
}

function renderCategoryPills() {
  const items = getTabItems();
  const counts = {};
  for (const item of items) for (const c of item.categories) counts[c] = (counts[c] || 0) + 1;
  const categories = Object.keys(CATEGORY_LABELS).filter((c) => counts[c]);

  const container = document.getElementById("category-pills");
  container.innerHTML =
    `<button class="pill${activeCategories.size === 0 ? " active" : ""}" data-cat="__all__">All</button>` +
    categories
      .map(
        (cat) =>
          `<button class="pill${activeCategories.has(cat) ? " active" : ""}" data-cat="${cat}">${CATEGORY_LABELS[cat]} (${counts[cat]})</button>`
      )
      .join("");

  container.querySelectorAll(".pill").forEach((pill) => {
    pill.addEventListener("click", () => {
      const cat = pill.dataset.cat;
      if (cat === "__all__") {
        activeCategories.clear();
      } else if (activeCategories.has(cat)) {
        activeCategories.delete(cat);
      } else {
        activeCategories.add(cat);
      }
      visibleCount = PAGE_SIZE;
      renderCategoryPills();
      renderFeed();
    });
  });
}

function renderTrustToggles() {
  const officialBtn = document.getElementById("trust-official");
  const analysisBtn = document.getElementById("trust-analysis");
  const showTrustFilter = currentTab === "feed"; // only meaningful on the mixed feed tab
  officialBtn.style.display = showTrustFilter ? "inline-block" : "none";
  analysisBtn.style.display = showTrustFilter ? "inline-block" : "none";
  officialBtn.classList.toggle("active", activeTrust.has("official"));
  analysisBtn.classList.toggle("active", activeTrust.has("analysis"));
}

function renderSourceMenu() {
  const items = getTabItems();
  const counts = {};
  for (const item of items) counts[item.source] = (counts[item.source] || 0) + 1;
  const container = document.getElementById("source-filter");
  container.innerHTML = Object.entries(counts)
    .sort((a, b) => b[1] - a[1])
    .map(
      ([source, count]) => `
      <label class="source-check">
        <span><input type="checkbox" data-source="${source}" ${activeSources.has(source) ? "checked" : ""}/> ${SOURCE_LABELS[source] || source}</span>
        <span class="count">${count}</span>
      </label>`
    )
    .join("");
  container.querySelectorAll("input[type=checkbox]").forEach((box) => {
    box.addEventListener("change", () => {
      const src = box.dataset.source;
      box.checked ? activeSources.add(src) : activeSources.delete(src);
      visibleCount = PAGE_SIZE;
      renderFeed();
      updateClearButton();
    });
  });
}

function updateClearButton() {
  document.getElementById("clear-filters").style.display = hasActiveFilters() ? "inline-block" : "none";
}

function dateGroupLabel(isoDate) {
  const date = new Date(isoDate);
  const now = new Date();
  const diffDays = Math.floor((now.setHours(0, 0, 0, 0) - new Date(date).setHours(0, 0, 0, 0)) / 86400000);
  if (diffDays === 0) return "Today";
  if (diffDays === 1) return "Yesterday";
  if (diffDays > 1 && diffDays < 7) return "This week";
  return date.toLocaleDateString(undefined, { year: "numeric", month: "long" });
}

function sortItems(items) {
  const sorted = [...items];
  if (sortOrder === "oldest") sorted.sort((a, b) => new Date(a.published_at) - new Date(b.published_at));
  else if (sortOrder === "actionable")
    sorted.sort((a, b) => b.actionable - a.actionable || new Date(b.published_at) - new Date(a.published_at));
  else sorted.sort((a, b) => new Date(b.published_at) - new Date(a.published_at));
  return sorted;
}

function renderFeed() {
  const items = sortItems(getFilteredItems());
  const feed = document.getElementById("feed");
  const loadMoreRow = document.getElementById("load-more-row");
  updateClearButton();

  if (items.length === 0) {
    feed.innerHTML = '<div class="empty-state">No items match these filters.</div>';
    loadMoreRow.style.display = "none";
    return;
  }

  const visible = items.slice(0, visibleCount);
  const groupByDate = sortOrder !== "actionable";
  let html = "";
  let lastGroup = null;

  for (const item of visible) {
    if (groupByDate) {
      const group = dateGroupLabel(item.published_at);
      if (group !== lastGroup) {
        html += `<div class="date-group-heading">${group}</div>`;
        lastGroup = group;
      }
    }
    const statusBadge = item.actionable
      ? '<span class="badge status-actionable">Actionable</span>'
      : '<span class="badge status-info">Info</span>';
    const trustBadge =
      item.source_trust === "official"
        ? `<span class="badge trust-official">${ICONS.landmark} Official</span>`
        : `<span class="badge trust-analysis">${ICONS.scale} Analysis</span>`;
    const catBadges = item.categories.map((c) => `<span class="badge category">${CATEGORY_LABELS[c] || c}</span>`).join("");

    html += `
      <div class="card">
        <div class="badge-row">${statusBadge}${catBadges}${trustBadge}</div>
        <h3><a href="${item.url}" target="_blank" rel="noopener">${item.title}</a></h3>
        ${item.summary ? `<p>${item.summary}</p>` : ""}
        <div class="card-meta">${SOURCE_LABELS[item.source] || item.source} · ${timeAgo(item.published_at)}</div>
      </div>`;
  }

  feed.innerHTML = html;
  loadMoreRow.style.display = visibleCount < items.length ? "flex" : "none";
}

function formatDelta(delta) {
  if (delta === null || delta === undefined) return "";
  if (delta === 0) return '<span class="tracker-delta flat">no change</span>';
  const arrow = delta > 0 ? "↑" : "↓";
  const cls = delta > 0 ? "up" : "down";
  return `<span class="tracker-delta ${cls}">${arrow} ${Math.abs(delta)}mo</span>`;
}

function renderTracker() {
  const container = document.getElementById("bulletin-tracker");
  if (!bulletinData || !bulletinData.month) {
    container.innerHTML = `
      <div class="tracker-widget">
        <div class="tracker-header">Visa Bulletin tracker</div>
        <div class="empty-state" style="padding:10px 0">${bulletinData?.note || "Not yet available."}</div>
      </div>`;
    return;
  }

  const eb = bulletinData.final_action?.employment_based || {};
  const movement = bulletinData.movement?.final_action?.employment_based || {};
  const highlights = [
    ["EB-2", "INDIA", "EB-2 India"],
    ["EB-3", "INDIA", "EB-3 India"],
    ["EB-2", "CHINA", "EB-2 China"],
  ].filter(([cat, country]) => eb[cat] && eb[cat][country]);

  if (highlights.length === 0) {
    container.innerHTML = "";
    return;
  }

  const cells = highlights
    .map(([cat, country, label]) => {
      const value = eb[cat][country];
      const delta = movement[cat] ? movement[cat][country] : null;
      return `
        <div class="tracker-cell">
          <div class="tracker-label">${label}</div>
          <div><span class="tracker-date">${value}</span>${formatDelta(delta)}</div>
        </div>`;
    })
    .join("");

  container.innerHTML = `
    <div class="tracker-widget">
      <div class="tracker-header"><span>Visa Bulletin tracker</span><span class="tracker-month">${bulletinData.month}</span></div>
      <div class="tracker-grid">${cells}</div>
    </div>`;
}

document.getElementById("trust-official").addEventListener("click", (e) => {
  e.target.classList.contains("active") ? activeTrust.delete("official") : activeTrust.add("official");
  visibleCount = PAGE_SIZE;
  renderTrustToggles();
  renderFeed();
});
document.getElementById("trust-analysis").addEventListener("click", (e) => {
  e.target.classList.contains("active") ? activeTrust.delete("analysis") : activeTrust.add("analysis");
  visibleCount = PAGE_SIZE;
  renderTrustToggles();
  renderFeed();
});
document.getElementById("actionable-toggle").addEventListener("click", (e) => {
  actionableOnly = !actionableOnly;
  e.target.classList.toggle("active", actionableOnly);
  visibleCount = PAGE_SIZE;
  renderFeed();
});
document.getElementById("search").addEventListener("input", (e) => {
  searchTerm = e.target.value.trim().toLowerCase();
  visibleCount = PAGE_SIZE;
  renderFeed();
});
document.getElementById("date-range").addEventListener("change", (e) => {
  dateRange = e.target.value;
  visibleCount = PAGE_SIZE;
  renderFeed();
});
document.getElementById("sort-order").addEventListener("change", (e) => {
  sortOrder = e.target.value;
  renderFeed();
});
document.getElementById("load-more").addEventListener("click", () => {
  visibleCount += PAGE_SIZE;
  renderFeed();
});
document.getElementById("clear-filters").addEventListener("click", () => {
  resetFilters();
  renderTrustToggles();
  document.getElementById("actionable-toggle").classList.remove("active");
  renderCategoryPills();
  renderFeed();
});
document.getElementById("refresh-btn").addEventListener("click", () => loadFeed());

function updateThemeToggleIcon() {
  const theme = document.documentElement.dataset.theme;
  document.getElementById("theme-toggle").innerHTML = theme === "light" ? ICONS.sun : ICONS.moon;
}
document.getElementById("theme-toggle").addEventListener("click", () => {
  const next = document.documentElement.dataset.theme === "light" ? "dark" : "light";
  document.documentElement.dataset.theme = next;
  localStorage.setItem("theme", next);
  updateThemeToggleIcon();
});
updateThemeToggleIcon();

document.getElementById("case-status-form").addEventListener("submit", (e) => {
  e.preventDefault();
  const receipt = document.getElementById("receipt-number").value.trim().toUpperCase();
  if (!receipt) return;
  window.open(
    `https://egov.uscis.gov/casestatus/mycasestatus.do?appReceiptNum=${encodeURIComponent(receipt)}`,
    "_blank",
    "noopener"
  );
});

async function loadBulletin() {
  try {
    const res = await fetch(`../data/visa_bulletin.json?t=${Date.now()}`, { cache: "no-store" });
    bulletinData = await res.json();
    renderBulletinTab();
    renderTracker();
    renderMovementBanner();
  } catch (err) {
    document.getElementById("bulletin").innerHTML =
      '<div class="empty-state">Could not load data/visa_bulletin.json.</div>';
  }
}

function renderBulletinTab() {
  const container = document.getElementById("bulletin");
  const bulletin = bulletinData;

  if (!bulletin || !bulletin.month) {
    container.innerHTML = `<div class="empty-state">${bulletin?.note || "Visa Bulletin data not yet available."}</div>`;
    return;
  }

  let html = `<p style="color:var(--muted)">${bulletin.month} &middot; <a href="${bulletin.source_url}" style="color:inherit" target="_blank" rel="noopener">source</a> &middot; ${bulletin.data_source || ""}</p>`;

  for (const [bulletinType, label] of [
    ["final_action", "Final Action Dates"],
    ["dates_for_filing", "Dates for Filing Applications"],
  ]) {
    const sections = bulletin[bulletinType] || {};
    const movementSections = bulletin.movement?.[bulletinType] || {};
    for (const [sectionKey, categories] of Object.entries(sections)) {
      const countries = Object.keys(COUNTRY_LABELS);
      const movementCategories = movementSections[sectionKey] || {};
      const rows = Object.entries(categories)
        .map(([cat, values]) => {
          const cells = countries
            .map((c) => {
              const delta = movementCategories[cat] ? movementCategories[cat][c] : null;
              const deltaHtml =
                delta === null || delta === undefined
                  ? ""
                  : delta === 0
                  ? '<span class="delta flat">·</span>'
                  : `<span class="delta ${delta > 0 ? "up" : "down"}">${delta > 0 ? "↑" : "↓"}${Math.abs(delta)}mo</span>`;
              return `<td>${values[c] || "U"}${deltaHtml}</td>`;
            })
            .join("");
          return `<tr><td>${categoryDisplay(cat)}</td>${cells}</tr>`;
        })
        .join("");
      html += `
        <div class="table-scroll">
          <table class="bulletin">
            <caption>${label} — ${SECTION_LABELS[sectionKey] || sectionKey}</caption>
            <thead><tr><th>Category</th>${countries.map((c) => `<th>${COUNTRY_LABELS[c]}</th>`).join("")}</tr></thead>
            <tbody>${rows}</tbody>
          </table>
        </div>`;
    }
  }

  container.innerHTML = html;
}

document.querySelectorAll(".tab").forEach((tab) => {
  tab.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((t) => t.classList.remove("active"));
    tab.classList.add("active");
    currentTab = tab.dataset.tab;
    const isFeedLike = currentTab === "feed" || currentTab === "analysis";

    document.getElementById("feed-view").style.display = isFeedLike ? "block" : "none";
    document.getElementById("bulletin-view").style.display = isFeedLike ? "none" : "block";

    if (isFeedLike) {
      resetFilters();
      document.getElementById("actionable-toggle").classList.remove("active");
      renderAll();
    }
  });
});

loadFeed();
loadBulletin();
