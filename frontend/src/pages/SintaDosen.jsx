import { useState, useEffect } from 'react';
import { Users, TrendingUp, Award, Calendar, ExternalLink, Building2, GraduationCap, RefreshCw, Search, ArrowUp, ArrowDown } from 'lucide-react';
import apiService from '../services/apiService';
import { toast } from 'react-hot-toast';

const SintaDosen = () => {
  const [dosenData, setDosenData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [statsLoading, setStatsLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [currentPage, setCurrentPage] = useState(1);
  const [pagination, setPagination] = useState(null);
  const [sortConfig, setSortConfig] = useState({ key: null, direction: 'asc' });
  
  // Faculty and Department filters
  const [faculties, setFaculties] = useState([]);
  const [departments, setDepartments] = useState([]);
  const [selectedFaculty, setSelectedFaculty] = useState('');
  const [selectedDepartment, setSelectedDepartment] = useState('');
  const [loadingDepartments, setLoadingDepartments] = useState(false);
  
  const [stats, setStats] = useState({
    totalDosen: 0,
    totalSitasiGS: 0,
    totalSitasiScopus: 0,
    avgHIndex: 0,
    medianHIndex: 0,
    totalPublikasi: 0,
    previousDate: null,
    previousValues: {}
  });

  const perPage = 20;

  // Fetch faculties on component mount
  useEffect(() => {
    fetchFaculties();
  }, []);

  // Fetch departments when faculty changes
  useEffect(() => {
    if (selectedFaculty) {
      fetchDepartments(selectedFaculty);
    } else {
      setDepartments([]);
      setSelectedDepartment('');
    }
  }, [selectedFaculty]);

  // Fetch data when filters change
  useEffect(() => {
    fetchDosenData();
  }, [currentPage, searchTerm, selectedFaculty, selectedDepartment]);

  // Fetch stats when filters change
  useEffect(() => {
    fetchStats();
  }, [searchTerm, selectedFaculty, selectedDepartment]);

  const fetchFaculties = async () => {
    try {
      const response = await apiService.getSintaFaculties();
      if (response.success) {
        setFaculties(response.data.faculties || []);
      } else {
        console.error('Error fetching faculties:', response.error);
      }
    } catch (error) {
      console.error('Error fetching faculties:', error);
    }
  };

  const fetchDepartments = async (faculty) => {
    try {
      setLoadingDepartments(true);
      const response = await apiService.getSintaDepartments(faculty);
      if (response.success) {
        setDepartments(response.data.departments || []);
      } else {
        console.error('Error fetching departments:', response.error);
        setDepartments([]);
      }
    } catch (error) {
      console.error('Error fetching departments:', error);
      setDepartments([]);
    } finally {
      setLoadingDepartments(false);
    }
  };

  const fetchDosenData = async () => {
    try {
      setLoading(true);
      const params = {
        page: currentPage,
        perPage: perPage,
        search: searchTerm
      };

      if (selectedFaculty) {
        params.faculty = selectedFaculty;
      }
      if (selectedDepartment) {
        params.department = selectedDepartment;
      }

      const response = await apiService.getSintaDosen(params);
      if (response.success) {
        setDosenData(response.data.data || []);
        const paginationData = response.data.pagination;
        if (paginationData) {
          setPagination({
            currentPage: paginationData.page,
            totalPages: paginationData.pages,
            totalRecords: paginationData.total,
            perPage: paginationData.per_page
          });
        } else {
          setPagination(null);
        }
      } else {
        toast.error('Gagal mengambil data dosen SINTA');
        console.error('Error fetching SINTA dosen data:', response.error);
      }
    } catch (error) {
      console.error('Error fetching SINTA dosen data:', error);
      toast.error('Terjadi kesalahan saat mengambil data');
    } finally {
      setLoading(false);
    }
  };

  const fetchStats = async () => {
    try {
      setStatsLoading(true);
      const params = {};
      
      if (searchTerm) params.search = searchTerm;
      if (selectedFaculty) params.faculty = selectedFaculty;
      if (selectedDepartment) params.department = selectedDepartment;

      const response = await apiService.getSintaDosenStats(params);
      if (response.success) {
        setStats({
          totalDosen: response.data.totalDosen || 0,
          totalSitasiGS: response.data.totalSitasiGS || 0,
          totalSitasiScopus: response.data.totalSitasiScopus || 0,
          avgHIndex: response.data.avgHIndex || 0,
          medianHIndex: response.data.medianHIndex || 0,
          totalPublikasi: response.data.totalPublikasi || 0,
          previousDate: response.data.previousDate || null,
          previousValues: response.data.previousValues || {}
        });
      }
    } catch (error) {
      console.error('Error fetching SINTA dosen stats:', error);
    } finally {
      setStatsLoading(false);
    }
  };

  const handleSearchChange = (e) => {
    setSearchTerm(e.target.value);
    setCurrentPage(1);
  };

  const handlePageChange = (page) => {
    setCurrentPage(page);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const handleFacultyChange = (e) => {
    const faculty = e.target.value;
    setSelectedFaculty(faculty);
    setSelectedDepartment(''); // Reset department when faculty changes
    setCurrentPage(1);
  };

  const handleDepartmentChange = (e) => {
    setSelectedDepartment(e.target.value);
    setCurrentPage(1);
  };

  const handleResetFilters = () => {
    setSelectedFaculty('');
    setSelectedDepartment('');
    setSearchTerm('');
    setCurrentPage(1);
  };

  const handleSort = (key) => {
    let direction = 'asc';
    if (sortConfig.key === key && sortConfig.direction === 'asc') {
      direction = 'desc';
    }
    setSortConfig({ key, direction });
  };

  const getSortedData = () => {
    if (!sortConfig.key) return dosenData;

    return [...dosenData].sort((a, b) => {
      const aVal = a[sortConfig.key];
      const bVal = b[sortConfig.key];

      if (aVal === null || aVal === undefined) return 1;
      if (bVal === null || bVal === undefined) return -1;

      if (typeof aVal === 'number' && typeof bVal === 'number') {
        return sortConfig.direction === 'asc' ? aVal - bVal : bVal - aVal;
      }

      const aStr = String(aVal).toLowerCase();
      const bStr = String(bVal).toLowerCase();
      
      if (aStr < bStr) return sortConfig.direction === 'asc' ? -1 : 1;
      if (aStr > bStr) return sortConfig.direction === 'asc' ? 1 : -1;
      return 0;
    });
  };

  const StatCard = ({ title, value, icon: Icon, color, subtitle, loading, previousValue, previousDate }) => {
    const getNumericValue = (val) => {
      if (typeof val === 'number') return val;
      if (typeof val === 'string') {
        const cleaned = val.replace(/,/g, '');
        return parseFloat(cleaned) || 0;
      }
      return 0;
    };
    
    const currentValue = getNumericValue(value);
    const prevValue = previousValue || 0;
    const isIncreased = currentValue > prevValue;
    const isDecreased = currentValue < prevValue;
    const isEqual = Math.abs(currentValue - prevValue) < 0.01;
    
    const formatPrevValue = (val) => {
      if (typeof val === 'number') {
        if (val % 1 !== 0) {
          return val.toFixed(1);
        }
        return val.toLocaleString('id-ID');
      }
      return val || '0';
    };
    
    return (
      <div className="bg-white rounded-lg shadow-md p-6 border-l-4" style={{ borderColor: color }}>
        <div className="flex items-center justify-between">
          <div className="flex-1">
            <p className="text-sm font-medium text-gray-600">{title}</p>
            {loading ? (
              <div className="mt-2 h-8 w-24 bg-gray-200 animate-pulse rounded"></div>
            ) : (
              <>
                <div className="flex items-center gap-2 mt-1">
                  <p className="text-2xl font-bold text-gray-900">
                    {typeof value === 'string' ? value : value.toLocaleString()}
                  </p>
                  {previousDate && !isEqual && (
                    <div className="flex items-center">
                      {isIncreased ? (
                        <ArrowUp className="w-5 h-5 text-green-600" />
                      ) : isDecreased ? (
                        <ArrowDown className="w-5 h-5 text-red-600" />
                      ) : null}
                    </div>
                  )}
                </div>
                {subtitle && (
                  <p className="text-xs text-gray-500 mt-1">{subtitle}</p>
                )}
                {previousDate && (
                  <p className="text-xs text-gray-500 mt-2">
                    sebelumnya {previousDate}: {formatPrevValue(prevValue)}
                  </p>
                )}
              </>
            )}
          </div>
          <div className="p-3 rounded-full" style={{ backgroundColor: `${color}20` }}>
            <Icon className="w-8 h-8" style={{ color }} />
          </div>
        </div>
      </div>
    );
  };

  const sortedData = getSortedData();

  return (
    <div className="min-h-screen bg-gray-50 py-8">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900">Data Dosen SINTA</h1>
          <p className="mt-2 text-sm text-gray-600">
            Daftar dosen dengan data dari SINTA (Science and Technology Index)
          </p>
        </div>

        {/* Stats Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-6 mb-8">
          <StatCard
            title="Total Dosen"
            value={stats.totalDosen}
            icon={Users}
            color="#3B82F6"
            loading={statsLoading}
            previousValue={stats.previousValues?.totalDosen}
            previousDate={stats.previousDate}
          />
          <StatCard
            title="Total Publikasi"
            value={stats.totalPublikasi}
            icon={TrendingUp}
            color="#059669"
            loading={statsLoading}
            previousValue={stats.previousValues?.totalPublikasi}
            previousDate={stats.previousDate}
          />
          <StatCard
            title="Sitasi Google Scholar"
            value={stats.totalSitasiGS}
            icon={Award}
            color="#EF4444"
            subtitle="Total dari GS"
            loading={statsLoading}
            previousValue={stats.previousValues?.totalSitasiGS}
            previousDate={stats.previousDate}
          />
          <StatCard
            title="Sitasi Scopus"
            value={stats.totalSitasiScopus}
            icon={Award}
            color="#F97316"
            subtitle="Total dari Scopus"
            loading={statsLoading}
            previousValue={stats.previousValues?.totalSitasiScopus}
            previousDate={stats.previousDate}
          />
          <StatCard
            title="Rata-rata H-Index"
            value={stats.avgHIndex}
            icon={Award}
            color="#8B5CF6"
            subtitle={`Median: ${stats.medianHIndex}`}
            loading={statsLoading}
            previousValue={stats.previousValues?.avgHIndex}
            previousDate={stats.previousDate}
          />
        </div>

        {/* Data Table with Integrated Filters */}
        <div className="bg-white rounded-lg shadow-md overflow-hidden">
          {/* Table Header */}
          <div className="px-6 py-4 border-b border-gray-200">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-xl font-semibold text-gray-900">Daftar Dosen SINTA</h2>
              <button
                onClick={fetchDosenData}
                className="inline-flex items-center px-3 py-2 border border-gray-300 rounded-md text-sm font-medium text-gray-700 bg-white hover:bg-gray-50"
                disabled={loading}
              >
                <RefreshCw className={`h-4 w-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
                Refresh
              </button>
            </div>

            {/* Filters Section */}
            <div className="space-y-4">
              {/* Search Bar */}
              <div className="relative">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-5 w-5 text-gray-400" />
                <input
                  type="text"
                  placeholder="Cari nama dosen..."
                  value={searchTerm}
                  onChange={handleSearchChange}
                  className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
              </div>

              {/* Faculty and Department Filters */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {/* Faculty Filter */}
                <div className="relative">
                  <label htmlFor="faculty" className="block text-sm font-semibold text-gray-700 mb-2 flex items-center">
                    <Building2 className="w-4 h-4 mr-1.5 text-blue-600" />
                    Fakultas
                  </label>
                  <div className="relative">
                    <select
                      id="faculty"
                      value={selectedFaculty}
                      onChange={handleFacultyChange}
                      className="w-full pl-4 pr-10 py-2.5 border-2 border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 bg-white hover:border-gray-400 transition-all duration-200 appearance-none cursor-pointer shadow-sm"
                      style={{
                        backgroundImage: `url("data:image/svg+xml,%3csvg xmlns='http://www.w3.org/2000/svg' fill='none' viewBox='0 0 20 20'%3e%3cpath stroke='%236b7280' stroke-linecap='round' stroke-linejoin='round' stroke-width='1.5' d='M6 8l4 4 4-4'/%3e%3c/svg%3e")`,
                        backgroundPosition: 'right 0.5rem center',
                        backgroundRepeat: 'no-repeat',
                        backgroundSize: '1.5em 1.5em'
                      }}
                    >
                      <option value="">✨ Semua Fakultas</option>
                      {faculties.map((faculty) => (
                        <option key={faculty} value={faculty}>
                          {faculty}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>

                {/* Department Filter */}
                <div className="relative">
                  <label htmlFor="department" className="block text-sm font-semibold text-gray-700 mb-2 flex items-center">
                    <GraduationCap className="w-4 h-4 mr-1.5 text-indigo-600" />
                    Jurusan
                  </label>
                  <div className="relative">
                    <select
                      id="department"
                      value={selectedDepartment}
                      onChange={handleDepartmentChange}
                      disabled={!selectedFaculty || loadingDepartments}
                      className="w-full pl-4 pr-10 py-2.5 border-2 border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 bg-white hover:border-gray-400 transition-all duration-200 appearance-none cursor-pointer shadow-sm disabled:bg-gray-50 disabled:cursor-not-allowed disabled:border-gray-200 disabled:text-gray-500"
                      style={{
                        backgroundImage: !selectedFaculty || loadingDepartments ? 'none' : `url("data:image/svg+xml,%3csvg xmlns='http://www.w3.org/2000/svg' fill='none' viewBox='0 0 20 20'%3e%3cpath stroke='%236b7280' stroke-linecap='round' stroke-linejoin='round' stroke-width='1.5' d='M6 8l4 4 4-4'/%3e%3c/svg%3e")`,
                        backgroundPosition: 'right 0.5rem center',
                        backgroundRepeat: 'no-repeat',
                        backgroundSize: '1.5em 1.5em'
                      }}
                    >
                      <option value="">
                        {!selectedFaculty ? '🔒 Pilih fakultas terlebih dahulu' : loadingDepartments ? '⏳ Memuat...' : '✨ Semua Jurusan'}
                      </option>
                      {departments.map((dept) => (
                        <option key={dept} value={dept}>
                          {dept}
                        </option>
                      ))}
                    </select>
                  </div>
                  {loadingDepartments && (
                    <div className="flex items-center mt-2">
                      <RefreshCw className="w-3 h-3 text-indigo-500 animate-spin mr-1" />
                      <p className="text-xs text-indigo-600 font-medium">Memuat jurusan...</p>
                    </div>
                  )}
                </div>

                {/* Reset Button */}
                <div className="flex items-end">
                  <button
                    onClick={handleResetFilters}
                    disabled={!selectedFaculty && !selectedDepartment && !searchTerm}
                    className="w-full px-4 py-2.5 bg-gradient-to-r from-gray-100 to-gray-200 text-gray-700 rounded-lg hover:from-gray-200 hover:to-gray-300 transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed font-medium shadow-sm flex items-center justify-center group"
                  >
                    <RefreshCw className="w-4 h-4 mr-2 group-hover:rotate-180 transition-transform duration-300" />
                    Reset Filter
                  </button>
                </div>
              </div>

              {/* Active Filters Display */}
              {(selectedFaculty || selectedDepartment) && (
                <div className="flex items-center flex-wrap gap-2">
                  <span className="text-sm text-gray-600">Filter aktif:</span>
                  {selectedFaculty && (
                    <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-blue-100 text-blue-800">
                      <Building2 className="w-4 h-4 mr-1" />
                      {selectedFaculty}
                    </span>
                  )}
                  {selectedDepartment && (
                    <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-indigo-100 text-indigo-800">
                      <GraduationCap className="w-4 h-4 mr-1" />
                      {selectedDepartment}
                    </span>
                  )}
                </div>
              )}
            </div>
          </div>

          {/* Table Content */}
          <div className="overflow-x-auto">
            {loading ? (
              <div className="flex items-center justify-center py-12">
                <RefreshCw className="h-8 w-8 text-gray-400 animate-spin" />
                <span className="ml-2 text-gray-500">Memuat data...</span>
              </div>
            ) : sortedData.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-12">
                <Users className="h-12 w-12 text-gray-400 mb-4" />
                <p className="text-gray-500">Tidak ada data dosen SINTA ditemukan</p>
              </div>
            ) : (
              <>
                <table className="min-w-full divide-y divide-gray-200">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-100" onClick={() => handleSort('v_nama_dosen')}>
                        Nama Dosen {sortConfig.key === 'v_nama_dosen' && (sortConfig.direction === 'asc' ? '↑' : '↓')}
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Fakultas
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Jurusan
                      </th>
                      <th className="px-6 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-100" onClick={() => handleSort('n_total_publikasi')}>
                        Publikasi {sortConfig.key === 'n_total_publikasi' && (sortConfig.direction === 'asc' ? '↑' : '↓')}
                      </th>
                      <th className="px-6 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-100" onClick={() => handleSort('n_sitasi_gs')}>
                        Sitasi GS {sortConfig.key === 'n_sitasi_gs' && (sortConfig.direction === 'asc' ? '↑' : '↓')}
                      </th>
                      <th className="px-6 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-100" onClick={() => handleSort('n_sitasi_scopus')}>
                        Sitasi Scopus {sortConfig.key === 'n_sitasi_scopus' && (sortConfig.direction === 'asc' ? '↑' : '↓')}
                      </th>
                      <th className="px-6 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-100" onClick={() => handleSort('n_h_index_gs_sinta')}>
                        H-Index GS {sortConfig.key === 'n_h_index_gs_sinta' && (sortConfig.direction === 'asc' ? '↑' : '↓')}
                      </th>
                      <th className="px-6 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-100" onClick={() => handleSort('n_h_index_scopus')}>
                        H-Index Scopus {sortConfig.key === 'n_h_index_scopus' && (sortConfig.direction === 'asc' ? '↑' : '↓')}
                      </th>
                      <th className="px-6 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-100" onClick={() => handleSort('n_skor_sinta')}>
                        Skor SINTA {sortConfig.key === 'n_skor_sinta' && (sortConfig.direction === 'asc' ? '↑' : '↓')}
                      </th>
                      <th className="px-6 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-100" onClick={() => handleSort('n_skor_sinta_3yr')}>
                        Skor SINTA 3 Thn {sortConfig.key === 'n_skor_sinta_3yr' && (sortConfig.direction === 'asc' ? '↑' : '↓')}
                      </th>
                      <th className="px-6 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Last Updated
                      </th>
                      <th className="px-6 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Aksi
                      </th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    {sortedData.map((row, index) => (
                      <tr key={index} className="hover:bg-gray-50">
                        <td className="px-6 py-4 whitespace-nowrap">
                          <div className="flex items-center">
                            <div className="h-10 w-10 bg-blue-100 rounded-full flex items-center justify-center flex-shrink-0">
                              <Users className="h-5 w-5 text-blue-600" />
                            </div>
                            <div className="ml-3">
                              <p className="text-sm font-medium text-gray-900">{row.v_nama_dosen || 'N/A'}</p>
                              {row.v_id_sinta && (
                                <p className="text-xs text-gray-500">SINTA ID: {row.v_id_sinta}</p>
                              )}
                            </div>
                          </div>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-700">
                          {row.v_nama_fakultas || 'N/A'}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                          {row.v_nama_jurusan || 'N/A'}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-center">
                          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
                            {(row.n_total_publikasi || 0).toLocaleString()}
                          </span>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-center">
                          <span className="text-sm font-semibold text-red-600">
                            {(row.n_sitasi_gs || 0).toLocaleString()}
                          </span>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-center">
                          <span className="text-sm font-semibold text-orange-600">
                            {(row.n_sitasi_scopus || 0).toLocaleString()}
                          </span>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-center">
                          <span className="inline-flex items-center px-2 py-1 rounded text-sm font-medium bg-red-100 text-red-800">
                            {row.n_h_index_gs_sinta || 0}
                          </span>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-center">
                          <span className="inline-flex items-center px-2 py-1 rounded text-sm font-medium bg-orange-100 text-orange-800">
                            {row.n_h_index_scopus || 0}
                          </span>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-center">
                          <span className="text-sm font-medium text-purple-600">
                            {(Number(row.n_skor_sinta) || 0).toFixed(2)}
                          </span>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-center">
                          <span className="text-sm font-medium text-indigo-600">
                            {(Number(row.n_skor_sinta_3yr) || 0).toFixed(2)}
                          </span>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-center text-sm text-gray-500">
                          {row.t_tanggal_unduh ? new Date(row.t_tanggal_unduh).toLocaleDateString('id-ID') : 'N/A'}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-center">
                          <div className="flex items-center justify-center space-x-2">
                            {row.v_id_sinta && (
                              <a
                                href={`https://sinta.kemdikbud.go.id/authors/profile/${row.v_id_sinta}`}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="text-indigo-600 hover:text-indigo-900 inline-flex items-center text-sm"
                                title="Lihat profil SINTA"
                              >
                                <ExternalLink className="w-4 h-4 mr-1" />
                                SINTA
                              </a>
                            )}
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>

                {/* Pagination */}
                {pagination && pagination.totalPages > 1 && (
                  <div className="px-6 py-4 border-t border-gray-200 flex items-center justify-between">
                    <div className="text-sm text-gray-700">
                      Menampilkan <span className="font-medium">{((pagination.currentPage - 1) * pagination.perPage) + 1}</span> - <span className="font-medium">{Math.min(pagination.currentPage * pagination.perPage, pagination.totalRecords)}</span> dari <span className="font-medium">{pagination.totalRecords}</span> data
                    </div>
                    <div className="flex space-x-2">
                      <button
                        onClick={() => handlePageChange(pagination.currentPage - 1)}
                        disabled={pagination.currentPage === 1}
                        className="px-4 py-2 border border-gray-300 rounded-md text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        Previous
                      </button>
                      
                      {[...Array(pagination.totalPages)].map((_, i) => {
                        const page = i + 1;
                        if (
                          page === 1 ||
                          page === pagination.totalPages ||
                          (page >= pagination.currentPage - 1 && page <= pagination.currentPage + 1)
                        ) {
                          return (
                            <button
                              key={page}
                              onClick={() => handlePageChange(page)}
                              className={`px-4 py-2 border rounded-md text-sm font-medium ${
                                page === pagination.currentPage
                                  ? 'bg-blue-600 text-white border-blue-600'
                                  : 'border-gray-300 text-gray-700 bg-white hover:bg-gray-50'
                              }`}
                            >
                              {page}
                            </button>
                          );
                        } else if (
                          page === pagination.currentPage - 2 ||
                          page === pagination.currentPage + 2
                        ) {
                          return <span key={page} className="px-2">...</span>;
                        }
                        return null;
                      })}

                      <button
                        onClick={() => handlePageChange(pagination.currentPage + 1)}
                        disabled={pagination.currentPage === pagination.totalPages}
                        className="px-4 py-2 border border-gray-300 rounded-md text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        Next
                      </button>
                    </div>
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default SintaDosen;