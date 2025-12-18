import api from './api';

const settingsService = {
  // Get all settings
  async getSettings() {
    const response = await api.get('/settings');
    return response.data;
  },

  // Update scheduler settings
  async updateScheduler(settings) {
    const response = await api.put('/settings/scheduler', settings);
    return response.data;
  },

  // Update storage settings
  async updateStorage(settings) {
    const response = await api.put('/settings/storage', settings);
    return response.data;
  },

  // Update profile
  async updateProfile(data) {
    const response = await api.put('/settings/profile', data);
    return response.data;
  },

  // Get scheduled jobs
  async getScheduledJobs() {
    const response = await api.get('/settings/scheduled-jobs');
    return response.data;
  },

  // Disconnect Jira
  async disconnectJira() {
    const response = await api.delete('/settings/jira');
    return response.data;
  },
};

export default settingsService;
