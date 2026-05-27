window.uploadFile = async function () {
    const fileInput = document.getElementById("fileInput");
    const uploadBtn = document.getElementById("uploadBtn");
    const selectBtn = document.getElementById("selectBtn");
    const fileNameDisplay = document.getElementById("file-name-display");
    const loader = document.getElementById("loader");
    const statsGrid = document.getElementById("stats-grid");
    const resultsContainer = document.getElementById("results-container");
    const errorToast = document.getElementById("errorToast");

    if (!fileInput.files.length) {
        alert("Please select a CSV file first.");
        return;
    }

    // UI Loading State
    uploadBtn.disabled = true;
    uploadBtn.textContent = "⏳ Processing...";
    loader.classList.remove("hidden");
    statsGrid.classList.add("hidden");
    resultsContainer.classList.add("hidden");
    errorToast.classList.remove("show");

    const formData = new FormData();
    formData.append("file", fileInput.files[0]);

    try {
        const response = await fetch("http://127.0.0.1:8000/upload", {
            method: "POST",
            body: formData
        });

        if (!response.ok) throw new Error(`HTTP ${response.status}: ${response.statusText}`);

        const data = await response.json();
        if (data.status !== "success") throw new Error(data.message || "Analysis failed");

        const result = data.data;
        renderDashboard(result);

        // UI Success State
        statsGrid.classList.remove("hidden");
        resultsContainer.classList.remove("hidden");
        uploadBtn.textContent = "🚀 Launch New Analysis";
    } catch (error) {
        console.error("Upload failed:", error);
        errorToast.textContent = `⚠️ ${error.message}`;
        errorToast.classList.add("show");
        setTimeout(() => errorToast.classList.remove("show"), 5000);
        uploadBtn.textContent = "🚀 Retry Upload";
    } finally {
        uploadBtn.disabled = false;
        loader.classList.add("hidden");
        
        // ✨ FIX: Reset file input so the user can upload the SAME file again!
        fileInput.value = ""; 
        selectBtn.classList.remove("hidden");
        uploadBtn.classList.add("hidden");
        fileNameDisplay.textContent = "";
    }
};

// ─────────────────────────────────────────────
// RENDER ENGINE
// ─────────────────────────────────────────────
function renderDashboard(d) {
    // 1. System Diagnostics
    const healthScore = d.dataset_health?.health_score ?? 0;
    document.getElementById("health-val").textContent = healthScore;
    document.getElementById("health-bar").style.width = `${healthScore}%`;

    const stabilityIndex = d.analytical_stability?.stability_index ?? 0;
    document.getElementById("stability-val").textContent = stabilityIndex;
    const stabLabel = d.analytical_stability?.label?.toLowerCase() || "unknown";
    const stabElement = document.getElementById("stability-label");
    stabElement.textContent = stabLabel.toUpperCase();
    stabElement.className = `stability-tag ${stabLabel}`;

    const confidence = d.executive_synthesis?.confidence ?? 0;
    document.getElementById("confidence-val").textContent = `${(confidence * 100).toFixed(1)}%`;
    document.getElementById("confidence-bar").style.width = `${confidence * 100}%`;

    // 2. AI Narrative
    document.getElementById("ai-narrative").textContent = 
        d.narrative_summary?.full_narrative || "AI analysis pending. Review metrics below.";

    // 3. Chart
    const chartImg = document.getElementById("analysis-chart");
    const chartPlaceholder = document.getElementById("chart-placeholder");
    if (d.chart_url) {
        chartImg.src = `http://127.0.0.1:8000${d.chart_url}?t=${Date.now()}`;
        chartImg.style.display = "block";
        chartPlaceholder.style.display = "none";
    } else {
        chartImg.style.display = "none";
        chartPlaceholder.style.display = "block";
    }

    // 4. Correlations Table
    const tbody = document.querySelector("#signals-table tbody");
    const pairs = d.correlations?.pairs || [];
    if (pairs.length > 0) {
        tbody.innerHTML = pairs.slice(0, 6).map(c => `
            <tr>
                <td><strong>${c.pair}</strong></td>
                <td>${c.pearson}</td>
                <td><span class="badge ${getStrengthClass(c.strength)}">${c.strength}</span></td>
                <td>${c.significance}</td>
            </tr>
        `).join("");
    } else {
        tbody.innerHTML = `<tr><td colspan="4" style="text-align:center; color:var(--text-dim)">No significant correlations detected.</td></tr>`;
    }

    // 5. Recommendations
    const recsList = document.getElementById("recommendations-list");
    const recs = d.recommendations?.recommendations || [];
    if (recs.length > 0) {
        recsList.innerHTML = recs.map(r => `
            <div class="rec-item">
                <span class="badge ${r.priority.toLowerCase()}">${r.priority}</span>
                <strong>${r.action}</strong>
                <div class="reason">${r.reason}</div>
            </div>
        `).join("");
    } else {
        recsList.innerHTML = `<p class="placeholder-text">No recommendations generated.</p>`;
    }
}

function getStrengthClass(strength) {
    if (["strong", "very strong"].includes(strength)) return "high";
    if (strength === "moderate") return "medium";
    return "low";
}

// ─────────────────────────────────────────────
// DRAG & DROP + FILE INPUT SETUP
// ─────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
    const dropZone = document.getElementById("drop-zone");
    const fileInput = document.getElementById("fileInput");
    const selectBtn = document.getElementById("selectBtn");
    const uploadBtn = document.getElementById("uploadBtn");
    const fileNameDisplay = document.getElementById("file-name-display");

    function handleFileSelected(files) {
        if (files.length > 0) {
            fileNameDisplay.textContent = `📁 ${files[0].name}`;
            selectBtn.classList.add("hidden");
            uploadBtn.classList.remove("hidden");
        }
    }

    dropZone.addEventListener("dragover", e => { 
        e.preventDefault(); 
        dropZone.style.borderColor = "var(--cyan)"; 
    });
    
    dropZone.addEventListener("dragleave", () => 
        dropZone.style.borderColor = "var(--glass-border)"
    );
    
    dropZone.addEventListener("drop", e => {
        e.preventDefault();
        dropZone.style.borderColor = "var(--glass-border)";
        if (e.dataTransfer.files.length) {
            fileInput.files = e.dataTransfer.files;
            handleFileSelected(e.dataTransfer.files);
        }
    });
    
    fileInput.addEventListener("change", () => handleFileSelected(fileInput.files));
});