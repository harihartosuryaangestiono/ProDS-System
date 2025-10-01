import { VALIDATION_RULES, DATE_FORMATS } from './constants';

// Date utilities
export const formatDate = (date, format = DATE_FORMATS.DISPLAY) => {
  if (!date) return '-';
  
  try {
    const d = new Date(date);
    if (isNaN(d.getTime())) return '-';
    
    const day = d.getDate().toString().padStart(2, '0');
    const month = (d.getMonth() + 1).toString().padStart(2, '0');
    const year = d.getFullYear();
    const hours = d.getHours().toString().padStart(2, '0');
    const minutes = d.getMinutes().toString().padStart(2, '0');
    
    switch (format) {
      case DATE_FORMATS.DISPLAY:
        return `${day}/${month}/${year}`;
      case DATE_FORMATS.API:
        return `${year}-${month}-${day}`;
      case DATE_FORMATS.DATETIME:
        return `${day}/${month}/${year} ${hours}:${minutes}`;
      default:
        return d.toLocaleDateString('id-ID');
    }
  } catch (error) {
    console.error('Date formatting error:', error);
    return '-';
  }
};

export const getRelativeTime = (date) => {
  if (!date) return '-';
  
  try {
    const now = new Date();
    const d = new Date(date);
    const diffInSeconds = Math.floor((now - d) / 1000);
    
    if (diffInSeconds < 60) return 'Baru saja';
    if (diffInSeconds < 3600) return `${Math.floor(diffInSeconds / 60)} menit yang lalu`;
    if (diffInSeconds < 86400) return `${Math.floor(diffInSeconds / 3600)} jam yang lalu`;
    if (diffInSeconds < 2592000) return `${Math.floor(diffInSeconds / 86400)} hari yang lalu`;
    if (diffInSeconds < 31536000) return `${Math.floor(diffInSeconds / 2592000)} bulan yang lalu`;
    return `${Math.floor(diffInSeconds / 31536000)} tahun yang lalu`;
  } catch (error) {
    console.error('Relative time error:', error);
    return '-';
  }
};

// Number utilities
export const formatNumber = (num, options = {}) => {
  if (num == null || isNaN(num)) return '0';
  
  const {
    minimumFractionDigits = 0,
    maximumFractionDigits = 0,
    locale = 'id-ID'
  } = options;
  
  return Number(num).toLocaleString(locale, {
    minimumFractionDigits,
    maximumFractionDigits
  });
};

export const formatCompactNumber = (num) => {
  if (num == null || isNaN(num)) return '0';
  
  const absNum = Math.abs(num);
  
  if (absNum >= 1000000) {
    return (num / 1000000).toFixed(1) + 'M';
  } else if (absNum >= 1000) {
    return (num / 1000).toFixed(1) + 'K';
  }
  
  return num.toString();
};

export const calculatePercentage = (value, total, decimals = 1) => {
  if (!total || total === 0) return '0%';
  const percentage = (value / total) * 100;
  return `${percentage.toFixed(decimals)}%`;
};

// String utilities
export const truncateText = (text, maxLength = 100, suffix = '...') => {
  if (!text || text.length <= maxLength) return text || '';
  return text.slice(0, maxLength) + suffix;
};

export const capitalizeFirst = (str) => {
  if (!str) return '';
  return str.charAt(0).toUpperCase() + str.slice(1).toLowerCase();
};

export const capitalizeWords = (str) => {
  if (!str) return '';
  return str.split(' ').map(word => capitalizeFirst(word)).join(' ');
};

export const slugify = (text) => {
  if (!text) return '';
  return text
    .toLowerCase()
    .replace(/[^\w\s-]/g, '')
    .replace(/[\s_-]+/g, '-')
    .replace(/^-+|-+$/g, '');
};

// Validation utilities
export const validateEmail = (email) => {
  if (!email) return { isValid: false, message: 'Email harus diisi' };
  if (!VALIDATION_RULES.EMAIL.test(email)) {
    return { isValid: false, message: 'Format email tidak valid' };
  }
  return { isValid: true, message: '' };
};

export const validatePassword = (password) => {
  if (!password) return { isValid: false, message: 'Password harus diisi' };
  if (password.length < VALIDATION_RULES.PASSWORD_MIN_LENGTH) {
    return { isValid: false, message: `Password minimal ${VALIDATION_RULES.PASSWORD_MIN_LENGTH} karakter` };
  }
  return { isValid: true, message: '' };
};

export const validateUsername = (username) => {
  if (!username) return { isValid: false, message: 'Username harus diisi' };
  if (username.length < VALIDATION_RULES.USERNAME_MIN_LENGTH) {
    return { isValid: false, message: `Username minimal ${VALIDATION_RULES.USERNAME_MIN_LENGTH} karakter` };
  }
  if (username.length > VALIDATION_RULES.USERNAME_MAX_LENGTH) {
    return { isValid: false, message: `Username maksimal ${VALIDATION_RULES.USERNAME_MAX_LENGTH} karakter` };
  }
  return { isValid: true, message: '' };
};

