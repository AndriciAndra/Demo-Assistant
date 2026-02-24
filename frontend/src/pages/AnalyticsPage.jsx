import React, { useState, useEffect } from 'react';
import { useOutletContext } from 'react-router-dom';
import {
  BarChart,
  Bar,
  LineChart,
  Line,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  Area,
  AreaChart,
} from 'recharts';
import {
  TrendingUp,
  Target,
  CheckCircle,
  Clock,
  Zap,
  Award,
  Activity,
  BarChart3,
  Flame,
  Timer,
} from 'lucide-react';
import { Card, Button, Dropdown, Alert } from '../components/common';
import { jiraService, analyticsService } from '../services';

// Color palette for charts
const COLORS = {
  primary: '#6366f1',
  success: '#10b981',
  warning: '#f59e0b',
  danger: '#ef4444',
  info: '#3b82f6',
  purple: '#8b5cf6',
  pink: '#ec4899',
  teal: '#14b8a6',
};

const PIE_COLORS = ['#10b981', '#3b82f6', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#14b8a6', '#6366f1'];

// Status colors for pie chart
const STATUS_COLORS = {
  'Done': '#10b981',
  'Closed': '#10b981',
  'Resolved': '#10b981',
  'In Progress': '#3b82f6',
  'In Review': '#8b5cf6',
  'To Do': '#9ca3af',
  'Open': '#9ca3af',
  'Blocked': '#ef4444',
};

// Custom tooltip for charts
const CustomTooltip = ({ active, payload, label }) => {
  if (active && payload && payload.length) {
    return (
      <div className="bg-white p-3 rounded-lg shadow-lg border border-gray-200">
        <p className="font-medium text-gray-700">{label}</p>
        {payload.map((entry, index) => (
          <p key={index} style={{ color: entry.color }} className="text-sm">
            {entry.name}: {entry.value}
          </p>
        ))}
      </div>
    );
  }
  return null;
};

// Stat Card Component
function StatCard({ icon: Icon, label, value, subValue, trend, color }) {
  return (
    <div className="bg-white rounded-xl p-5 shadow-sm border border-gray-100">
      <div className="flex items-center justify-between mb-3">
        <div className={`p-2 rounded-lg ${color}`}>
          <Icon size={20} className="text-white" />
        </div>
        {trend !== null && trend !== undefined && (
          <span
            className={`text-sm font-medium ${
              trend > 0 ? 'text-green-600' : trend < 0 ? 'text-red-600' : 'text-gray-500'
            }`}
          >
            {trend > 0 ? '↑' : trend < 0 ? '↓' : '→'} {Math.abs(trend)}%
          </span>
        )}
      </div>
      <div className="text-2xl font-bold text-gray-800">{value}</div>
      <div className="text-sm text-gray-500 mt-1">{label}</div>
      {subValue && <div className="text-xs text-gray-400 mt-1">{subValue}</div>}
    </div>
  );
}

export default function AnalyticsPage() {
  const { settings } = useOutletContext();
  const [projects, setProjects] = useState([]);
  const [selectedProject, setSelectedProject] = useState('');
  const [numSprints, setNumSprints] = useState(5);
  const [sprintData, setSprintData] = useState(null);
  const [currentSprint, setCurrentSprint] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (settings.jira_connected) {
      loadProjects();
    }
  }, [settings.jira_connected]);

  useEffect(() => {
    if (selectedProject) {
      loadAnalytics();
    }
  }, [selectedProject, numSprints]);

  const loadProjects = async () => {
    try {
      const data = await jiraService.getProjects();
      setProjects(data);
      if (data.length > 0) {
        setSelectedProject(data[0].key);
      }
    } catch (err) {
      setError('Failed to load projects');
    }
  };

  const loadAnalytics = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const [sprintPerf, current] = await Promise.all([
        analyticsService.getMySprintPerformance(selectedProject, numSprints),
        analyticsService.getMyCurrentSprint(selectedProject).catch(() => null),
      ]);
      setSprintData(sprintPerf);
      setCurrentSprint(current);
    } catch (err) {
      console.error('Analytics error:', err);
      setError('Failed to load analytics data');
    } finally {
      setIsLoading(false);
    }
  };

  // Prepare chart data
  const velocityData = sprintData?.sprints?.map((s) => ({
    name: s.sprint_name.replace('Sprint ', 'S'),
    velocity: s.metrics.velocity,
    issues: s.metrics.completed_issues,
  })) || [];

  const completionRateData = sprintData?.sprints?.map((s) => ({
    name: s.sprint_name.replace('Sprint ', 'S'),
    rate: s.metrics.completion_rate,
    total: s.metrics.total_issues,
    completed: s.metrics.completed_issues,
  })) || [];

  // Issues by Status (NEW - replaces Issues by Type)
  const issuesByStatusData = sprintData?.sprints?.length > 0
    ? Object.entries(
        sprintData.sprints.reduce((acc, sprint) => {
          Object.entries(sprint.by_status || {}).forEach(([status, count]) => {
            acc[status] = (acc[status] || 0) + count;
          });
          return acc;
        }, {})
      ).map(([name, value]) => ({ 
        name, 
        value,
        color: STATUS_COLORS[name] || '#9ca3af'
      }))
    : [];

  const sprintComparisonData = sprintData?.sprints?.map((s) => ({
    name: s.sprint_name.replace('Sprint ', 'S'),
    'Total Issues': s.metrics.total_issues,
    'Completed': s.metrics.completed_issues,
    'Story Points': s.metrics.completed_story_points,
  })) || [];

  // Calculate trend (compare last sprint to previous)
  const calculateTrend = (metric) => {
    if (!sprintData?.sprints || sprintData.sprints.length < 2) return null;
    const sprints = sprintData.sprints;
    const current = sprints[sprints.length - 1].metrics[metric];
    const previous = sprints[sprints.length - 2].metrics[metric];
    if (previous === 0) return null;
    return Math.round(((current - previous) / previous) * 100);
  };

  if (!settings.jira_connected) {
    return (
      <div className="max-w-7xl mx-auto">
        <h2 className="text-2xl font-bold text-gray-800 mb-4">My Performance</h2>
        <Alert type="warning">
          Please connect your Jira account in Settings to view analytics.
        </Alert>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h2 className="text-2xl font-bold text-gray-800">My Performance</h2>
          <p className="text-gray-500 mt-1">
            Track your personal progress across sprints
          </p>
        </div>
        <div className="flex items-center gap-4">
          <Dropdown
            value={selectedProject}
            options={projects.map((p) => ({ value: p.key, label: p.name }))}
            onChange={setSelectedProject}
            placeholder="Select project"
          />
          <Dropdown
            value={String(numSprints)}
            options={[
              { value: '3', label: 'Last 3 sprints' },
              { value: '5', label: 'Last 5 sprints' },
              { value: '10', label: 'Last 10 sprints' },
            ]}
            onChange={(val) => setNumSprints(Number(val))}
          />
          <Button variant="outline" onClick={loadAnalytics} loading={isLoading}>
            <Activity size={16} />
            Refresh
          </Button>
        </div>
      </div>

      {error && (
        <Alert type="error" className="mb-6">
          {error}
        </Alert>
      )}

      {isLoading ? (
        <div className="flex items-center justify-center h-96">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600"></div>
        </div>
      ) : sprintData ? (
        <>
          {/* Summary Stats */}
          <div className="grid grid-cols-5 gap-4 mb-8">
            <StatCard
              icon={Zap}
              label="Avg Velocity"
              value={sprintData.summary.avg_velocity}
              subValue="story points/sprint"
              // trend={calculateTrend('velocity')}
              color="bg-indigo-500"
            />
            <StatCard
              icon={Target}
              label="Avg Completion"
              value={`${sprintData.summary.avg_completion_rate}%`}
              subValue="issues completed"
              // trend={calculateTrend('completion_rate')}
              color="bg-green-500"
            />
            <StatCard
              icon={Timer}
              label="Avg Time to Complete"
              value={`${sprintData.summary.avg_time_to_complete_days || 0}d`}
              subValue="days per issue"
              color="bg-blue-500"
            />
            <StatCard
              icon={Flame}
              label="Current Streak"
              value={`${sprintData.summary.current_streak || 0} days`}
              subValue="consecutive completions"
              color="bg-orange-500"
            />
            <StatCard
              icon={Award}
              label="Total Points"
              value={sprintData.summary.total_points_all_sprints}
              subValue={`across ${sprintData.summary.total_sprints} sprints`}
              color="bg-purple-500"
            />
          </div>

          {/* Current Sprint Banner - FIXED */}
          {currentSprint?.sprint && (
            <Card className="p-6 mb-8 bg-gradient-to-r from-indigo-500 to-purple-600 text-white">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-lg font-semibold opacity-90">Current Sprint</h3>
                  <p className="text-2xl font-bold mt-1">{currentSprint.sprint.name}</p>
                  {currentSprint.sprint.goal && (
                    <p className="text-sm opacity-80 mt-2">Goal: {currentSprint.sprint.goal}</p>
                  )}
                </div>
                <div className="text-right">
                  <div className="text-4xl font-bold">
                    {currentSprint.my_stats?.completion_rate || 0}%
                  </div>
                  <p className="text-sm opacity-80 mt-1">
                    {currentSprint.my_stats?.completed_story_points || 0} / {currentSprint.my_stats?.total_story_points || 0} pts
                  </p>
                  <p className="text-sm opacity-80">
                    {currentSprint.my_stats?.completed_issues || 0} / {currentSprint.my_stats?.total_issues || 0} issues
                  </p>
                </div>
              </div>
              {/* Progress bar */}
              <div className="mt-4 bg-white/20 rounded-full h-3">
                <div
                  className="bg-white rounded-full h-3 transition-all"
                  style={{ width: `${currentSprint.my_stats?.completion_rate || 0}%` }}
                />
              </div>
            </Card>
          )}

          {/* Charts Row 1 - Trends */}
          <div className="grid grid-cols-2 gap-6 mb-8">
            {/* Velocity Trend */}
            <Card className="p-6">
              <h3 className="font-semibold text-gray-700 mb-4 flex items-center gap-2">
                <TrendingUp size={18} className="text-indigo-500" />
                My Velocity Trend
              </h3>
              <ResponsiveContainer width="100%" height={250}>
                <AreaChart data={velocityData}>
                  <defs>
                    <linearGradient id="velocityGradient" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor={COLORS.primary} stopOpacity={0.3} />
                      <stop offset="95%" stopColor={COLORS.primary} stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                  <XAxis dataKey="name" tick={{ fontSize: 12 }} />
                  <YAxis tick={{ fontSize: 12 }} />
                  <Tooltip content={<CustomTooltip />} />
                  <Area
                    type="monotone"
                    dataKey="velocity"
                    stroke={COLORS.primary}
                    fill="url(#velocityGradient)"
                    strokeWidth={2}
                    name="Story Points"
                  />
                </AreaChart>
              </ResponsiveContainer>
            </Card>

            {/* Completion Rate Trend */}
            <Card className="p-6">
              <h3 className="font-semibold text-gray-700 mb-4 flex items-center gap-2">
                <Target size={18} className="text-green-500" />
                Completion Rate Trend
              </h3>
              <ResponsiveContainer width="100%" height={250}>
                <LineChart data={completionRateData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                  <XAxis dataKey="name" tick={{ fontSize: 12 }} />
                  <YAxis tick={{ fontSize: 12 }} domain={[0, 100]} />
                  <Tooltip content={<CustomTooltip />} />
                  <Line
                    type="monotone"
                    dataKey="rate"
                    stroke={COLORS.success}
                    strokeWidth={2}
                    dot={{ fill: COLORS.success, strokeWidth: 2, r: 4 }}
                    name="Completion %"
                  />
                </LineChart>
              </ResponsiveContainer>
            </Card>
          </div>

          {/* Charts Row 2 - Distribution */}
          <div className="grid grid-cols-2 gap-6 mb-8">
            {/* Issues by Status (NEW - replaces Issues by Type) */}
            <Card className="p-6">
              <h3 className="font-semibold text-gray-700 mb-4">Issues by Status</h3>
              <ResponsiveContainer width="100%" height={220}>
                <PieChart>
                  <Pie
                    data={issuesByStatusData}
                    cx="50%"
                    cy="50%"
                    innerRadius={50}
                    outerRadius={80}
                    paddingAngle={2}
                    dataKey="value"
                    label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                    labelLine={false}
                  >
                    {issuesByStatusData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.color} />
                    ))}
                  </Pie>
                  <Tooltip />
                </PieChart>
              </ResponsiveContainer>
            </Card>

            {/* Sprint Comparison */}
            <Card className="p-6">
              <h3 className="font-semibold text-gray-700 mb-4">Sprint Comparison</h3>
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={sprintComparisonData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                  <XAxis dataKey="name" tick={{ fontSize: 10 }} />
                  <YAxis tick={{ fontSize: 12 }} />
                  <Tooltip content={<CustomTooltip />} />
                  <Legend wrapperStyle={{ fontSize: '12px' }} />
                  <Bar dataKey="Completed" fill={COLORS.success} radius={[4, 4, 0, 0]} />
                  <Bar dataKey="Story Points" fill={COLORS.primary} radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </Card>
          </div>

          {/* Recent Issues Table */}
          <Card className="p-6">
            <h3 className="font-semibold text-gray-700 mb-4 flex items-center gap-2">
              <BarChart3 size={18} className="text-gray-500" />
              Recent Sprint Issues
            </h3>
            {currentSprint?.issues?.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className="border-b border-gray-100">
                      <th className="text-left py-3 px-4 text-sm font-medium text-gray-500">Key</th>
                      <th className="text-left py-3 px-4 text-sm font-medium text-gray-500">Summary</th>
                      <th className="text-left py-3 px-4 text-sm font-medium text-gray-500">Type</th>
                      <th className="text-left py-3 px-4 text-sm font-medium text-gray-500">Status</th>
                      <th className="text-left py-3 px-4 text-sm font-medium text-gray-500">Points</th>
                    </tr>
                  </thead>
                  <tbody>
                    {currentSprint.issues.slice(0, 10).map((issue) => (
                      <tr key={issue.key} className="border-b border-gray-50 hover:bg-gray-50">
                        <td className="py-3 px-4">
                          <span className="text-indigo-600 font-medium">{issue.key}</span>
                        </td>
                        <td className="py-3 px-4 text-gray-700 max-w-xs truncate">{issue.summary}</td>
                        <td className="py-3 px-4">
                          <span className="px-2 py-1 bg-gray-100 rounded text-xs text-gray-600">
                            {issue.issue_type}
                          </span>
                        </td>
                        <td className="py-3 px-4">
                          <span
                            className={`px-2 py-1 rounded text-xs ${
                              issue.status.toLowerCase().includes('done')
                                ? 'bg-green-100 text-green-700'
                                : issue.status.toLowerCase().includes('progress')
                                ? 'bg-blue-100 text-blue-700'
                                : 'bg-gray-100 text-gray-600'
                            }`}
                          >
                            {issue.status}
                          </span>
                        </td>
                        <td className="py-3 px-4 text-gray-600">{issue.story_points || '-'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="text-gray-400 text-center py-8">No issues found in the current sprint</p>
            )}
          </Card>
        </>
      ) : (
        <div className="text-center py-16">
          <BarChart3 size={48} className="mx-auto text-gray-300 mb-4" />
          <p className="text-gray-500">Select a project to view your performance analytics</p>
        </div>
      )}
    </div>
  );
}
