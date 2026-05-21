window.uploadFile = async function () {

    const fileInput = document.getElementById("fileInput");
    const resultsDiv = document.getElementById("results");

    if (!fileInput.files.length) {
        alert("Please select a CSV file.");
        return;
    }

    resultsDiv.innerHTML = "<p>Uploading and analyzing file...</p>";

    const formData = new FormData();
    formData.append("file", fileInput.files[0]);

    try {

        const response = await fetch("http://127.0.0.1:8000/upload", {
            method: "POST",
            body: formData
        });

        const data = await response.json();

        console.log(data); //temporary

        if (data.status === "error") {

            resultsDiv.innerHTML =
                `<p style="color:red;">${data.message}</p>`;

            return;
        }

        const result = data.data;

        let output = `<h3>Analysis Results</h3>`;

        result.insights.summary.forEach(insight => {
            output += `<p>${insight}</p>`;
        });

        result.insights.metrics.forEach(metric => {
            output += `
                <div>
                    <h4>${metric.column}</h4>
                    <p>Mean: ${metric.mean}</p>
                    <p>Median: ${metric.median}</p>
                    <p>Std: ${metric.std}</p>
                    <p>Min: ${metric.min}</p>
                    <p>Max: ${metric.max}</p>
                </div>
            `;
        });

        if (result.chart_url) {

            output += `
                <img
                    src="http://127.0.0.1:8000${result.chart_url}" width="400"
                >
            `;
        }
        console.log(result.chart_url);
        resultsDiv.innerHTML = output;

    } catch (error) {

        resultsDiv.innerHTML =
            `<p style="color:red;">Server connection failed.</p>`;

        console.error(error);
    }
};