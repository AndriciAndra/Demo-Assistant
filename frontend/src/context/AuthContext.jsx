import React, { createContext, useContext, useState, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import authService from '../services/authService';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    // Check for token in URL (OAuth callback)
    const params = new URLSearchParams(location.search);
    const token = params.get('token');

    if (token) {
      // Save token and fetch user
      localStorage.setItem('token', token);
      // Remove token from URL
      window.history.replaceState({}, document.title, location.pathname);
      fetchUser();
    } else {
      // Check existing auth
      const { token: savedToken, user: savedUser } = authService.getAuth();
      if (savedToken && savedUser) {
        setUser(savedUser);
        fetchUser(); // Refresh user data
      }
      setLoading(false);
    }
  }, [location]);

  const fetchUser = async () => {
    try {
      const userData = await authService.getCurrentUser();
      setUser(userData);
      localStorage.setItem('user', JSON.stringify(userData));
    } catch (error) {
      console.error('Failed to fetch user:', error);
      logout();
    } finally {
      setLoading(false);
    }
  };

  const login = async () => {
    try {
      const { authorization_url } = await authService.getGoogleLoginUrl(
        `${window.location.origin}/`
      );
      window.location.href = authorization_url;
    } catch (error) {
      console.error('Failed to get login URL:', error);
      throw error;
    }
  };

  const logout = () => {
    authService.logout();
    setUser(null);
    navigate('/login');
  };

  const value = {
    user,
    loading,
    login,
    logout,
    isAuthenticated: !!user,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
