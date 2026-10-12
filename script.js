const rows = document.querySelector("#casino-rows");
const status = document.querySelector("#status");
const updatedAt = document.querySelector("#updated-at");

function addCell(row, value) {
  const cell = document.createElement("td");
  cell.textContent = value || "Not listed";
  row.append(cell);
}

function addSourceLink(row, url) {
  const cell = document.createElement("td");
  const sourceUrl = new URL(url);
  if (sourceUrl.protocol !== "https:") {
    throw new Error("The source link must use HTTPS.");
  }

  const link = document.createElement("a");
  link.href = sourceUrl.href;
  link.textContent = "View source";
  link.target = "_blank";
  link.rel = "noopener noreferrer";
  cell.append(link);
  row.append(cell);
}

async function loadBonuses() {
  try {
    const response = await fetch("./bonuses.json", { cache: "no-store" });
    if (!response.ok) {
      throw new Error(`Could not load bonus data (${response.status}).`);
    }

    const data = await response.json();
    if (!Array.isArray(data.casinos)) {
      throw new Error("The bonus data has an invalid format.");
    }

    if (data.casinos.length === 0) {
      status.textContent = "No bonus data yet. Run the scraper to populate this table.";
      return;
    }

    for (const casino of data.casinos) {
      if (!casino.casino || !casino.source_url) {
        throw new Error("A casino record is missing its name or source link.");
      }

      const row = document.createElement("tr");
      addCell(row, casino.casino);
      addCell(row, casino.welcome_bonus);
      addCell(row, casino.wagering_requirement);
      addCell(row, casino.minimum_deposit);
      addSourceLink(row, casino.source_url);
      rows.append(row);
    }

    status.textContent = "";
    if (data.scraped_at) {
      const date = new Date(data.scraped_at);
      if (!Number.isNaN(date.valueOf())) {
        updatedAt.textContent = `Data fetched ${date.toLocaleString()}`;
      }
    }
  } catch (error) {
    status.classList.add("error");
    status.textContent = `Bonus data unavailable: ${error.message}`;
  }
}

loadBonuses();