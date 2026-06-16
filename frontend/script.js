let chartInstances = [];

// ─────────────────────────────────────────────
// XSS SANITIZATION HELPER
// ─────────────────────────────────────────────
function escapeHTML(str) {
    if (typeof str !== 'string') return str;
    return str.replace(/[&<>'"]/g, 
        tag => ({
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            "'": '&#39;',
            '"': '&quot;'
        }[tag] || tag)
    );
}

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
        // FIX: Use relative URL instead of hardcoded localhost
        const response = await fetch("http://127.0.0.1:8000/upload", {
            method: "POST",
            body: formData
        });

        if (!response.ok) throw new Error(`HTTP ${response.status}: ${response.statusText}`);

        const data = await response.json();
        
        // FIX: Handle partial_success so the UI doesn't discard valid partial data
        if (data.status === "error") throw new Error(data.message || "Analysis failed");

        const result = data.data;
        renderDashboard(result);

        // UI Success State
        statsGrid.classList.remove("hidden");
        resultsContainer.classList.remove("hidden");
        uploadBtn.textContent = "🚀 Launch New Analysis";

        // ✅ BUTTERY SMOOTH AUTO-SCROLL
        setTimeout(() => {
            const element = document.getElementById("stats-grid");
            const y = element.getBoundingClientRect().top + window.pageYOffset - 30;
            window.scrollTo({ top: y, behavior: 'smooth' });
        }, 300);

    } catch (error) {
        console.error("Upload failed:", error);
        errorToast.textContent = `⚠️ ${error.message}`;
        errorToast.classList.add("show");
        setTimeout(() => errorToast.classList.remove("show"), 5000);
        uploadBtn.textContent = "🚀 Retry Upload";
    } finally {
        uploadBtn.disabled = false;
        loader.classList.add("hidden");
        fileInput.value = ""; 
        selectBtn.classList.remove("hidden");
        uploadBtn.classList.add("hidden");
    }
};

