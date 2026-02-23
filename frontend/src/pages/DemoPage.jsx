import React, { useState, useEffect } from 'react';
import { useOutletContext } from 'react-router-dom';
import { Target, Check, TrendingUp, Clock, RefreshCw, Sparkles } from 'lucide-react';
import { Card, Button, Dropdown, DateInput, MetricCard, Alert } from '../components/common';
import { jiraService, demoService } from '../services';

export default function DemoPage() {
  const { settings } = useOutletContext();
  const [projects, setProjects] = useState([]);
  const [sprints, setSprints] = useState([]);
  const [selectedProject, setSelectedProject] = useState('');
  const [selectedSprint, setSelectedSprint] = useState('');
  const [dateRange, setDateRange] = useState({
    start: new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
    end: new Date().toISOString().split('T')[0],
  });
  const [useSprintRange, setUseSprintRange] = useState(true);
  const [metrics, setMetrics] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);

  useEffect(() => {
    if (settings.jira_connected) {
      loadProjects();
    }
  }, [settings.jira_connected]);

  useEffect(() => {
    if (selectedProject) {
      loadSprints();
      setSelectedSprint('');
      setMetrics(null);
    }
  }, [selectedProject]);

  useEffect(() => {
    if (selectedSprint && useSprintRange) {
      loadPreview();
    }
  }, [selectedSprint]);

  useEffect(() => {
    if (!useSprintRange && selectedProject && dateRange.start && dateRange.end) {
      const timer = setTimeout(() => {
        loadPreview();
      }, 500);
      return () => clearTimeout(timer);
    }
  }, [dateRange.start, dateRange.end, useSprintRange]);

  const loadProjects = async () => {
    try {
      const data = await jiraService.getProjects();
      setProjects(data);
    } catch (err) {
      setError('Failed to load projects');
    }
  };

  const loadSprints = async () => {
    try {
      const data = await jiraService.getSprints(selectedProject);
      
      // Filter: only closed and active sprints (no future)
      // Sort: most recent first (by end_date or start_date)
      const filteredSprints = data
        .filter(s => s.state === 'closed' || s.state === 'active')
        .sort((a, b) => {
          const dateA = new Date(a.end_date || a.start_date || 0);
          const dateB = new Date(b.end_date || b.start_date || 0);
          return dateB - dateA; // Descending (newest first)
        });
      
      setSprints(filteredSprints);
    } catch (err) {
      console.error('Failed to load sprints:', err);
    }
  };

  const loadPreview = async () => {
    if (!selectedProject) return;
    
    if (useSprintRange && !selectedSprint) return;
    if (!useSprintRange && (!dateRange.start || !dateRange.end)) return;

    setIsLoading(true);
    setError(null);
    try {
      let data;
      if (useSprintRange && selectedSprint) {
        data = await demoService.previewBySprint(selectedProject, selectedSprint);
      } else {
        data = await demoService.preview(
          selectedProject,
          dateRange.start,
          dateRange.end
        );
      }
      setMetrics(data.metrics);
    } catch (err) {
      console.error('Failed to load preview:', err);
      setError('Failed to load metrics preview');
    } finally {
      setIsLoading(false);
    }
  };

  const handleGenerate = async () => {
    setIsGenerating(true);
    setError(null);
    setResult(null);
    try {
      const requestData = {
        jira_project_key: selectedProject,
        ...(useSprintRange && selectedSprint
          ? { sprint_id: parseInt(selectedSprint) }
          : {
              date_range: {
                start: new Date(dateRange.start).toISOString(),
                end: new Date(dateRange.end).toISOString(),
              },
            }),
      };
      const data = await demoService.generate(requestData);
      setResult(data);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to generate demo');
    } finally {
      setIsGenerating(false);
    }
  };

  const handleSprintSelect = (sprintId) => {
    setSelectedSprint(sprintId);
    const sprint = sprints.find(s => String(s.id) === String(sprintId));
    if (sprint && sprint.start_date && sprint.end_date) {
      setDateRange({
        start: sprint.start_date.split('T')[0],
        end: sprint.end_date.split('T')[0],
      });
    }
  };

  if (!settings.jira_connected) {
    return (
      <div className="max-w-4xl mx-auto">
        <h2 className="text-2xl font-bold text-gray-800 mb-4">Demo Generator</h2>
        <Alert type="warning">
          Please connect your Jira account in Settings to use the Demo Generator.
        </Alert>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto">
      <div className="mb-8">
        <h2 className="text-2xl font-bold text-gray-800">Demo Generator</h2>
        <p className="text-gray-500 mt-1">
          Generate presentation slides from your Jira sprint data
        </p>
      </div>

      {error && (
        <Alert type="error" className="mb-6">
          {error}
        </Alert>
      )}

      {result && (
        <Alert type="success" className="mb-6">
          Demo generated successfully!{' '}
          <a
            href={result.google_slides_url}
            target="_blank"
            rel="noopener noreferrer"
            className="underline font-medium"
          >
            Open in Google Slides
          </a>
        </Alert>
      )}

      {/* Selection */}
      <Card className="p-6 mb-6">
        <h3 className="font-semibold text-gray-700 mb-4">Select Data Source</h3>
        <div className="grid grid-cols-2 gap-4">
          <Dropdown
            label="Project"
            value={selectedProject}
            options={projects.map((p) => ({ value: p.key, label: p.name }))}
            onChange={setSelectedProject}
            placeholder="Select project"
          />
          {useSprintRange && (
            <Dropdown
              label="Sprint"
              value={selectedSprint}
              options={sprints.map((s) => ({
                value: String(s.id),
                label: `${s.name} (${s.state})`,
              }))}
              onChange={handleSprintSelect}
              placeholder="Select sprint"
            />
          )}
        </div>

        <div className="mt-4">
          <div className="flex items-center gap-4 mb-2">
            <label className="text-sm text-gray-500">
              {useSprintRange ? 'Using sprint dates' : 'Using custom date range'}
            </label>
            <button
              onClick={() => {
                setUseSprintRange(!useSprintRange);
                setMetrics(null);
              }}
              className="text-sm text-indigo-600 hover:text-indigo-700"
            >
              {useSprintRange ? 'Use date range instead' : 'Use sprint instead'}
            </button>
          </div>
          {!useSprintRange && (
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
          )}
        </div>
      </Card>

      {/* Metrics Preview */}
      <div className="mb-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-semibold text-gray-700">Metrics Preview</h3>
          <Button
            variant="outline"
            size="sm"
            onClick={loadPreview}
            loading={isLoading}
            disabled={!selectedProject || (useSprintRange && !selectedSprint)}
          >
            <RefreshCw size={16} />
            Refresh
          </Button>
        </div>
        <div className="grid grid-cols-4 gap-4">
          <MetricCard
            icon={Target}
            label="Total Issues"
            value={metrics?.total_issues ?? '-'}
            color="bg-blue-500"
          />
          <MetricCard
            icon={Check}
            label="Completed"
            value={metrics?.completed_issues ?? '-'}
            subValue={metrics ? `${metrics.completion_rate}%` : undefined}
            color="bg-green-500"
          />
          <MetricCard
            icon={TrendingUp}
            label="Story Points"
            value={metrics?.total_story_points ?? '-'}
            color="bg-purple-500"
          />
          <MetricCard
            icon={Clock}
            label="Completed Points"
            value={metrics?.completed_story_points ?? '-'}
            color="bg-orange-500"
          />
        </div>
      </div>

      {/* Generate Button */}
      <div className="flex justify-end">
        <Button
          onClick={handleGenerate}
          loading={isGenerating}
          disabled={!selectedProject || (useSprintRange && !selectedSprint) || !metrics}
          size="lg"
        >
          <Sparkles size={20} />
          Generate Demo Presentation
        </Button>
      </div>
    </div>
  );
}
