import api from './api';

const analyticsService = {
  // Get user's sprint performance history
  async getMySprintPerformance(projectKey, numSprints = 5) {
    const response = await api.get('/analytics/my-sprints', {
      params: {
        project_key: projectKey,
        num_sprints: numSprints,
      },
    });
    return response.data;
  },

  // Get user's current sprint data
  async getMyCurrentSprint(projectKey) {
    const response = await api.get('/analytics/my-current-sprint', {
      params: { project_key: projectKey },
    });
    return response.data;
  },

  // Get user's overall stats (last 90 days)
  async getMyOverview(projectKey) {
    const response = await api.get('/analytics/my-overview', {
      params: { project_key: projectKey },
    });
    return response.data;
  },
};

export default analyticsService;
