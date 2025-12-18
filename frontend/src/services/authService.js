import api from './api';

const authService = {
  // Get Google OAuth login URL
  async getGoogleLoginUrl(redirectUrl = window.location.origin) {
    const response = await api.get('/auth/google/login', {
      params: { redirect_url: redirectUrl },
    });
    return response.data;
  },

  // Exchange code for token (for SPA flow)
  async exchangeCodeForToken(code) {
    const response = await api.post('/auth/google/token', null, {
      params: { code },
    });
    return response.data;
  },

  // Get current user info
  async getCurrentUser() {
    const response = await api.get('/auth/me');
    return response.data;
  },

  // Refresh token
  async refreshToken() {
    const response = await api.post('/auth/refresh');
    return response.data;
  },

  // Logout
  async logout() {
    try {
      await api.post('/auth/logout');
    } catch (error) {
      // Ignore errors, just clear local storage
    }
    localStorage.removeItem('token');
    localStorage.removeItem('user');
  },

  // Save auth data to local storage
  saveAuth(token, user) {
    localStorage.setItem('token', token);
    localStorage.setItem('user', JSON.stringify(user));
  },

  // Get saved auth data
  getAuth() {
    const token = localStorage.getItem('token');
    const userStr = localStorage.getItem('user');
    const user = userStr ? JSON.parse(userStr) : null;
    return { token, user };
  },

  // Check if user is authenticated
  isAuthenticated() {
    return !!localStorage.getItem('token');
  },
};

export default authService;
