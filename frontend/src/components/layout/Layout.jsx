import React, { useState, useEffect } from 'react';
import { Outlet, Navigate } from 'react-router-dom';
import Sidebar from './Sidebar';
import { useAuth } from '../../hooks/useAuth';
import { settingsService } from '../../services';

export default function Layout() {
  const { isAuthenticated, loading } = useAuth();
  const [settings, setSettings] = useState({
    jira_connected: false,
    google_connected: false,
  });

  useEffect(() => {
    if (isAuthenticated) {
      loadSettings();
    }
  }, [isAuthenticated]);

  const loadSettings = async () => {
    try {
      const data = await settingsService.getSettings();
      setSettings(data);
    } catch (error) {
      console.error('Failed to load settings:', error);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600"></div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return (
    <div className="min-h-screen bg-gray-50 flex">
      <Sidebar
        jiraConnected={settings.jira_connected}
        googleConnected={settings.google_connected}
      />
      <main className="flex-1 p-8 overflow-auto">
        <Outlet context={{ settings, refreshSettings: loadSettings }} />
      </main>
    </div>
  );
}
