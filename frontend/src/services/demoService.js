import api from './api';

const demoService = {
  // Generate demo presentation
  async generate(data) {
    const response = await api.post('/demo/generate', data);
    return response.data;
  },

  // Preview demo content
  async preview(projectKey, startDate, endDate) {
    const response = await api.get('/demo/preview', {
      params: {
        jira_project_key: projectKey,
        start_date: startDate,
        end_date: endDate,
      },
    });
    return response.data;
  },

  // Get demo history
  async getHistory(limit = 10) {
    const response = await api.get('/demo/history', {
      params: { limit },
    });
    return response.data;
  },

  // Delete demo
  async delete(demoId) {
    const response = await api.delete(`/demo/${demoId}`);
    return response.data;
  },
};

export default demoService;
