// ============ PAGE NAVIGATION ============
class AdminPanel {
    constructor() {
        this.currentPage = 'dashboard';
        this.init();
    }

    init() {
        this.setupEventListeners();
        this.loadDarkModePreference();
    }

    setupEventListeners() {
        // Sidebar navigation
        document.querySelectorAll('.nav-link').forEach(link => {
            link.addEventListener('click', (e) => {
                e.preventDefault();
                const page = link.getAttribute('data-page');
                this.showPage(page);
            });
        });

        // Sidebar toggle
        const sidebarToggle = document.getElementById('sidebarToggle');
        if (sidebarToggle) {
            sidebarToggle.addEventListener('click', () => {
                this.toggleSidebar();
            });
        }

        // Dark mode toggle
        const darkModeToggle = document.getElementById('darkModeToggle');
        if (darkModeToggle) {
            darkModeToggle.addEventListener('click', () => {
                this.toggleDarkMode();
            });
        }

        // Table search
        const studentSearch = document.getElementById('studentSearch');
        if (studentSearch) {
            studentSearch.addEventListener('input', (e) => {
                this.searchTable(e.target.value);
            });
        }

        // Close modals on background click
        document.querySelectorAll('.modal').forEach(modal => {
            modal.addEventListener('hide.bs.modal', function() {
                this.resetForm(this.querySelector('form'));
            });
        });
    }

    showPage(pageId) {
        // Hide all page sections
        document.querySelectorAll('.page-section').forEach(el => {
            el.classList.remove('active');
        });

        // Show selected page
        const targetPage = document.getElementById('page-' + pageId);
        if (targetPage) {
            targetPage.classList.add('active');
            this.currentPage = pageId;

            // Update active nav item
            document.querySelectorAll('.nav-link').forEach(link => {
                link.classList.remove('active');
            });
            document.querySelector(`[data-page="${pageId}"]`).classList.add('active');

            // Emit page change event for charts
            const event = new CustomEvent('pageChanged', { detail: pageId });
            document.dispatchEvent(event);

            // Trigger chart initialization if needed
            if (pageId === 'dashboard') {
                setTimeout(() => {
                    if (window.initRevenueChart) initRevenueChart();
                    if (window.initBatchChart) initBatchChart();
                }, 100);
            }
        }
    }

    toggleSidebar() {
        document.body.classList.toggle('sidebar-collapsed');
    }

    toggleDarkMode() {
        const isDarkMode = document.body.classList.toggle('dark-mode');
        localStorage.setItem('darkMode', isDarkMode);
        
        // Update icon
        const toggle = document.getElementById('darkModeToggle');
        if (toggle) {
            toggle.innerHTML = isDarkMode ? '<i class="bi bi-sun"></i>' : '<i class="bi bi-moon"></i>';
        }
    }

    loadDarkModePreference() {
        const darkMode = localStorage.getItem('darkMode') === 'true';
        if (darkMode) {
            document.body.classList.add('dark-mode');
            const toggle = document.getElementById('darkModeToggle');
            if (toggle) {
                toggle.innerHTML = '<i class="bi bi-sun"></i>';
            }
        }
    }

    searchTable(query) {
        const table = document.getElementById('batchTable');
        if (!table) return;

        const rows = table.querySelectorAll('tbody tr');
        query = query.toLowerCase();

        rows.forEach(row => {
            const text = row.textContent.toLowerCase();
            row.style.display = text.includes(query) ? '' : 'none';
        });
    }

    resetForm(form) {
        if (form) {
            form.reset();
        }
    }
}

// ============ NOTIFICATIONS SYSTEM ============
class NotificationManager {
    constructor() {
        this.container = document.getElementById('toastContainer');
    }

    show(message, type = 'info', duration = 3000) {
        const toastId = 'toast-' + Date.now();
        const toast = document.createElement('div');
        toast.id = toastId;
        toast.className = `toast ${type}`;
        toast.setAttribute('role', 'alert');
        toast.setAttribute('aria-live', 'assertive');
        toast.setAttribute('aria-atomic', 'true');

        const iconMap = {
            success: 'check-circle',
            danger: 'exclamation-circle',
            warning: 'exclamation-triangle',
            info: 'info-circle'
        };

        toast.innerHTML = `
            <div class="d-flex align-items-start">
                <i class="bi bi-${iconMap[type] || 'info-circle'} me-2"></i>
                <div class="toast-body">
                    ${message}
                </div>
                <button type="button" class="btn-close ms-auto" data-bs-dismiss="toast"></button>
            </div>
        `;

        this.container.appendChild(toast);

        const bsToast = new bootstrap.Toast(toast);
        bsToast.show();

        // Auto remove
        setTimeout(() => {
            toast.remove();
        }, duration + 500);
    }

