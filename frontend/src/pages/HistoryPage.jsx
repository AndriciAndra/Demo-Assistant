import React, { useState, useEffect } from 'react';
import { Play, FileText, Eye, Download, Link, Trash2 } from 'lucide-react';
import { Card, Button, Alert } from '../components/common';
import { demoService, reviewService } from '../services';
import { format } from 'date-fns';

export default function HistoryPage() {
  const [activeFilter, setActiveFilter] = useState('all');
  const [history, setHistory] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    loadHistory();
  }, []);

  const loadHistory = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const [demos, reviews] = await Promise.all([
        demoService.getHistory(20),
        reviewService.getHistory(20),
      ]);

      const combined = [
        ...demos.map((d) => ({ ...d, type: 'demo' })),
        ...reviews.map((r) => ({ ...r, type: 'self_review' })),
      ].sort((a, b) => new Date(b.created_at) - new Date(a.created_at));

      setHistory(combined);
    } catch (err) {
      setError('Failed to load history');
    } finally {
      setIsLoading(false);
    }
  };

  const handleDelete = async (item) => {
    if (!confirm('Are you sure you want to delete this item?')) return;

    try {
      if (item.type === 'demo') {
        await demoService.delete(item.id);
      } else {
        await reviewService.delete(item.id);
      }
      setHistory(history.filter((h) => h.id !== item.id || h.type !== item.type));
    } catch (err) {
      setError('Failed to delete item');
    }
  };

  const filteredHistory = history.filter((item) => {
    if (activeFilter === 'all') return true;
    if (activeFilter === 'demos') return item.type === 'demo';
    if (activeFilter === 'reviews') return item.type === 'self_review';
    return true;
  });

  const filters = [
    { key: 'all', label: 'All' },
    { key: 'demos', label: 'Demos' },
    { key: 'reviews', label: 'Self Reviews' },
  ];

  // Get download URL - handles both old firebase_url and new download_url
  const getDownloadUrl = (item) => {
    return item.download_url || item.firebase_url;
  };

  return (
    <div className="max-w-4xl mx-auto">
      <div className="mb-8">
        <h2 className="text-2xl font-bold text-gray-800">History</h2>
        <p className="text-gray-500 mt-1">View and manage your generated files</p>
      </div>

      {error && (
        <Alert type="error" className="mb-6">
          {error}
        </Alert>
      )}

      <Card className="overflow-hidden">
        {/* Filters */}
        <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between">
          <div className="flex gap-2">
            {filters.map((filter) => (
              <button
                key={filter.key}
                onClick={() => setActiveFilter(filter.key)}
                className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                  activeFilter === filter.key
                    ? 'bg-indigo-50 text-indigo-600'
                    : 'text-gray-500 hover:bg-gray-50'
                }`}
              >
                {filter.label}
              </button>
            ))}
          </div>
          <Button variant="outline" size="sm" onClick={loadHistory}>
            Refresh
          </Button>
        </div>

        {/* List */}
        {isLoading ? (
          <div className="p-12 text-center">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600 mx-auto"></div>
            <p className="text-gray-400 mt-4">Loading history...</p>
          </div>
        ) : filteredHistory.length === 0 ? (
          <div className="p-12 text-center">
            <p className="text-gray-400">No items found</p>
          </div>
        ) : (
          <div className="divide-y divide-gray-100">
            {filteredHistory.map((item) => (
              <div
                key={`${item.type}-${item.id}`}
                className="px-6 py-4 flex items-center justify-between hover:bg-gray-50 transition-colors"
              >
                <div className="flex items-center gap-4">
                  <div
                    className={`p-2 rounded-lg ${
                      item.type === 'demo' ? 'bg-purple-100' : 'bg-green-100'
                    }`}
                  >
                    {item.type === 'demo' ? (
                      <Play size={18} className="text-purple-600" />
                    ) : (
                      <FileText size={18} className="text-green-600" />
                    )}
                  </div>
                  <div>
                    <p className="font-medium text-gray-700">{item.filename}</p>
                    <p className="text-sm text-gray-400">
                      {item.jira_project_key} •{' '}
                      {format(new Date(item.created_at), 'MMM d, yyyy')}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  {item.google_slides_id && (
                    <a
                      href={`https://docs.google.com/presentation/d/${item.google_slides_id}/edit`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
                      title="Open in Slides"
                    >
                      <Eye size={18} className="text-gray-400" />
                    </a>
                  )}
                  {getDownloadUrl(item) && (
                    <a
                      href={getDownloadUrl(item)}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
                      title="Download"
                    >
                      <Download size={18} className="text-gray-400" />
                    </a>
                  )}
                  {item.drive_url && (
                    <a
                      href={item.drive_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
                      title="Open in Drive"
                    >
                      <Link size={18} className="text-gray-400" />
                    </a>
                  )}
                  <button
                    onClick={() => handleDelete(item)}
                    className="p-2 hover:bg-red-50 rounded-lg transition-colors"
                    title="Delete"
                  >
                    <Trash2 size={18} className="text-red-400" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}