// Array utilities
export const sortArray = (array, key, direction = 'asc') => {
  return [...array].sort((a, b) => {
    const aValue = typeof key === 'function' ? key(a) : a[key];
    const bValue = typeof key === 'function' ? key(b) : b[key];
    
    if (aValue == null && bValue == null) return 0;
    if (aValue == null) return direction === 'asc' ? 1 : -1;
    if (bValue == null) return direction === 'asc' ? -1 : 1;
    
    if (typeof aValue === 'number' && typeof bValue === 'number') {
      return direction === 'asc' ? aValue - bValue : bValue - aValue;
    }
    
    const aString = String(aValue).toLowerCase();
    const bString = String(bValue).toLowerCase();
    
    if (aString < bString) return direction === 'asc' ? -1 : 1;
    if (aString > bString) return direction === 'asc' ? 1 : -1;
    return 0;
  });
};

export const groupBy = (array, key) => {
  return array.reduce((groups, item) => {
    const group = typeof key === 'function' ? key(item) : item[key];
    if (!groups[group]) {
      groups[group] = [];
    }
    groups[group].push(item);
    return groups;
  }, {});
};

export const uniqueBy = (array, key) => {
  const seen = new Set();
  return array.filter(item => {
    const value = typeof key === 'function' ? key(item) : item[key];
    if (seen.has(value)) {
      return false;
    }
    seen.add(value);
    return true;
  });
};

// Object utilities
export const cleanObject = (obj) => {
  const cleaned = {};
  Object.keys(obj).forEach(key => {
    const value = obj[key];
    if (value !== null && value !== undefined && value !== '') {
      cleaned[key] = value;
    }
  });
  return cleaned;
};

export const deepClone = (obj) => {
  if (obj === null || typeof obj !== 'object') return obj;
  if (obj instanceof Date) return new Date(obj);
  if (obj instanceof Array) return obj.map(item => deepClone(item));
  if (typeof obj === 'object') {
    const cloned = {};
    Object.keys(obj).forEach(key => {
      cloned[key] = deepClone(obj[key]);
    });
    return cloned;
  }
  return obj;
};

// URL utilities
export const buildQueryString = (params) => {
  const cleaned = cleanObject(params);
  const searchParams = new URLSearchParams();
  
  Object.keys(cleaned).forEach(key => {
    const value = cleaned[key];
    if (Array.isArray(value)) {
      value.forEach(item => searchParams.append(key, item));
    } else {
      searchParams.append(key, value);
    }
  });
  
  return searchParams.toString();
};

export const parseQueryString = (queryString) => {
  const params = {};
  const searchParams = new URLSearchParams(queryString);
  
  for (const [key, value] of searchParams.entries()) {
    if (params[key]) {
      if (Array.isArray(params[key])) {
        params[key].push(value);
      } else {
        params[key] = [params[key], value];
      }
    } else {
      params[key] = value;
    }
  }
  
  return params;
};

// File utilities
export const formatFileSize = (bytes) => {
  if (bytes === 0) return '0 Bytes';
  
  const k = 1024;
  const sizes = ['Bytes', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
};

export const getFileExtension = (filename) => {
  if (!filename) return '';
  return filename.slice((filename.lastIndexOf('.') - 1 >>> 0) + 2);
};

// Local storage utilities
export const setLocalStorage = (key, value) => {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch (error) {
    console.error('Error setting localStorage:', error);
  }
};

export const getLocalStorage = (key, defaultValue = null) => {
  try {
    const item = localStorage.getItem(key);
    return item ? JSON.parse(item) : defaultValue;
  } catch (error) {
    console.error('Error getting localStorage:', error);
    return defaultValue;
  }
};

export const removeLocalStorage = (key) => {
  try {
    localStorage.removeItem(key);
  } catch (error) {
    console.error('Error removing localStorage:', error);
  }
};

// Debounce utility
export const debounce = (func, wait) => {
  let timeout;
  return function executedFunction(...args) {
    const later = () => {
      clearTimeout(timeout);
      func(...args);
    };
    clearTimeout(timeout);
    timeout = setTimeout(later, wait);
  };
};

// Throttle utility
export const throttle = (func, limit) => {
  let inThrottle;
  return function executedFunction(...args) {
    if (!inThrottle) {
      func.apply(this, args);
      inThrottle = true;
      setTimeout(() => inThrottle = false, limit);
    }
  };
};

// Color utilities
export const getRandomColor = () => {
  const colors = ['#3B82F6', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6', '#EC4899', '#06B6D4', '#84CC16'];
  return colors[Math.floor(Math.random() * colors.length)];
};

export const hexToRgba = (hex, alpha = 1) => {
  const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
  if (!result) return null;
  
  const r = parseInt(result[1], 16);
  const g = parseInt(result[2], 16);
  const b = parseInt(result[3], 16);
  
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
};

// Publication utilities
export const getPublicationTypeColor = (type) => {
  const colors = {
    'artikel': '#10B981',
    'buku': '#8B5CF6',
    'prosiding': '#F59E0B',
    'penelitian': '#3B82F6'
  };
  return colors[type?.toLowerCase()] || '#6B7280';
};

export const getSintaRanking = (score) => {
  if (!score) return 'Unranked';
  if (score >= 4) return 'Sinta 1';
  if (score >= 3) return 'Sinta 2';
  if (score >= 2) return 'Sinta 3';
  if (score >= 1.5) return 'Sinta 4';
  if (score >= 1) return 'Sinta 5';
  return 'Sinta 6';
};