    success(message, duration = 3000) {
        this.show(message, 'success', duration);
    }

    error(message, duration = 3000) {
        this.show(message, 'danger', duration);
    }

    warning(message, duration = 3000) {
        this.show(message, 'warning', duration);
    }

    info(message, duration = 3000) {
        this.show(message, 'info', duration);
    }
}

// ============ FORM HANDLER ============
class FormHandler {
    constructor() {
        this.setupFormSubmitHandlers();
    }

    setupFormSubmitHandlers() {
        // Batch form
        document.querySelectorAll('form').forEach(form => {
            form.addEventListener('submit', (e) => {
                e.preventDefault();
                this.handleFormSubmit(form);
            });
        });
    }

    handleFormSubmit(form) {
        const isValid = form.checkValidity();
        
        if (!isValid) {
            e.preventDefault();
            e.stopPropagation();
            notificationManager.warning('Please fill in all required fields');
        } else {
            // Simulate form submission
            const formData = new FormData(form);
            const modal = form.closest('.modal');
            
            // Get the action from form or button
            const submitBtn = form.querySelector('button[type="submit"]');
            const action = submitBtn?.textContent || 'Action';

            if (modal) {
                const bsModal = bootstrap.Modal.getInstance(modal);
                if (bsModal) {
                    bsModal.hide();
                }
            }

            notificationManager.success(`${action} completed successfully!`);
            
            // Reset form
            form.reset();
        }
    }
}

// ============ TABLE UTILITIES ============
class TableManager {
    constructor() {
        this.setupTableFeatures();
    }

    setupTableFeatures() {
        this.makeTablesSortable();
        this.setupTableActions();
    }

    makeTablesSortable() {
        const tables = document.querySelectorAll('table');
        tables.forEach(table => {
            const headers = table.querySelectorAll('thead th');
            headers.forEach((header, index) => {
                header.style.cursor = 'pointer';
                header.addEventListener('click', () => {
                    this.sortTable(table, index);
                });
            });
        });
    }

    sortTable(table, columnIndex) {
        const tbody = table.querySelector('tbody');
        const rows = Array.from(tbody.querySelectorAll('tr'));

        // Toggle sort order
        const isAscending = table.dataset.sortOrder !== 'asc';
        table.dataset.sortColumn = columnIndex;
        table.dataset.sortOrder = isAscending ? 'asc' : 'desc';

        rows.sort((a, b) => {
            const aValue = a.cells[columnIndex]?.textContent.trim() || '';
            const bValue = b.cells[columnIndex]?.textContent.trim() || '';

            let comparison = 0;
            if (!isNaN(aValue) && !isNaN(bValue)) {
                comparison = parseFloat(aValue) - parseFloat(bValue);
            } else {
                comparison = aValue.localeCompare(bValue);
            }

            return isAscending ? comparison : -comparison;
        });

        rows.forEach(row => tbody.appendChild(row));
    }

    setupTableActions() {
        // Add click handlers to action buttons
        document.querySelectorAll('.btn-outline-secondary, .btn-outline-danger').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const action = e.target.closest('button').getAttribute('data-action') || 'Action';
                notificationManager.info(`${action} initiated...`);
            });
        });
    }
}

// ============ DATA TABLE PAGINATION ============
class PaginationManager {
    constructor(itemsPerPage = 10) {
        this.itemsPerPage = itemsPerPage;
        this.currentPage = 1;
    }

    paginate(tableId) {
        const table = document.getElementById(tableId);
        if (!table) return;

        const tbody = table.querySelector('tbody');
        const rows = Array.from(tbody.querySelectorAll('tr'));
        const totalPages = Math.ceil(rows.length / this.itemsPerPage);

        rows.forEach((row, index) => {
            const pageNum = Math.floor(index / this.itemsPerPage) + 1;
            row.style.display = pageNum === this.currentPage ? '' : 'none';
        });

        return { currentPage: this.currentPage, totalPages };
    }

    nextPage(tableId) {
        this.currentPage++;
        this.paginate(tableId);
    }

    prevPage(tableId) {
        if (this.currentPage > 1) {
            this.currentPage--;
            this.paginate(tableId);
        }
    }

    goToPage(tableId, pageNum) {
        this.currentPage = pageNum;
        this.paginate(tableId);
    }
}

