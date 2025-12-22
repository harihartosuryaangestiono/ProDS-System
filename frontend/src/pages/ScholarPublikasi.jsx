import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Users, TrendingUp, Award, Calendar, ExternalLink, Building2, GraduationCap, RefreshCw, Search, ArrowUp, ArrowDown, FileText, Download } from 'lucide-react';
import apiService from '../services/apiService';
import { toast } from 'react-hot-toast';
import Layout from '../components/Layout';
import LoadingOverlay from '../components/LoadingOverlay';

const ScholarPublikasi = () => {
  const navigate = useNavigate();
  const [publikasiData, setPublikasiData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [statsLoading, setStatsLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [currentPage, setCurrentPage] = useState(1);
  const [pagination, setPagination] = useState(null);
  const [sortConfig, setSortConfig] = useState({ key: null, direction: 'asc' });
  const [filterTipe, setFilterTipe] = useState('all');
  const [yearStart, setYearStart] = useState('');
  const [yearEnd, setYearEnd] = useState('');
  
  // Faculty and Department filters
  const [faculties, setFaculties] = useState([]);
  const [departments, setDepartments] = useState([]);
  const [selectedFaculty, setSelectedFaculty] = useState('');
  const [selectedDepartment, setSelectedDepartment] = useState('');
  const [loadingDepartments, setLoadingDepartments] = useState(false);
  const [facultyDeptMap, setFacultyDeptMap] = useState({});
  
  const [aggregateStats, setAggregateStats] = useState({
    totalPublikasi: 0,
    totalSitasi: 0,
    avgSitasi: 0,
    medianSitasi: 0,
    recentPublikasi: 0,
    previousDate: null,
    previousValues: {}
  });
  const perPage = 20;

  const publikasiTypes = [
    { value: 'all', label: 'Semua Tipe' },
    { value: 'artikel', label: 'Artikel' },
    { value: 'prosiding', label: 'Prosiding' },
    { value: 'buku', label: 'Buku' },
    { value: 'penelitian', label: 'Penelitian' },
    { value: 'lainnya', label: 'Lainnya' }
  ];

  const currentYear = new Date().getFullYear();
  const yearOptions = [];
  for (let year = currentYear; year >= 1990; year--) {
    yearOptions.push(year);
  }

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

  useEffect(() => {
    const token = localStorage.getItem('token');
    if (!token) {
      navigate('/login');
      return;
    }
    fetchPublikasiData();
  }, [currentPage, searchTerm, filterTipe, yearStart, yearEnd, selectedFaculty, selectedDepartment]);

  useEffect(() => {
    fetchAggregateStats();
  }, [searchTerm, filterTipe, yearStart, yearEnd, selectedFaculty, selectedDepartment]);


  const fetchAggregateStats = async () => {
    try {
      setStatsLoading(true);
      
      const params = { search: searchTerm };
      
      if (filterTipe !== 'all') params.tipe = filterTipe;
      if (yearStart) params.year_start = yearStart;
      if (yearEnd) params.year_end = yearEnd;
      if (selectedFaculty) params.faculty = selectedFaculty;
      if (selectedDepartment) params.department = selectedDepartment;
      
      const response = await apiService.getScholarPublikasiStats(params);

      if (response.success) {
        const fullParams = {
          page: 1,
          per_page: 10000,
          search: searchTerm
        };
        
        if (filterTipe !== 'all') fullParams.tipe = filterTipe;
        if (yearStart) fullParams.year_start = yearStart;
        if (yearEnd) fullParams.year_end = yearEnd;
        if (selectedFaculty) fullParams.faculty = selectedFaculty;
        if (selectedDepartment) fullParams.department = selectedDepartment;
        
        const fullResponse = await apiService.getScholarPublikasi(fullParams);
        const allData = fullResponse.success ? (fullResponse.data.data || []) : [];
        const recentPublikasi = allData.filter(pub => {
          const year = parseInt(pub.v_tahun_publikasi);
          return year >= currentYear - 2;
        }).length;

        setAggregateStats({
          totalPublikasi: response.data.totalPublikasi || 0,
          totalSitasi: response.data.totalSitasi || 0,
          avgSitasi: response.data.avgSitasi || 0,
          medianSitasi: response.data.medianSitasi || 0,
          recentPublikasi,
          previousDate: response.data.previousDate || null,
          previousValues: response.data.previousValues || {}
        });
      } else {
        await fetchAllDataForStats();
      }
    } catch (error) {
      console.error('Error fetching aggregate stats:', error);
      await fetchAllDataForStats();
    } finally {
      setStatsLoading(false);
    }
  };

  const fetchAllDataForStats = async () => {
    try {
      const params = {
        page: 1,
        per_page: 10000,
        search: searchTerm
      };
      
      if (filterTipe !== 'all') params.tipe = filterTipe;
      if (yearStart) params.year_start = yearStart;
      if (yearEnd) params.year_end = yearEnd;
      if (selectedFaculty) params.faculty = selectedFaculty;
      if (selectedDepartment) params.department = selectedDepartment;
      
      const response = await apiService.getScholarPublikasi(params);

      if (response.success) {
        const allData = response.data.data || [];
        const totalPublikasi = response.data.pagination?.total || allData.length;
        const totalSitasi = allData.reduce((sum, pub) => sum + (pub.n_total_sitasi || 0), 0);
        const avgSitasi = allData.length > 0 ? (totalSitasi / allData.length).toFixed(1) : 0;
        
        const sitasiValues = allData.map(p => p.n_total_sitasi || 0).sort((a, b) => a - b);
        const medianSitasi = sitasiValues.length > 0 
          ? sitasiValues[Math.floor(sitasiValues.length / 2)] 
          : 0;
        
        const recentPublikasi = allData.filter(pub => {
          const year = parseInt(pub.v_tahun_publikasi);
          return year >= currentYear - 2;
        }).length;

        setAggregateStats({
          totalPublikasi,
          totalSitasi,
          avgSitasi,
          medianSitasi,
          recentPublikasi
        });
      }
    } catch (error) {
      console.error('Error fetching all data for stats:', error);
    }
  };

  const fetchPublikasiData = async () => {
    try {
      setLoading(true);
      const params = {
        page: currentPage,
        per_page: perPage,
        search: searchTerm
      };
      
      if (filterTipe !== 'all') params.tipe = filterTipe;
      if (yearStart) params.year_start = yearStart;
      if (yearEnd) params.year_end = yearEnd;
      if (selectedFaculty) params.faculty = selectedFaculty;
      if (selectedDepartment) params.department = selectedDepartment;
      
      const response = await apiService.getScholarPublikasi(params);

      if (response.success) {
        setPublikasiData(response.data.data || []);
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
        toast.error('Gagal mengambil data publikasi Google Scholar');
        console.error('Error fetching Scholar publikasi data:', response.error);
      }
    } catch (error) {
      toast.error('Terjadi kesalahan saat mengambil data');
      console.error('Error fetching Scholar publikasi data:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleSearchChange = (e) => {
    setSearchTerm(e.target.value);
    setCurrentPage(1);
  };

  const handleFilterChange = (e) => {
    setFilterTipe(e.target.value);
    setCurrentPage(1);
  };

  const handleYearStartChange = (e) => {
    setYearStart(e.target.value);
    setCurrentPage(1);
  };

  const handleYearEndChange = (e) => {
    setYearEnd(e.target.value);
    setCurrentPage(1);
  };

  const handleFacultyChange = (e) => {
    const faculty = e.target.value;
    setSelectedFaculty(faculty);
    setSelectedDepartment('');
    setCurrentPage(1);
  };

  const handleDepartmentChange = (e) => {
    setSelectedDepartment(e.target.value);
    setCurrentPage(1);
  };

  const handleResetFilters = () => {
    setYearStart('');
    setYearEnd('');
    setFilterTipe('all');
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
      if (filterTipe !== 'all') params.tipe = filterTipe;
      if (yearStart) params.year_start = yearStart;
      if (yearEnd) params.year_end = yearEnd;
      if (selectedFaculty) params.faculty = selectedFaculty;
      if (selectedDepartment) params.department = selectedDepartment;
      
      const result = await apiService.exportScholarPublikasi(params);
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

  const handlePageChange = (page) => {
    setCurrentPage(page);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const handleSort = (key) => {
    let direction = 'asc';
    if (sortConfig.key === key && sortConfig.direction === 'asc') {
      direction = 'desc';
    }
    setSortConfig({ key, direction });
  };

  const getSortedData = () => {
    if (!sortConfig.key) return publikasiData;

    return [...publikasiData].sort((a, b) => {
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

  const formatPages = (pages) => {
    const p = pages ? String(pages).trim() : '';
    // Jika ada isinya dan bukan "N/A", tambahkan prefix "pp."
    if (p && p.toLowerCase() !== 'n/a') {
      return `pp. ${p}`;
    }
    return '-';
  };

  const sortedData = getSortedData();

  return (
    <>
      <LoadingOverlay 
        isLoading={loading} 
        message="Memuat data publikasi Google Scholar..."
        subMessage="Mohon tunggu sebentar"
      />
      <Layout
        title="Data Publikasi Google Scholar"
      description="Daftar publikasi dengan data dari Google Scholar"
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
            onClick={fetchPublikasiData}
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
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
          <StatCard
            title="Total Publikasi"
            value={aggregateStats.totalPublikasi}
            icon={FileText}
            color="#DC2626"
            loading={statsLoading}
            previousValue={aggregateStats.previousValues?.totalPublikasi}
            previousDate={aggregateStats.previousDate}
          />
          <StatCard
            title="Total Sitasi"
            value={aggregateStats.totalSitasi}
            icon={Award}
            color="#059669"
            loading={statsLoading}
            previousValue={aggregateStats.previousValues?.totalSitasi}
            previousDate={aggregateStats.previousDate}
          />
          <StatCard
            title="Rata-rata Sitasi"
            value={aggregateStats.avgSitasi}
            icon={Award}
            color="#D97706"
            subtitle={`Median: ${aggregateStats.medianSitasi}`}
            loading={statsLoading}
            previousValue={aggregateStats.previousValues?.avgSitasi}
            previousDate={aggregateStats.previousDate}
          />
          <StatCard
            title="Publikasi Terbaru"
            value={aggregateStats.recentPublikasi}
            icon={Calendar}
            color="#7C3AED"
            subtitle="2 tahun terakhir"
            loading={statsLoading}
            previousValue={aggregateStats.previousValues?.recentPublikasi}
            previousDate={aggregateStats.previousDate}
          />
        </div>

        {/* Data Table with Integrated Filters */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden hover:shadow-md transition-shadow duration-300">
          {/* Table Header */}
          <div className="px-6 py-5 border-b border-gray-200 bg-gray-50/50">
            <h2 className="text-xl font-semibold text-gray-900">Daftar Publikasi Google Scholar</h2>

            {/* Filters Section */}
            <div className="space-y-4">
              {/* Search Bar */}
              <div className="relative">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-5 w-5 text-gray-400" />
                <input
                  type="text"
                  placeholder="Cari publikasi..."
                  value={searchTerm}
                  onChange={handleSearchChange}
                  className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-red-500 focus:border-transparent"
                />
              </div>

              {/* Type and Year Filters */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {/* Type Filter */}
                <div className="relative">
                  <label htmlFor="filter-tipe" className="block text-sm font-semibold text-gray-700 mb-2 flex items-center">
                    <FileText className="w-4 h-4 mr-1.5 text-red-600" />
                    Tipe Publikasi
                  </label>
                  <div className="relative">
                    <select
                      id="filter-tipe"
                      value={filterTipe}
                      onChange={handleFilterChange}
                      className="w-full pl-4 pr-10 py-2.5 border-2 border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-red-500 focus:border-red-500 bg-white hover:border-gray-400 transition-all duration-200 appearance-none cursor-pointer shadow-sm"
                      style={{
                        backgroundImage: `url("data:image/svg+xml,%3csvg xmlns='http://www.w3.org/2000/svg' fill='none' viewBox='0 0 20 20'%3e%3cpath stroke='%236b7280' stroke-linecap='round' stroke-linejoin='round' stroke-width='1.5' d='M6 8l4 4 4-4'/%3e%3c/svg%3e")`,
                        backgroundPosition: 'right 0.5rem center',
                        backgroundRepeat: 'no-repeat',
                        backgroundSize: '1.5em 1.5em'
                      }}
                    >
                      {publikasiTypes.map((type) => (
                        <option key={type.value} value={type.value}>
                          {type.label}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>

                {/* Year Range Filter */}
                <div className="relative md:col-span-2">
                  <label className="block text-sm font-semibold text-gray-700 mb-2 flex items-center">
                    <Calendar className="w-4 h-4 mr-1.5 text-purple-600" />
                    Rentang Tahun
                  </label>
                  <div className="flex items-center gap-2">
                    <select
                      value={yearStart}
                      onChange={handleYearStartChange}
                      className="flex-1 pl-4 pr-10 py-2.5 border-2 border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-purple-500 bg-white hover:border-gray-400 transition-all duration-200 appearance-none cursor-pointer shadow-sm"
                      style={{
                        backgroundImage: `url("data:image/svg+xml,%3csvg xmlns='http://www.w3.org/2000/svg' fill='none' viewBox='0 0 20 20'%3e%3cpath stroke='%236b7280' stroke-linecap='round' stroke-linejoin='round' stroke-width='1.5' d='M6 8l4 4 4-4'/%3e%3c/svg%3e")`,
                        backgroundPosition: 'right 0.5rem center',
                        backgroundRepeat: 'no-repeat',
                        backgroundSize: '1.5em 1.5em'
                      }}
                    >
                      <option value="">📅 Dari Tahun</option>
                      {yearOptions.map((year) => (
                        <option key={year} value={year}>
                          {year}
                        </option>
                      ))}
                    </select>
                    <span className="text-gray-500 font-medium">—</span>
                    <select
                      value={yearEnd}
                      onChange={handleYearEndChange}
                      className="flex-1 pl-4 pr-10 py-2.5 border-2 border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-purple-500 bg-white hover:border-gray-400 transition-all duration-200 appearance-none cursor-pointer shadow-sm"
                      style={{
                        backgroundImage: `url("data:image/svg+xml,%3csvg xmlns='http://www.w3.org/2000/svg' fill='none' viewBox='0 0 20 20'%3e%3cpath stroke='%236b7280' stroke-linecap='round' stroke-linejoin='round' stroke-width='1.5' d='M6 8l4 4 4-4'/%3e%3c/svg%3e")`,
                        backgroundPosition: 'right 0.5rem center',
                        backgroundRepeat: 'no-repeat',
                        backgroundSize: '1.5em 1.5em'
                      }}
                    >
                      <option value="">📅 Sampai Tahun</option>
                      {yearOptions.map((year) => (
                        <option key={year} value={year}>
                          {year}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>
              </div>

              {/* Faculty and Department Filters */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {/* Faculty Filter */}
                <div className="relative">
                  <label htmlFor="faculty" className="block text-sm font-semibold text-gray-700 mb-2 flex items-center">
                    <Building2 className="w-4 h-4 mr-1.5 text-orange-600" />
                    Fakultas
                  </label>
                  <div className="relative">
                    <select
                      id="faculty"
                      value={selectedFaculty}
                      onChange={handleFacultyChange}
                      className="w-full pl-4 pr-10 py-2.5 border-2 border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-orange-500 focus:border-orange-500 bg-white hover:border-gray-400 transition-all duration-200 appearance-none cursor-pointer shadow-sm"
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
                    <GraduationCap className="w-4 h-4 mr-1.5 text-emerald-600" />
                    Prodi
                  </label>
                  <div className="relative">
                    <select
                      id="department"
                      value={selectedDepartment}
                      onChange={handleDepartmentChange}
                      disabled={!selectedFaculty}
                      className="w-full pl-4 pr-10 py-2.5 border-2 border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500 bg-white hover:border-gray-400 transition-all duration-200 appearance-none cursor-pointer shadow-sm disabled:bg-gray-50 disabled:cursor-not-allowed disabled:border-gray-200 disabled:text-gray-500"
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
                    disabled={!selectedFaculty && !selectedDepartment && !searchTerm && filterTipe === 'all' && !yearStart && !yearEnd}
                    className="w-full px-4 py-2.5 bg-gradient-to-r from-gray-100 to-gray-200 text-gray-700 rounded-lg hover:from-gray-200 hover:to-gray-300 transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed font-medium shadow-sm flex items-center justify-center group"
                  >
                    <RefreshCw className="w-4 h-4 mr-2 group-hover:rotate-180 transition-transform duration-300" />
                    Reset Filter
                  </button>
                </div>
              </div>

              {/* Active Filters Display */}
              {(selectedFaculty || selectedDepartment || filterTipe !== 'all' || yearStart || yearEnd) && (
                <div className="flex items-center flex-wrap gap-2">
                  <span className="text-sm text-gray-600">Filter aktif:</span>
                  {selectedFaculty && (
                    <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-orange-100 text-orange-800">
                      <Building2 className="w-4 h-4 mr-1" />
                      {selectedFaculty}
                    </span>
                  )}
                  {selectedDepartment && (
                    <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-emerald-100 text-emerald-800">
                      <GraduationCap className="w-4 h-4 mr-1" />
                      {selectedDepartment}
                    </span>
                  )}
                  {filterTipe !== 'all' && (
                    <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-red-100 text-red-800">
                      <FileText className="w-4 h-4 mr-1" />
                      {publikasiTypes.find(t => t.value === filterTipe)?.label}
                    </span>
                  )}
                  {(yearStart || yearEnd) && (
                    <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-purple-100 text-purple-800">
                      <Calendar className="w-4 h-4 mr-1" />
                      {yearStart || '...'} - {yearEnd || '...'}
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
                <FileText className="h-12 w-12 text-gray-400 mb-4" />
                <p className="text-gray-500">Tidak ada data publikasi Google Scholar ditemukan</p>
              </div>
            ) : (
              <>
                <table className="min-w-full divide-y divide-gray-200">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-6 py-4 text-left text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-100 min-w-[180px]" onClick={() => handleSort('authors')}>
                        <div className="flex items-center gap-2">
                          <span>Author</span>
                          {sortConfig.key === 'authors' && (sortConfig.direction === 'asc' ? '↑' : '↓')}
                        </div>
                      </th>
                      <th className="px-6 py-4 text-left text-xs font-medium text-gray-500 uppercase tracking-wider min-w-[120px]">
                        Prodi
                      </th>
                      <th className="px-6 py-4 text-left text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-100 min-w-[300px]" onClick={() => handleSort('v_judul')}>
                        <div className="flex items-center gap-2">
                          <span>Judul Publikasi</span>
                          {sortConfig.key === 'v_judul' && (sortConfig.direction === 'asc' ? '↑' : '↓')}
                        </div>
                      </th>
                      <th className="px-6 py-4 text-center text-xs font-medium text-gray-500 uppercase tracking-wider min-w-[100px]">
                        Tipe
                      </th>
                      <th className="px-6 py-4 text-center text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-100 min-w-[80px]" onClick={() => handleSort('v_tahun_publikasi')}>
                        <div className="flex items-center justify-center gap-2">
                          <span>Tahun</span>
                          {sortConfig.key === 'v_tahun_publikasi' && (sortConfig.direction === 'asc' ? '↑' : '↓')}
                        </div>
                      </th>
                      <th className="px-6 py-4 text-left text-xs font-medium text-gray-500 uppercase tracking-wider min-w-[200px]">
                        Venue/Jurnal
                      </th>
                      <th className="px-6 py-4 text-left text-xs font-medium text-gray-500 uppercase tracking-wider min-w-[150px]">
                        Publisher
                      </th>
                      <th className="px-6 py-4 text-center text-xs font-medium text-gray-500 uppercase tracking-wider min-w-[100px]">
                        Vol/Issue
                      </th>
                      <th className="px-6 py-4 text-center text-xs font-medium text-gray-500 uppercase tracking-wider min-w-[80px]">
                        Pages
                      </th>
                      <th className="px-6 py-4 text-center text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-100 min-w-[80px]" onClick={() => handleSort('n_total_sitasi')}>
                        <div className="flex items-center justify-center gap-2">
                          <span>Sitasi</span>
                          {sortConfig.key === 'n_total_sitasi' && (sortConfig.direction === 'asc' ? '↑' : '↓')}
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
                          <div className="max-w-[180px]">
                            <p className="text-sm text-gray-900 line-clamp-2" title={row.authors || 'N/A'}>
                              {row.authors || 'N/A'}
                            </p>
                          </div>
                        </td>
                        <td className="px-6 py-4">
                          <div className="max-w-[120px]">
                            <span className="inline-flex items-center px-2 py-1 rounded-md text-xs font-medium bg-red-100 text-red-800 truncate max-w-full" title={row.v_nama_jurusan || 'N/A'}>
                              {row.v_nama_jurusan || 'N/A'}
                            </span>
                          </div>
                        </td>
                        <td className="px-6 py-4">
                          <div className="max-w-[300px]">
                            <p className="text-sm font-medium text-gray-900 line-clamp-2" title={row.v_judul || 'N/A'}>
                              {row.v_judul || 'N/A'}
                            </p>
                          </div>
                        </td>
                        <td className="px-6 py-4 text-center">
                          <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium whitespace-nowrap ${
                            row.tipe === 'Artikel' ? 'bg-green-100 text-green-800' :
                            row.tipe === 'Prosiding' ? 'bg-yellow-100 text-yellow-800' :
                            row.tipe === 'Buku' ? 'bg-purple-100 text-purple-800' :
                            row.tipe === 'Penelitian' ? 'bg-blue-100 text-blue-800' :
                            row.tipe === 'Lainnya' ? 'bg-indigo-100 text-indigo-800' :
                            'bg-gray-100 text-gray-800'
                          }`}>
                            {row.tipe || 'N/A'}
                          </span>
                        </td>
                        <td className="px-6 py-4 text-center">
                          <span className="inline-flex items-center px-2 py-1 rounded text-xs font-medium bg-blue-100 text-blue-800 whitespace-nowrap">
                            {row.v_tahun_publikasi || 'N/A'}
                          </span>
                        </td>
                        <td className="px-6 py-4">
                          <div className="max-w-[200px]">
                            <p className="text-sm text-gray-900 truncate" title={row.venue || 'N/A'}>
                              {row.venue || 'N/A'}
                            </p>
                          </div>
                        </td>
                        <td className="px-6 py-4">
                          <div className="max-w-[150px]">
                            <p className="text-sm text-gray-700 truncate" title={row.publisher || '-'}>
                              {row.publisher || '-'}
                            </p>
                          </div>
                        </td>
                        <td className="px-6 py-4 text-center">
                          <span className="text-xs text-gray-600 whitespace-nowrap">
                            {row.vol_issue || '-'}
                          </span>
                        </td>
                        <td className="px-6 py-4 text-center">
                          <span className="text-xs text-gray-600 whitespace-nowrap">
                            {formatPages(row.pages)}
                          </span>
                        </td>
                        <td className="px-6 py-4 text-center">
                          <span className={`text-sm font-semibold whitespace-nowrap ${
                            (row.n_total_sitasi || 0) > 100 ? 'text-red-600' :
                            (row.n_total_sitasi || 0) > 50 ? 'text-orange-600' :
                            (row.n_total_sitasi || 0) > 10 ? 'text-yellow-600' :
                            'text-gray-600'
                          }`}>
                            {(row.n_total_sitasi || 0).toLocaleString()}
                          </span>
                        </td>
                        <td className="px-6 py-4 text-center">
                          <span className="text-xs text-gray-500 whitespace-nowrap">
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
                                title="Lihat di Google Scholar"
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

export default ScholarPublikasi;