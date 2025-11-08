import { useState, useEffect } from 'react';
import { Play, User, Lock, Database, AlertCircle, CheckCircle, Clock, Target, RefreshCw, Download, Globe, FileText, Loader, Square } from 'lucide-react';

const ScrapingDashboard = () => {
  const [activeTab, setActiveTab] = useState('sinta-dosen');
  const [credentials, setCredentials] = useState({
    username: '',
    password: ''
  });
  const [dosenConfig, setDosenConfig] = useState({
    affiliationId: '1397',
    targetDosen: 473,  // Ubah nilai default ke number
    maxPages: 50,     // Ubah nilai default ke number
    maxCycles: 20     // Ubah nilai default ke number
  });
  const [gsConfig, setGsConfig] = useState({
    maxAuthors: 473,
    scrapeFromBeginning: false
  });
  const [isLoading, setIsLoading] = useState(false);
  const [scrapingProgress, setScrapingProgress] = useState(null);
  const [scrapingResults, setScrapingResults] = useState(null);
  const [currentJobId, setCurrentJobId] = useState(null);
  const [isCancelling, setIsCancelling] = useState(false);

  // WebSocket/Polling for progress updates
  // REPLACE useEffect untuk WebSocket/Polling di Scraping.jsx
// Mulai dari line ~25 hingga ~115

useEffect(() => {
  let pollInterval = null;
  
  if (currentJobId && isLoading) {
    console.log(`🔄 Starting job monitoring for: ${currentJobId}`);
    
    // Langsung gunakan polling saja, skip WebSocket karena sering gagal
    pollInterval = setInterval(async () => {
      try {
        console.log(`📡 Polling job status: ${currentJobId}`);
        
        const response = await fetch(`/api/scraping/jobs/${currentJobId}`);
        
        if (!response.ok) {
          console.error(`❌ Job status request failed: ${response.status}`);
          return;
        }
        
        const data = await response.json();
        console.log(`✅ Job status received:`, data);
        
        if (data.success && data.job) {
          const job = data.job;
          
          setScrapingProgress({
            status: job.status,
            message: job.message || 'Processing...',
            currentCount: job.current || 0,
            targetCount: job.total || 0
          });
          
          // Check for completion
          if (job.status === 'completed') {
            console.log('✅ Job completed!', job.result);
            // Check if result indicates success or failure
            const result = job.result || {};
            if (result.success === false) {
              // Job completed but with error
              console.error('❌ Job completed with error:', result.error);
              setScrapingResults({
                success: false,
                error: result.error || result.message || job.message || 'Scraping failed',
                traceback: result.traceback
              });
            } else {
              // Job completed successfully
              setScrapingResults({
                success: true,
                message: result.message || job.message || 'Scraping completed successfully!',
                summary: result
              });
            }
            setIsLoading(false);
            setCurrentJobId(null);
            clearInterval(pollInterval);
          } else if (job.status === 'failed') {
            console.error('❌ Job failed:', job.error);
            setScrapingResults({
              success: false,
              error: job.error || job.message || 'Scraping failed',
              traceback: job.traceback
            });
            setIsLoading(false);
            setCurrentJobId(null);
            clearInterval(pollInterval);
          } else if (job.status === 'cancelled') {
            setScrapingResults({
              success: false,
              error: job.message || 'Scraping cancelled by user'
            });
            setIsLoading(false);
            setIsCancelling(false);
            setCurrentJobId(null);
            clearInterval(pollInterval);
          }
        }
      } catch (error) {
        console.error('❌ Polling error:', error);
        // Don't stop polling on error, continue trying
      }
    }, 2000); // Poll setiap 2 detik
  }
  
  // Cleanup
  return () => {
    if (pollInterval) {
      console.log('🛑 Stopping job monitoring');
      clearInterval(pollInterval);
    }
  };
}, [currentJobId, isLoading]);

// HAPUS semua kode WebSocket yang lama!

  const handleCredentialChange = (e) => {
    setCredentials(prev => ({
      ...prev,
      [e.target.name]: e.target.value
    }));
  };

  const handleDosenConfigChange = (e) => {
    const { name, value } = e.target;
    
    // Pastikan nilai yang diset adalah number yang valid
    const numValue = name === 'affiliationId' ? value : parseInt(value) || 0;
    
    setDosenConfig(prev => ({
      ...prev,
      [name]: numValue
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
    setScrapingProgress({
      status: 'starting',
      message: 'Memulai scraping...',
      currentCount: 0,
      targetCount: payload.target_dosen || payload.max_authors || 100
    });
  
    try {
      const response = await fetch(`/api/scraping/${endpoint}`, { // Ubah URL menjadi relatif
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json',
        },
        credentials: 'include',
        body: JSON.stringify(payload)
      });
  
      const data = await response.json();
  
      if (data.success) {
        if (data.job_id) {
          setCurrentJobId(data.job_id);
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
        setScrapingResults({
          success: false,
          error: data.error
        });
        setIsLoading(false);
      }
    } catch (error) {
      setScrapingResults({
        success: false,
        error: 'Network error: ' + error.message
      });
      setIsLoading(false);
    }
  };

  const handleSintaDosen = async () => {
    if (!credentials.username || !credentials.password) {
      alert('Username dan password SINTA harus diisi');
      return;
    }

    await startScraping('sinta/dosen', {
      username: credentials.username,
      password: credentials.password,
      affiliation_id: dosenConfig.affiliationId,
      target_dosen: dosenConfig.targetDosen,
      max_pages: dosenConfig.maxPages,
      max_cycles: dosenConfig.maxCycles
    });
  };

  const handleSintaScopus = async () => {
    if (!credentials.username || !credentials.password) {
      alert('Username dan password SINTA harus diisi');
      return;
    }

    await startScraping('sinta/scopus', {
      username: credentials.username,
      password: credentials.password
    });
  };

  const handleSintaGoogleScholar = async () => {
    if (!credentials.username || !credentials.password) {
      alert('Username dan password SINTA harus diisi');
      return;
    }

    await startScraping('sinta/googlescholar', {
      username: credentials.username,
      password: credentials.password
    });
  };

  const handleSintaGaruda = async () => {
    if (!credentials.username || !credentials.password) {
      alert('Username dan password SINTA harus diisi');
      return;
    }

    await startScraping('sinta/garuda', {
      username: credentials.username,
      password: credentials.password
    });
  };

  const handleGoogleScholar = async () => {
    // Konfirmasi untuk scrape dari awal
    if (gsConfig.scrapeFromBeginning) {
      const confirmed = window.confirm(
        '⚠️ PERHATIAN: Anda akan melakukan scraping dari awal!\n\n' +
        'Ini akan mengulang semua dosen yang sudah selesai di-scrape sebelumnya.\n\n' +
        'Apakah Anda yakin ingin melanjutkan?'
      );
      
      if (!confirmed) {
        return;
      }
    }

    setIsLoading(true);
    setScrapingResults(null);
    setScrapingProgress({
      status: 'starting',
      message: 'Memulai scraping Google Scholar...',
      currentCount: 0,
      targetCount: gsConfig.maxAuthors
    });

    try {
      const response = await fetch('http://localhost:5002/api/scraping/googlescholar/scrape', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          max_authors: gsConfig.maxAuthors,
          scrape_from_beginning: gsConfig.scrapeFromBeginning
        })
      });

      const data = await response.json();

      if (data.success) {
        setCurrentJobId(data.job_id);
        // Tampilkan instruksi login jika diperlukan
        if (data.instructions) {
          alert(data.instructions);
        }
      } else {
        setScrapingResults({
          success: false,
          error: data.error
        });
        setIsLoading(false);
      }
    } catch (error) {
      setScrapingResults({
        success: false,
        error: 'Network error: ' + error.message
      });
      setIsLoading(false);
    }
  };

  const cancelCurrentJob = async () => {
    if (!currentJobId) return;
    try {
      setIsCancelling(true);
      const response = await fetch(`/api/scraping/jobs/${currentJobId}/cancel`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });
      const data = await response.json();
      if (!data.success) {
        setIsCancelling(false);
        alert(data.error || 'Gagal mengirim perintah cancel');
      }
    } catch (e) {
      setIsCancelling(false);
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
    const percentage = (scrapingProgress.currentCount / scrapingProgress.targetCount) * 100;
    return Math.min(Math.round(percentage), 100);
  };

  const getStatusColor = () => {
    if (!scrapingProgress) return 'bg-gray-500';
    switch (scrapingProgress.status) {
      case 'starting':
      case 'running':
      case 'waiting_login':
      case 'ready':
        return 'bg-blue-500';
      case 'completed':
        return 'bg-green-500';
      case 'failed':
        return 'bg-red-500';
      default:
        return 'bg-gray-500';
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 py-8">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Header */}
        <div className="mb-8">
          <div className="flex items-center mb-2">
            <Database className="w-8 h-8 text-blue-600 mr-3" />
            <h1 className="text-3xl font-bold text-gray-900">Data Scraping Dashboard</h1>
          </div>
          <p className="text-sm text-gray-600">
            Scraping data akademik dari berbagai sumber (SINTA, Scopus, Google Scholar, Garuda)
          </p>
        </div>

        {/* Tabs */}
        <div className="mb-6">
          <div className="flex flex-wrap gap-2">
            <TabButton
              id="sinta-dosen"
              label="SINTA Dosen"
              icon={User}
              isActive={activeTab === 'sinta-dosen'}
              onClick={() => setActiveTab('sinta-dosen')}
            />
            <TabButton
              id="sinta-scopus"
              label="SINTA Scopus"
              icon={FileText}
              isActive={activeTab === 'sinta-scopus'}
              onClick={() => setActiveTab('sinta-scopus')}
            />
            <TabButton
              id="sinta-gs"
              label="SINTA Google Scholar"
              icon={Globe}
              isActive={activeTab === 'sinta-gs'}
              onClick={() => setActiveTab('sinta-gs')}
            />
            <TabButton
              id="sinta-garuda"
              label="SINTA Garuda"
              icon={Database}
              isActive={activeTab === 'sinta-garuda'}
              onClick={() => setActiveTab('sinta-garuda')}
            />
            <TabButton
              id="google-scholar"
              label="Google Scholar"
              icon={Globe}
              isActive={activeTab === 'google-scholar'}
              onClick={() => setActiveTab('google-scholar')}
            />
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
                  className={`h-2.5 rounded-full ${getStatusColor()}`}
                  style={{ width: `${getProgressPercentage()}%` }}
                ></div>
              </div>
            </div>
          </div>
        )}

        {/* Results */}
        {scrapingResults && (
          <div className={`mb-6 p-4 rounded-lg ${
            scrapingResults.success ? 'bg-green-50 border-green-500' : 'bg-red-50 border-red-500'
          } border`}>
            <div className="flex items-start">
              {scrapingResults.success ? (
                <CheckCircle className="w-5 h-5 text-green-500 mt-0.5 mr-3" />
              ) : (
                <AlertCircle className="w-5 h-5 text-red-500 mt-0.5 mr-3" />
              )}
              <div>
                <h3 className={`text-lg font-medium ${
                  scrapingResults.success ? 'text-green-800' : 'text-red-800'
                }`}>
                  {scrapingResults.success ? 'Scraping Berhasil' : 'Scraping Gagal'}
                </h3>
                <p className={`text-sm ${
                  scrapingResults.success ? 'text-green-700' : 'text-red-700'
                }`}>
                  {scrapingResults.success ? scrapingResults.message : scrapingResults.error}
                </p>
                {scrapingResults.traceback && (
                  <details className="mt-2">
                    <summary className="text-xs text-gray-600 cursor-pointer hover:text-gray-800">
                      Show error details
                    </summary>
                    <pre className="mt-2 text-xs bg-white rounded p-2 overflow-auto max-h-40 border border-gray-300">
                      {scrapingResults.traceback}
                    </pre>
                  </details>
                )}
                {scrapingResults.summary && scrapingResults.success && (
                  <pre className="mt-2 text-sm bg-white rounded p-2 overflow-auto border border-gray-300">
                    {JSON.stringify(scrapingResults.summary, null, 2)}
                  </pre>
                )}
              </div>
            </div>
          </div>
        )}

        {/* SINTA Credentials (Common for SINTA tabs) */}
        {activeTab !== 'google-scholar' && (
          <div className="bg-white rounded-lg shadow-md p-6 mb-6">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">Kredensial SINTA</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Username/Email SINTA
                </label>
                <div className="relative">
                  <User className="absolute left-3 top-1/2 transform -translate-y-1/2 h-5 w-5 text-gray-400" />
                  <input
                    type="text"
                    name="username"
                    value={credentials.username}
                    onChange={handleCredentialChange}
                    disabled={isLoading}
                    className="w-full pl-10 pr-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-100"
                    placeholder="Masukkan username atau email SINTA"
                  />
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Password SINTA
                </label>
                <div className="relative">
                  <Lock className="absolute left-3 top-1/2 transform -translate-y-1/2 h-5 w-5 text-gray-400" />
                  <input
                    type="password"
                    name="password"
                    value={credentials.password}
                    onChange={handleCredentialChange}
                    disabled={isLoading}
                    className="w-full pl-10 pr-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-100"
                    placeholder="Masukkan password SINTA"
                  />
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Tab Content */}
        <div className="bg-white rounded-lg shadow-md p-6">
          {activeTab === 'sinta-dosen' && (
            <div>
              <h3 className="text-lg font-semibold text-gray-900 mb-4">Scraping SINTA Dosen</h3>
              
              <div className="bg-yellow-50 border-l-4 border-yellow-400 p-4 mb-6">
                <div className="flex">
                  <AlertCircle className="h-5 w-5 text-yellow-400" />
                  <div className="ml-3">
                    <p className="text-sm text-yellow-700">
                      Proses ini dapat memakan waktu lama (hingga beberapa jam) tergantung target dosen yang ditentukan.
                    </p>
                  </div>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Affiliation ID
                  </label>
                  <input
                    type="text"
                    name="affiliationId"
                    value={dosenConfig.affiliationId}
                    onChange={handleDosenConfigChange}
                    disabled={isLoading}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-100"
                  />
                  <p className="mt-1 text-xs text-gray-500">ID afiliasi (default: 1397 untuk Unpar)</p>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    <Target className="w-4 h-4 inline mr-1" />
                    Target Dosen
                  </label>
                  <input
                    type="number"
                    name="targetDosen"
                    value={dosenConfig.targetDosen}
                    onChange={handleDosenConfigChange}
                    min="1"
                    disabled={isLoading}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-100"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Max Pages per Cycle
                  </label>
                  <input
                    type="number"
                    name="maxPages"
                    value={dosenConfig.maxPages}
                    onChange={handleDosenConfigChange}
                    min="1"
                    disabled={isLoading}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-100"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    <RefreshCw className="w-4 h-4 inline mr-1" />
                    Max Cycles
                  </label>
                  <input
                    type="number"
                    name="maxCycles"
                    value={dosenConfig.maxCycles}
                    onChange={handleDosenConfigChange}
                    min="1"
                    disabled={isLoading}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-100"
                  />
                </div>
              </div>

              <div className="flex items-center space-x-3">
                <button
                  onClick={handleSintaDosen}
                  disabled={isLoading || !credentials.username || !credentials.password}
                  className="w-full flex items-center justify-center px-4 py-3 border border-transparent text-sm font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  {isLoading ? (
                    <>
                      <Loader className="animate-spin -ml-1 mr-3 h-5 w-5" />
                      Sedang Scraping...
                    </>
                  ) : (
                    <>
                      <Play className="-ml-1 mr-3 h-5 w-5" />
                      Mulai Scraping SINTA Dosen
                    </>
                  )}
                </button>
                {isLoading && currentJobId && (
                  <button
                    onClick={cancelCurrentJob}
                    className={`inline-flex items-center px-4 py-2 rounded-lg text-white ${isCancelling ? 'bg-gray-400 cursor-wait' : 'bg-red-600 hover:bg-red-700'}`}
                    disabled={isCancelling}
                  >
                    {isCancelling ? (
                      <>
                        <Loader className="w-4 h-4 mr-2 animate-spin" />
                        Menghentikan...
                      </>
                    ) : (
                      <>
                        <Square className="w-4 h-4 mr-2" />
                        Stop
                      </>
                    )}
                  </button>
                )}
              </div>
            </div>
          )}

          {activeTab === 'sinta-scopus' && (
            <div>
              <h3 className="text-lg font-semibold text-gray-900 mb-4">Scraping SINTA Scopus</h3>
              
              <div className="bg-blue-50 border-l-4 border-blue-400 p-4 mb-6">
                <div className="flex">
                  <AlertCircle className="h-5 w-5 text-blue-400" />
                  <div className="ml-3">
                    <p className="text-sm text-blue-700">
                      Scraping publikasi Scopus dari semua dosen yang ada di database.
                    </p>
                  </div>
                </div>
              </div>

              <button
                onClick={handleSintaScopus}
                disabled={isLoading || !credentials.username || !credentials.password}
                className="w-full flex items-center justify-center px-4 py-3 border border-transparent text-sm font-medium rounded-md text-white bg-orange-600 hover:bg-orange-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-orange-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                {isLoading ? (
                  <>
                    <Loader className="animate-spin -ml-1 mr-3 h-5 w-5" />
                    Sedang Scraping...
                  </>
                ) : (
                  <>
                    <Play className="-ml-1 mr-3 h-5 w-5" />
                    Mulai Scraping Scopus
                  </>
                )}
              </button>
            </div>
          )}

          {activeTab === 'sinta-gs' && (
            <div>
              <h3 className="text-lg font-semibold text-gray-900 mb-4">Scraping SINTA Google Scholar</h3>
              
              <div className="bg-green-50 border-l-4 border-green-400 p-4 mb-6">
                <div className="flex">
                  <AlertCircle className="h-5 w-5 text-green-400" />
                  <div className="ml-3">
                    <p className="text-sm text-green-700">
                      Scraping publikasi Google Scholar dari semua dosen yang ada di database.
                    </p>
                  </div>
                </div>
              </div>

              <button
                onClick={handleSintaGoogleScholar}
                disabled={isLoading || !credentials.username || !credentials.password}
                className="w-full flex items-center justify-center px-4 py-3 border border-transparent text-sm font-medium rounded-md text-white bg-green-600 hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-green-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                {isLoading ? (
                  <>
                    <Loader className="animate-spin -ml-1 mr-3 h-5 w-5" />
                    Sedang Scraping...
                  </>
                ) : (
                  <>
                    <Play className="-ml-1 mr-3 h-5 w-5" />
                    Mulai Scraping Google Scholar
                  </>
                )}
              </button>
            </div>
          )}

          {activeTab === 'sinta-garuda' && (
            <div>
              <h3 className="text-lg font-semibold text-gray-900 mb-4">Scraping SINTA Garuda</h3>
              
              <div className="bg-purple-50 border-l-4 border-purple-400 p-4 mb-6">
                <div className="flex">
                  <AlertCircle className="h-5 w-5 text-purple-400" />
                  <div className="ml-3">
                    <p className="text-sm text-purple-700">
                      Scraping publikasi Garuda dari semua dosen yang ada di database.
                    </p>
                  </div>
                </div>
              </div>

              <button
                onClick={handleSintaGaruda}
                disabled={isLoading || !credentials.username || !credentials.password}
                className="w-full flex items-center justify-center px-4 py-3 border border-transparent text-sm font-medium rounded-md text-white bg-purple-600 hover:bg-purple-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-purple-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                {isLoading ? (
                  <>
                    <Loader className="animate-spin -ml-1 mr-3 h-5 w-5" />
                    Sedang Scraping...
                  </>
                ) : (
                  <>
                    <Play className="-ml-1 mr-3 h-5 w-5" />
                    Mulai Scraping Garuda
                  </>
                )}
              </button>
            </div>
          )}

          {activeTab === 'google-scholar' && (
            <div>
              <h3 className="text-lg font-semibold text-gray-900 mb-4">Scraping Google Scholar</h3>
              
              <div className="bg-blue-50 border-l-4 border-blue-400 p-4 mb-6">
                <div className="flex">
                  <AlertCircle className="h-5 w-5 text-blue-400" />
                  <div className="ml-3">
                    <p className="text-sm text-blue-700">
                      Scraping langsung dari Google Scholar (tidak melalui SINTA).
                      Browser akan terbuka untuk login manual ke Google Scholar.
                    </p>
                  </div>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    <Target className="w-4 h-4 inline mr-1" />
                    Max Authors
                  </label>
                  <input
                    type="number"
                    name="maxAuthors"
                    value={gsConfig.maxAuthors}
                    onChange={handleGsConfigChange}
                    disabled={isLoading}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-100"
                  />
                </div>

                <div className="flex items-center">
                  <input
                    type="checkbox"
                    name="scrapeFromBeginning"
                    checked={gsConfig.scrapeFromBeginning}
                    onChange={handleGsConfigChange}
                    disabled={isLoading}
                    className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
                  />
                  <label className="ml-2 block text-sm text-gray-900">
                    Scrape dari awal (ulang semua)
                  </label>
                </div>
              </div>

              <button
                onClick={handleGoogleScholar}
                disabled={isLoading}
                className="w-full flex items-center justify-center px-4 py-3 border border-transparent text-sm font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                {isLoading ? (
                  <>
                    <Loader className="animate-spin -ml-1 mr-3 h-5 w-5" />
                    Sedang Scraping...
                  </>
                ) : (
                  <>
                    <Play className="-ml-1 mr-3 h-5 w-5" />
                    Mulai Scraping Google Scholar
                  </>
                )}
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default ScrapingDashboard;