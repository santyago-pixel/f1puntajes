(function () {
  "use strict";

  var CSV_PATH = "data/scores.csv";

  var CHART_COLORS = [
    "#38bdf8",
    "#818cf8",
    "#f472b6",
    "#fbbf24",
    "#34d399",
    "#fb923c",
    "#a78bfa",
    "#f87171",
    "#22d3ee",
    "#a3e635",
  ];

  function parseCSV(text) {
    var lines = text.trim().split("\n");
    if (lines.length < 2) return null;

    var headers = lines[0].split(",").map(function (h) {
      return h.trim();
    });
    var people = headers.slice(1);

    var rows = [];
    for (var i = 1; i < lines.length; i++) {
      var cols = lines[i].split(",").map(function (c) {
        return c.trim();
      });
      if (cols.length < 2) continue;

      var row = { date: cols[0], scores: {} };
      for (var j = 1; j < cols.length; j++) {
        var val = parseFloat(cols[j]);
        row.scores[people[j - 1]] = isNaN(val) ? 0 : val;
      }
      rows.push(row);
    }

    return { people: people, rows: rows };
  }

  function formatDate(dateStr) {
    var parts = dateStr.split("-");
    if (parts.length === 3) {
      var months = [
        "Jan", "Feb", "Mar", "Apr", "May", "Jun",
        "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
      ];
      var monthIndex = parseInt(parts[1], 10) - 1;
      return months[monthIndex] + " " + parseInt(parts[2], 10);
    }
    return dateStr;
  }

  function renderStandings(data) {
    var section = document.getElementById("standings-section");
    var container = document.getElementById("standings");
    var lastRow = data.rows[data.rows.length - 1];

    var sorted = data.people
      .map(function (name) {
        return { name: name, score: lastRow.scores[name] || 0 };
      })
      .sort(function (a, b) {
        return b.score - a.score;
      });

    var html = '<ol class="standings-list">';
    for (var i = 0; i < sorted.length; i++) {
      var rankClass = i < 3 ? " standings-top" + (i + 1) : "";
      html +=
        '<li class="standings-item' + rankClass + '">' +
        '<span class="standings-name">' + escapeHtml(sorted[i].name) + "</span>" +
        '<span class="standings-score">' + sorted[i].score + "</span>" +
        "</li>";
    }
    html += "</ol>";

    container.innerHTML = html;
    section.hidden = false;
  }

  function renderTable(data) {
    var section = document.getElementById("table-section");
    var thead = document.getElementById("tableHead");
    var tbody = document.getElementById("tableBody");

    var headHtml = "<tr><th>Date</th>";
    for (var i = 0; i < data.people.length; i++) {
      headHtml += "<th>" + escapeHtml(data.people[i]) + "</th>";
    }
    headHtml += "</tr>";
    thead.innerHTML = headHtml;

    var bodyHtml = "";
    for (var r = data.rows.length - 1; r >= 0; r--) {
      var row = data.rows[r];
      bodyHtml += "<tr><td>" + formatDate(row.date) + "</td>";
      for (var p = 0; p < data.people.length; p++) {
        bodyHtml += "<td>" + (row.scores[data.people[p]] || 0) + "</td>";
      }
      bodyHtml += "</tr>";
    }
    tbody.innerHTML = bodyHtml;
    section.hidden = false;
  }

  function renderChart(data) {
    var section = document.getElementById("chart-section");
    var ctx = document.getElementById("scoreChart").getContext("2d");

    var labels = data.rows.map(function (row) {
      return formatDate(row.date);
    });

    // Determine top 10 scorers by latest score
    var lastRow = data.rows[data.rows.length - 1];
    var sortedPeople = data.people
      .slice()
      .sort(function (a, b) {
        return (lastRow.scores[b] || 0) - (lastRow.scores[a] || 0);
      })
      .slice(0, 10);

    var datasets = sortedPeople.map(function (name, idx) {
      return {
        label: name,
        data: data.rows.map(function (row) {
          return row.scores[name] || 0;
        }),
        borderColor: CHART_COLORS[idx % CHART_COLORS.length],
        backgroundColor: CHART_COLORS[idx % CHART_COLORS.length] + "22",
        borderWidth: 2.5,
        pointRadius: 4,
        pointHoverRadius: 6,
        tension: 0.3,
        fill: false,
      };
    });

    new Chart(ctx, {
      type: "line",
      data: { labels: labels, datasets: datasets },
      options: {
        responsive: true,
        maintainAspectRatio: true,
        interaction: { mode: "index", intersect: false },
        plugins: {
          legend: {
            labels: {
              color: "#94a3b8",
              usePointStyle: true,
              pointStyle: "circle",
              padding: 20,
              font: { size: 13 },
            },
          },
          tooltip: {
            backgroundColor: "rgba(15, 23, 42, 0.95)",
            titleColor: "#e2e8f0",
            bodyColor: "#cbd5e1",
            borderColor: "rgba(148, 163, 184, 0.2)",
            borderWidth: 1,
            padding: 12,
            cornerRadius: 8,
          },
        },
        scales: {
          x: {
            ticks: { color: "#64748b", font: { size: 12 } },
            grid: { color: "rgba(148, 163, 184, 0.08)" },
          },
          y: {
            ticks: { color: "#64748b", font: { size: 12 } },
            grid: { color: "rgba(148, 163, 184, 0.08)" },
            beginAtZero: true,
          },
        },
      },
    });

    section.hidden = false;
  }

  function escapeHtml(str) {
    var div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
  }

  function showError(message) {
    var loading = document.getElementById("loading");
    var errorEl = document.getElementById("error");
    loading.hidden = true;
    errorEl.textContent = message;
    errorEl.hidden = false;
  }

  function init() {
    fetch(CSV_PATH)
      .then(function (res) {
        if (!res.ok) throw new Error("Could not load " + CSV_PATH + " (HTTP " + res.status + ")");
        return res.text();
      })
      .then(function (text) {
        var data = parseCSV(text);
        if (!data || data.rows.length === 0) {
          showError("The CSV file is empty or has an invalid format.");
          return;
        }

        document.getElementById("loading").hidden = true;

        renderStandings(data);
        renderChart(data);
        renderTable(data);
      })
      .catch(function (err) {
        showError("Error loading scores: " + err.message);
      });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
