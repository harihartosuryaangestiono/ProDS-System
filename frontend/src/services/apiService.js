// file: src/services/apiService.js

import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:5005';

// Create axios instance
const apiService = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  withCredentials: true,
  timeout: 30000, // 30 second timeout
});

// Request interceptor to add the auth token to headers
apiService.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`; // Ensure Bearer prefix
    } else {
      // Redirect to login if token is missing
      if (window.location.pathname !== '/login') {
        window.location.href = '/login';
        return Promise.reject('Authentication required');
      }
    }
    
    if (import.meta.env.DEV) {
      console.log(`API Request: ${config.method.toUpperCase()} ${config.url}`, {
        params: config.params,
        headers: config.headers, // Log headers for debugging
      });
    }
    
    return config;
  },
  (error) => {
    console.error('Request interceptor error:', error);
    return Promise.reject(error);
  }
);

// Response interceptor to handle token expiration or invalid tokens
apiService.interceptors.response.use(
  (response) => {
    if (import.meta.env.DEV) {
      console.log(`API Response: ${response.config.url} - Status: ${response.status}`);
    }
    return response;
  },
  (error) => {
    console.error('API Error:', {
      url: error.config?.url,
      status: error.response?.status,
      message: error.message,
      data: error.response?.data
    });
    
    if (error.response && error.response.status === 401) {
      console.warn('Unauthorized access - clearing tokens');
      localStorage.removeItem('token');
      localStorage.removeItem('user');
      
      if (window.location.pathname !== '/login') {
        window.location.href = '/login';
      }
    }
    
    return Promise.reject(error);
  }
);

// ===================================
// Helper Functions
// ===================================

/**
 * Build pagination parameters
 * @param {object} params - The parameters object
 * @param {number} params.page - Page number
 * @param {number} params.perPage - Items per page
 * @param {string} params.search - Search term
 * @returns {Object} Formatted parameters
 */
apiService.buildPaginationParams = (page = 1, perPage = 20, search = '') => {
  return {
    page,
    per_page: perPage,
    search: search ? search.trim() : '',
  };
};

/**
 * Handle API response and errors consistently
 * @param {Function} apiCall - The API call function
 * @param {string} errorMessage - Default error message
 * @returns {Object} Standardized response object
 */
const handleResponse = async (apiCall, errorMessage = 'API request failed') => {
  try {
    const response = await apiCall();
    return {
      success: true,
      data: response.data
    };
  } catch (error) {
    console.error(errorMessage, error);
    
    const message = 
      error.response?.data?.message || 
      error.response?.data?.error || 
      error.message || 
      'Unknown error occurred';
    
    return {
      success: false,
      error: message,
      statusCode: error.response?.status,
      details: error.response?.data
    };
  }
};

// ===================================
// SINTA API Functions
// ===================================

/**
 * Get SINTA Dosen data with pagination and search
 * @param {object} params - The parameters object
 * @param {number} params.page - Page number
 * @param {number} params.perPage - Items per page
 * @param {string} params.search - Search term
 */
apiService.getSintaDosen = async (params) => {
  return handleResponse(
    () => apiService.get('/api/sinta/dosen', { params }),
    'Error fetching SINTA dosen'
  );
};

/**
 * Get SINTA Dosen aggregate statistics
 * Returns total citations from both Google Scholar (n_total_sitasi_gs) and Scopus (n_sitasi_scopus)
 * @param {object} params - The parameters object
 * @param {string} params.search - Search term (optional)
 * @returns {Promise} Response with { totalDosen, totalSitasi, avgHIndex }
 */
apiService.getSintaDosenStats = async (params = {}) => {
  const queryParams = {
    search: params?.search || ''
  };
  return handleResponse(
    () => apiService.get('/api/sinta/dosen/stats', { params: queryParams }),
    'Error fetching SINTA dosen statistics'
  );
};

/**
 * Get SINTA Publikasi data with pagination and search
 * @param {object} params - The parameters object
 * @param {number} params.page - Page number
 * @param {number} params.perPage - Items per page
 * @param {string} params.search - Search term
 */
apiService.getSintaPublikasi = async (params) => {
  return handleResponse(
    () => apiService.get('/api/sinta/publikasi', { params }),
    'Error fetching SINTA publikasi'
  );
};

/**
 * Debug endpoint for SINTA publikasi
 */
apiService.debugSintaPublikasi = async () => {
  return handleResponse(
    () => apiService.get('/api/sinta/publikasi/debug'),
    'Error fetching SINTA publikasi debug info'
  );
};

// ===================================
// Scholar API Functions
// ===================================

/**
 * Get Google Scholar Dosen data with pagination and search
 * @param {object} params - The parameters object
 * @param {number} params.page - Page number
 * @param {number} params.perPage - Items per page
 * @param {string} params.search - Search term
 */
apiService.getScholarDosen = async (params) => {
  return handleResponse(
    () => apiService.get('/api/scholar/dosen', { params }),
    'Error fetching Scholar dosen'
  );
};

/**
 * Get Google Scholar Dosen aggregate statistics
 * @param {object} params - The parameters object
 * @param {string} params.search - Search term (optional)
 */
apiService.getScholarDosenStats = async (params = {}) => {
  const queryParams = {
    search: params?.search || ''
  };
  return handleResponse(
    () => apiService.get('/api/scholar/dosen/stats', { params: queryParams }),
    'Error fetching Scholar dosen statistics'
  );
};

/**
 * Get Google Scholar Publikasi data with pagination and search
 * @param {object} params - The parameters object
 * @param {number} params.page - Page number
 * @param {number} params.perPage - Items per page
 * @param {string} params.search - Search term
 */
apiService.getScholarPublikasi = async (params) => {
  return handleResponse(
    () => apiService.get('/api/scholar/publikasi', { params }),
    'Error fetching Scholar publikasi'
  );
};

// ===================================
// Dashboard API Functions
// ===================================

/**
 * Get dashboard statistics
 */
apiService.getDashboardStats = async () => {
  return handleResponse(
    () => apiService.get('/api/dashboard/stats'),
    'Error fetching dashboard stats'
  );
};

// ===================================
// Authentication API Functions
// ===================================

/**
 * Login user
 * @param {string} username - Username
 * @param {string} password - Password
 */
apiService.login = async (username, password) => {
  return handleResponse(
    async () => {
      const response = await apiService.post('/api/auth/login', { username, password });
      if (response.data.token) {
        localStorage.setItem('token', response.data.token);
        localStorage.setItem('user', JSON.stringify(response.data.user));
      }
      return response;
    },
    'Error during login'
  );
};

/**
 * Logout user
 */
apiService.logout = async () => {
  return handleResponse(
    () => apiService.post('/api/auth/logout'),
    'Error during logout'
  );
};

/**
 * Register new user
 * @param {object} userData - User registration data
 */
apiService.register = async (userData) => {
  return handleResponse(
    () => apiService.post('/api/auth/register', userData),
    'Error during registration'
  );
};

/**
 * Get current user profile
 */
apiService.getCurrentUser = async () => {
  return handleResponse(
    () => apiService.get('/api/auth/me'),
    'Error fetching user profile'
  );
};

// ===================================
// Export
// ===================================

export default apiService;