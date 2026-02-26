// ============ FORM VALIDATION ============
class FormValidator {
    constructor() {
        this.rules = {};
    }

    addRule(fieldName, rule, message) {
        if (!this.rules[fieldName]) {
            this.rules[fieldName] = [];
        }
        this.rules[fieldName].push({ rule, message });
    }

    validate(formData) {
        const errors = {};

        Object.keys(this.rules).forEach(fieldName => {
            const value = formData[fieldName];
            this.rules[fieldName].forEach(({ rule, message }) => {
                if (!rule(value)) {
                    if (!errors[fieldName]) {
                        errors[fieldName] = [];
                    }
                    errors[fieldName].push(message);
                }
            });
        });

        return {
            isValid: Object.keys(errors).length === 0,
            errors
        };
    }

    static rules = {
        required: (value) => value && value.trim().length > 0,
        email: (value) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value),
        phone: (value) => /^[0-9]{10}$/.test(value.replace(/\D/g, '')),
        minLength: (min) => (value) => value.length >= min,
        maxLength: (max) => (value) => value.length <= max,
        numeric: (value) => /^[0-9]+$/.test(value),
        alphanumeric: (value) => /^[a-zA-Z0-9]+$/.test(value)
    };
}

// ============ DATA STORAGE ============
class StorageManager {
    constructor(prefix = 'coachmaster_') {
        this.prefix = prefix;
    }

    set(key, value) {
        try {
            localStorage.setItem(this.prefix + key, JSON.stringify(value));
            return true;
        } catch (e) {
            console.error('[v0] Storage error:', e);
            return false;
        }
    }

    get(key, defaultValue = null) {
        try {
            const item = localStorage.getItem(this.prefix + key);
            return item ? JSON.parse(item) : defaultValue;
        } catch (e) {
            console.error('[v0] Storage error:', e);
            return defaultValue;
        }
    }

    remove(key) {
        try {
            localStorage.removeItem(this.prefix + key);
            return true;
        } catch (e) {
            console.error('[v0] Storage error:', e);
            return false;
        }
    }

    clear() {
        try {
            Object.keys(localStorage)
                .filter(key => key.startsWith(this.prefix))
                .forEach(key => localStorage.removeItem(key));
            return true;
        } catch (e) {
            console.error('[v0] Storage error:', e);
            return false;
        }
    }
}

// ============ API SERVICE ============
class ApiService {
    constructor(baseUrl = '/api') {
        this.baseUrl = baseUrl;
        this.timeout = 10000;
    }

    async request(endpoint, options = {}) {
        const url = `${this.baseUrl}${endpoint}`;
        const config = {
            method: options.method || 'GET',
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            },
            body: options.data ? JSON.stringify(options.data) : undefined
        };

        try {
            const response = await Promise.race([
                fetch(url, config),
                new Promise((_, reject) =>
                    setTimeout(() => reject(new Error('Request timeout')), this.timeout)
                )
            ]);

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            return await response.json();
        } catch (error) {
            console.error('[v0] API error:', error);
            throw error;
        }
    }

    get(endpoint, options = {}) {
        return this.request(endpoint, { ...options, method: 'GET' });
    }

    post(endpoint, data, options = {}) {
        return this.request(endpoint, { ...options, method: 'POST', data });
    }

    put(endpoint, data, options = {}) {
        return this.request(endpoint, { ...options, method: 'PUT', data });
    }

    delete(endpoint, options = {}) {
        return this.request(endpoint, { ...options, method: 'DELETE' });
    }
}

// ============ DATE UTILITIES ============
const DateUtils = {
    now: () => new Date(),

    format: (date, format = 'dd/MM/yyyy') => {
        const d = new Date(date);
        const day = String(d.getDate()).padStart(2, '0');
        const month = String(d.getMonth() + 1).padStart(2, '0');
        const year = d.getFullYear();
        
        return format
            .replace('dd', day)
            .replace('MM', month)
            .replace('yyyy', year);
    },

    addDays: (date, days) => {
        const result = new Date(date);
        result.setDate(result.getDate() + days);
        return result;
    },

    getDaysBetween: (date1, date2) => {
        const d1 = new Date(date1);
        const d2 = new Date(date2);
        const diffTime = Math.abs(d2 - d1);
        return Math.ceil(diffTime / (1000 * 60 * 60 * 24));
    },

    isToday: (date) => {
        const today = new Date();
        return date.toDateString() === today.toDateString();
    },

    getMonthName: (monthIndex) => {
        const months = ['January', 'February', 'March', 'April', 'May', 'June',
                       'July', 'August', 'September', 'October', 'November', 'December'];
        return months[monthIndex];
    }
};

// ============ NUMBER UTILITIES ============
const NumberUtils = {
    formatCurrency: (value, currency = 'INR', locale = 'en-IN') => {
        return new Intl.NumberFormat(locale, {
            style: 'currency',
            currency: currency,
            minimumFractionDigits: 0,
            maximumFractionDigits: 0
        }).format(value);
    },

    formatPercent: (value, decimals = 2) => {
        return (value).toFixed(decimals) + '%';
    },

    abbreviate: (value) => {
        if (value >= 1000000) return (value / 1000000).toFixed(1) + 'M';
        if (value >= 1000) return (value / 1000).toFixed(1) + 'K';
        return value;
    },

    random: (min = 0, max = 100) => {
        return Math.floor(Math.random() * (max - min + 1)) + min;
    }
};

