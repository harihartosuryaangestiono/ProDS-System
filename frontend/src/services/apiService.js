// file: src/services/apiService.js

import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:5002';

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
    
    // Backend sudah return { success: true, data: {...} }
    // Jadi langsung return response.data
    return response.data;  // ✅ PERBAIKAN INI
    
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
    search: params?.search || '',
    ...(params.faculty && { faculty: params.faculty }),
    ...(params.department && { department: params.department })
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

apiService.getSintaPublikasiStats = async (params = {}) => {
  const queryParams = {
    search: params?.search || '',
    ...(params.tipe && params.tipe !== 'all' && { tipe: params.tipe }),
    ...(params.year_start && { year_start: params.year_start }),
    ...(params.year_end && { year_end: params.year_end }),
    ...(params.faculty && { faculty: params.faculty }),
    ...(params.department && { department: params.department })
  };
  
  return handleResponse(
    () => apiService.get('/api/sinta/publikasi/stats', { params: queryParams }),
    'Error fetching SINTA publikasi statistics'
  );
};

// ===================================
// ✨ SINTA Publikasi Faculty & Department
// ===================================

apiService.getSintaPublikasiFaculties = async () => {
  return handleResponse(
    () => apiService.get('/api/sinta/publikasi/faculties'),
    'Error fetching SINTA publikasi faculties'
  );
};

apiService.getSintaPublikasiDepartments = async (faculty) => {
  return handleResponse(
    () => apiService.get('/api/sinta/publikasi/departments', { 
      params: { faculty } 
    }),
    'Error fetching SINTA publikasi departments'
  );
};

// ===================================
// ✨ TAMBAHAN BARU: SINTA Faculty & Department
// ===================================

apiService.getSintaFaculties = async () => {
  return handleResponse(
    () => apiService.get('/api/sinta/dosen/faculties'),
    'Error fetching SINTA faculties'
  );
};

