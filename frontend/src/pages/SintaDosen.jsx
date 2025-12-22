import { useState, useEffect } from 'react';
import { Users, TrendingUp, Award, Calendar, ExternalLink, Building2, GraduationCap, RefreshCw, Search, ArrowUp, ArrowDown, Download } from 'lucide-react';
import apiService from '../services/apiService';
import { toast } from 'react-hot-toast';
import Layout from '../components/Layout';
import LoadingOverlay from '../components/LoadingOverlay';

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
  const [facultyDeptMap, setFacultyDeptMap] = useState({});
  
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

  const handleExport = async () => {
    try {
      toast.loading('Mengekspor data ke Excel...', { id: 'export' });
      const params = {};
      if (searchTerm) params.search = searchTerm;
      if (selectedFaculty) params.faculty = selectedFaculty;
      if (selectedDepartment) params.department = selectedDepartment;
      
      const result = await apiService.exportSintaDosen(params);
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
        message="Memuat data dosen SINTA..."
        subMessage="Mohon tunggu sebentar"
      />
      <Layout
        title="Data Dosen SINTA"
        description="Daftar dosen dengan data dari SINTA (Science and Technology Index)"
      headerActions={
        <>
          <button
            onClick={handleExport}
            className="btn-apple-success"
            disabled={loading}
          >
            <Download className="h-4 w-4 mr-2" />
            Export Excel
          </button>
          <button
            onClick={fetchDosenData}
            className="btn-apple-secondary"
            disabled={loading}
          >
            <RefreshCw className={`h-4 w-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </>
      }
    >

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

        {/* Data Table with Integrated Filters - Apple Style */}
        <div className="apple-card overflow-hidden animate-slide-up-apple">
          {/* Table Header */}
          <div className="px-8 py-6 border-b border-[#E5E5EA] bg-[#F5F5F7]">
            <h2 
              className="text-2xl font-semibold text-[#1D1D1F] mb-2"
              style={{ letterSpacing: '-0.022em' }}
            >
              Daftar Dosen SINTA
            </h2>

            {/* Filters Section */}
            <div className="space-y-4">
              {/* Search Bar - Apple Style */}
              <div className="relative">
                <Search className="absolute left-4 top-1/2 transform -translate-y-1/2 h-5 w-5 text-[#86868B]" />
                <input
                  type="text"
                  placeholder="Cari nama dosen..."
                  value={searchTerm}
                  onChange={handleSearchChange}
                  className="input-apple pl-12 search-expand-apple"
                />
              </div>

              {/* Faculty and Department Filters */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {/* Faculty Filter - Apple Style */}
                <div className="relative">
                  <label 
                    htmlFor="faculty" 
                    className="block text-sm font-semibold text-[#1D1D1F] mb-2 flex items-center"
                    style={{ letterSpacing: '-0.011em' }}
                  >
                    <Building2 className="w-4 h-4 mr-2 text-[#0A84FF]" />
                    Fakultas
                  </label>
                  <div className="relative">
                    <select
                      id="faculty"
                      value={selectedFaculty}
                      onChange={handleFacultyChange}
                      className="input-apple pr-12 cursor-pointer"
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

                {/* Department Filter - Apple Style */}
                <div className="relative">
                  <label 
                    htmlFor="department" 
                    className="block text-sm font-semibold text-[#1D1D1F] mb-2 flex items-center"
                    style={{ letterSpacing: '-0.011em' }}
                  >
                    <GraduationCap className="w-4 h-4 mr-2 text-[#0A84FF]" />
                    Prodi
                  </label>
                  <div className="relative">
                    <select
                      id="department"
                      value={selectedDepartment}
                      onChange={handleDepartmentChange}
                      disabled={!selectedFaculty}
                      className="input-apple pr-12 cursor-pointer disabled:bg-[#F5F5F7] disabled:cursor-not-allowed disabled:border-[#D2D2D7] disabled:text-[#86868B]"
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
                <table className="w-full border-collapse">
                  <thead>
                    <tr className="bg-[#F5F5F7] border-b-2 border-[#E5E5EA]">
                      {/* Kolom 1: Nama Dosen */}
                      <th 
                        className="px-4 py-3 text-left text-xs font-semibold text-[#1D1D1F] uppercase tracking-wider cursor-pointer hover:bg-[#E5E5EA] transition-colors"
                        onClick={() => handleSort('v_nama_dosen')}
                      >
                        <div className="flex items-center gap-2">
                          <span>Nama Dosen</span>
                          {sortConfig.key === 'v_nama_dosen' && (sortConfig.direction === 'asc' ? '↑' : '↓')}
                        </div>
                      </th>
                      {/* Kolom 2: Fakultas */}
                      <th className="px-4 py-3 text-left text-xs font-semibold text-[#1D1D1F] uppercase tracking-wider min-w-[140px]">Fakultas</th>
                      {/* Kolom 3: Prodi */}
                      <th className="px-4 py-3 text-left text-xs font-semibold text-[#1D1D1F] uppercase tracking-wider min-w-[160px]">Prodi</th>
                      {/* Kolom 4: Publikasi */}
                      <th 
                        className="px-4 py-3 text-center text-xs font-semibold text-[#1D1D1F] uppercase tracking-wider cursor-pointer hover:bg-[#E5E5EA] transition-colors min-w-[100px]"
                        onClick={() => handleSort('n_total_publikasi')}
                      >
                        <div className="flex items-center justify-center gap-2">
                          <span>Publikasi</span>
                          {sortConfig.key === 'n_total_publikasi' && (sortConfig.direction === 'asc' ? '↑' : '↓')}
                        </div>
                      </th>
                      {/* Kolom 5: Sitasi GS */}
                      <th 
                        className="px-4 py-3 text-center text-xs font-semibold text-[#1D1D1F] uppercase tracking-wider cursor-pointer hover:bg-[#E5E5EA] transition-colors min-w-[100px]"
                        onClick={() => handleSort('n_sitasi_gs')}
                      >
                        <div className="flex items-center justify-center gap-2">
                          <span>Sitasi GS</span>
                          {sortConfig.key === 'n_sitasi_gs' && (sortConfig.direction === 'asc' ? '↑' : '↓')}
                        </div>
                      </th>
                      {/* Kolom 6: Sitasi Scopus */}
                      <th 
                        className="px-4 py-3 text-center text-xs font-semibold text-[#1D1D1F] uppercase tracking-wider cursor-pointer hover:bg-[#E5E5EA] transition-colors min-w-[120px]"
                        onClick={() => handleSort('n_sitasi_scopus')}
                      >
                        <div className="flex items-center justify-center gap-2">
                          <span>Sitasi Scopus</span>
                          {sortConfig.key === 'n_sitasi_scopus' && (sortConfig.direction === 'asc' ? '↑' : '↓')}
                        </div>
                      </th>
                      {/* Kolom 7: H-Index GS */}
                      <th 
                        className="px-4 py-3 text-center text-xs font-semibold text-[#1D1D1F] uppercase tracking-wider cursor-pointer hover:bg-[#E5E5EA] transition-colors min-w-[100px]"
                        onClick={() => handleSort('n_h_index_gs_sinta')}
                      >
                        <div className="flex items-center justify-center gap-2">
                          <span>H-Index GS</span>
                          {sortConfig.key === 'n_h_index_gs_sinta' && (sortConfig.direction === 'asc' ? '↑' : '↓')}
                        </div>
                      </th>
                      {/* Kolom 8: H-Index Scopus */}
                      <th 
                        className="px-4 py-3 text-center text-xs font-semibold text-[#1D1D1F] uppercase tracking-wider cursor-pointer hover:bg-[#E5E5EA] transition-colors min-w-[120px]"
                        onClick={() => handleSort('n_h_index_scopus')}
                      >
                        <div className="flex items-center justify-center gap-2">
                          <span>H-Index Scopus</span>
                          {sortConfig.key === 'n_h_index_scopus' && (sortConfig.direction === 'asc' ? '↑' : '↓')}
                        </div>
                      </th>
                      {/* Kolom 9: Skor SINTA */}
                      <th 
                        className="px-4 py-3 text-center text-xs font-semibold text-[#1D1D1F] uppercase tracking-wider cursor-pointer hover:bg-[#E5E5EA] transition-colors min-w-[100px]"
                        onClick={() => handleSort('n_skor_sinta')}
                      >
                        <div className="flex items-center justify-center gap-2">
                          <span>Skor SINTA</span>
                          {sortConfig.key === 'n_skor_sinta' && (sortConfig.direction === 'asc' ? '↑' : '↓')}
                        </div>
                      </th>
                      {/* Kolom 10: Skor SINTA 3 Thn */}
                      <th 
                        className="px-4 py-3 text-center text-xs font-semibold text-[#1D1D1F] uppercase tracking-wider cursor-pointer hover:bg-[#E5E5EA] transition-colors min-w-[120px]"
                        onClick={() => handleSort('n_skor_sinta_3yr')}
                      >
                        <div className="flex items-center justify-center gap-2">
                          <span>Skor SINTA 3 Thn</span>
                          {sortConfig.key === 'n_skor_sinta_3yr' && (sortConfig.direction === 'asc' ? '↑' : '↓')}
                        </div>
                      </th>
                      {/* Kolom 11: Last Updated */}
                      <th className="px-4 py-3 text-center text-xs font-semibold text-[#1D1D1F] uppercase tracking-wider min-w-[120px]">Last Updated</th>
                      {/* Kolom 12: Aksi */}
                      <th className="px-4 py-3 text-center text-xs font-semibold text-[#1D1D1F] uppercase tracking-wider min-w-[100px]">Aksi</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#E5E5EA]">
                    {sortedData.map((row, index) => (
                      <tr 
                        key={index} 
                        className="hover:bg-[#F5F5F7] transition-colors border-b border-[#E5E5EA]"
                      >
                        {/* Kolom 1: Nama Dosen */}
                        <td className="px-4 py-3">
                          <div className="flex items-center">
                            <div className="h-9 w-9 bg-[#0A84FF]/10 rounded-full flex items-center justify-center flex-shrink-0 mr-3">
                              <Users className="h-4 w-4 text-[#0A84FF]" />
                            </div>
                            <div className="flex-1 min-w-0">
                              <p 
                                className="text-sm font-semibold text-[#1D1D1F] truncate"
                                title={row.v_nama_dosen || 'N/A'}
                              >
                                {row.v_nama_dosen || 'N/A'}
                              </p>
                              {row.v_id_sinta && (
                                <p className="text-xs text-[#6E6E73] mt-0.5">
                                  ID: {row.v_id_sinta}
                                </p>
                              )}
                            </div>
                          </div>
                        </td>
                        {/* Kolom 2: Fakultas */}
                        <td className="px-4 py-3">
                          <p className="text-sm text-[#1D1D1F] truncate" title={row.v_nama_fakultas || 'N/A'}>
                            {row.v_nama_fakultas || '-'}
                          </p>
                        </td>
                        {/* Kolom 3: Prodi */}
                        <td className="px-4 py-3">
                          <p className="text-sm text-[#1D1D1F] truncate" title={row.v_nama_jurusan || 'N/A'}>
                            {row.v_nama_jurusan || 'N/A'}
                          </p>
                        </td>
                        {/* Kolom 4: Publikasi */}
                        <td className="px-4 py-3 text-center">
                          <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold bg-blue-100 text-blue-800">
                            {(row.n_total_publikasi || 0).toLocaleString()}
                          </span>
                        </td>
                        {/* Kolom 5: Sitasi GS */}
                        <td className="px-4 py-3 text-center">
                          <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold bg-blue-100 text-blue-800">
                            {(row.n_sitasi_gs || 0).toLocaleString()}
                          </span>
                        </td>
                        {/* Kolom 6: Sitasi Scopus */}
                        <td className="px-4 py-3 text-center">
                          <span className="text-sm font-semibold text-[#FF7A59]">
                            {(row.n_sitasi_scopus || 0).toLocaleString()}
                          </span>
                        </td>
                        {/* Kolom 7: H-Index GS */}
                        <td className="px-4 py-3 text-center">
                          <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold bg-orange-100 text-orange-800">
                            {row.n_h_index_gs_sinta || 0}
                          </span>
                        </td>
                        {/* Kolom 8: H-Index Scopus */}
                        <td className="px-4 py-3 text-center">
                          <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold bg-red-100 text-red-800">
                            {row.n_h_index_scopus || 0}
                          </span>
                        </td>
                        {/* Kolom 9: Skor SINTA */}
                        <td className="px-4 py-3 text-center">
                          <span className="text-sm font-semibold text-[#0A84FF]">
                            {(Number(row.n_skor_sinta) || 0).toFixed(2)}
                          </span>
                        </td>
                        {/* Kolom 10: Skor SINTA 3 Thn */}
                        <td className="px-4 py-3 text-center">
                          <span className="text-sm font-semibold text-[#0A84FF]">
                            {(Number(row.n_skor_sinta_3yr) || 0).toFixed(2)}
                          </span>
                        </td>
                        {/* Kolom 11: Last Updated */}
                        <td className="px-4 py-3 text-center">
                          <span className="text-xs text-[#6E6E73] whitespace-nowrap">
                            {row.t_tanggal_unduh ? new Date(row.t_tanggal_unduh).toLocaleDateString('id-ID', { day: '2-digit', month: 'short', year: 'numeric' }) : '-'}
                          </span>
                        </td>
                        {/* Kolom 12: Aksi */}
                        <td className="px-4 py-3 text-center">
                          {(row.v_link_url || row.v_id_sinta) && (
                            <a
                              href={row.v_link_url || `https://sinta.kemdiktisaintek.go.id/authors/profile/${row.v_id_sinta}`}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="inline-flex items-center px-2.5 py-1.5 text-xs font-medium text-[#1D1D1F] bg-[#F5F5F7] rounded-lg hover:bg-[#E5E5EA] transition-colors"
                              title="Lihat profil SINTA"
                            >
                              <ExternalLink className="w-3.5 h-3.5 mr-1" />
                              SINTA
                            </a>
                          )}
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
    </Layout>
    </>
  );
};

export default SintaDosen;