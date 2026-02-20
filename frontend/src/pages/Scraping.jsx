import { useState, useEffect } from 'react';
import { Play, User, Lock, Database, AlertCircle, CheckCircle, Clock, Target, Globe, FileText, Loader, Square, Bug, ChevronDown, ChevronUp, Copy, Check } from 'lucide-react';
import Layout from '../components/Layout';

const ScrapingDashboard = () => {
  const [activeTab, setActiveTab] = useState('sinta-dosen');
  const [credentials, setCredentials] = useState({
    username: '',
    password: ''
  });
  const [gsConfig, setGsConfig] = useState({
    maxAuthors: 20,
    scrapeFromBeginning: false
  });
  const [gsDosenConfig, setGsDosenConfig] = useState({
    maxPages: 100,
    searchQuery: '"Universitas Katolik Parahyangan" OR "Parahyangan Catholic University" OR "unpar"'
  });
  const [isLoading, setIsLoading] = useState(false);
  const [scrapingProgress, setScrapingProgress] = useState(null);
  const [scrapingResults, setScrapingResults] = useState(null);
  const [currentJobId, setCurrentJobId] = useState(null);
  const [isCancelling, setIsCancelling] = useState(false);

  // Debug panel state
  const [showDebug, setShowDebug] = useState(false);
  const [debugLogs, setDebugLogs] = useState([]);
  const [copiedDebug, setCopiedDebug] = useState(false);

  const addDebugLog = (type, message, data = null) => {
    const timestamp = new Date().toISOString().split('T')[1].slice(0, 12);
    setDebugLogs(prev => [
      ...prev,
      { timestamp, type, message, data: data ? JSON.stringify(data, null, 2) : null }
    ]);
    if (type === 'error') console.error(`[${timestamp}] ${message}`, data);
    else console.log(`[${timestamp}] ${message}`, data);
  };

  const copyDebugToClipboard = () => {
    const text = debugLogs
      .map(log => `[${log.timestamp}] [${log.type.toUpperCase()}] ${log.message}${log.data ? '\n' + log.data : ''}`)
      .join('\n');
    navigator.clipboard.writeText(text).then(() => {
      setCopiedDebug(true);
      setTimeout(() => setCopiedDebug(false), 2000);
    });
  };

  const clearDebugLogs = () => setDebugLogs([]);

  useEffect(() => {
    let pollInterval = null;

    if (currentJobId && isLoading) {
      addDebugLog('info', `Starting job monitoring`, { job_id: currentJobId });

      pollInterval = setInterval(async () => {
        try {
          addDebugLog('info', `Polling job status`, { job_id: currentJobId });

          const response = await fetch(`/api/scraping/jobs/${currentJobId}`);

          if (!response.ok) {
            addDebugLog('error', `Job status request failed`, { status: response.status, statusText: response.statusText });
            return;
          }

          const data = await response.json();
          addDebugLog('info', `Job status received`, data);

          if (data.success && data.job) {
            const job = data.job;

            setScrapingProgress({
              status: job.status,
              message: job.message || 'Processing...',
              currentCount: job.current || 0,
              targetCount: job.total || 0
            });

            if (job.status === 'completed') {
              addDebugLog('info', `Job completed`, { result: job.result });

              const result = job.result || {};

              // Cek apakah result kosong
              if (!result || Object.keys(result).length === 0) {
                addDebugLog('error', `Result is empty`, { job });
                setScrapingResults({
                  success: false,
                  error: job.message || 'Scraper selesai tapi tidak ada data yang dikembalikan.',
                  debugInfo: { job, result }
                });
              } else if (result.success === false) {
                addDebugLog('error', `Job completed with failure`, { result });
                setScrapingResults({
                  success: false,
                  error: result.error || result.message || job.message || job.error || 'Scraping gagal (tidak ada detail error)',
                  traceback: result.traceback || null,
                  debugInfo: { job, result }
                });
              } else {
                addDebugLog('info', `Job completed successfully`, { result });
                setScrapingResults({
                  success: true,
                  message: result.message || job.message || 'Scraping selesai!',
                  summary: result
                });
              }

              setIsLoading(false);
              setCurrentJobId(null);
              clearInterval(pollInterval);

            } else if (job.status === 'failed') {
              addDebugLog('error', `Job failed`, { error: job.error, message: job.message });
              setScrapingResults({
                success: false,
                error: job.error || job.message || 'Scraping gagal',
                traceback: job.traceback || null,
                debugInfo: { job }
              });
              setIsLoading(false);
              setCurrentJobId(null);
              clearInterval(pollInterval);

            } else if (job.status === 'cancelled') {
              addDebugLog('info', `Job cancelled`);
              setScrapingResults({
                success: false,
                error: job.message || 'Scraping dibatalkan oleh user'
              });
              setIsLoading(false);
              setIsCancelling(false);
              setCurrentJobId(null);
              clearInterval(pollInterval);
            }
          }
        } catch (error) {
          addDebugLog('error', `Polling error`, { message: error.message, stack: error.stack });
        }
      }, 2000);
    }

    return () => {
      if (pollInterval) {
        addDebugLog('info', 'Stopping job monitoring');
        clearInterval(pollInterval);
      }
    };
  }, [currentJobId, isLoading]);

  const handleCredentialChange = (e) => {
    setCredentials(prev => ({ ...prev, [e.target.name]: e.target.value }));
  };

  const handleGsDosenConfigChange = (e) => {
    const { name, value } = e.target;
    setGsDosenConfig(prev => ({
      ...prev,
      [name]: name === 'maxPages' ? parseInt(value) || 1 : value
    }));
  };

  const handleGsConfigChange = (e) => {
    const { name, type, checked, value } = e.target;
    setGsConfig(prev => ({
      ...prev,
      [name]: type === 'checkbox' ? checked : parseInt(value)
    }));
  };

  const startScraping = async (endpoint, payload) => {
    setIsLoading(true);
    setScrapingResults(null);
    setDebugLogs([]);
    setScrapingProgress({
      status: 'starting',
      message: 'Memulai scraping...',
      currentCount: 0,
      targetCount: payload.target_dosen || payload.max_authors || 0
    });

    addDebugLog('info', `Starting scraping`, { endpoint, payload });

    try {
      const response = await fetch(`/api/scraping/${endpoint}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json',
        },
        credentials: 'include',
        body: JSON.stringify(payload)
      });

      addDebugLog('info', `Response received`, { status: response.status, ok: response.ok });

      const data = await response.json();
      addDebugLog('info', `Response data`, data);

      if (data.success) {
        if (data.job_id) {
          setCurrentJobId(data.job_id);
          addDebugLog('info', `Job started`, { job_id: data.job_id });
          setScrapingProgress(prev => ({
            ...prev,
            job_id: data.job_id,
            message: data.message || 'Job started, waiting for updates...'
          }));
        } else {
          setScrapingResults({
            success: true,
            message: data.message,
            summary: data.summary
          });
          setIsLoading(false);
        }
      } else {
        addDebugLog('error', `Start scraping failed`, data);
        setScrapingResults({
          success: false,
          error: data.error || data.message || 'Gagal memulai scraping',
          debugInfo: data
        });
        setIsLoading(false);
      }
    } catch (error) {
      addDebugLog('error', `Network error`, { message: error.message, stack: error.stack });
      setScrapingResults({
        success: false,
        error: 'Network error: ' + error.message,
        debugInfo: { type: 'network_error', message: error.message }
      });
      setIsLoading(false);
    }
  };

  const handleSintaDosen = async () => {
    if (!credentials.username || !credentials.password) {
      alert('Username dan password SINTA harus diisi');
      return;
    }
    await startScraping('sinta/dosen', { username: credentials.username, password: credentials.password });
  };

  const handleSintaScopus = async () => {
    if (!credentials.username || !credentials.password) {
      alert('Username dan password SINTA harus diisi');
      return;
    }
    await startScraping('sinta/scopus', { username: credentials.username, password: credentials.password });
  };

  const handleSintaGoogleScholar = async () => {
    if (!credentials.username || !credentials.password) {
      alert('Username dan password SINTA harus diisi');
      return;
    }
    await startScraping('sinta/googlescholar', { username: credentials.username, password: credentials.password });
  };

  const handleSintaGaruda = async () => {
    if (!credentials.username || !credentials.password) {
      alert('Username dan password SINTA harus diisi');
      return;
    }
    await startScraping('sinta/garuda', { username: credentials.username, password: credentials.password });
  };

  const handleGoogleScholar = async () => {
    if (gsConfig.scrapeFromBeginning) {
      const confirmed = window.confirm(
        '⚠️ PERHATIAN: Anda akan melakukan scraping dari awal!\n\n' +
        'Ini akan mengulang semua dosen yang sudah selesai di-scrape sebelumnya.\n\n' +
        'Apakah Anda yakin ingin melanjutkan?'
      );
      if (!confirmed) return;
    }

    setIsLoading(true);
    setScrapingResults(null);
    setDebugLogs([]);
    setScrapingProgress({
      status: 'starting',
      message: 'Memulai scraping Google Scholar...',
      currentCount: 0,
      targetCount: gsConfig.maxAuthors
    });

    addDebugLog('info', 'Starting GS Publikasi scraping', gsConfig);

    try {
      const response = await fetch('/api/scraping/googlescholar/scrape', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          max_authors: gsConfig.maxAuthors,
          scrape_from_beginning: gsConfig.scrapeFromBeginning
        })
      });

      const data = await response.json();
      addDebugLog('info', 'GS Publikasi response', data);

      if (data.success) {
        setCurrentJobId(data.job_id);
        if (data.instructions) alert(data.instructions);
      } else {
        addDebugLog('error', 'GS Publikasi start failed', data);
        setScrapingResults({ success: false, error: data.error, debugInfo: data });
        setIsLoading(false);
      }
    } catch (error) {
      addDebugLog('error', 'GS Publikasi network error', { message: error.message });
      setScrapingResults({ success: false, error: 'Network error: ' + error.message });
      setIsLoading(false);
    }
  };

  const handleGoogleScholarDosen = async () => {
    setIsLoading(true);
    setScrapingResults(null);
    setDebugLogs([]);
    setScrapingProgress({
      status: 'starting',
      message: 'Memulai scraping dosen Google Scholar...',
      currentCount: 0,
      targetCount: gsDosenConfig.maxPages * 10
    });

    addDebugLog('info', 'Starting GS Dosen scraping', gsDosenConfig);

    try {
      const response = await fetch('/api/scraping/googlescholar/dosen', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          max_pages: gsDosenConfig.maxPages,
          search_query: gsDosenConfig.searchQuery
        })
      });

      const data = await response.json();
      addDebugLog('info', 'GS Dosen response', data);

      if (data.success) {
        setCurrentJobId(data.job_id);
        if (data.instructions) alert(data.instructions);
      } else {
        addDebugLog('error', 'GS Dosen start failed', data);
        setScrapingResults({ success: false, error: data.error, debugInfo: data });
        setIsLoading(false);
      }
    } catch (error) {
      addDebugLog('error', 'GS Dosen network error', { message: error.message });
      setScrapingResults({ success: false, error: 'Network error: ' + error.message });
      setIsLoading(false);
    }
  };

  const cancelCurrentJob = async () => {
    if (!currentJobId) return;
    try {
      setIsCancelling(true);
      addDebugLog('info', 'Cancelling job', { job_id: currentJobId });
      const response = await fetch(`/api/scraping/jobs/${currentJobId}/cancel`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });
      const data = await response.json();
      addDebugLog('info', 'Cancel response', data);
      if (!data.success) {
        setIsCancelling(false);
        alert(data.error || 'Gagal mengirim perintah cancel');
      }
    } catch (e) {
      setIsCancelling(false);
      addDebugLog('error', 'Cancel network error', { message: e.message });
      alert('Network error saat membatalkan: ' + e.message);
    }
  };

  const TabButton = ({ id, label, icon: Icon, isActive, onClick }) => (
    <button
      onClick={onClick}
      className={`flex items-center px-4 py-2 text-sm font-medium rounded-lg transition-colors duration-200 ${
        isActive
          ? 'bg-blue-600 text-white shadow-md'
          : 'text-gray-600 hover:text-blue-600 hover:bg-blue-50'
      }`}
    >
      <Icon className="w-4 h-4 mr-2" />
      {label}
    </button>
  );

  const getProgressPercentage = () => {
    if (!scrapingProgress || !scrapingProgress.targetCount) return 0;
    return Math.min(Math.round((scrapingProgress.currentCount / scrapingProgress.targetCount) * 100), 100);
  };

  const getStatusColor = () => {
    if (!scrapingProgress) return 'bg-gray-500';
    switch (scrapingProgress.status) {
      case 'starting': case 'running': case 'waiting_login': case 'ready': return 'bg-blue-500';
      case 'completed': return 'bg-green-500';
      case 'failed': return 'bg-red-500';
      default: return 'bg-gray-500';
    }
  };

  const getDebugLogColor = (type) => {
    switch (type) {
      case 'error': return 'text-red-400';
      case 'warn': return 'text-yellow-400';
      case 'info': return 'text-blue-400';
      default: return 'text-gray-400';
    }
  };

  const CancelButton = () => (
    isLoading && currentJobId ? (
      <button
        onClick={cancelCurrentJob}
        disabled={isCancelling}
        className={`inline-flex items-center px-4 py-3 rounded-md text-white text-sm font-medium transition-colors ${
          isCancelling
            ? 'bg-gray-400 cursor-wait'
            : 'bg-red-600 hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500'
        }`}
      >
        {isCancelling ? (
          <><Loader className="w-4 h-4 mr-2 animate-spin" />Menghentikan...</>
        ) : (
          <><Square className="w-4 h-4 mr-2" />Stop</>
        )}
      </button>
    ) : null
  );

  return (
    <Layout
      title={
        <div className="flex items-center">
          <Database className="w-8 h-8 text-blue-600 mr-3" />
          <span>Data Scraping Dashboard</span>
        </div>
      }
      description="Scraping data akademik dari berbagai sumber (SINTA, Scopus, Google Scholar, Garuda)"
      maxWidth="max-w-6xl"
    >
      {/* Tabs */}
      <div className="mb-6">
        <div className="flex flex-wrap gap-2">
          <TabButton id="sinta-dosen" label="SINTA Dosen" icon={User} isActive={activeTab === 'sinta-dosen'} onClick={() => setActiveTab('sinta-dosen')} />
          <TabButton id="sinta-scopus" label="SINTA Scopus" icon={FileText} isActive={activeTab === 'sinta-scopus'} onClick={() => setActiveTab('sinta-scopus')} />
          <TabButton id="sinta-gs" label="SINTA Google Scholar" icon={Globe} isActive={activeTab === 'sinta-gs'} onClick={() => setActiveTab('sinta-gs')} />
          <TabButton id="sinta-garuda" label="SINTA Garuda" icon={Database} isActive={activeTab === 'sinta-garuda'} onClick={() => setActiveTab('sinta-garuda')} />
          <TabButton id="gs-dosen" label="GS Dosen" icon={User} isActive={activeTab === 'gs-dosen'} onClick={() => setActiveTab('gs-dosen')} />
          <TabButton id="google-scholar" label="GS Publikasi" icon={Globe} isActive={activeTab === 'google-scholar'} onClick={() => setActiveTab('google-scholar')} />
        </div>
      </div>

      {/* Progress Bar */}
      {isLoading && scrapingProgress && (
        <div className="mb-6">
          <div className="bg-white rounded-lg shadow-sm p-4">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center">
                <Clock className="w-5 h-5 text-blue-500 mr-2" />
                <span className="font-medium text-gray-700">
                  {scrapingProgress.message || 'Sedang memproses...'}
                </span>
              </div>
              <span className="text-sm text-gray-500">
                {scrapingProgress.currentCount || 0} / {scrapingProgress.targetCount || '?'}
              </span>
            </div>
            <div className="w-full bg-gray-200 rounded-full h-2.5">
              <div
                className={`h-2.5 rounded-full transition-all duration-500 ${getStatusColor()}`}
                style={{ width: `${getProgressPercentage()}%` }}
              />
            </div>
            {scrapingProgress.job_id && (
              <p className="mt-1 text-xs text-gray-400">Job ID: {scrapingProgress.job_id}</p>
            )}
          </div>
        </div>
      )}

      {/* ─── Results Panel ─── */}
      {scrapingResults && (
        <div className={`mb-6 rounded-lg border ${
          scrapingResults.success
            ? 'bg-green-50 border-green-300'
            : 'bg-red-50 border-red-300'
        }`}>
          {/* Header */}
          <div className={`flex items-start p-4 ${scrapingResults.success ? '' : 'border-b border-red-200'}`}>
            {scrapingResults.success ? (
              <CheckCircle className="w-5 h-5 text-green-500 mt-0.5 mr-3 flex-shrink-0" />
            ) : (
              <AlertCircle className="w-5 h-5 text-red-500 mt-0.5 mr-3 flex-shrink-0" />
            )}
            <div className="flex-1 min-w-0">
              <h3 className={`text-lg font-semibold ${scrapingResults.success ? 'text-green-800' : 'text-red-800'}`}>
                {scrapingResults.success ? 'Scraping Berhasil' : 'Scraping Gagal'}
              </h3>
              <p className={`text-sm mt-0.5 ${scrapingResults.success ? 'text-green-700' : 'text-red-700'}`}>
                {scrapingResults.success ? scrapingResults.message : (scrapingResults.error || 'Terjadi error tidak diketahui')}
              </p>

              {/* Summary (success) */}
              {scrapingResults.success && scrapingResults.summary && (
                <pre className="mt-3 text-xs bg-white rounded-md p-3 overflow-auto border border-green-200 max-h-40">
                  {JSON.stringify(scrapingResults.summary, null, 2)}
                </pre>
              )}

              {/* Traceback (error) */}
              {!scrapingResults.success && scrapingResults.traceback && (
                <details className="mt-3">
                  <summary className="text-xs text-red-600 cursor-pointer hover:text-red-800 font-medium select-none">
                    ▶ Lihat traceback Python
                  </summary>
                  <pre className="mt-2 text-xs bg-white rounded-md p-3 overflow-auto max-h-48 border border-red-200 whitespace-pre-wrap">
                    {scrapingResults.traceback}
                  </pre>
                </details>
              )}
            </div>
          </div>

          {/* ─── Debug Info Panel (hanya saat error) ─── */}
          {!scrapingResults.success && (
            <div className="p-4">
              <button
                onClick={() => setShowDebug(prev => !prev)}
                className="flex items-center gap-2 text-sm text-red-600 hover:text-red-800 font-medium transition-colors"
              >
                <Bug className="w-4 h-4" />
                {showDebug ? 'Sembunyikan' : 'Tampilkan'} Debug Info
                {showDebug ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
              </button>

              {showDebug && (
                <div className="mt-3 space-y-3">
                  {/* Raw debugInfo dari result */}
                  {scrapingResults.debugInfo && (
                    <div>
                      <p className="text-xs font-semibold text-gray-600 mb-1">Raw Response dari Backend:</p>
                      <pre className="text-xs bg-gray-900 text-green-300 rounded-md p-3 overflow-auto max-h-48 border border-gray-700">
                        {JSON.stringify(scrapingResults.debugInfo, null, 2)}
                      </pre>
                    </div>
                  )}

                  {/* Activity log */}
                  {debugLogs.length > 0 && (
                    <div>
                      <div className="flex items-center justify-between mb-1">
                        <p className="text-xs font-semibold text-gray-600">Activity Log ({debugLogs.length} entries):</p>
                        <div className="flex gap-2">
                          <button
                            onClick={copyDebugToClipboard}
                            className="flex items-center gap-1 text-xs text-gray-500 hover:text-gray-700 bg-gray-100 hover:bg-gray-200 px-2 py-1 rounded transition-colors"
                          >
                            {copiedDebug ? <Check className="w-3 h-3 text-green-500" /> : <Copy className="w-3 h-3" />}
                            {copiedDebug ? 'Copied!' : 'Copy'}
                          </button>
                          <button
                            onClick={clearDebugLogs}
                            className="text-xs text-gray-500 hover:text-red-600 bg-gray-100 hover:bg-red-50 px-2 py-1 rounded transition-colors"
                          >
                            Clear
                          </button>
                        </div>
                      </div>
                      <div className="bg-gray-900 rounded-md p-3 overflow-auto max-h-64 font-mono text-xs border border-gray-700">
                        {debugLogs.map((log, i) => (
                          <div key={i} className="mb-1">
                            <span className="text-gray-500">[{log.timestamp}]</span>{' '}
                            <span className={`font-semibold ${getDebugLogColor(log.type)}`}>
                              [{log.type.toUpperCase()}]
                            </span>{' '}
                            <span className="text-gray-200">{log.message}</span>
                            {log.data && (
                              <pre className="mt-0.5 ml-4 text-gray-400 whitespace-pre-wrap">{log.data}</pre>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Quick action: Copy error to clipboard */}
                  <button
                    onClick={() => {
                      const info = {
                        error: scrapingResults.error,
                        traceback: scrapingResults.traceback,
                        debugInfo: scrapingResults.debugInfo,
                        logs: debugLogs
                      };
                      navigator.clipboard.writeText(JSON.stringify(info, null, 2));
                      alert('Debug info berhasil disalin ke clipboard!');
                    }}
                    className="flex items-center gap-2 text-xs text-gray-600 hover:text-gray-800 bg-gray-100 hover:bg-gray-200 px-3 py-2 rounded-md transition-colors"
                  >
                    <Copy className="w-3.5 h-3.5" />
                    Salin semua debug info ke clipboard
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Debug log toggle saat loading (live monitoring) */}
      {isLoading && debugLogs.length > 0 && (
        <div className="mb-6">
          <button
            onClick={() => setShowDebug(prev => !prev)}
            className="flex items-center gap-2 text-sm text-gray-500 hover:text-gray-700 mb-2"
          >
            <Bug className="w-4 h-4" />
            Live Log ({debugLogs.length})
            {showDebug ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
          </button>
          {showDebug && (
            <div className="bg-gray-900 rounded-md p-3 overflow-auto max-h-40 font-mono text-xs border border-gray-700">
              {debugLogs.slice(-20).map((log, i) => (
                <div key={i} className="mb-0.5">
                  <span className="text-gray-500">[{log.timestamp}]</span>{' '}
                  <span className={`font-semibold ${getDebugLogColor(log.type)}`}>[{log.type.toUpperCase()}]</span>{' '}
                  <span className="text-gray-200">{log.message}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* SINTA Credentials */}
      {activeTab !== 'google-scholar' && activeTab !== 'gs-dosen' && (
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6 mb-6 hover:shadow-md transition-shadow duration-300">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">Kredensial SINTA</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Username/Email SINTA</label>
              <div className="relative">
                <User className="absolute left-3 top-1/2 transform -translate-y-1/2 h-5 w-5 text-gray-400" />
                <input
                  type="text" name="username" value={credentials.username}
                  onChange={handleCredentialChange} disabled={isLoading}
                  className="w-full pl-10 pr-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-100"
                  placeholder="Masukkan username atau email SINTA"
                />
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Password SINTA</label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 transform -translate-y-1/2 h-5 w-5 text-gray-400" />
                <input
                  type="password" name="password" value={credentials.password}
                  onChange={handleCredentialChange} disabled={isLoading}
                  className="w-full pl-10 pr-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-100"
                  placeholder="Masukkan password SINTA"
                />
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Tab Content */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6 hover:shadow-md transition-shadow duration-300">

        {/* SINTA Dosen */}
        {activeTab === 'sinta-dosen' && (
          <div>
            <h3 className="text-lg font-semibold text-gray-900 mb-4">Scraping SINTA Dosen</h3>
            <div className="bg-yellow-50 border-l-4 border-yellow-400 p-4 mb-6">
              <div className="flex">
                <AlertCircle className="h-5 w-5 text-yellow-400" />
                <p className="ml-3 text-sm text-yellow-700">
                  Proses ini dapat memakan waktu lama (hingga beberapa jam) tergantung target dosen.
                </p>
              </div>
            </div>
            <div className="bg-blue-50 border border-blue-100 rounded-lg p-4 mb-6">
              <h4 className="text-sm font-semibold text-blue-800 mb-2 flex items-center">
                <Database className="w-4 h-4 mr-2" />Konfigurasi Otomatis
              </h4>
              <ul className="text-sm text-blue-700 space-y-1 list-disc list-inside">
                <li>ID afiliasi otomatis menggunakan <strong>1397</strong>.</li>
                <li>Target dosen dan jumlah halaman per siklus dibaca langsung dari metadata halaman SINTA.</li>
                <li>Maksimal siklus scraping: <strong>20</strong> (default).</li>
              </ul>
            </div>
            <div className="flex items-center space-x-3">
              <button onClick={handleSintaDosen} disabled={isLoading || !credentials.username || !credentials.password}
                className="flex-1 flex items-center justify-center px-4 py-3 text-sm font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors">
                {isLoading ? <><Loader className="animate-spin -ml-1 mr-3 h-5 w-5" />Sedang Scraping...</> : <><Play className="-ml-1 mr-3 h-5 w-5" />Mulai Scraping SINTA Dosen</>}
              </button>
              <CancelButton />
            </div>
          </div>
        )}

        {/* SINTA Scopus */}
        {activeTab === 'sinta-scopus' && (
          <div>
            <h3 className="text-lg font-semibold text-gray-900 mb-4">Scraping SINTA Scopus</h3>
            <div className="bg-blue-50 border-l-4 border-blue-400 p-4 mb-6">
              <div className="flex">
                <AlertCircle className="h-5 w-5 text-blue-400" />
                <p className="ml-3 text-sm text-blue-700">Scraping publikasi Scopus dari semua dosen yang ada di database.</p>
              </div>
            </div>
            <div className="flex items-center space-x-3">
              <button onClick={handleSintaScopus} disabled={isLoading || !credentials.username || !credentials.password}
                className="flex-1 flex items-center justify-center px-4 py-3 text-sm font-medium rounded-md text-white bg-orange-600 hover:bg-orange-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors">
                {isLoading ? <><Loader className="animate-spin -ml-1 mr-3 h-5 w-5" />Sedang Scraping...</> : <><Play className="-ml-1 mr-3 h-5 w-5" />Mulai Scraping Scopus</>}
              </button>
              <CancelButton />
            </div>
          </div>
        )}

        {/* SINTA Google Scholar */}
        {activeTab === 'sinta-gs' && (
          <div>
            <h3 className="text-lg font-semibold text-gray-900 mb-4">Scraping SINTA Google Scholar</h3>
            <div className="bg-green-50 border-l-4 border-green-400 p-4 mb-6">
              <div className="flex">
                <AlertCircle className="h-5 w-5 text-green-400" />
                <p className="ml-3 text-sm text-green-700">Scraping publikasi Google Scholar dari semua dosen yang ada di database.</p>
              </div>
            </div>
            <div className="flex items-center space-x-3">
              <button onClick={handleSintaGoogleScholar} disabled={isLoading || !credentials.username || !credentials.password}
                className="flex-1 flex items-center justify-center px-4 py-3 text-sm font-medium rounded-md text-white bg-green-600 hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors">
                {isLoading ? <><Loader className="animate-spin -ml-1 mr-3 h-5 w-5" />Sedang Scraping...</> : <><Play className="-ml-1 mr-3 h-5 w-5" />Mulai Scraping Google Scholar</>}
              </button>
              <CancelButton />
            </div>
          </div>
        )}

        {/* SINTA Garuda */}
        {activeTab === 'sinta-garuda' && (
          <div>
            <h3 className="text-lg font-semibold text-gray-900 mb-4">Scraping SINTA Garuda</h3>
            <div className="bg-purple-50 border-l-4 border-purple-400 p-4 mb-6">
              <div className="flex">
                <AlertCircle className="h-5 w-5 text-purple-400" />
                <p className="ml-3 text-sm text-purple-700">Scraping publikasi Garuda dari semua dosen yang ada di database.</p>
              </div>
            </div>
            <div className="flex items-center space-x-3">
              <button onClick={handleSintaGaruda} disabled={isLoading || !credentials.username || !credentials.password}
                className="flex-1 flex items-center justify-center px-4 py-3 text-sm font-medium rounded-md text-white bg-purple-600 hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors">
                {isLoading ? <><Loader className="animate-spin -ml-1 mr-3 h-5 w-5" />Sedang Scraping...</> : <><Play className="-ml-1 mr-3 h-5 w-5" />Mulai Scraping Garuda</>}
              </button>
              <CancelButton />
            </div>
          </div>
        )}

        {/* GS Dosen */}
        {activeTab === 'gs-dosen' && (
          <div>
            <h3 className="text-lg font-semibold text-gray-900 mb-4">Scraping Google Scholar Dosen</h3>
            <div className="bg-blue-50 border-l-4 border-blue-400 p-4 mb-6">
              <div className="flex">
                <AlertCircle className="h-5 w-5 text-blue-400" />
                <p className="ml-3 text-sm text-blue-700">
                  Scraping profil dosen langsung dari Google Scholar. Browser akan terbuka untuk scraping.
                </p>
              </div>
            </div>
            <div className="grid grid-cols-1 gap-4 mb-6">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  <Target className="w-4 h-4 inline mr-1" />Max Pages
                </label>
                <input type="number" name="maxPages" value={gsDosenConfig.maxPages}
                  onChange={handleGsDosenConfigChange} min="1" max="1000" disabled={isLoading}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-100"
                />
                <p className="mt-1 text-xs text-gray-500">Maksimal halaman yang akan di-scrape (~10 profil per halaman)</p>
              </div>
            </div>
            <div className="flex items-center space-x-3">
              <button onClick={handleGoogleScholarDosen} disabled={isLoading}
                className="flex-1 flex items-center justify-center px-4 py-3 text-sm font-medium rounded-md text-white bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors">
                {isLoading ? <><Loader className="animate-spin -ml-1 mr-3 h-5 w-5" />Sedang Scraping...</> : <><Play className="-ml-1 mr-3 h-5 w-5" />Mulai Scraping Dosen</>}
              </button>
              <CancelButton />
            </div>
          </div>
        )}

        {/* GS Publikasi */}
        {activeTab === 'google-scholar' && (
          <div>
            <h3 className="text-lg font-semibold text-gray-900 mb-4">Scraping Google Scholar Publikasi</h3>
            <div className="bg-yellow-50 border-l-4 border-yellow-400 p-4 mb-4">
              <div className="flex">
                <AlertCircle className="h-5 w-5 text-yellow-400" />
                <div className="ml-3">
                  <p className="text-sm text-yellow-800 font-medium mb-1">⚠️ Informasi Penting: Scraping Parsial</p>
                  <p className="text-sm text-yellow-700">
                    Scraping dilakukan secara parsial dengan membatasi jumlah author. Default maksimal: <strong>20</strong>.
                  </p>
                </div>
              </div>
            </div>
            <div className="bg-blue-50 border-l-4 border-blue-400 p-4 mb-6">
              <div className="flex">
                <AlertCircle className="h-5 w-5 text-blue-400" />
                <p className="ml-3 text-sm text-blue-700">Scraping langsung dari Google Scholar (tidak melalui SINTA).</p>
              </div>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  <Target className="w-4 h-4 inline mr-1" />Max Authors
                </label>
                <input type="number" name="maxAuthors" value={gsConfig.maxAuthors}
                  onChange={handleGsConfigChange} disabled={isLoading}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-100"
                />
              </div>
              <div className="flex items-center">
                <input type="checkbox" name="scrapeFromBeginning" checked={gsConfig.scrapeFromBeginning}
                  onChange={handleGsConfigChange} disabled={isLoading}
                  className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
                />
                <label className="ml-2 block text-sm text-gray-900">Scrape dari awal (ulang semua)</label>
              </div>
            </div>
            <div className="flex items-center space-x-3">
              <button onClick={handleGoogleScholar} disabled={isLoading}
                className="flex-1 flex items-center justify-center px-4 py-3 text-sm font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors">
                {isLoading ? <><Loader className="animate-spin -ml-1 mr-3 h-5 w-5" />Sedang Scraping...</> : <><Play className="-ml-1 mr-3 h-5 w-5" />Mulai Scraping Google Scholar</>}
              </button>
              <CancelButton />
            </div>
          </div>
        )}
      </div>
    </Layout>
  );
};

export default ScrapingDashboard;