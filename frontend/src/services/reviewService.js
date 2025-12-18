import api from './api';

const reviewService = {
  // Get AI-recommended template
  async recommendTemplate(data) {
    const response = await api.post('/self-review/recommend', data);
    return response.data;
  },

  // Generate self-review PDF
  async generate(data) {
    const response = await api.post('/self-review/generate', data);
    return response.data;
  },

  // Get review history
  async getHistory(limit = 10) {
    const response = await api.get('/self-review/history', {
      params: { limit },
    });
    return response.data;
  },

  // Delete review
  async delete(reviewId) {
    const response = await api.delete(`/self-review/${reviewId}`);
    return response.data;
  },
};

export default reviewService;