// ============ QUICK ADD FUNCTIONALITY ============
class QuickAddManager {
    constructor() {
        this.setupQuickAdd();
    }

    setupQuickAdd() {
        const quickAddItems = document.querySelectorAll('#quickAddModal .list-group-item');
        quickAddItems.forEach(item => {
            item.addEventListener('click', (e) => {
                e.preventDefault();
                const action = item.textContent.trim();
                this.handleQuickAdd(action);
            });
        });
    }

    handleQuickAdd(action) {
        const modalMap = {
            'Add Student': 'studentModal',
            'Add Teacher': 'teacherModal',
            'Create Batch': 'batchModal',
            'Record Payment': 'paymentModal'
        };

        const targetModal = modalMap[action];
        if (targetModal) {
            bootstrap.Modal.getOrCreateInstance(document.getElementById('quickAddModal')).hide();
            setTimeout(() => {
                bootstrap.Modal.getOrCreateInstance(document.getElementById(targetModal)).show();
            }, 300);
        }
    }
}

// ============ REVIEW MANAGEMENT ============
class ReviewManager {
    constructor() {
        this.setupReviewHandlers();
    }

    setupReviewHandlers() {
        // Review type filter
        document.querySelectorAll('input[name="reviewType"]').forEach(radio => {
            radio.addEventListener('change', (e) => {
                this.filterReviews(e.target.value);
            });
        });

        // Approve/Reject buttons
        document.querySelectorAll('.review-item .btn-outline-success').forEach(btn => {
            btn.addEventListener('click', () => {
                const reviewItem = btn.closest('.review-item');
                const reviewName = reviewItem.querySelector('h6')?.textContent || 'Review';
                this.approveReview(reviewItem, reviewName);
            });
        });

        document.querySelectorAll('.review-item .btn-outline-danger').forEach(btn => {
            btn.addEventListener('click', () => {
                const reviewItem = btn.closest('.review-item');
                const reviewName = reviewItem.querySelector('h6')?.textContent || 'Review';
                this.rejectReview(reviewItem, reviewName);
            });
        });

        // Review response modal
        document.querySelectorAll('.review-item').forEach(review => {
            review.addEventListener('dblclick', () => {
                bootstrap.Modal.getOrCreateInstance(document.getElementById('reviewModal')).show();
            });
        });
    }

    filterReviews(type) {
        console.log('[v0] Filtering reviews by type:', type);
        notificationManager.info(`Showing ${type} reviews...`);
        // Implementation would filter reviews based on type
    }

    approveReview(reviewItem, reviewName) {
        reviewItem.classList.remove('review-pending');
        reviewItem.classList.add('review-approved');
        notificationManager.success(`Review for "${reviewName}" approved and published!`);
        
        // Fade out and update UI
        reviewItem.style.opacity = '0.7';
        setTimeout(() => {
            reviewItem.style.opacity = '1';
        }, 500);
    }

    rejectReview(reviewItem, reviewName) {
        notificationManager.warning(`Review for "${reviewName}" rejected.`);
        
        // Fade out and remove
        reviewItem.style.animation = 'fadeOut 0.3s';
        setTimeout(() => {
            reviewItem.remove();
        }, 300);
    }
}

// ============ INITIALIZE APPLICATION ============
let adminPanel;
let notificationManager;
let formHandler;
let tableManager;
let paginationManager;
let quickAddManager;
let reviewManager;

document.addEventListener('DOMContentLoaded', function() {
    // Initialize managers
    adminPanel = new AdminPanel();
    notificationManager = new NotificationManager();
    formHandler = new FormHandler();
    tableManager = new TableManager();
    paginationManager = new PaginationManager(10);
    quickAddManager = new QuickAddManager();
    reviewManager = new ReviewManager();

    // Set default active page
    adminPanel.showPage('dashboard');

    // Log initialization
    console.log('[v0] CoachMaster Admin Panel initialized successfully');
});

// ============ UTILITY FUNCTIONS ============
function formatCurrency(value) {
    return new Intl.NumberFormat('en-IN', {
        style: 'currency',
        currency: 'INR'
    }).format(value);
}

function formatDate(date) {
    return new Intl.DateTimeFormat('en-IN', {
        year: 'numeric',
        month: 'short',
        day: 'numeric'
    }).format(new Date(date));
}

function formatPhoneNumber(phone) {
    return phone.replace(/(\d{2})(\d{5})(\d{5})/, '+$1-$2...$3');
}
