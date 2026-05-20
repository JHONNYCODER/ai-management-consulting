window.uploadFile = async function () {

    const fileInput = document.getElementById("fileInput");

    if (!fileInput.files.length) {
        alert("Please select a CSV file.");
        return;
    }

    const formData = new FormData();
    formData.append("file", fileInput.files[0]);

    const response = await fetch("http://127.0.0.1:8000/upload", {
        method: "POST",
        body: formData
    });

    const data = await response.json();

    let output = `<h3>Analysis Results</h3>`;

    data.insights.forEach(insight => {
        output += `<p>${insight}</p>`;
    });

    if (data.chart_url) {
        output += `<img src="http://127.0.0.1:8000${data.chart_url}" width="400">`;
    }

    document.getElementById("results").innerHTML = output;
};