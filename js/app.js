const $ = (id) => document.getElementById(id);

function prettyCurrency(v) {
  if (typeof v !== "number" || Number.isNaN(v)) return "N/A";
  return `$${v.toLocaleString()}`;
}

function renderAnalyzeOutput(data) {
  const rent = data?.rent_estimate || {};
  const flag = data?.flag || {};
  const zillow = rent?.zillow || {};

  const lines = [
    "TENANT SHIELD ANALYSIS",
    "",
    `Fair rent range: ${prettyCurrency(rent.fair_rent_low)} - ${prettyCurrency(rent.fair_rent_high)}`,
    `Fair rent midpoint: ${prettyCurrency(rent.fair_rent_mid)}`,
    `Pricing flag: ${flag.label || "N/A"} (${flag.level || "unknown"})`,
    `Monthly delta: ${prettyCurrency(flag.monthly_delta)}`,
    `Annual delta: ${prettyCurrency(flag.annual_delta)}`,
    "",
    "Zillow signal",
    `Status: ${zillow.status || "missing"}`,
    `Metro value: ${zillow.metro_value ?? "N/A"}`,
    `National value: ${zillow.national_value ?? "N/A"}`,
    `Applied adjustment: ${prettyCurrency(zillow.applied_adjustment)}`,
    "",
    "Nearby ZIP comparisons",
  ];

  const nearby = Array.isArray(data?.nearby_zips) ? data.nearby_zips : [];
  if (!nearby.length) {
    lines.push("- N/A");
  } else {
    for (const n of nearby) {
      lines.push(`- ${n.zip_code} (${n.neighborhood}): ${prettyCurrency(n.estimated_fair_rent)}`);
    }
  }

  lines.push("", "Raw JSON", JSON.stringify(data, null, 2));
  return lines.join("\n");
}

async function loadZips() {
  const sel = $("zip");
  if (!sel) return;
  const res = await fetch("/zips");
  if (!res.ok) throw new Error(`Failed loading zips (${res.status})`);
  const zips = await res.json();
  sel.innerHTML = "";
  for (const z of zips) {
    const opt = document.createElement("option");
    opt.value = z.zip;
    opt.textContent = `${z.zip} ${z.neighborhood ? "- " + z.neighborhood : ""}`;
    sel.appendChild(opt);
  }
}

async function analyze() {
  const out = $("out");
  if (!out) return;

  const payload = {
    address: $("address")?.value?.trim() || "",
    zip_code: $("zip")?.value || "",
    bedrooms: $("bedrooms")?.value || "2",
    asking_rent: Number($("asking_rent")?.value || 0),
    amenities: [],
    sqft: null,
  };

  out.textContent = "Analyzing...";

  const res = await fetch("/analyze", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  let body;
  try {
    body = await res.json();
  } catch {
    const text = await res.text();
    out.textContent = text || `Unexpected response (${res.status})`;
    return;
  }

  if (!res.ok) {
    const detail = body?.detail || body?.message || JSON.stringify(body);
    out.textContent = `Request failed (${res.status}): ${detail}`;
    return;
  }

  out.textContent = renderAnalyzeOutput(body);
}

window.addEventListener("DOMContentLoaded", async () => {
  const out = $("out");
  try {
    await loadZips();
  } catch (err) {
    if (out) out.textContent = `Startup error: ${err?.message || err}`;
  }

  $("go")?.addEventListener("click", analyze);
});