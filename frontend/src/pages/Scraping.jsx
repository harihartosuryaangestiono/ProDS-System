import { useState } from 'react';
import { toast } from 'react-hot-toast';
import { Download, Play, User, Lock, Database, Globe, AlertCircle, CheckCircle, Clock } from 'lucide-react';
import apiService from '../services/apiService';

const Scraping = () => {
  const [activeTab, setActiveTab] = useState('sinta');
  const [scrapingType, setScrapingType] = useState('dosen');
  const [sintaCredentials, setSintaCredentials] = useState({
    username: '',
    password: ''
  });
  const [isLoading, setIsLoading] = useState(false);
  const [scrapingResults, setScrapingResults] = useState(null);

  const handleCredentialChange = (e) => {
    setSintaCredentials(prev => ({
      ...prev,
      [e.target.name]: e.target.value
    }));
  };

  const handleSintaScraping = async () => {
    if (!sintaCredentials.username || !sintaCredentials.password) {
      toast.error('Username dan password SINTA harus diisi');
      return;
    }

    setIsLoading(true);
    setScrapingResults(null);

    try {
      const response = await apiService.scrapeSinta({
        username: sintaCredentials.username,
        password: sintaCredentials.password,
        type: scrapingType
      });

      if (response.success) {
        setScrapingResults({
          success: true,
          message: response.data.message,
          details: response.data.result || response.data.results
        });
        toast.success('Scraping SINTA berhasil!');
      } else {
        setScrapingResults({
          success: false,
          error: response.error
        });
        toast.error('Scraping SINTA gagal: ' + response.error);
      }
    } catch (error) {
      setScrapingResults({
        success: false,
        error: 'Network error occurred'
      });
      toast.error('Terjadi kesalahan jaringan');
      console.error('SINTA scraping error:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleScholarScraping = async () => {
    setIsLoading(true);
    setScrapingResults(null);

    try {
      const response = await apiService.scrapeScholar({
        type: scrapingType
      });

      if (response.success) {
        setScrapingResults({
          success: true,
          message: response.data.message,
          details: response.data.result
        });
        toast.success('Scraping Google Scholar berhasil!');
      } else {
        setScrapingResults({
          success: false,
          error: response.error
        });
        toast.error('Scraping Google Scholar gagal: ' + response.error);
      }
    } catch (error) {
      setScrapingResults({
        success: false,
        error: 'Network error occurred'
      });
      toast.error('Terjadi kesalahan jaringan');
      console.error('Scholar scraping error:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const TabButton = ({ id, label, icon: Icon, isActive, onClick }) => (
    <button
      onClick={onClick}
      className={`flex items-center px-6 py-3 text-sm font-medium rounded-lg transition-colors duration-200 ${
        isActive
          ? 'bg-blue-600 text-white shadow-md'
          : 'text-gray-600 hover:text-blue-600 hover:bg-blue-50'
      }`}
    >
      <Icon className="w-5 h-5 mr-2" />
      {label}
    </button>
  );

  const TypeSelector = ({ value, onChange, disabled }) => (
    <div className="flex space-x-4">
      <label className="flex items-center">
        <input
          type="radio"
          name="scrapingType"
          value="dosen"
          checked={value === 'dosen'}
          onChange={(e) => onChange(e.target.value)}
          disabled={disabled}
          className="mr-2 text-blue-600 focus:ring-blue-500"
        />
        <span className="text-sm font-medium text-gray-700">Data Dosen</span>
      </label>
      <label className="flex items-center">
        <input
          type="radio"
          name="scrapingType"
          value="publikasi"
          checked={value === 'publikasi'}
          onChange={(e) => onChange(e.target.value)}
          disabled={disabled}
          className="mr-2 text-blue-600 focus:ring-blue-500"
        />
        <span className="text-sm font-medium text-gray-700">Data Publikasi</span>
      </label>
    </div>
  );

  return (
    <div className="min-h-screen bg-gray-50 py-8">
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900">Data Scraping</h1>
          <p className="mt-2 text-sm text-gray-600">
            Lakukan scraping data dari SINTA atau Google Scholar
          </p>
        </div>

        {/* Tabs */}
        <div className="mb-8">
          <div className="flex space-x-4">
            <TabButton
              id="sinta"
              label="SINTA"
              icon={Database}
              isActive={activeTab === 'sinta'}
              onClick={() => setActiveTab('sinta')}
            />
            <TabButton
              id="scholar"
              label="Google Scholar"
              icon={Globe}
              isActive={activeTab === 'scholar'}
              onClick={() => setActiveTab('scholar')}
            />
          </div>
        </div>

        {/* Content */}
        <div className="bg-white rounded-lg shadow-md">
          {/* SINTA Tab */}
          {activeTab === 'sinta' && (
            <div className="p-6">
              <div className="flex items-center mb-6">
                <Database className="w-6 h-6 text-blue-600 mr-3" />
                <h2 className="text-xl font-semibold text-gray-900">Scraping SINTA</h2>
              </div>

              {/* Warning */}
              <div className="bg-yellow-50 border-l-4 border-yellow-400 p-4 mb-6">
                <div className="flex">
                  <AlertCircle className="h-5 w-5 text-yellow-400" />
                  <div className="ml-3">
                    <p className="text-sm text-yellow-700">
                      <strong>Perhatian:</strong> Diperlukan akun SINTA yang valid untuk melakukan scraping. 
                      Proses ini dapat memakan waktu lama tergantung jumlah data.
                    </p>
                  </div>
                </div>
              </div>

              {/* Credentials Form */}
              <div className="space-y-4 mb-6">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Username/Email SINTA
                  </label>
                  <div className="relative">
                    <User className="absolute left-3 top-1/2 transform -translate-y-1/2 h-5 w-5 text-gray-400" />
                    <input
                      type="text"
                      name="username"
                      value={sintaCredentials.username}
                      onChange={handleCredentialChange}
                      disabled={isLoading}
                      className="w-full pl-10 pr-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
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
                      value={sintaCredentials.password}
                      onChange={handleCredentialChange}
                      disabled={isLoading}
                      className="w-full pl-10 pr-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
                      placeholder="Masukkan password SINTA"
                    />
                  </div>
                </div>
              </div>

              {/* Type Selection */}
              <div className="mb-6">
                <label className="block text-sm font-medium text-gray-700 mb-3">
                  Pilih Jenis Data
                </label>
                <TypeSelector 
                  value={scrapingType} 
                  onChange={setScrapingType}
                  disabled={isLoading}
                />
              </div>

              {/* Action Button */}
              <button
                onClick={handleSintaScraping}
                disabled={isLoading || !sintaCredentials.username || !sintaCredentials.password}
                className="w-full flex items-center justify-center px-4 py-3 border border-transparent text-sm font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isLoading ? (
                  <>
                    <Clock className="animate-spin -ml-1 mr-3 h-5 w-5" />
                    Sedang Scraping...
                  </>
                ) : (
                  <>
                    <Play className="-ml-1 mr-3 h-5 w-5" />
                    Mulai Scraping SINTA
                  </>
                )}
              </button>
            </div>
          )}

          {/* Google Scholar Tab */}
          {activeTab === 'scholar' && (
            <div className="p-6">
              <div className="flex items-center mb-6">
                <Globe className="w-6 h-6 text-green-600 mr-3" />
                <h2 className="text-xl font-semibold text-gray-900">Scraping Google Scholar</h2>
              </div>

              {/* Info */}
              <div className="bg-blue-50 border-l-4 border-blue-400 p-4 mb-6">
                <div className="flex">
                  <AlertCircle className="h-5 w-5 text-blue-400" />
                  <div className="ml-3">
                    <p className="text-sm text-blue-700">
                      <strong>Info:</strong> Scraping Google Scholar menggunakan API publik dan tidak memerlukan login. 
                      Proses akan mengambil data dosen dan publikasi dari Universitas Parahyangan.
                    </p>
                  </div>
                </div>
              </div>

              {/* Type Selection */}
              <div className="mb-6">
                <label className="block text-sm font-medium text-gray-700 mb-3">
                  Pilih Jenis Data
                </label>
                <TypeSelector 
                  value={scrapingType} 
                  onChange={setScrapingType}
                  disabled={isLoading}
                />
              </div>

              {/* Action Button */}
              <button
                onClick={handleScholarScraping}
                disabled={isLoading}
                className="w-full flex items-center justify-center px-4 py-3 border border-transparent text-sm font-medium rounded-md text-white bg-green-600 hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-green-500 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isLoading ? (
                  <>
                    <Clock className="animate-spin -ml-1 mr-3 h-5 w-5" />
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

        {/* Results */}
        {scrapingResults && (
          <div className="mt-8">
            <div className={`bg-white rounded-lg shadow-md p-6 border-l-4 ${
              scrapingResults.success ? 'border-green-400' : 'border-red-400'
            }`}>
              <div className="flex items-center mb-4">
                {scrapingResults.success ? (
                  <CheckCircle className="h-6 w-6 text-green-600 mr-3" />
                ) : (
                  <AlertCircle className="h-6 w-6 text-red-600 mr-3" />
                )}
                <h3 className="text-lg font-semibold text-gray-900">
                  Hasil Scraping
                </h3>
              </div>

              {scrapingResults.success ? (
                <div>
                  <p className="text-green-700 mb-4">{scrapingResults.message}</p>
                  {scrapingResults.details && (
                    <div className="bg-gray-50 rounded-md p-4">
                      <h4 className="text-sm font-medium text-gray-900 mb-2">Detail:</h4>
                      <pre className="text-xs text-gray-600 overflow-auto max-h-64">
                        {typeof scrapingResults.details === 'object' 
                          ? JSON.stringify(scrapingResults.details, null, 2)
                          : scrapingResults.details
                        }
                      </pre>
                    </div>
                  )}
                </div>
              ) : (
                <div>
                  <p className="text-red-700 mb-2">Scraping gagal!</p>
                  <p className="text-sm text-gray-600">{scrapingResults.error}</p>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default Scraping;