apiService.getSintaDepartments = async (faculty) => {
  return handleResponse(
    () => apiService.get('/api/sinta/dosen/departments', { 
      params: { faculty } 
    }),
    'Error fetching SINTA departments'
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
    search: params?.search || '',
    ...(params.faculty && { faculty: params.faculty }),
    ...(params.department && { department: params.department })
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

apiService.getScholarPublikasiStats = async (params = {}) => {
  const queryParams = {
    search: params?.search || '',
    ...(params.tipe && params.tipe !== 'all' && { tipe: params.tipe }),
    ...(params.year_start && { year_start: params.year_start }),
    ...(params.year_end && { year_end: params.year_end }),
    ...(params.faculty && { faculty: params.faculty }),
    ...(params.department && { department: params.department })
  };
  
  return handleResponse(
    () => apiService.get('/api/scholar/publikasi/stats', { params: queryParams }),
    'Error fetching Scholar publikasi statistics'
  );
};

// ===================================
// ✨ Scholar Faculty & Department
// ===================================

apiService.getScholarFaculties = async () => {
  return handleResponse(
    () => apiService.get('/api/scholar/dosen/faculties'),
    'Error fetching Scholar faculties'
  );
};

apiService.getScholarDepartments = async (faculty) => {
  return handleResponse(
    () => apiService.get('/api/scholar/dosen/departments', { 
      params: { faculty } 
    }),
    'Error fetching Scholar departments'
  );
};

// ===================================
// Export to Excel Functions
// ===================================

apiService.exportSintaDosen = async (params = {}) => {
  try {
    const token = localStorage.getItem('token');
    const queryParams = new URLSearchParams();
    
    if (params.search) queryParams.append('search', params.search);
    if (params.faculty) queryParams.append('faculty', params.faculty);
    if (params.department) queryParams.append('department', params.department);
    
    const url = `${API_BASE_URL}/api/sinta/dosen/export?${queryParams.toString()}`;
    
    const response = await fetch(url, {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${token}`,
      },
    });
    
    if (!response.ok) {
      throw new Error('Export failed');
    }
    
    const blob = await response.blob();
    const downloadUrl = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = downloadUrl;
    link.download = `sinta_dosen_${new Date().toISOString().split('T')[0]}.xlsx`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(downloadUrl);
    
    return { success: true };
  } catch (error) {
    console.error('Export error:', error);
    return { success: false, error: error.message };
  }
};

apiService.exportSintaPublikasi = async (params = {}) => {
  try {
    const token = localStorage.getItem('token');
    const queryParams = new URLSearchParams();
    
    if (params.search) queryParams.append('search', params.search);
    if (params.tipe && params.tipe !== 'all') queryParams.append('tipe', params.tipe);
    if (params.terindeks && params.terindeks !== 'all') queryParams.append('terindeks', params.terindeks);
    if (params.year_start) queryParams.append('year_start', params.year_start);
    if (params.year_end) queryParams.append('year_end', params.year_end);
    if (params.faculty) queryParams.append('faculty', params.faculty);
    if (params.department) queryParams.append('department', params.department);
    
    const url = `${API_BASE_URL}/api/sinta/publikasi/export?${queryParams.toString()}`;
    
    const response = await fetch(url, {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${token}`,
      },
    });
    
    if (!response.ok) {
      throw new Error('Export failed');
    }
    
    const blob = await response.blob();
    const downloadUrl = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = downloadUrl;
    link.download = `sinta_publikasi_${new Date().toISOString().split('T')[0]}.xlsx`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(downloadUrl);
    
    return { success: true };
  } catch (error) {
    console.error('Export error:', error);
    return { success: false, error: error.message };
  }
};

apiService.exportScholarDosen = async (params = {}) => {
  try {
    const token = localStorage.getItem('token');
    const queryParams = new URLSearchParams();
    
    if (params.search) queryParams.append('search', params.search);
    if (params.faculty) queryParams.append('faculty', params.faculty);
    if (params.department) queryParams.append('department', params.department);
    
    const url = `${API_BASE_URL}/api/scholar/dosen/export?${queryParams.toString()}`;
    
    const response = await fetch(url, {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${token}`,
      },
    });
    
    if (!response.ok) {
      throw new Error('Export failed');
    }
    
    const blob = await response.blob();
    const downloadUrl = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = downloadUrl;
    link.download = `scholar_dosen_${new Date().toISOString().split('T')[0]}.xlsx`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(downloadUrl);
    
    return { success: true };
  } catch (error) {
    console.error('Export error:', error);
    return { success: false, error: error.message };
  }
};

apiService.exportScholarPublikasi = async (params = {}) => {
  try {
    const token = localStorage.getItem('token');
    const queryParams = new URLSearchParams();
    
    if (params.search) queryParams.append('search', params.search);
    if (params.tipe && params.tipe !== 'all') queryParams.append('tipe', params.tipe);
    if (params.year_start) queryParams.append('year_start', params.year_start);
    if (params.year_end) queryParams.append('year_end', params.year_end);
    if (params.faculty) queryParams.append('faculty', params.faculty);
    if (params.department) queryParams.append('department', params.department);
    
    const url = `${API_BASE_URL}/api/scholar/publikasi/export?${queryParams.toString()}`;
    
    const response = await fetch(url, {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${token}`,
      },
    });
    
    if (!response.ok) {
      throw new Error('Export failed');
    }
    
    const blob = await response.blob();
    const downloadUrl = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = downloadUrl;
    link.download = `scholar_publikasi_${new Date().toISOString().split('T')[0]}.xlsx`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(downloadUrl);
    
    return { success: true };
  } catch (error) {
    console.error('Export error:', error);
    return { success: false, error: error.message };
  }
};

// ===================================
// Dashboard API Functions
// ===================================

apiService.getDashboardStats = async (faculty = '', department = '') => {
  console.log('🔧 API Service - getDashboardStats called with:', { faculty, department });
  
  const params = {};
  if (faculty) params.faculty = faculty;
  if (department) params.department = department;
  
  console.log('🔧 API Service - params:', params);
  
  try {
    const result = await handleResponse(
      () => apiService.get('/api/dashboard/stats', { params }),
      'Error fetching dashboard statistics'
    );
    
    console.log('🔧 API Service - result:', result);
    return result;
  } catch (error) {
    console.error('🔧 API Service - ERROR:', error);
    return {
      success: false,
      error: error.message
    };
  }
};

apiService.getDashboardFaculties = async () => {
  return handleResponse(
    () => apiService.get('/api/dashboard/faculties'),
    'Error fetching dashboard faculties'
  );
};

apiService.getDashboardDepartments = async (faculty) => {
  return handleResponse(
    () => apiService.get('/api/dashboard/departments', { 
      params: { faculty } 
    }),
    'Error fetching dashboard departments'
  );
};

// ===================================
// Authentication API Functions
// ===================================

apiService.login = async (email, password) => {
  return handleResponse(
    async () => {
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
    () => apiService.post('/auth/register', userData),
    'Error during registration'
  );
};

export default apiService;