// ============ STRING UTILITIES ============
const StringUtils = {
    capitalize: (str) => {
        return str.charAt(0).toUpperCase() + str.slice(1).toLowerCase();
    },

    truncate: (str, length = 50) => {
        return str.length > length ? str.substring(0, length) + '...' : str;
    },

    slug: (str) => {
        return str.toLowerCase()
            .trim()
            .replace(/[^\w\s-]/g, '')
            .replace(/[\s_-]+/g, '-')
            .replace(/^-+|-+$/g, '');
    },

    getInitials: (name) => {
        return name
            .split(' ')
            .map(n => n.charAt(0))
            .join('')
            .toUpperCase()
            .slice(0, 2);
    }
};

// ============ ARRAY UTILITIES ============
const ArrayUtils = {
    unique: (arr) => [...new Set(arr)],

    groupBy: (arr, key) => {
        return arr.reduce((acc, obj) => {
            const group = obj[key];
            if (!acc[group]) acc[group] = [];
            acc[group].push(obj);
            return acc;
        }, {});
    },

    sortBy: (arr, key, ascending = true) => {
        return [...arr].sort((a, b) => {
            if (a[key] < b[key]) return ascending ? -1 : 1;
            if (a[key] > b[key]) return ascending ? 1 : -1;
            return 0;
        });
    },

    filterBy: (arr, key, value) => {
        return arr.filter(item => item[key] === value);
    }
};

// ============ DOM UTILITIES ============
const DomUtils = {
    byId: (id) => document.getElementById(id),

    query: (selector, parent = document) => {
        return parent.querySelector(selector);
    },

    queryAll: (selector, parent = document) => {
        return Array.from(parent.querySelectorAll(selector));
    },

    addClass: (el, className) => {
        el.classList.add(className);
    },

    removeClass: (el, className) => {
        el.classList.remove(className);
    },

    toggleClass: (el, className) => {
        el.classList.toggle(className);
    },

    hasClass: (el, className) => {
        return el.classList.contains(className);
    },

    setText: (el, text) => {
        el.textContent = text;
    },

    setHtml: (el, html) => {
        el.innerHTML = html;
    },

    show: (el) => {
        el.style.display = '';
    },

    hide: (el) => {
        el.style.display = 'none';
    },

    toggle: (el) => {
        el.style.display = el.style.display === 'none' ? '' : 'none';
    }
};

// ============ EVENT UTILITIES ============
const EventUtils = {
    on: (el, event, handler) => {
        el.addEventListener(event, handler);
    },

    off: (el, event, handler) => {
        el.removeEventListener(event, handler);
    },

    once: (el, event, handler) => {
        el.addEventListener(event, handler, { once: true });
    },

    trigger: (el, eventName, detail = {}) => {
        el.dispatchEvent(new CustomEvent(eventName, { detail }));
    }
};

// ============ COLOR UTILITIES ============
const ColorUtils = {
    hexToRgb: (hex) => {
        const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
        return result ? {
            r: parseInt(result[1], 16),
            g: parseInt(result[2], 16),
            b: parseInt(result[3], 16)
        } : null;
    },

    rgbToHex: (r, g, b) => {
        return "#" + ((1 << 24) + (r << 16) + (g << 8) + b).toString(16).slice(1);
    },

    lighten: (hex, percent) => {
        const rgb = ColorUtils.hexToRgb(hex);
        if (!rgb) return hex;
        const factor = 1 + (percent / 100);
        return ColorUtils.rgbToHex(
            Math.min(255, Math.round(rgb.r * factor)),
            Math.min(255, Math.round(rgb.g * factor)),
            Math.min(255, Math.round(rgb.b * factor))
        );
    }
};

// ============ DEBOUNCE & THROTTLE ============
function debounce(func, wait = 300) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

function throttle(func, limit = 300) {
    let inThrottle;
    return function(...args) {
        if (!inThrottle) {
            func.apply(this, args);
            inThrottle = true;
            setTimeout(() => inThrottle = false, limit);
        }
    };
}

// ============ PERFORMANCE MONITORING ============
class PerformanceMonitor {
    constructor() {
        this.marks = {};
    }

    start(label) {
        this.marks[label] = performance.now();
    }

    end(label) {
        if (!this.marks[label]) {
            console.warn('[v0] Performance mark not found:', label);
            return;
        }

        const duration = performance.now() - this.marks[label];
        console.log(`[v0] ${label} took ${duration.toFixed(2)}ms`);
        delete this.marks[label];
        return duration;
    }
}

// ============ EXPORT & INITIALIZE ============
// Make utilities globally available
window.FormValidator = FormValidator;
window.StorageManager = StorageManager;
window.ApiService = ApiService;
window.DateUtils = DateUtils;
window.NumberUtils = NumberUtils;
window.StringUtils = StringUtils;
window.ArrayUtils = ArrayUtils;
window.DomUtils = DomUtils;
window.EventUtils = EventUtils;
window.ColorUtils = ColorUtils;
window.debounce = debounce;
window.throttle = throttle;
window.PerformanceMonitor = PerformanceMonitor;

console.log('[v0] Utilities loaded successfully');
