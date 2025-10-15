// file: src/services/apiService.js

import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:5000';

// Create axios instance
const apiService = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  withCredentials: true,
  timeout: 30000,
});

// Request interceptor
apiService.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    
    // Skip auth check for login/register endpoints
    const isAuthEndpoint = config.url.includes('/auth/login') || config.url.includes('/auth/register');
    
    if (!token && !isAuthEndpoint && window.location.pathname !== '/login') {
      window.location.href = '/login';
      return Promise.reject('Authentication required');
    }
    
    if (import.meta.env.DEV) {
      console.log(`API Request: ${config.method.toUpperCase()} ${config.url}`, config.data);
    }
    
    return config;
  },
  (error) => {
    console.error('Request interceptor error:', error);
    return Promise.reject(error);
  }
);

// Response interceptor
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

apiService.getSintaDosen = async (params) => {
  return handleResponse(
    () => apiService.get('/api/sinta/dosen', { params }),
    'Error fetching SINTA dosen'
  );
};

apiService.getSintaDosenStats = async (params = {}) => {
  const queryParams = {
    search: params?.search || ''
  };
  return handleResponse(
    () => apiService.get('/api/sinta/dosen/stats', { params: queryParams }),
    'Error fetching SINTA dosen statistics'
  );
};

apiService.getSintaPublikasi = async (params) => {
  return handleResponse(
    () => apiService.get('/api/sinta/publikasi', { params }),
    'Error fetching SINTA publikasi'
  );
};

// ===================================
// Scholar API Functions
// ===================================

apiService.getScholarDosen = async (params) => {
  return handleResponse(
    () => apiService.get('/api/scholar/dosen', { params }),
    'Error fetching Scholar dosen'
  );
};

apiService.getScholarDosenStats = async (params = {}) => {
  const queryParams = {
    search: params?.search || ''
  };
  return handleResponse(
    () => apiService.get('/api/scholar/dosen/stats', { params: queryParams }),
    'Error fetching Scholar dosen statistics'
  );
};

apiService.getScholarPublikasi = async (params) => {
  return handleResponse(
    () => apiService.get('/api/scholar/publikasi', { params }),
    'Error fetching Scholar publikasi'
  );
};

// ===================================
// Dashboard API Functions
// ===================================

apiService.getDashboardStats = async () => {
  return handleResponse(
    () => apiService.get('/api/dashboard/stats'),
    'Error fetching dashboard stats'
  );
};

// ===================================
// Authentication API Functions (FIXED)
// ===================================

apiService.login = async (email, password) => {
  return handleResponse(
    async () => {
      // FIXED: Changed from /api/auth/login to /auth/login
      const response = await apiService.post('/auth/login', {
        v_email: email,
        v_password_hash: password
      });
      if (response.data.token) {
        localStorage.setItem('token', response.data.token);
        localStorage.setItem('user', JSON.stringify(response.data.user));
      }
      return response;
    },
    'Error during login'
  );
};

apiService.logout = async () => {
  localStorage.removeItem('token');
  localStorage.removeItem('user');
  return { success: true };
};

apiService.register = async (userData) => {
  return handleResponse(
    // FIXED: Changed from /api/auth/register to /auth/register
    () => apiService.post('/auth/register', userData),
    'Error during registration'
  );
};

export default apiService;