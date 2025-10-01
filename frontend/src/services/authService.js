import apiService from './apiService';

const authService = {
  register: async (username, email, password) => {
    try {
      console.log('Sending registration data:', { username, email, password }); // Debug log
      const response = await apiService.post('/auth/register', {
        v_username: username,
        v_email: email,
        v_password_hash: password
      });
      
      if (response.data && response.data.success) {
        return {
          success: true,
          data: response.data
        };
      } else {
        return {
          success: false,
          error: response.data?.error || 'Registration failed'
        };
      }
    } catch (error) {
      console.error('Registration error:', error.response?.data || error);
      return {
        success: false,
        error: error.response?.data?.error || error.message || 'Registration failed'
      };
    }
  },

  login: async (email, password) => {
    try {
      const response = await apiService.post('/auth/login', {
        v_email: email,
        v_password_hash: password,
      });
      if (response.data.token) {
        localStorage.setItem('token', response.data.token);
        localStorage.setItem('user', JSON.stringify(response.data.user));
      }
      return {
        success: true,
        data: response.data
      };
    } catch (error) {
      console.error('Login error:', error);
      return {
        success: false,
        error: error.response?.data?.error || 'Terjadi kesalahan saat login'
      };
    }
  },

  logout: () => {
    localStorage.removeItem('token');
    localStorage.removeItem('user');
  },

  getCurrentUser: () => {
    const user = localStorage.getItem('user');
    return user ? JSON.parse(user) : null;
  },

  getToken: () => {
    return localStorage.getItem('token');
  },
};

export default authService;