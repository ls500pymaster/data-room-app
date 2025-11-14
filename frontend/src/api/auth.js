import { apiClient } from './client';

export const authApi = {
  /**
   * Initiates OAuth flow - redirects to backend, which redirects to Google
   */
  initiateLogin() {
    // Use relative path in production, absolute URL in development
    const apiUrl = process.env.REACT_APP_API_URL || 
      (process.env.NODE_ENV === 'production' ? '' : 'http://localhost:8000');
    const loginUrl = `${apiUrl}/api/auth/login`;
    window.location.href = loginUrl;
  },

  /**
   * Gets current user
   */
  async getCurrentUser() {
    return apiClient.get('/auth/user');
  },

  /**
   * Gets URL for loading avatar through proxy
   */
  getAvatarUrl() {
    // apiClient.baseURL already contains /api, so just add /auth/avatar
    return `${apiClient.baseURL}/auth/avatar`;
  },

  /**
   * Sign out
   */
  async logout() {
    return apiClient.post('/auth/logout');
  },

  /**
   * Alternative login method - sends tokens from Google OAuth
   * (used if frontend handles Google OAuth itself)
   */
  async loginWithTokens(loginData) {
    return apiClient.post('/auth/login', loginData);
  },

  /**
   * Register new user with email and password
   */
  async register(email, password, fullName, phone) {
    return apiClient.post('/auth/register', {
      email,
      password,
      full_name: fullName || null,
      phone: phone || null,
    });
  },

  /**
   * Login with email and password
   */
  async loginWithPassword(email, password) {
    return apiClient.post('/auth/login', {
      email,
      password,
    });
  },
};

