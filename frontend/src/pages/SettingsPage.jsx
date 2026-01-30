import React, { useState, useEffect } from 'react';
import { useOutletContext } from 'react-router-dom';
import { FolderOpen, Info } from 'lucide-react';
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
    frequency: 'weekly',
    days: ['thu'],
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
  const [isRunningNow, setIsRunningNow] = useState(false);
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
      const result = await settingsService.updateScheduler(schedulerSettings);
      setMessage({ 
        type: 'success', 
        text: `Scheduler settings saved! Cache expires in ${result.cache_expiry_hours} hours.` 
      });
      refreshSettings();
    } catch (err) {
      setMessage({ type: 'error', text: 'Failed to save scheduler settings' });
    } finally {
      setIsSavingScheduler(false);
    }
  };

  const handleRunNow = async () => {
    setIsRunningNow(true);
    setMessage(null);
    try {
      await settingsService.runSchedulerNow();
      setMessage({ type: 'success', text: 'Scraper completed! Data cached in MongoDB.' });
    } catch (err) {
      setMessage({ 
        type: 'error', 
        text: err.response?.data?.detail || 'Failed to run scraper' 
      });
    } finally {
      setIsRunningNow(false);
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

  const toggleDay = (day) => {
    const currentDays = schedulerSettings.days || [];
    if (currentDays.includes(day)) {
      // Remove day (but keep at least one)
      if (currentDays.length > 1) {
        setSchedulerSettings({
          ...schedulerSettings,
          days: currentDays.filter(d => d !== day)
        });
      }
    } else {
      // Add day
      setSchedulerSettings({
        ...schedulerSettings,
        days: [...currentDays, day]
      });
    }
  };

  const frequencyOptions = [
    { value: 'daily', label: 'Daily' },
    { value: 'weekly', label: 'Weekly' },
    { value: 'custom', label: 'Custom (select days)' },
  ];

  const allDays = [
    { value: 'mon', label: 'Monday' },
    { value: 'tue', label: 'Tuesday' },
    { value: 'wed', label: 'Wednesday' },
    { value: 'thu', label: 'Thursday' },
    { value: 'fri', label: 'Friday' },
    { value: 'sat', label: 'Saturday' },
    { value: 'sun', label: 'Sunday' },
  ];

  const hourOptions = Array.from({ length: 24 }, (_, i) => ({
    value: i.toString(),
    label: i.toString().padStart(2, '0'),
  }));

  const minuteOptions = Array.from({ length: 60 }, (_, i) => ({
    value: i.toString(),
    label: i.toString().padStart(2, '0'),
  }));

  // Calculate cache expiry for display
  const getCacheExpiryText = () => {
    const { frequency, days } = schedulerSettings;
    if (frequency === 'daily') return '~36 hours';
    if (frequency === 'weekly') return '~8 days';
    if (frequency === 'custom') {
      const numDays = days?.length || 1;
      if (numDays >= 5) return '~36 hours';
      if (numDays >= 3) return '~3 days';
      if (numDays >= 2) return '~4 days';
      return '~8 days';
    }
    return '~7 days';
  };

  // Format schedule description
  const getScheduleDescription = () => {
    const { frequency, days } = schedulerSettings;
    const hour = schedulerSettings.hour ?? 0;
    const minute = schedulerSettings.minute ?? 0;
    const timeStr = `${hour.toString().padStart(2, '0')}:${minute.toString().padStart(2, '0')}`;
    
    if (frequency === 'daily') {
      return `Every day at ${timeStr}`;
    } else if (frequency === 'weekly') {
      const dayLabel = allDays.find(d => d.value === days?.[0])?.label || 'Thu';
      return `Every ${dayLabel} at ${timeStr}`;
    } else {
      const dayLabels = days?.map(d => allDays.find(day => day.value === d)?.label).join(', ') || 'Thu';
      return `Every ${dayLabels} at ${timeStr}`;
    }
  };

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
            <p className="text-sm text-gray-400">Schedule automatic Jira data caching</p>
          </div>
        </div>

        <Toggle
          label="Enable Scheduler"
          description="Automatically cache Jira data on schedule"
          checked={schedulerSettings.enabled}
          onChange={(checked) =>
            setSchedulerSettings({ ...schedulerSettings, enabled: checked })
          }
        />

        {schedulerSettings.enabled && (
          <div className="mt-4 space-y-4">
            {/* Frequency */}
            <Dropdown
              label="Frequency"
              value={schedulerSettings.frequency}
              options={frequencyOptions}
              onChange={(val) =>
                setSchedulerSettings({ 
                  ...schedulerSettings, 
                  frequency: val,
                  days: val === 'daily' ? allDays.map(d => d.value) : 
                        val === 'weekly' ? [schedulerSettings.days?.[0] || 'thu'] :
                        schedulerSettings.days
                })
              }
            />

            {/* Day selection for weekly */}
            {schedulerSettings.frequency === 'weekly' && (
              <Dropdown
                label="Day"
                value={schedulerSettings.days?.[0] || 'thu'}
                options={allDays.map(d => ({ value: d.value, label: d.label }))}
                onChange={(val) =>
                  setSchedulerSettings({ ...schedulerSettings, days: [val] })
                }
              />
            )}

            {/* Day selection for custom */}
            {schedulerSettings.frequency === 'custom' && (
              <div>
                <label className="block text-sm text-gray-500 mb-2">Select Days</label>
                <div className="flex gap-2">
                  {allDays.map((day) => (
                    <button
                      key={day.value}
                      onClick={() => toggleDay(day.value)}
                      className={`px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                        schedulerSettings.days?.includes(day.value)
                          ? 'bg-indigo-600 text-white'
                          : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                      }`}
                    >
                      {day.label}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* Time selection */}
            <div className="grid grid-cols-2 gap-4">
              <Dropdown
                label="Hour"
                value={String(schedulerSettings.hour ?? 0)}
                options={hourOptions}
                onChange={(val) =>
                  setSchedulerSettings({ ...schedulerSettings, hour: Number(val) })
                }
              />
              <Dropdown
                label="Minute"
                value={String(schedulerSettings.minute ?? 0)}
                options={minuteOptions}
                onChange={(val) =>
                  setSchedulerSettings({ ...schedulerSettings, minute: Number(val) })
                }
              />
            </div>

            {/* Schedule summary */}
            <div className="p-3 bg-indigo-50 rounded-lg">
              <div className="flex items-start gap-2">
                <Info size={16} className="text-indigo-600 mt-0.5" />
                <div className="text-sm">
                  <p className="text-indigo-700 font-medium">{getScheduleDescription()}</p>
                  <p className="text-indigo-600 mt-1">
                    Cache expires after {getCacheExpiryText()}
                  </p>
                </div>
              </div>
            </div>
          </div>
        )}

        <div className="mt-4 flex gap-3">
          <Button
            variant="outline"
            onClick={handleSaveScheduler}
            loading={isSavingScheduler}
          >
            Save Scheduler Settings
          </Button>
          {settings.jira_connected && (
            <Button
              variant="secondary"
              onClick={handleRunNow}
              loading={isRunningNow}
            >
              Run Now
            </Button>
          )}
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
