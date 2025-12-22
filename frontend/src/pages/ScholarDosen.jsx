import { useState, useEffect } from 'react';
import { Users, TrendingUp, Award, Calendar, ExternalLink, Building2, GraduationCap, RefreshCw, Search, ArrowUp, ArrowDown, Download } from 'lucide-react';
import apiService from '../services/apiService';
import { toast } from 'react-hot-toast';
import Layout from '../components/Layout';
import LoadingOverlay from '../components/LoadingOverlay';

const ScholarDosen = () => {
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
  const [facultyDeptMap, setFacultyDeptMap] = useState({});
  
  const [stats, setStats] = useState({
    totalDosen: 0,
    totalPublikasi: 0,
    totalSitasi: 0,
    avgHIndex: 0,
    medianHIndex: 0,
    previousDate: null,
    previousValues: {}
  });

  const perPage = 20;

  // Fetch mapping on component mount (like dashboard)
  useEffect(() => {
    const fetchMapping = async () => {
      try {
        setLoadingDepartments(true);
        const response = await apiService.getDashboardMapping();
        
        if (response.success && response.data) {
          console.log("✅ Mapping loaded from DB:", response.data);
          setFacultyDeptMap(response.data);
          // Set daftar Fakultas berdasarkan keys dari response
          setFaculties(Object.keys(response.data).sort());
        } else {
          console.error('❌ Invalid mapping response:', response);
        }
      } catch (error) {
        console.error("❌ Failed to load mapping:", error);
      } finally {
        setLoadingDepartments(false);
      }
    };

    fetchMapping();
  }, []);

  // Update departments when faculty changes (using mapping from state)
  useEffect(() => {
    if (selectedFaculty) {
      // Ambil data dari State facultyDeptMap, bukan dari API
      const depts = facultyDeptMap[selectedFaculty] || [];
      setDepartments(depts.sort());
    } else {
      setDepartments([]);
      setSelectedDepartment('');
    }
  }, [selectedFaculty, facultyDeptMap]);

  // Fetch data when filters change
  useEffect(() => {
    fetchDosenData();
  }, [currentPage, searchTerm, selectedFaculty, selectedDepartment]);

  // Fetch stats when filters change
  useEffect(() => {
    fetchStats();
  }, [searchTerm, selectedFaculty, selectedDepartment]);


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

      const response = await apiService.getScholarDosen(params);
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
        toast.error('Gagal mengambil data dosen Google Scholar');
        console.error('Error fetching Scholar dosen data:', response.error);
      }
    } catch (error) {
      console.error('Error fetching Scholar dosen data:', error);
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

      const response = await apiService.getScholarDosenStats(params);
      if (response.success) {
        setStats({
          totalDosen: response.data.totalDosen || 0,
          totalPublikasi: response.data.totalPublikasi || 0,
          totalSitasi: response.data.totalSitasi || 0,
          avgHIndex: response.data.avgHIndex || 0,
          medianHIndex: response.data.medianHIndex || 0,
          previousDate: response.data.previousDate || null,
          previousValues: response.data.previousValues || {}
        });
      } else {
        console.error('Error fetching Scholar dosen stats:', response.error);
      }
    } catch (error) {
      console.error('Error fetching Scholar dosen stats:', error);
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

  const handleExport = async () => {
    try {
      toast.loading('Mengekspor data ke Excel...', { id: 'export' });
      const params = {};
      if (searchTerm) params.search = searchTerm;
      if (selectedFaculty) params.faculty = selectedFaculty;
      if (selectedDepartment) params.department = selectedDepartment;
      
      const result = await apiService.exportScholarDosen(params);
      if (result.success) {
        toast.success('Data berhasil diekspor ke Excel', { id: 'export' });
      } else {
        toast.error('Gagal mengekspor data', { id: 'export' });
      }
    } catch (error) {
      console.error('Export error:', error);
      toast.error('Terjadi kesalahan saat mengekspor data', { id: 'export' });
    }
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
      <div className="bg-white rounded-xl shadow-sm hover:shadow-md border border-gray-200 p-6 transition-all duration-300 group">
        <div className="flex items-start justify-between mb-4">
          <div className="flex-1 min-w-0">
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3">{title}</p>
            {loading ? (
              <div className="h-10 w-32 bg-gray-200 animate-pulse rounded"></div>
            ) : (
              <div className="flex items-baseline gap-2">
                <p className="text-3xl font-bold text-gray-900 leading-tight">
                  {typeof value === 'string' ? value : value.toLocaleString('id-ID')}
                </p>
                {previousDate && !isEqual && (
                  <div className="flex items-center pb-1">
                    {isIncreased ? (
                      <ArrowUp className="w-4 h-4 text-green-600" />
                    ) : isDecreased ? (
                      <ArrowDown className="w-4 h-4 text-red-600" />
                    ) : null}
                  </div>
                )}
              </div>
            )}
          </div>
          <div className="flex-shrink-0 ml-4">
            <div className="w-12 h-12 rounded-lg flex items-center justify-center transition-all duration-300 group-hover:scale-110" style={{ backgroundColor: `${color}15` }}>
              <Icon className="w-6 h-6" style={{ color }} />
            </div>
          </div>
        </div>
        
        {!loading && (
          <div className="space-y-1.5 pt-3 border-t border-gray-100">
            {subtitle && (
              <p className="text-xs font-medium text-gray-600">{subtitle}</p>
            )}
            {previousDate && (
              <p className="text-xs text-gray-500">
                sebelumnya {previousDate}: {formatPrevValue(prevValue)}
              </p>
            )}
          </div>
        )}
      </div>
    );
  };

  const sortedData = getSortedData();

  return (
    <>
      <LoadingOverlay 
        isLoading={loading} 
        message="Memuat data dosen Google Scholar..."
        subMessage="Mohon tunggu sebentar"
      />
      <Layout
        title="Data Dosen Google Scholar"
      description="Daftar dosen dengan data dari Google Scholar"
      headerActions={
        <>
          <button
            onClick={handleExport}
            className="inline-flex items-center px-4 py-2.5 border border-green-300 rounded-lg text-sm font-medium text-green-700 bg-white hover:bg-green-50 hover:border-green-400 shadow-sm hover:shadow transition-all duration-200"
            disabled={loading}
          >
            <Download className="h-4 w-4 mr-2" />
            Export Excel
          </button>
          <button
            onClick={fetchDosenData}
            className="inline-flex items-center px-4 py-2.5 border border-gray-300 rounded-lg text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 hover:border-gray-400 shadow-sm hover:shadow transition-all duration-200"
            disabled={loading}
          >
            <RefreshCw className={`h-4 w-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </>
      }
    >

        {/* Stats Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
          <StatCard
            title="Total Dosen"
            value={stats.totalDosen}
            icon={Users}
            color="#DC2626"
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
            title="Total Sitasi"
            value={stats.totalSitasi}
            icon={Award}
            color="#D97706"
            loading={statsLoading}
            previousValue={stats.previousValues?.totalSitasi}
            previousDate={stats.previousDate}
          />
          <StatCard
            title="Rata-rata H-Index"
            value={stats.avgHIndex}
            icon={Award}
            color="#7C3AED"
            subtitle={`Median: ${stats.medianHIndex}`}
            loading={statsLoading}
            previousValue={stats.previousValues?.avgHIndex}
            previousDate={stats.previousDate}
          />
        </div>

        {/* Data Table with Integrated Filters */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden hover:shadow-md transition-shadow duration-300">
          {/* Table Header */}
          <div className="px-6 py-5 border-b border-gray-200 bg-gray-50/50">
            <h2 className="text-xl font-semibold text-gray-900">Daftar Dosen Google Scholar</h2>

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
                  className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-red-500 focus:border-transparent"
                />
              </div>

              {/* Faculty and Department Filters */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {/* Faculty Filter */}
                <div className="relative">
                  <label htmlFor="faculty" className="block text-sm font-semibold text-gray-700 mb-2 flex items-center">
                    <Building2 className="w-4 h-4 mr-1.5 text-red-600" />
                    Fakultas
                  </label>
                  <div className="relative">
                    <select
                      id="faculty"
                      value={selectedFaculty}
                      onChange={handleFacultyChange}
                      className="w-full pl-4 pr-10 py-2.5 border-2 border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-red-500 focus:border-red-500 bg-white hover:border-gray-400 transition-all duration-200 appearance-none cursor-pointer shadow-sm"
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
                    <GraduationCap className="w-4 h-4 mr-1.5 text-blue-600" />
                    Prodi
                  </label>
                  <div className="relative">
                    <select
                      id="department"
                      value={selectedDepartment}
                      onChange={handleDepartmentChange}
                      disabled={!selectedFaculty}
                      className="w-full pl-4 pr-10 py-2.5 border-2 border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 bg-white hover:border-gray-400 transition-all duration-200 appearance-none cursor-pointer shadow-sm disabled:bg-gray-50 disabled:cursor-not-allowed disabled:border-gray-200 disabled:text-gray-500"
                      style={{
                        backgroundImage: !selectedFaculty ? 'none' : `url("data:image/svg+xml,%3csvg xmlns='http://www.w3.org/2000/svg' fill='none' viewBox='0 0 20 20'%3e%3cpath stroke='%236b7280' stroke-linecap='round' stroke-linejoin='round' stroke-width='1.5' d='M6 8l4 4 4-4'/%3e%3c/svg%3e")`,
                        backgroundPosition: 'right 0.5rem center',
                        backgroundRepeat: 'no-repeat',
                        backgroundSize: '1.5em 1.5em'
                      }}
                    >
                      <option value="">
                        {!selectedFaculty ? '🔒 Pilih fakultas terlebih dahulu' : '✨ Semua Prodi'}
                      </option>
                      {departments.map((dept) => (
                        <option key={dept} value={dept}>
                          {dept}
                        </option>
                      ))}
                    </select>
                  </div>
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
                    <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-red-100 text-red-800">
                      <Building2 className="w-4 h-4 mr-1" />
                      {selectedFaculty}
                    </span>
                  )}
                  {selectedDepartment && (
                    <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-blue-100 text-blue-800">
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
                <p className="text-gray-500">Tidak ada data dosen Google Scholar ditemukan</p>
              </div>
            ) : (
              <>
                <table className="min-w-full divide-y divide-gray-200">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-6 py-4 text-left text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-100 min-w-[200px]" onClick={() => handleSort('v_nama_dosen')}>
                        <div className="flex items-center gap-2">
                          <span>Nama Dosen</span>
                          {sortConfig.key === 'v_nama_dosen' && (sortConfig.direction === 'asc' ? '↑' : '↓')}
                        </div>
                      </th>
                      <th className="px-6 py-4 text-left text-xs font-medium text-gray-500 uppercase tracking-wider min-w-[150px]">
                        Fakultas
                      </th>
                      <th className="px-6 py-4 text-left text-xs font-medium text-gray-500 uppercase tracking-wider min-w-[150px]">
                        Prodi
                      </th>
                      <th className="px-6 py-4 text-center text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-100" onClick={() => handleSort('n_total_publikasi')}>
                        <div className="flex items-center justify-center gap-2">
                          <span>Publikasi</span>
                          {sortConfig.key === 'n_total_publikasi' && (sortConfig.direction === 'asc' ? '↑' : '↓')}
                        </div>
                      </th>
                      <th className="px-6 py-4 text-center text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-100" onClick={() => handleSort('n_total_sitasi_gs')}>
                        <div className="flex items-center justify-center gap-2">
                          <span>Sitasi</span>
                          {sortConfig.key === 'n_total_sitasi_gs' && (sortConfig.direction === 'asc' ? '↑' : '↓')}
                        </div>
                      </th>
                      <th className="px-6 py-4 text-center text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-100" onClick={() => handleSort('n_total_sitasi_gs2020')}>
                        <div className="flex items-center justify-center gap-2">
                          <span>Sitasi (2020)</span>
                          {sortConfig.key === 'n_total_sitasi_gs2020' && (sortConfig.direction === 'asc' ? '↑' : '↓')}
                        </div>
                      </th>
                      <th className="px-6 py-4 text-center text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-100" onClick={() => handleSort('n_h_index_gs')}>
                        <div className="flex items-center justify-center gap-2">
                          <span>H-Index</span>
                          {sortConfig.key === 'n_h_index_gs' && (sortConfig.direction === 'asc' ? '↑' : '↓')}
                        </div>
                      </th>
                      <th className="px-6 py-4 text-center text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-100" onClick={() => handleSort('n_h_index_gs2020')}>
                        <div className="flex items-center justify-center gap-2">
                          <span>H-Index (2020)</span>
                          {sortConfig.key === 'n_h_index_gs2020' && (sortConfig.direction === 'asc' ? '↑' : '↓')}
                        </div>
                      </th>
                      <th className="px-6 py-4 text-center text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-100" onClick={() => handleSort('n_i10_index_gs')}>
                        <div className="flex items-center justify-center gap-2">
                          <span>i10-Index</span>
                          {sortConfig.key === 'n_i10_index_gs' && (sortConfig.direction === 'asc' ? '↑' : '↓')}
                        </div>
                      </th>
                      <th className="px-6 py-4 text-center text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-100" onClick={() => handleSort('n_i10_index_gs2020')}>
                        <div className="flex items-center justify-center gap-2">
                          <span>i10-Index (2020)</span>
                          {sortConfig.key === 'n_i10_index_gs2020' && (sortConfig.direction === 'asc' ? '↑' : '↓')}
                        </div>
                      </th>
                      <th className="px-6 py-4 text-center text-xs font-medium text-gray-500 uppercase tracking-wider min-w-[120px]">
                        Last Updated
                      </th>
                      <th className="px-6 py-4 text-center text-xs font-medium text-gray-500 uppercase tracking-wider min-w-[100px]">
                        Aksi
                      </th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    {sortedData.map((row, index) => (
                      <tr key={index} className="hover:bg-gray-50 transition-colors">
                        <td className="px-6 py-4">
                          <div className="flex items-center min-w-[200px]">
                            <div className="h-10 w-10 bg-red-100 rounded-full flex items-center justify-center flex-shrink-0">
                              <Users className="h-5 w-5 text-red-600" />
                            </div>
                            <div className="ml-3 flex-1 min-w-0">
                              <p className="text-sm font-medium text-gray-900 truncate" title={row.v_nama_dosen || 'N/A'}>
                                {row.v_nama_dosen || 'N/A'}
                              </p>
                              {row.v_id_googleScholar && (
                                <p className="text-xs text-gray-500 mt-0.5">ID: {row.v_id_googleScholar}</p>
                              )}
                            </div>
                          </div>
                        </td>
                        <td className="px-6 py-4">
                          <div className="max-w-[200px]">
                            <p className="text-sm text-gray-700 truncate" title={row.v_nama_fakultas || 'N/A'}>
                              {row.v_nama_fakultas || 'N/A'}
                            </p>
                          </div>
                        </td>
                        <td className="px-6 py-4">
                          <div className="max-w-[200px]">
                            <p className="text-sm text-gray-900 truncate" title={row.v_nama_jurusan || 'N/A'}>
                              {row.v_nama_jurusan || 'N/A'}
                            </p>
                          </div>
                        </td>
                        <td className="px-6 py-4 text-center">
                          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
                            {(row.n_total_publikasi || 0).toLocaleString()}
                          </span>
                        </td>
                        <td className="px-6 py-4 text-center">
                          <span className="text-sm font-semibold text-green-600">
                            {(row.n_total_sitasi_gs || 0).toLocaleString()}
                          </span>
                        </td>
                        <td className="px-6 py-4 text-center">
                          <span className="text-sm font-semibold text-teal-600">
                            {(row.n_total_sitasi_gs2020 || 0).toLocaleString()}
                          </span>
                        </td>
                        <td className="px-6 py-4 text-center">
                          <span className="inline-flex items-center px-2 py-1 rounded text-xs font-medium bg-yellow-100 text-yellow-800">
                            {row.n_h_index_gs || 0}
                          </span>
                        </td>
                        <td className="px-6 py-4 text-center">
                          <span className="inline-flex items-center px-2 py-1 rounded text-xs font-medium bg-amber-100 text-amber-800">
                            {row.n_h_index_gs2020 || 0}
                          </span>
                        </td>
                        <td className="px-6 py-4 text-center">
                          <span className="inline-flex items-center px-2 py-1 rounded text-xs font-medium bg-purple-100 text-purple-800">
                            {row.n_i10_index_gs || 0}
                          </span>
                        </td>
                        <td className="px-6 py-4 text-center">
                          <span className="inline-flex items-center px-2 py-1 rounded text-xs font-medium bg-violet-100 text-violet-800">
                            {row.n_i10_index_gs2020 || 0}
                          </span>
                        </td>
                        <td className="px-6 py-4 text-center">
                          <span className="text-xs text-gray-500">
                            {row.t_tanggal_unduh ? new Date(row.t_tanggal_unduh).toLocaleDateString('id-ID', { day: '2-digit', month: 'short', year: 'numeric' }) : 'N/A'}
                          </span>
                        </td>
                        <td className="px-6 py-4 text-center">
                          <div className="flex items-center justify-center">
                            {row.v_link_url && (
                              <a
                                href={row.v_link_url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="text-red-600 hover:text-red-900 inline-flex items-center text-xs whitespace-nowrap"
                                title="Lihat profil Google Scholar"
                              >
                                <ExternalLink className="w-3.5 h-3.5 mr-1" />
                                Scholar
                              </a>
                            )}
                            {row.v_id_googleScholar && !row.v_link_url && (
                              <a
                                href={`https://scholar.google.com/citations?user=${row.v_id_googleScholar}`}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="text-red-600 hover:text-red-900 inline-flex items-center text-xs whitespace-nowrap"
                                title="Lihat profil Google Scholar"
                              >
                                <ExternalLink className="w-3.5 h-3.5 mr-1" />
                                Scholar
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
                                  ? 'bg-red-600 text-white border-red-600'
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
    </Layout>
    </>
  );
};

export default ScholarDosen;