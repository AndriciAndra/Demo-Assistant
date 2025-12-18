import React, { useState, useEffect } from 'react';
import { useOutletContext } from 'react-router-dom';
import { FolderOpen } from 'lucide-react';
import { Card, Button, Dropdown, Toggle, Alert } from '../components/common';
import { jiraService, settingsService } from '../services';

export default function SettingsPage() {
  const { settings, refreshSettings } = useOutletContext();
  const [jiraCredentials, setJiraCredentials] = useState({
    base_url: '',
    email: '',
    api_token: '',
  });
  const [schedulerSettings, setSchedulerSettings] = useState({
    enabled: false,
    day_of_week: 'thu',
    hour: 18,
    minute: 0,
  });
  const [storageSettings, setStorageSettings] = useState({
    sync_to_drive: false,
    drive_folder_id: '',
  });
  const [isConnectingJira, setIsConnectingJira] = useState(false);
  const [isSavingScheduler, setIsSavingScheduler] = useState(false);
  const [isSavingStorage, setIsSavingStorage] = useState(false);
  const [message, setMessage] = useState(null);

  useEffect(() => {
    if (settings) {
      setSchedulerSettings(settings.scheduler || schedulerSettings);
      setStorageSettings(settings.storage || storageSettings);
    }
  }, [settings]);

  const handleConnectJira = async () => {
    setIsConnectingJira(true);
    setMessage(null);
    try {
      await jiraService.connect(jiraCredentials);
      setMessage({ type: 'success', text: 'Jira connected successfully!' });
      refreshSettings();
      setJiraCredentials({ base_url: '', email: '', api_token: '' });
    } catch (err) {
      setMessage({
        type: 'error',
        text: err.response?.data?.detail || 'Failed to connect Jira',
      });
    } finally {
      setIsConnectingJira(false);
    }
  };

  const handleDisconnectJira = async () => {
    if (!confirm('Are you sure you want to disconnect Jira?')) return;
    try {
      await settingsService.disconnectJira();
      setMessage({ type: 'success', text: 'Jira disconnected' });
      refreshSettings();
    } catch (err) {
      setMessage({ type: 'error', text: 'Failed to disconnect Jira' });
    }
  };

  const handleSaveScheduler = async () => {
    setIsSavingScheduler(true);
    setMessage(null);
    try {
      await settingsService.updateScheduler(schedulerSettings);
      setMessage({ type: 'success', text: 'Scheduler settings saved!' });
      refreshSettings();
    } catch (err) {
      setMessage({ type: 'error', text: 'Failed to save scheduler settings' });
    } finally {
      setIsSavingScheduler(false);
    }
  };

  const handleSaveStorage = async () => {
    setIsSavingStorage(true);
    setMessage(null);
    try {
      await settingsService.updateStorage(storageSettings);
      setMessage({ type: 'success', text: 'Storage settings saved!' });
      refreshSettings();
    } catch (err) {
      setMessage({ type: 'error', text: 'Failed to save storage settings' });
    } finally {
      setIsSavingStorage(false);
    }
  };

  const dayOptions = [
    { value: 'mon', label: 'Monday' },
    { value: 'tue', label: 'Tuesday' },
    { value: 'wed', label: 'Wednesday' },
    { value: 'thu', label: 'Thursday' },
    { value: 'fri', label: 'Friday' },
    { value: 'sat', label: 'Saturday' },
    { value: 'sun', label: 'Sunday' },
  ];

  const hourOptions = Array.from({ length: 24 }, (_, i) => ({
    value: i,
    label: `${i.toString().padStart(2, '0')}:00`,
  }));

  return (
    <div className="max-w-4xl mx-auto">
      <div className="mb-8">
        <h2 className="text-2xl font-bold text-gray-800">Settings</h2>
        <p className="text-gray-500 mt-1">
          Configure your integrations and preferences
        </p>
      </div>

      {message && (
        <Alert type={message.type} className="mb-6">
          {message.text}
        </Alert>
      )}

      {/* Jira Connection */}
      <Card className="p-6 mb-6">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center">
              <span className="text-blue-600 font-bold text-sm">J</span>
            </div>
            <div>
              <h3 className="font-semibold text-gray-700">Jira Integration</h3>
              <p className="text-sm text-gray-400">Connect your Atlassian account</p>
            </div>
          </div>
          <div
            className={`px-3 py-1 rounded-full text-sm ${
              settings.jira_connected
                ? 'bg-green-100 text-green-600'
                : 'bg-gray-100 text-gray-500'
            }`}
          >
            {settings.jira_connected ? 'Connected' : 'Not connected'}
          </div>
        </div>

        {settings.jira_connected ? (
          <div className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
            <div>
              <p className="text-sm text-gray-600">Jira account connected</p>
              <p className="text-xs text-gray-400">
                You can now use Demo Generator with your Jira projects
              </p>
            </div>
            <button
              onClick={handleDisconnectJira}
              className="text-sm text-red-500 hover:text-red-600"
            >
              Disconnect
            </button>
          </div>
        ) : (
          <div className="space-y-4">
            <div>
              <label className="block text-sm text-gray-500 mb-2">
                Jira URL
              </label>
              <input
                type="text"
                value={jiraCredentials.base_url}
                onChange={(e) =>
                  setJiraCredentials({ ...jiraCredentials, base_url: e.target.value })
                }
                placeholder="https://your-domain.atlassian.net"
                className="w-full px-4 py-3 bg-gray-50 border border-gray-200 rounded-lg outline-none focus:border-indigo-300"
              />
            </div>
            <div>
              <label className="block text-sm text-gray-500 mb-2">Email</label>
              <input
                type="email"
                value={jiraCredentials.email}
                onChange={(e) =>
                  setJiraCredentials({ ...jiraCredentials, email: e.target.value })
                }
                placeholder="your-email@example.com"
                className="w-full px-4 py-3 bg-gray-50 border border-gray-200 rounded-lg outline-none focus:border-indigo-300"
              />
            </div>
            <div>
              <label className="block text-sm text-gray-500 mb-2">
                API Token
              </label>
              <input
                type="password"
                value={jiraCredentials.api_token}
                onChange={(e) =>
                  setJiraCredentials({ ...jiraCredentials, api_token: e.target.value })
                }
                placeholder="Your Jira API token"
                className="w-full px-4 py-3 bg-gray-50 border border-gray-200 rounded-lg outline-none focus:border-indigo-300"
              />
              <p className="text-xs text-gray-400 mt-2">
                Get your API token from{' '}
                <a
                  href="https://id.atlassian.com/manage-profile/security/api-tokens"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-indigo-600 hover:underline"
                >
                  Atlassian Account Settings
                </a>
              </p>
            </div>
            <Button
              onClick={handleConnectJira}
              loading={isConnectingJira}
              disabled={
                !jiraCredentials.base_url ||
                !jiraCredentials.email ||
                !jiraCredentials.api_token
              }
            >
              Connect Jira
            </Button>
          </div>
        )}
      </Card>

      {/* Google Connection */}
      <Card className="p-6 mb-6">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-red-100 rounded-lg flex items-center justify-center">
              <span className="text-red-600 font-bold text-sm">G</span>
            </div>
            <div>
              <h3 className="font-semibold text-gray-700">Google Integration</h3>
              <p className="text-sm text-gray-400">For Slides and Drive storage</p>
            </div>
          </div>
          <div
            className={`px-3 py-1 rounded-full text-sm ${
              settings.google_connected
                ? 'bg-green-100 text-green-600'
                : 'bg-gray-100 text-gray-500'
            }`}
          >
            {settings.google_connected ? 'Connected' : 'Not connected'}
          </div>
        </div>
        <div className="p-4 bg-gray-50 rounded-lg">
          <p className="text-sm text-gray-600">
            {settings.google_connected
              ? 'Google account connected via OAuth login'
              : 'Google account will be connected when you log in'}
          </p>
        </div>
      </Card>

      {/* Scheduler */}
      <Card className="p-6 mb-6">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="font-semibold text-gray-700">Automatic Scheduling</h3>
            <p className="text-sm text-gray-400">Schedule automatic data scraping</p>
          </div>
        </div>

        <Toggle
          label="Enable Scheduler"
          description="Automatically scrape Jira data on schedule"
          checked={schedulerSettings.enabled}
          onChange={(checked) =>
            setSchedulerSettings({ ...schedulerSettings, enabled: checked })
          }
        />

        {schedulerSettings.enabled && (
          <div className="grid grid-cols-2 gap-4 mt-4">
            <Dropdown
              label="Day"
              value={schedulerSettings.day_of_week}
              options={dayOptions}
              onChange={(val) =>
                setSchedulerSettings({ ...schedulerSettings, day_of_week: val })
              }
            />
            <Dropdown
              label="Time"
              value={schedulerSettings.hour}
              options={hourOptions}
              onChange={(val) =>
                setSchedulerSettings({ ...schedulerSettings, hour: val })
              }
            />
          </div>
        )}

        <div className="mt-4">
          <Button
            variant="outline"
            onClick={handleSaveScheduler}
            loading={isSavingScheduler}
          >
            Save Scheduler Settings
          </Button>
        </div>
      </Card>

      {/* Storage */}
      <Card className="p-6">
        <h3 className="font-semibold text-gray-700 mb-4">Storage Settings</h3>

        <Toggle
          label="Sync to Google Drive"
          description="Automatically save files to Drive"
          checked={storageSettings.sync_to_drive}
          onChange={(checked) =>
            setStorageSettings({ ...storageSettings, sync_to_drive: checked })
          }
        />

        {storageSettings.sync_to_drive && (
          <div className="mt-4">
            <label className="block text-sm text-gray-500 mb-2">
              Drive Folder ID (optional)
            </label>
            <div className="flex items-center gap-2">
              <FolderOpen size={20} className="text-gray-400" />
              <input
                type="text"
                value={storageSettings.drive_folder_id || ''}
                onChange={(e) =>
                  setStorageSettings({
                    ...storageSettings,
                    drive_folder_id: e.target.value,
                  })
                }
                placeholder="Enter folder ID or leave empty for root"
                className="flex-1 px-4 py-3 bg-gray-50 border border-gray-200 rounded-lg outline-none focus:border-indigo-300"
              />
            </div>
          </div>
        )}

        <div className="mt-4">
          <Button
            variant="outline"
            onClick={handleSaveStorage}
            loading={isSavingStorage}
          >
            Save Storage Settings
          </Button>
        </div>
      </Card>
    </div>
  );
}
