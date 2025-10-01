// API Configuration
export const API_BASE_URL = process.env.NODE_ENV === 'production' 
  ? 'https://your-production-api.com' 
  : 'http://localhost:5000';

// Application constants
export const APP_NAME = 'ProDS System';
export const APP_DESCRIPTION = 'Sistem Publikasi Dosen SINTA & Google Scholar';

// Pagination
export const DEFAULT_PER_PAGE = 20;
export const PER_PAGE_OPTIONS = [10, 20, 50, 100];

// Routes
export const ROUTES = {
  HOME: '/',
  LOGIN: '/login',
  REGISTER: '/register',
  DASHBOARD: '/dashboard',
  SINTA_DOSEN: '/sinta/dosen',
  SINTA_PUBLIKASI: '/sinta/publikasi',
  SCHOLAR_DOSEN: '/scholar/dosen',
  SCHOLAR_PUBLIKASI: '/scholar/publikasi',
  SCRAPING: '/scraping'
};

// API Endpoints
export const API_ENDPOINTS = {
  // Auth
  LOGIN: '/api/auth/login',
  REGISTER: '/api/auth/register',
  LOGOUT: '/api/auth/logout',
  
  // Dashboard
  DASHBOARD_STATS: '/api/dashboard/stats',
  
  // SINTA
  SINTA_DOSEN: '/api/sinta/dosen',
  SINTA_PUBLIKASI: '/api/sinta/publikasi',
  
  // Google Scholar
  SCHOLAR_DOSEN: '/api/scholar/dosen',
  SCHOLAR_PUBLIKASI: '/api/scholar/publikasi',
  
  // Scraping
  SCRAPE_SINTA: '/api/scraping/sinta',
  SCRAPE_SCHOLAR: '/api/scraping/scholar'
};

// Publication types
export const PUBLICATION_TYPES = {
  ARTIKEL: 'artikel',
  BUKU: 'buku',
  PROSIDING: 'prosiding',
  PENELITIAN: 'penelitian'
};

// Publication sources
export const PUBLICATION_SOURCES = {
  SINTA: 'SINTA',
  SINTA_GARUDA: 'SINTA_Garuda',
  SINTA_GOOGLE_SCHOLAR: 'SINTA_GoogleScholar',
  SINTA_SCOPUS: 'SINTA_Scopus',
  GOOGLE_SCHOLAR: 'Google Scholar'
};

// Colors for charts and UI
export const COLORS = {
  PRIMARY: '#3B82F6',
  SUCCESS: '#10B981',
  WARNING: '#F59E0B',
  ERROR: '#EF4444',
  INFO: '#8B5CF6',
  GRAY: '#6B7280',
  SINTA: '#8B5CF6',
  SCHOLAR: '#DC2626'
};

// Chart colors
export const CHART_COLORS = [
  '#3B82F6', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6',
  '#EC4899', '#06B6D4', '#84CC16', '#F97316', '#6366F1'
];

// Data table settings
export const TABLE_SETTINGS = {
  DEFAULT_SORT: { key: null, direction: 'asc' },
  SORT_DIRECTIONS: {
    ASC: 'asc',
    DESC: 'desc'
  }
};

// Toast notification settings
export const TOAST_SETTINGS = {
  DURATION: {
    SHORT: 2000,
    MEDIUM: 4000,
    LONG: 6000
  },
  POSITION: 'top-right'
};

// Local storage keys
export const STORAGE_KEYS = {
  TOKEN: 'prods_token',
  USER: 'prods_user',
  THEME: 'prods_theme',
  PREFERENCES: 'prods_preferences'
};

// Validation rules
export const VALIDATION_RULES = {
  EMAIL: /^[^\s@]+@[^\s@]+\.[^\s@]+$/,
  PASSWORD_MIN_LENGTH: 6,
  USERNAME_MIN_LENGTH: 3,
  USERNAME_MAX_LENGTH: 50
};

// Date formats
export const DATE_FORMATS = {
  DISPLAY: 'DD/MM/YYYY',
  API: 'YYYY-MM-DD',
  DATETIME: 'DD/MM/YYYY HH:mm'
};

// File upload settings
export const FILE_UPLOAD = {
  MAX_SIZE: 5 * 1024 * 1024, // 5MB
  ALLOWED_TYPES: ['text/csv', 'application/vnd.ms-excel', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet']
};

// Status constants
export const STATUS = {
  IDLE: 'idle',
  LOADING: 'loading',
  SUCCESS: 'success',
  ERROR: 'error'
};

// Scraping status
export const SCRAPING_STATUS = {
  IDLE: 'idle',
  RUNNING: 'running',
  COMPLETED: 'completed',
  FAILED: 'failed'
};

// Error messages
export const ERROR_MESSAGES = {
  NETWORK_ERROR: 'Terjadi kesalahan jaringan',
  AUTH_REQUIRED: 'Anda harus login terlebih dahulu',
  ACCESS_DENIED: 'Akses ditolak',
  NOT_FOUND: 'Data tidak ditemukan',
  SERVER_ERROR: 'Terjadi kesalahan server',
  VALIDATION_ERROR: 'Data tidak valid',
  UNKNOWN_ERROR: 'Terjadi kesalahan yang tidak diketahui'
};

// Success messages
export const SUCCESS_MESSAGES = {
  LOGIN_SUCCESS: 'Login berhasil',
  REGISTER_SUCCESS: 'Registrasi berhasil',
  UPDATE_SUCCESS: 'Data berhasil diperbarui',
  DELETE_SUCCESS: 'Data berhasil dihapus',
  SCRAPING_SUCCESS: 'Scraping berhasil dilakukan'
};