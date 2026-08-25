// Chart.js Live Dashboard Analytics

let stationChart = null;
let villageChart = null;

function getChartThemeColors() {
    const isDark = document.documentElement.classList.contains('dark');
    return {
        textColor: isDark ? '#94a3b8' : '#64748b',
        gridColor: isDark ? 'rgba(255, 255, 255, 0.08)' : 'rgba(0, 0, 0, 0.05)',
        pendingBg: isDark ? '#1e293b' : '#e2e8f0',
        villagePendingBg: isDark ? '#1e293b' : '#f1f5f9'
    };
}

function initCharts(stationLabels, stationVoted, stationTotal, villageLabels, villageVoted, villageTotal) {
    const theme = getChartThemeColors();

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
                        backgroundColor: theme.pendingBg,
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
                        grid: { display: false },
                        ticks: { color: theme.textColor }
                    },
                    y: {
                        stacked: true,
                        beginAtZero: true,
                        ticks: { stepSize: 2, color: theme.textColor },
                        grid: { color: theme.gridColor }
                    }
                },
                plugins: {
                    legend: {
                        position: 'top',
                        labels: { color: theme.textColor }
                    }
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
                        backgroundColor: theme.villagePendingBg,
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
                        grid: { display: false },
                        ticks: { color: theme.textColor }
                    },
                    y: {
                        stacked: true,
                        beginAtZero: true,
                        ticks: { color: theme.textColor },
                        grid: { color: theme.gridColor }
                    }
                },
                plugins: {
                    legend: {
                        position: 'top',
                        labels: { color: theme.textColor }
                    }
                }
            }
        });
    }
}

// Dynamically update charts on theme toggle (Light / Dark)
window.updateChartsTheme = function(isDark) {
    const theme = getChartThemeColors();
    
    [stationChart, villageChart].forEach(chart => {
        if (chart) {
            if (chart.options.scales.x && chart.options.scales.x.ticks) {
                chart.options.scales.x.ticks.color = theme.textColor;
            }
            if (chart.options.scales.y) {
                if (chart.options.scales.y.ticks) chart.options.scales.y.ticks.color = theme.textColor;
                if (chart.options.scales.y.grid) chart.options.scales.y.grid.color = theme.gridColor;
            }
            if (chart.options.plugins && chart.options.plugins.legend && chart.options.plugins.legend.labels) {
                chart.options.plugins.legend.labels.color = theme.textColor;
            }
            if (chart.data.datasets && chart.data.datasets[1]) {
                chart.data.datasets[1].backgroundColor = theme.pendingBg;
            }
            chart.update();
        }
    });
};

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
