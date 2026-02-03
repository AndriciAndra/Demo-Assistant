import React from 'react';
import { NavLink } from 'react-router-dom';
import { Play, FileText, History, Settings, Sparkles, LogOut, BarChart3 } from 'lucide-react';
import { useAuth } from '../../hooks/useAuth';

const navItems = [
  { to: '/', icon: Play, label: 'Demo Generator' },
  { to: '/review', icon: FileText, label: 'Self Review' },
  { to: '/analytics', icon: BarChart3, label: 'My Performance' },
  { to: '/history', icon: History, label: 'History' },
  { to: '/settings', icon: Settings, label: 'Settings' },
];

export default function Sidebar({ jiraConnected, googleConnected }) {
  const { user, logout } = useAuth();

  return (
    <aside className="w-64 bg-white border-r border-gray-200 p-4 flex flex-col h-screen sticky top-0">
      {/* Logo */}
      <div className="flex items-center gap-3 px-4 py-3 mb-6">
        <div className="w-10 h-10 bg-indigo-600 rounded-xl flex items-center justify-center">
          <Sparkles size={22} className="text-white" />
        </div>
        <div>
          <h1 className="font-bold text-gray-800">Demo Assistant</h1>
          <p className="text-xs text-gray-400">Powered by AI</p>
        </div>
      </div>

      {/* Navigation */}
      <nav className="space-y-2 flex-1">
        {navItems.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              `flex items-center gap-3 w-full px-4 py-3 rounded-lg transition-all ${
                isActive
                  ? 'bg-indigo-600 text-white'
                  : 'text-gray-600 hover:bg-gray-100'
              }`
            }
          >
            <Icon size={20} />
            <span className="font-medium">{label}</span>
          </NavLink>
        ))}
      </nav>

      {/* Connection Status */}
      <div className="border-t border-gray-100 pt-4 mt-4 space-y-2">
        <div className="flex items-center gap-2 px-4 py-2 text-sm">
          <div
            className={`w-2 h-2 rounded-full ${
              jiraConnected ? 'bg-green-500' : 'bg-red-500'
            }`}
          />
          <span className="text-gray-600">Jira</span>
          <span className={jiraConnected ? 'text-green-600' : 'text-red-600'}>
            {jiraConnected ? 'Connected' : 'Disconnected'}
          </span>
        </div>
        <div className="flex items-center gap-2 px-4 py-2 text-sm">
          <div
            className={`w-2 h-2 rounded-full ${
              googleConnected ? 'bg-green-500' : 'bg-red-500'
            }`}
          />
          <span className="text-gray-600">Google</span>
          <span className={googleConnected ? 'text-green-600' : 'text-red-600'}>
            {googleConnected ? 'Connected' : 'Disconnected'}
          </span>
        </div>
      </div>

      {/* User */}
      <div className="border-t border-gray-100 pt-4 mt-4">
        <div className="flex items-center gap-3 px-4 py-2">
          <div className="w-8 h-8 bg-gray-200 rounded-full flex items-center justify-center">
            <span className="text-sm font-medium text-gray-600">
              {user?.name?.charAt(0)?.toUpperCase() || user?.email?.charAt(0)?.toUpperCase() || '?'}
            </span>
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-gray-700 truncate">
              {user?.name || 'User'}
            </p>
            <p className="text-xs text-gray-400 truncate">{user?.email}</p>
          </div>
          <button
            onClick={logout}
            className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
            title="Logout"
          >
            <LogOut size={16} className="text-gray-400" />
          </button>
        </div>
      </div>
    </aside>
  );
}