// ─────────────────────────────────────────────
// RENDER ENGINE
// ─────────────────────────────────────────────
function renderDashboard(d) {
    // 1. System Diagnostics
    const healthScore = d.dataset_health?.health_score ?? 0;
    const healthEl = document.getElementById("health-val");
    animateValue(healthEl, 0, healthScore, 1200);
    
    if (healthScore >= 75) healthEl.style.color = "#10b981";
    else if (healthScore >= 40) healthEl.style.color = "#f59e0b";
    else healthEl.style.color = "#ef4444";
    
    document.getElementById("health-bar").style.width = `${healthScore}%`;

    const stabilityIndex = d.analytical_stability?.stability_index ?? 0;
    animateValue(document.getElementById("stability-val"), 0, stabilityIndex, 1200);
    
    const stabLabel = d.analytical_stability?.label?.toLowerCase() || "unknown";
    const stabElement = document.getElementById("stability-label");
    stabElement.textContent = stabLabel.toUpperCase();
    stabElement.className = `stability-tag ${stabLabel}`;

    const confidence = d.executive_synthesis?.confidence ?? 0;
    const confPercent = (confidence * 100).toFixed(1);
    const confEl = document.getElementById("confidence-val");
    animateValue(confEl, 0, parseFloat(confPercent), 1200, '%');
    
    const confNum = parseFloat(confPercent);
    if (confNum >= 70) confEl.style.color = "#10b981";
    else if (confNum >= 40) confEl.style.color = "#f59e0b";
    else confEl.style.color = "#ef4444";
    
    document.getElementById("confidence-bar").style.width = `${confPercent}%`;

    // 2. AI Narrative (XSS PATCHED using escapeHTML)
    const narrativeEl = document.getElementById("ai-narrative");
    const narrativeData = d.narrative_summary?.full_narrative || "";
    
    if (narrativeEl) {
        if (Array.isArray(narrativeData)) {
            narrativeEl.innerHTML = `<ul class="ai-points-list">` + 
                narrativeData.map(p => `
                    <li class="ai-point-item">
                        <div class="ai-analysis-text">📊 ${escapeHTML(p.analysis || '')}</div>
                        <div class="ai-suggestion-text">${escapeHTML(p.suggestion || '')}</div>
                    </li>
                `).join("") + `</ul>`;
        } else {
            narrativeEl.textContent = narrativeData || "AI analysis pending. Review metrics below.";
        }
    }

    // 3. Animated Charts Grid
    const chartsContainer = document.getElementById("charts-container");
    const chartPlaceholder = document.getElementById("chart-placeholder");
    const mainGrid = document.getElementById("results-container");

    if (chartsContainer) {
        chartInstances.forEach(c => c.destroy());
        chartInstances = [];
        chartsContainer.innerHTML = '';

        if (d.charts && d.charts.length === 1) {
            mainGrid.classList.add("single-chart-layout");
        } else {
            mainGrid.classList.remove("single-chart-layout");
        }

        if (d.charts && d.charts.length > 0) {
            chartPlaceholder.style.display = "none";

            d.charts.forEach((chartData, index) => {
                const box = document.createElement('div');
                box.className = 'chart-box';
                
                const title = document.createElement('h5');
                title.textContent = chartData.title || `Chart ${index + 1}`;
                
                const canvas = document.createElement('canvas');
                canvas.id = `chart-${index}`;
                
                box.appendChild(title);
                box.appendChild(canvas);
                chartsContainer.appendChild(box);

                const type = chartData.type || 'line';
                let formattedDatasets = [];

                if (type === 'doughnut') {
                    const neonColors = ['#00f3ff', '#bc13fe', '#10b981', '#f59e0b', '#ef4444', '#6366f1', '#ec4899', '#14b8a6'];
                    formattedDatasets = chartData.datasets.map(ds => ({
                        ...ds,
                        backgroundColor: ds.data.map((_, i) => neonColors[i % neonColors.length]),
                        borderColor: '#050810',
                        borderWidth: 3,
                        hoverOffset: 10
                    }));
                } else if (type === 'scatter') {
                    formattedDatasets = chartData.datasets.map(ds => ({
                        ...ds,
                        backgroundColor: 'rgba(188, 19, 254, 0.6)',
                        borderColor: '#bc13fe',
                        pointRadius: 6,
                        pointHoverRadius: 9,
                        showLine: true,
                        borderWidth: 2,
                        tension: 0.3
                    }));
                } else {
                    formattedDatasets = chartData.datasets.map(ds => ({
                        ...ds,
                        borderColor: '#00f3ff',
                        backgroundColor: 'rgba(0, 243, 255, 0.1)',
                        borderWidth: 3,
                        pointBackgroundColor: '#bc13fe',
                        pointBorderColor: '#fff',
                        pointRadius: 4,
                        pointHoverRadius: 7,
                        tension: 0.4,
                        fill: true
                    }));
                }

                const ctx = canvas.getContext('2d');
                const newChart = new Chart(ctx, {
                    type: type,
                    data: {
                        labels: chartData.labels,
                        datasets: formattedDatasets
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        animation: {
                            duration: 1500,
                            easing: 'easeInOutQuart'
                        },
                        scales: type === 'doughnut' ? {} : {
                            x: {
                                ticks: { color: '#94a3b8', font: { size: 10 } },
                                grid: { color: 'rgba(255, 255, 255, 0.05)' }
                            },
                            y: {
                                ticks: { color: '#94a3b8', font: { size: 10 } },
                                grid: { color: 'rgba(255, 255, 255, 0.05)' }
                            }
                        },
                        plugins: {
                            legend: {
                                display: type === 'doughnut' || type === 'scatter',
                                labels: { color: '#e2e8f0', font: { size: 11 } }
                            },
                            tooltip: {
                                backgroundColor: 'rgba(15, 23, 42, 0.9)',
                                titleColor: '#00f3ff',
                                bodyColor: '#e2e8f0',
                                borderColor: 'rgba(255,255,255,0.1)',
                                borderWidth: 1,
                            }
                        }
                    }
                });
                
                chartInstances.push(newChart);
            });
        } else {
            chartPlaceholder.style.display = "block";
        }
    }

    // 4. Correlations Table (XSS PATCHED using escapeHTML)
    const tbody = document.querySelector("#signals-table tbody");
    const pairs = d.correlations?.pairs || [];
    if (tbody) {
        if (pairs.length > 0) {
            tbody.innerHTML = pairs.slice(0, 6).map(c => `
                <tr>
                    <td><strong>${escapeHTML(c.pair)}</strong></td>
                    <td>${escapeHTML(c.pearson)}</td>
                    <td><span class="badge ${getStrengthClass(c.strength)}">${escapeHTML(c.strength)}</span></td>
                    <td>${escapeHTML(c.significance)}</td>
                </tr>
            `).join("");
        } else {
            tbody.innerHTML = `<tr><td colspan="4" style="text-align:center; color:var(--text-dim)">No significant correlations detected.</td></tr>`;
        }
    }

    // 5. Recommendations (XSS PATCHED using escapeHTML)
    const recsList = document.getElementById("recommendations-list");
    const recs = d.recommendations?.recommendations || [];
    if (recsList) {
        if (recs.length > 0) {
            recsList.innerHTML = recs.map(r => `
                <div class="rec-item">
                    <span class="badge ${r.priority.toLowerCase()}">${escapeHTML(r.priority)}</span>
                    <strong>${escapeHTML(r.action)}</strong>
                    <div class="reason">${escapeHTML(r.reason)}</div>
                </div>
            `).join("");
        } else {
            recsList.innerHTML = `<p class="placeholder-text">No recommendations generated.</p>`;
        }
    }
} 

function getStrengthClass(strength) {
    if (["strong", "very strong"].includes(strength)) return "high";
    if (strength === "moderate") return "medium";
    return "low";
}

// ─────────────────────────────────────────────
// ANIMATED COUNTERS
// ─────────────────────────────────────────────
function animateValue(element, start, end, duration, suffix = '') {
    let startTimestamp = null;
    const step = (timestamp) => {
        if (!startTimestamp) startTimestamp = timestamp;
        const progress = Math.min((timestamp - startTimestamp) / duration, 1);
        const current = Math.floor(progress * (end - start) + start);
        element.textContent = current + suffix;
        if (progress < 1) {
            window.requestAnimationFrame(step);
        }
    };
    window.requestAnimationFrame(step);
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