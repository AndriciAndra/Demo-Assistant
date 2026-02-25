import React, { useState, useEffect } from 'react';
import { useOutletContext } from 'react-router-dom';
import { Target, Check, TrendingUp, Users, Sparkles, FileText, Download } from 'lucide-react';
import { Card, Button, Dropdown, DateInput, MetricCard, Alert } from '../components/common';
import { jiraService, reviewService } from '../services';
import api from '../services/api';

export default function ReviewPage() {
  const { settings } = useOutletContext();
  const [projects, setProjects] = useState([]);
  const [selectedProject, setSelectedProject] = useState('');
  const [dateRange, setDateRange] = useState({
    start: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
    end: new Date().toISOString().split('T')[0],
  });
  const [template, setTemplate] = useState('');
  const [metrics, setMetrics] = useState(null);
  const [isLoadingTemplate, setIsLoadingTemplate] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [isDownloading, setIsDownloading] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);

  useEffect(() => {
    if (settings.jira_connected) {
      loadProjects();
    }
  }, [settings.jira_connected]);

  const loadProjects = async () => {
    try {
      const data = await jiraService.getProjects();
      setProjects(data);
    } catch (err) {
      setError('Failed to load projects');
    }
  };

  const handleRecommendTemplate = async () => {
    if (!selectedProject) {
      setError('Please select a project first');
      return;
    }

    setIsLoadingTemplate(true);
    setError(null);
    try {
      const data = await reviewService.recommendTemplate({
        jira_project_key: selectedProject,
        date_range: {
          start: new Date(dateRange.start).toISOString(),
          end: new Date(dateRange.end).toISOString(),
        },
      });
      setTemplate(data.recommended_template);
      setMetrics(data.metrics_preview);
    } catch (err) {
      setError('Failed to get template recommendation');
    } finally {
      setIsLoadingTemplate(false);
    }
  };

  const handleGenerate = async () => {
    if (!selectedProject) {
      setError('Please select a project first');
      return;
    }

    setIsGenerating(true);
    setError(null);
    setResult(null);
    try {
      const data = await reviewService.generate({
        jira_project_key: selectedProject,
        date_range: {
          start: new Date(dateRange.start).toISOString(),
          end: new Date(dateRange.end).toISOString(),
        },
        template: template || null,
      });
      setResult(data);
    } catch (err) {
      setError('Failed to generate self-review');
    } finally {
      setIsGenerating(false);
    }
  };

  const handleDownload = async () => {
    if (!result?.download_url) return;

    const path = result.download_url;

    // If it's a full URL, just open it
    if (path.startsWith('http')) {
      window.open(path, '_blank');
      return;
    }

    // Remove /api prefix if present since api instance already has baseURL with /api
    const cleanPath = path.startsWith('/api') ? path.replace('/api', '') : path;

    // For API paths, download via axios
    setIsDownloading(true);
    try {
      const response = await api.get(cleanPath, {
        responseType: 'blob',
        timeout: 30000,
      });

      // Create download link
      const blob = new Blob([response.data], { type: 'application/pdf' });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;

      // Use filename from result or generate one
      const filename = result.filename || `self_review_${selectedProject}_${new Date().toISOString().split('T')[0]}.pdf`;
      link.setAttribute('download', filename);
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
    } catch (err) {
      console.error('Download failed:', err);
      setError('Failed to download file');
    } finally {
      setIsDownloading(false);
    }
  };

  if (!settings.jira_connected) {
    return (
      <div className="max-w-4xl mx-auto">
        <h2 className="text-2xl font-bold text-gray-800 mb-4">Self Review Generator</h2>
        <Alert type="warning">
          Please connect your Jira account in Settings to use the Self Review Generator.
        </Alert>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto">
      <div className="mb-8">
        <h2 className="text-2xl font-bold text-gray-800">Self Review Generator</h2>
        <p className="text-gray-500 mt-1">
          Generate your performance review based on completed work
        </p>
      </div>

      {error && (
        <Alert type="error" className="mb-6">
          {error}
        </Alert>
      )}

      {result && (
        <Alert type="success" className="mb-6">
          <div className="flex items-center justify-between">
            <span>Self-review generated successfully!</span>
            <button
              onClick={handleDownload}
              disabled={isDownloading}
              className="inline-flex items-center gap-2 px-3 py-1 bg-green-600 text-white rounded-md hover:bg-green-700 transition-colors disabled:opacity-50"
            >
              {isDownloading ? (
                <>
                  <div className="animate-spin h-4 w-4 border-2 border-white border-t-transparent rounded-full" />
                  Downloading...
                </>
              ) : (
                <>
                  <Download size={16} />
                  Download PDF
                </>
              )}
            </button>
          </div>
        </Alert>
      )}

      {/* Selection */}
      <Card className="p-6 mb-6">
        <h3 className="font-semibold text-gray-700 mb-4">Review Period</h3>
        <div className="grid grid-cols-2 gap-4 mb-4">
          <Dropdown
            label="Project"
            value={selectedProject}
            options={projects.map((p) => ({ value: p.key, label: p.name }))}
            onChange={setSelectedProject}
            placeholder="Select project"
          />
        </div>
        <div className="flex gap-4">
          <DateInput
            label="Start Date"
            value={dateRange.start}
            onChange={(val) => setDateRange({ ...dateRange, start: val })}
            className="flex-1"
          />
          <DateInput
            label="End Date"
            value={dateRange.end}
            onChange={(val) => setDateRange({ ...dateRange, end: val })}
            className="flex-1"
          />
        </div>
      </Card>

      {/* Template */}
      <Card className="p-6 mb-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-semibold text-gray-700">Review Template</h3>
          <Button
            variant="outline"
            size="sm"
            onClick={handleRecommendTemplate}
            loading={isLoadingTemplate}
            disabled={!selectedProject}
          >
            <Sparkles size={16} />
            AI Recommend
          </Button>
        </div>
        <textarea
          value={template}
          onChange={(e) => setTemplate(e.target.value)}
          placeholder={`Enter your template or let AI recommend one based on your work data...

Example:
SUMMARY
[Describe your overall impact and value delivered]

KEY ACCOMPLISHMENTS  
[Describe main achievements and their business impact]

CHALLENGES OVERCOME
[Describe difficult problems you solved]

GOALS FOR NEXT PERIOD
[What you plan to focus on next]`}
          className="w-full h-48 px-4 py-3 bg-gray-50 border border-gray-200 rounded-lg resize-none outline-none focus:border-indigo-300 text-gray-700 placeholder:text-gray-400"
        />
      </Card>

      {/* Metrics Preview */}
      {metrics && (
        <div className="mb-6">
          <h3 className="font-semibold text-gray-700 mb-4">Work Summary</h3>
          <div className="grid grid-cols-4 gap-4">
            <MetricCard
              icon={Target}
              label="Total Issues"
              value={metrics.total_issues}
              color="bg-blue-500"
            />
            <MetricCard
              icon={Check}
              label="Completed"
              value={metrics.completed_issues}
              subValue={`${metrics.completion_rate}%`}
              color="bg-green-500"
            />
            <MetricCard
              icon={TrendingUp}
              label="Story Points"
              value={metrics.total_story_points || '-'}
              color="bg-purple-500"
            />
            <MetricCard
              icon={Users}
              label="Issue Types"
              value={Object.keys(metrics.by_type || {}).length}
              color="bg-pink-500"
            />
          </div>
        </div>
      )}

      {/* Generate Button */}
      <Card className="p-6">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="font-semibold text-gray-700">Generate Self Review</h3>
            <p className="text-sm text-gray-400 mt-1">
              Creates a PDF document with your performance review
            </p>
          </div>
          <Button
            onClick={handleGenerate}
            loading={isGenerating}
            disabled={!selectedProject}
          >
            <FileText size={18} />
            Generate PDF
          </Button>
        </div>
      </Card>
    </div>
  );
}
