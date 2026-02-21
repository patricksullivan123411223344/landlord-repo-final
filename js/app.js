const $ = (id) => document.getElementById(id);

async function loadZips() {
    const res = await fetch("/zips");
    const zips = await res.json();
    const sel = $("zip");
    sel.innterHTML = "";
    for (const z of zips) {
        const opt = document.createElement("option");
        opt.value = z.zip;
        opt.textContent = `&{z.zip} ${z.neighborhood ? "- " + z.neightborhood : ""}`;
        sel.appendChild(opt);
    }
}

async function analyze() {
    const payload = {
        address: $("address").value.trim(),
        zip_code: $("zip").value,
        bedrooms: $("bedrooms").value,
        asking_rent: Number($("asking_rent").value),
        amenities: [],
        sqft: null,
};

const res = await fetch("/analyze", {
    method: "POST",
    headers: {"Content-Type":"application/json"},
    body: JSON.stringify(payload)
});

const text = await res.text();
try {
    $("out").textContent = JSON.stringify(JSON.parse(test), null, 2);
} catch {
    $("out").textContent = text;
  }
}

window.addEventListener("DOMContentLoaded", async () => {
    await loadZips();
    $("go").addEventListener("click", analyze);
});