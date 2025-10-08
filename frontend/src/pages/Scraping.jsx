import { useState, useEffect } from 'react';
import { Play, User, Lock, Database, AlertCircle, CheckCircle, Clock, Target, RefreshCw, Download, Globe, FileText, Loader } from 'lucide-react';

const ScrapingDashboard = () => {
  const [activeTab, setActiveTab] = useState('sinta-dosen');
  const [credentials, setCredentials] = useState({
    username: '',
    password: ''
  });
  const [dosenConfig, setDosenConfig] = useState({
    affiliationId: '1397',
    targetDosen: 473,
    maxPages: 50,
    maxCycles: 20
  });
  const [gsConfig, setGsConfig] = useState({
    maxAuthors: 10,
    scrapeFromBeginning: false
  });
  const [isLoading, setIsLoading] = useState(false);
  const [scrapingProgress, setScrapingProgress] = useState(null);
  const [scrapingResults, setScrapingResults] = useState(null);
  const [currentJobId, setCurrentJobId] = useState(null);

  // WebSocket/Polling for progress updates
  useEffect(() => {
    let pollInterval = null;
    
    if (currentJobId && isLoading) {
      pollInterval = setInterval(async () => {
        try {
          const response = await fetch(`http://localhost:5000/api/scraping/jobs/${currentJobId}`);
          const data = await response.json();
          
          if (data.success && data.job) {
            const job = data.job;
            
            setScrapingProgress({
              status: job.status,
              message: job.message,
              currentCount: job.current,
              targetCount: job.total
            });
            
            if (job.status === 'completed') {
              setScrapingResults({
                success: true,
                message: job.message,
                summary: job.result
              });
              setIsLoading(false);
              setCurrentJobId(null);
            } else if (job.status === 'failed') {
              setScrapingResults({
                success: false,
                error: job.error || job.message
              });
              setIsLoading(false);
              setCurrentJobId(null);
            }
          }
        } catch (error) {
          console.error('Polling error:', error);
        }
      }, 2000); // Poll every 2 seconds
    }
    
    return () => {
      if (pollInterval) clearInterval(pollInterval);
    };
  }, [currentJobId, isLoading]);

  const handleCredentialChange = (e) => {
    setCredentials(prev => ({
      ...prev,
      [e.target.name]: e.target.value
    }));
  };

  const handleDosenConfigChange = (e) => {
    const value = e.target.name === 'affiliationId' ? e.target.value : parseInt(e.target.value);
    setDosenConfig(prev => ({
      ...prev,
      [e.target.name]: value
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
      const response = await fetch(`http://localhost:5000/api/scraping/${endpoint}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
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
    // Confirmation for scrape from beginning
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

    await startScraping('googlescholar/scrape', {
      max_authors: gsConfig.maxAuthors,
      scrape_from_beginning: gsConfig.scrapeFromBeginning
    });
  };

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
        <div className="bg-white rounded-lg shadow-md p-6 mb-6">
          {activeTab === 'sinta-dosen' && (
            <div>
              <h3 className="text-lg font-semibold text-gray-900 mb-4">Scraping SINTA Dosen</h3>
              
              <div className="bg-yellow-50 border-l-4 border-yellow-400 p-4 mb-6">
                <div className="flex">
                  <AlertCircle className="h-5 w-5 text-yellow-400 flex-shrink-0" />
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
                    disabled={isLoading}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-100"
                  />
                </div>
              </div>

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
            </div>
          )}

          {activeTab === 'sinta-scopus' && (
            <div>
              <h3 className="text-lg font-semibold text-gray-900 mb-4">Scraping SINTA Scopus</h3>
              
              <div className="bg-blue-50 border-l-4 border-blue-400 p-4 mb-6">
                <div className="flex">
                  <AlertCircle className="h-5 w-5 text-blue-400 flex-shrink-0" />
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
                  <AlertCircle className="h-5 w-5 text-green-400 flex-shrink-0" />
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
                  <AlertCircle className="h-5 w-5 text-purple-400 flex-shrink-0" />
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
              
              <div className="bg-red-50 border-l-4 border-red-400 p-4 mb-6">
                <div className="flex">
                  <AlertCircle className="h-5 w-5 text-red-400 flex-shrink-0" />
                  <div className="ml-3">
                    <p className="text-sm text-red-700 font-semibold mb-2">
                      ⚠️ Perhatian: Browser Otomatis
                    </p>
                    <p className="text-sm text-red-700">
                      Browser Chrome akan terbuka secara otomatis. Scraping akan berjalan di server. 
                      Jika diminta login, silakan login ke Google Scholar untuk menghindari CAPTCHA.
                    </p>
                  </div>
                </div>
              </div>

              <div className="bg-blue-50 border-l-4 border-blue-400 p-4 mb-6">
                <div className="flex">
                  <AlertCircle className="h-5 w-5 text-blue-400 flex-shrink-0" />
                  <div className="ml-3">
                    <p className="text-sm text-blue-700">
                      Scraping akan mengambil profil dan publikasi dosen dari database yang memiliki URL Google Scholar. 
                      Data akan disimpan ke database dan file CSV secara otomatis.
                    </p>
                  </div>
                </div>
              </div>

              <div className="space-y-4 mb-6">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    <Target className="w-4 h-4 inline mr-1" />
                    Maksimum Authors
                  </label>
                  <input
                    type="number"
                    name="maxAuthors"
                    value={gsConfig.maxAuthors}
                    onChange={handleGsConfigChange}
                    disabled={isLoading}
                    min="1"
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-100"
                  />
                  <p className="mt-1 text-xs text-gray-500">Jumlah maksimum author yang akan di-scrape dari database</p>
                </div>

                <div className="flex items-start">
                  <div className="flex items-center h-5">
                    <input
                      id="scrapeFromBeginning"
                      name="scrapeFromBeginning"
                      type="checkbox"
                      checked={gsConfig.scrapeFromBeginning}
                      onChange={handleGsConfigChange}
                      disabled={isLoading}
                      className="w-4 h-4 text-red-600 border-gray-300 rounded focus:ring-red-500 disabled:opacity-50"
                    />
                  </div>
                  <div className="ml-3">
                    <label htmlFor="scrapeFromBeginning" className="text-sm font-medium text-gray-700">
                      Scraping Dari Awal (Reset Status)
                    </label>
                    <p className="text-xs text-gray-500 mt-1">
                      ⚠️ Centang opsi ini untuk mengulang scraping semua dosen (termasuk yang sudah selesai). 
                      Jika tidak dicentang, hanya dosen yang belum selesai yang akan di-scrape.
                    </p>
                  </div>
                </div>
              </div>

              <button
                onClick={handleGoogleScholar}
                disabled={isLoading}
                className="w-full flex items-center justify-center px-4 py-3 border border-transparent text-sm font-medium rounded-md text-white bg-red-600 hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
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

        {/* Progress Section */}
        {scrapingProgress && (
          <div className="bg-white rounded-lg shadow-md p-6 mb-6">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">Progress Scraping</h3>
            
            <div className="mb-4">
              <div className="flex justify-between mb-2">
                <span className="text-sm font-medium text-gray-700">
                  {scrapingProgress.currentCount || 0} / {scrapingProgress.targetCount || 0} items
                </span>
                <span className="text-sm font-medium text-gray-700">
                  {getProgressPercentage()}%
                </span>
              </div>
              <div className="w-full bg-gray-200 rounded-full h-3">
                <div
                  className={`h-3 rounded-full transition-all duration-500 ${getStatusColor()}`}
                  style={{ width: `${getProgressPercentage()}%` }}
                />
              </div>
            </div>

            <div className="bg-blue-50 border border-blue-200 rounded-md p-4">
              <div className="flex items-start">
                <Clock className="h-5 w-5 text-blue-500 mt-0.5 flex-shrink-0" />
                <div className="ml-3 flex-1">
                  <p className="text-sm font-medium text-blue-900">{scrapingProgress.message || 'Processing...'}</p>
                  {scrapingProgress.job_id && (
                    <p className="text-xs text-blue-700 mt-1">
                      Job ID: {scrapingProgress.job_id}
                    </p>
                  )}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Results Section */}
        {scrapingResults && (
          <div className="bg-white rounded-lg shadow-md p-6">
            <div className="flex items-center mb-4">
              {scrapingResults.success ? (
                <CheckCircle className="w-6 h-6 text-green-500 mr-2 flex-shrink-0" />
              ) : (
                <AlertCircle className="w-6 h-6 text-red-500 mr-2 flex-shrink-0" />
              )}
              <h3 className="text-lg font-semibold text-gray-900">
                Hasil Scraping
              </h3>
            </div>
            
            {scrapingResults.success ? (
              <div className="space-y-4">
                <div className="bg-green-50 border border-green-200 rounded-md p-4">
                  <p className="text-sm text-green-800 font-medium">{scrapingResults.message}</p>
                </div>

                {scrapingResults.summary && (
                  <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                    {Object.entries(scrapingResults.summary).map(([key, value]) => (
                      <div key={key} className="bg-gray-50 rounded-lg p-4">
                        <p className="text-xs text-gray-500 uppercase">{key.replace(/_/g, ' ')}</p>
                        <p className="text-2xl font-bold text-gray-900 mt-1">
                          {typeof value === 'number' ? value.toLocaleString() : value}
                        </p>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ) : (
              <div className="bg-red-50 border border-red-200 rounded-md p-4">
                <p className="text-sm text-red-800">Error: {scrapingResults.error}</p>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default ScrapingDashboard;