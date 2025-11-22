// Use relative path in production (same domain), absolute URL in development
const getApiUrl = () => {
  if (process.env.REACT_APP_API_URL) {
    return process.env.REACT_APP_API_URL;
  }
  // In production, if served from same domain, use relative path
  if (process.env.NODE_ENV === 'production') {
    return '';
  }
  return 'http://localhost:8000';
};

const API_URL = getApiUrl();

class ApiClient {
  constructor() {
    this.baseURL = `${API_URL}/api`;
  }

  async request(endpoint, options = {}) {
    const url = `${this.baseURL}${endpoint}`;
    
    // Check if body is FormData - don't stringify it and don't set Content-Type
    const isFormData = options.body instanceof FormData;
    
    const config = {
      ...options,
      credentials: 'include', // For working with cookies
      headers: {
        // Only set Content-Type for non-FormData requests
        ...(isFormData ? {} : { 'Content-Type': 'application/json' }),
        ...options.headers,
      },
    };

    try {
      const response = await fetch(url, config);
      
      if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: response.statusText }));
        throw new Error(error.detail || `HTTP error! status: ${response.status}`);
      }

      // 204 No Content has no body
      if (response.status === 204) {
        return null;
      }

      return await response.json();
    } catch (error) {
      console.error('API request failed:', error);
      throw error;
    }
  }

  async get(endpoint) {
    return this.request(endpoint, { method: 'GET' });
  }

  async post(endpoint, data, options = {}) {
    // If data is FormData, pass it directly; otherwise stringify
    const body = data instanceof FormData ? data : JSON.stringify(data);
    
    return this.request(endpoint, {
      method: 'POST',
      body,
      ...options,
    });
  }

  async delete(endpoint) {
    return this.request(endpoint, { method: 'DELETE' });
  }
}

export const apiClient = new ApiClient();

