// ============ CHART.JS CONFIGURATION ============
const chartColors = {
    primary: '#4F46E5',
    success: '#10B981',
    warning: '#F59E0B',
    danger: '#EF4444',
    info: '#3B82F6',
    lightBg: '#F3F4F6',
    borderColor: '#E5E7EB'
};

// Chart defaults
Chart.defaults.font.family = "Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif";
Chart.defaults.color = '#6B7280';

// ============ REVENUE TREND CHART ============
function initRevenueChart() {
    const ctx = document.getElementById('revenueChart');
    if (!ctx) return;

    const dates = ['1 Oct', '5 Oct', '10 Oct', '15 Oct', '20 Oct', '25 Oct', '30 Oct'];
    const data = [35000, 42000, 38000, 52000, 61000, 58000, 72000];

    new Chart(ctx, {
        type: 'line',
        data: {
            labels: dates,
            datasets: [{
                label: 'Revenue (₹)',
                data: data,
                borderColor: chartColors.primary,
                backgroundColor: `${chartColors.primary}15`,
                borderWidth: 3,
                fill: true,
                tension: 0.4,
                pointRadius: 5,
                pointBackgroundColor: chartColors.primary,
                pointBorderColor: '#FFFFFF',
                pointBorderWidth: 2,
                pointHoverRadius: 7,
                pointHoverBackgroundColor: chartColors.primary,
                pointHoverBorderWidth: 2
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            plugins: {
                legend: {
                    display: true,
                    position: 'top',
                    labels: {
                        usePointStyle: true,
                        padding: 20,
                        font: { size: 12, weight: '600' },
                        generateLabels: () => []
                    }
                },
                tooltip: {
                    backgroundColor: '#111827',
                    padding: 12,
                    borderRadius: 8,
                    titleFont: { size: 13, weight: '700' },
                    bodyFont: { size: 12 },
                    callbacks: {
                        label: function(context) {
                            return '₹' + context.parsed.y.toLocaleString('en-IN');
                        }
                    }
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    max: 80000,
                    ticks: {
                        callback: function(value) {
                            return '₹' + (value / 1000) + 'k';
                        },
                        font: { size: 11 }
                    },
                    grid: {
                        color: chartColors.borderColor,
                        drawBorder: false
                    }
                },
                x: {
                    grid: {
                        display: false,
                        drawBorder: false
                    },
                    ticks: {
                        font: { size: 11 }
                    }
                }
            }
        }
    });
}

// ============ BATCH DISTRIBUTION CHART ============
function initBatchChart() {
    const ctx = document.getElementById('batchChart');
    if (!ctx) return;

    new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: ['Science 10th', 'JEE Mains', 'Commerce 12th', 'NEET', 'Arts 11th'],
            datasets: [{
                data: [80, 60, 90, 40, 55],
                backgroundColor: [
                    chartColors.primary,
                    chartColors.info,
                    chartColors.success,
                    chartColors.warning,
                    chartColors.danger
                ],
                borderColor: '#FFFFFF',
                borderWidth: 2,
                hoverOffset: 8
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: {
                        usePointStyle: true,
                        padding: 15,
                        font: { size: 11, weight: '600' }
                    }
                },
                tooltip: {
                    backgroundColor: '#111827',
                    padding: 10,
                    borderRadius: 6,
                    titleFont: { size: 12, weight: '700' },
                    bodyFont: { size: 11 },
                    callbacks: {
                        label: function(context) {
                            return '₹' + context.parsed + 'k';
                        }
                    }
                }
            }
        }
    });
}

// ============ RATING DISTRIBUTION CHART ============
function initRatingChart() {
    const ctx = document.getElementById('ratingChart');
    if (!ctx) return;

    new Chart(ctx, {
        type: 'bar',
        data: {
            labels: ['5 Stars', '4 Stars', '3 Stars', '2 Stars', '1 Star'],
            datasets: [{
                label: 'Number of Reviews',
                data: [245, 65, 20, 8, 4],
                backgroundColor: [
                    chartColors.success,
                    chartColors.info,
                    chartColors.warning,
                    '#FCA5A5',
                    chartColors.danger
                ],
                borderRadius: 6,
                borderSkipped: false
            }]
        },
        options: {
            indexAxis: 'y',
            responsive: true,
            maintainAspectRatio: true,
            plugins: {
                legend: {
                    display: false
                },
                tooltip: {
                    backgroundColor: '#111827',
                    padding: 10,
                    borderRadius: 6,
                    titleFont: { size: 12, weight: '700' },
                    bodyFont: { size: 11 }
                }
            },
            scales: {
                x: {
                    beginAtZero: true,
                    ticks: {
                        font: { size: 11 }
                    },
                    grid: {
                        color: chartColors.borderColor
                    }
                },
                y: {
                    ticks: {
                        font: { size: 11 }
                    },
                    grid: {
                        display: false,
                        drawBorder: false
                    }
                }
            }
        }
    });
}

// ============ INITIALIZE CHARTS ============
function initializeDashboard() {
    // Check if we're on the dashboard page
    const dashboardSection = document.getElementById('page-dashboard');
    if (dashboardSection && dashboardSection.classList.contains('active')) {
        // Give DOM time to render
        setTimeout(() => {
            initRevenueChart();
            initBatchChart();
        }, 100);
    }
}

function initializeReviews() {
    // Check if we're on the reviews page
    const reviewsSection = document.getElementById('page-reviews');
    if (reviewsSection && reviewsSection.classList.contains('active')) {
        setTimeout(() => {
            initRatingChart();
        }, 100);
    }
}

// Initialize on load
document.addEventListener('DOMContentLoaded', function() {
    initializeDashboard();
    initializeReviews();
});

// Re-initialize charts when pages are shown
document.addEventListener('pageChanged', function(e) {
    if (e.detail === 'dashboard') {
        setTimeout(() => {
            initRevenueChart();
            initBatchChart();
        }, 100);
    } else if (e.detail === 'reviews') {
        setTimeout(() => {
            initRatingChart();
        }, 100);
    }
});
