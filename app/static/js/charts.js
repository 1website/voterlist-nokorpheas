// Chart.js Live Dashboard Analytics

let stationChart = null;
let villageChart = null;

function initCharts(stationLabels, stationVoted, stationTotal, villageLabels, villageVoted, villageTotal) {
    // 1. Station Turnout Bar Chart
    const stationCtx = document.getElementById('stationChart');
    if (stationCtx && typeof Chart !== 'undefined') {
        stationChart = new Chart(stationCtx, {
            type: 'bar',
            data: {
                labels: stationLabels,
                datasets: [
                    {
                        label: 'បោះឆ្នោតរួច (Voted)',
                        data: stationVoted,
                        backgroundColor: '#10b981',
                        borderRadius: 6
                    },
                    {
                        label: 'មិនទាន់បោះ (Pending)',
                        data: stationTotal.map((tot, idx) => tot - stationVoted[idx]),
                        backgroundColor: '#e2e8f0',
                        borderRadius: 6
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    x: {
                        stacked: true,
                        grid: { display: false }
                    },
                    y: {
                        stacked: true,
                        beginAtZero: true,
                        ticks: { stepSize: 2 }
                    }
                },
                plugins: {
                    legend: { position: 'top' }
                }
            }
        });
    }

    // 2. Village Turnout Bar Chart
    const villageCtx = document.getElementById('villageChart');
    if (villageCtx && typeof Chart !== 'undefined') {
        villageChart = new Chart(villageCtx, {
            type: 'bar',
            data: {
                labels: villageLabels,
                datasets: [
                    {
                        label: 'បោះឆ្នោតរួច',
                        data: villageVoted,
                        backgroundColor: '#3b82f6',
                        borderRadius: 6
                    },
                    {
                        label: 'មិនទាន់បោះ',
                        data: villageTotal.map((tot, idx) => tot - villageVoted[idx]),
                        backgroundColor: '#f1f5f9',
                        borderRadius: 6
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    x: {
                        stacked: true,
                        grid: { display: false }
                    },
                    y: {
                        stacked: true,
                        beginAtZero: true
                    }
                },
                plugins: {
                    legend: { position: 'top' }
                }
            }
        });
    }
}

// Auto-refresh stats from server every 10 seconds
async function refreshDashboardStats() {
    try {
        const res = await fetch('/api/dashboard/stats');
        const data = await res.json();

        // Update overall percentage text & meter
        const turnoutElem = document.getElementById('dashboardTurnoutPct');
        if (turnoutElem) turnoutElem.innerText = `${data.turnout_pct}%`;

        const totalVotedElem = document.getElementById('dashboardTotalVoted');
        if (totalVotedElem) totalVotedElem.innerText = data.total_voted;

        const totalNotVotedElem = document.getElementById('dashboardTotalNotVoted');
        if (totalNotVotedElem) totalNotVotedElem.innerText = data.total_not_voted;

        const progressBar = document.getElementById('dashboardProgressBar');
        if (progressBar) progressBar.style.width = `${data.turnout_pct}%`;

        // Update Charts
        if (stationChart && data.stations) {
            stationChart.data.labels = data.stations.labels;
            stationChart.data.datasets[0].data = data.stations.voted;
            stationChart.data.datasets[1].data = data.stations.total.map((tot, idx) => tot - data.stations.voted[idx]);
            stationChart.update();
        }

        if (villageChart && data.villages) {
            villageChart.data.labels = data.villages.labels;
            villageChart.data.datasets[0].data = data.villages.voted;
            villageChart.data.datasets[1].data = data.villages.total.map((tot, idx) => tot - data.villages.voted[idx]);
            villageChart.update();
        }
    } catch (e) {
        console.log("Auto refresh error", e);
    }
}
