import React, { useState, useEffect } from 'react';
import { authApi } from '../api/auth';
import Register from './Register';
import './Auth.css';

function Auth({ onAuthChange }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [showRegister, setShowRegister] = useState(false);
  const [showPasswordLogin, setShowPasswordLogin] = useState(false);
  const [loginFormData, setLoginFormData] = useState({ email: '', password: '' });
  const [loginLoading, setLoginLoading] = useState(false);

  useEffect(() => {
    // Check if we came from OAuth callback
    const urlParams = new URLSearchParams(window.location.search);
    const auth = urlParams.get('auth');
    
    if (auth === 'success') {
      // Clear URL parameters
      window.history.replaceState({}, document.title, window.location.pathname);
      // Load user
      fetchUser();
    } else if (auth === 'error') {
      const reason = urlParams.get('reason');
      setError(`Authentication failed: ${reason || 'unknown error'}`);
      // Clear URL parameters
      window.history.replaceState({}, document.title, window.location.pathname);
      fetchUser();
    } else {
      fetchUser();
    }
  }, []);

  const fetchUser = async () => {
    try {
      setLoading(true);
      setError(null);
      const userData = await authApi.getCurrentUser();
      setUser(userData);
    } catch (err) {
      // 401 means user is not authenticated - this is normal
      if (err.message.includes('401') || err.message.includes('Not authenticated')) {
        setUser(null);
      } else {
        setError(err.message);
      }
    } finally {
      setLoading(false);
    }
  };

  const handleLogin = () => {
    authApi.initiateLogin();
  };

  const handleLogout = async () => {
    try {
      await authApi.logout();
      setUser(null);
    } catch (err) {
      setError(err.message);
    }
  };

  const handleRegisterSuccess = async () => {
    // After successful registration, load user
    await fetchUser();
    setShowRegister(false);
  };

  const handlePasswordLogin = async (e) => {
    e.preventDefault();
    setError(null);
    setLoginLoading(true);
    
    try {
      await authApi.loginWithPassword(loginFormData.email, loginFormData.password);
      await fetchUser();
      setShowPasswordLogin(false);
      setLoginFormData({ email: '', password: '' });
    } catch (err) {
      setError(err.message || 'Login error');
    } finally {
      setLoginLoading(false);
    }
  };

  const handleLoginChange = (e) => {
    const { name, value } = e.target;
    setLoginFormData((prev) => ({ ...prev, [name]: value }));
    setError(null);
  };

  useEffect(() => {
    if (typeof onAuthChange === 'function') {
      onAuthChange(user);
    }
  }, [user, onAuthChange]);

  if (loading) {
    return (
      <div className="auth-container">
        <div className="auth-loading">Loading...</div>
      </div>
    );
  }

  if (error && !user) {
    return (
      <div className="auth-container">
        <div className="auth-error">Error: {error}</div>
        <button onClick={handleLogin} className="auth-button auth-button-primary">
          Sign in with Google
        </button>
      </div>
    );
  }

  if (!user) {
    if (showRegister) {
      return (
        <Register
          onSuccess={handleRegisterSuccess}
          onSwitchToLogin={() => setShowRegister(false)}
        />
      );
    }

    return (
      <div className="auth-container">
        <div className="auth-tabs">
          <button
            className={`auth-tab ${!showPasswordLogin ? 'active' : ''}`}
            onClick={() => {
              setShowPasswordLogin(false);
              setError(null);
            }}
          >
            Google
          </button>
          <button
            className={`auth-tab ${showPasswordLogin ? 'active' : ''}`}
            onClick={() => {
              setShowPasswordLogin(true);
              setError(null);
            }}
          >
            Email/Password
          </button>
        </div>

        {error && (
          <div className="auth-error">{error}</div>
        )}

        {showPasswordLogin ? (
          <form onSubmit={handlePasswordLogin} className="auth-login-form">
            <div className="auth-form-group">
              <label htmlFor="login-email">Email</label>
              <input
                type="email"
                id="login-email"
                name="email"
                value={loginFormData.email}
                onChange={handleLoginChange}
                required
                disabled={loginLoading}
                placeholder="example@email.com"
              />
            </div>

            <div className="auth-form-group">
              <label htmlFor="login-password">Password</label>
              <input
                type="password"
                id="login-password"
                name="password"
                value={loginFormData.password}
                onChange={handleLoginChange}
                required
                disabled={loginLoading}
                placeholder="Enter password"
              />
            </div>

            <button
              type="submit"
              className="auth-button auth-button-primary"
              disabled={loginLoading}
            >
              {loginLoading ? 'Signing in...' : 'Sign In'}
            </button>
          </form>
        ) : (
          <button onClick={handleLogin} className="auth-button auth-button-primary">
            <svg
              width="18"
              height="18"
              viewBox="0 0 18 18"
              fill="none"
              xmlns="http://www.w3.org/2000/svg"
              style={{ marginRight: '8px' }}
            >
              <path
                d="M17.64 9.2c0-.637-.057-1.25-.164-1.84H9v3.48h4.844c-.209 1.125-.843 2.078-1.796 2.717v2.258h2.908c1.702-1.567 2.684-3.874 2.684-6.615z"
                fill="#4285F4"
              />
              <path
                d="M9 18c2.43 0 4.467-.806 5.96-2.185l-2.908-2.258c-.806.54-1.837.86-3.052.86-2.344 0-4.328-1.584-5.038-3.71H.957v2.332C2.438 15.983 5.482 18 9 18z"
                fill="#34A853"
              />
              <path
                d="M3.962 10.707c-.18-.54-.282-1.117-.282-1.707s.102-1.167.282-1.707V5.961H.957C.348 7.175 0 8.55 0 10s.348 2.825.957 4.039l3.005-2.332z"
                fill="#FBBC05"
              />
              <path
                d="M9 3.58c1.321 0 2.508.454 3.44 1.345l2.582-2.58C13.463.891 11.426 0 9 0 5.482 0 2.438 2.017.957 4.961L3.962 7.293C4.672 5.163 6.656 3.58 9 3.58z"
                fill="#EA4335"
              />
            </svg>
            Sign in with Google
          </button>
        )}

        <div className="auth-switch">
          <span>Don't have an account? </span>
          <button
            type="button"
            className="auth-link-button"
            onClick={() => setShowRegister(true)}
            disabled={loginLoading}
          >
            Sign Up
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="auth-container">
      <div className="auth-user-info">
        {user.avatar_url && (
          <img
            src={authApi.getAvatarUrl()}
            alt={user.full_name || user.email}
            className="auth-avatar"
            onError={(e) => {
              // Fallback to original URL if proxy doesn't work
              if (e.target.src !== user.avatar_url) {
                e.target.src = user.avatar_url;
              }
            }}
          />
        )}
        <div className="auth-user-details">
          <div className="auth-user-name">{user.full_name || user.email}</div>
          <div className="auth-user-email">{user.email}</div>
          <div className="auth-user-status">Status: {user.status}</div>
        </div>
      </div>
      <button onClick={handleLogout} className="auth-button auth-button-secondary">
        Sign Out
      </button>
    </div>
  );
}

Auth.defaultProps = {
  onAuthChange: () => {},
};

export default Auth;

