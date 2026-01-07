import api from './api';

const jiraService = {
  // Connect Jira account
  async connect(credentials) {
    const response = await api.post('/jira/connect', credentials);
    return response.data;
  },

  // Test Jira connection
  async testConnection() {
    const response = await api.get('/jira/test');
    return response.data;
  },

  // Get all projects
  async getProjects() {
    const response = await api.get('/jira/projects');
    return response.data;
  },

  // Get sprints for a project
  async getSprints(projectKey, state = null) {
    const params = state ? { state } : {};
    const response = await api.get(`/jira/projects/${projectKey}/sprints`, { params });
    return response.data;
  },

  // Get velocity data
  async getVelocity(projectKey, sprints = 5) {
    const response = await api.get(`/jira/projects/${projectKey}/velocity`, {
      params: { sprints },
    });
    return response.data;
  },
};

export default jiraService;
