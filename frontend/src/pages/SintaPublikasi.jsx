import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { FileText, Award, Calendar, ExternalLink, Building2, GraduationCap, RefreshCw, Search } from 'lucide-react';
import apiService from '../services/apiService';
import { toast } from 'react-hot-toast';

const SintaPublikasi = () => {
  const navigate = useNavigate();
  const [publikasiData, setPublikasiData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [statsLoading, setStatsLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [currentPage, setCurrentPage] = useState(1);
  const [pagination, setPagination] = useState(null);
  const [sortConfig, setSortConfig] = useState({ key: null, direction: 'asc' });
  const [filterTipe, setFilterTipe] = useState('all');
  const [filterTerindeks, setFilterTerindeks] = useState('all');
  const [yearStart, setYearStart] = useState('');
  const [yearEnd, setYearEnd] = useState('');
  
  // Faculty and Department filters
  const [faculties, setFaculties] = useState([]);
  const [departments, setDepartments] = useState([]);
  const [selectedFaculty, setSelectedFaculty] = useState('');
  const [selectedDepartment, setSelectedDepartment] = useState('');
  const [loadingDepartments, setLoadingDepartments] = useState(false);
  
  const [aggregateStats, setAggregateStats] = useState({
    totalPublikasi: 0,
    totalSitasi: 0,
    avgSitasi: 0,
    medianSitasi: 0,
    recentPublikasi: 0
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

  const terindeksOptions = [
    { value: 'all', label: 'Semua Terindeks' },
    { value: 'Scopus', label: 'Scopus' },
    { value: 'WoS', label: 'Web of Science' },
    { value: 'DOAJ', label: 'DOAJ' },
    { value: 'Garuda', label: 'Garuda' },
    { value: 'SINTA', label: 'SINTA' },
    { value: 'Other', label: 'Lainnya' }
  ];

  const currentYear = new Date().getFullYear();
  const yearOptions = [];
  for (let year = currentYear; year >= 1990; year--) {
    yearOptions.push(year);
  }

  // Fetch faculties on component mount
  useEffect(() => {
    const token = localStorage.getItem('token');
    if (!token) {
      navigate('/login');
      return;
    }
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
    fetchPublikasiData();
  }, [currentPage, searchTerm, filterTipe, filterTerindeks, yearStart, yearEnd, selectedFaculty, selectedDepartment]);

  // Fetch stats when filters change
  useEffect(() => {
    fetchAggregateStats();
  }, [searchTerm, filterTipe, filterTerindeks, yearStart, yearEnd, selectedFaculty, selectedDepartment]);

  const fetchFaculties = async () => {
    try {
      const response = await apiService.getSintaPublikasiFaculties();
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
      const response = await apiService.getSintaPublikasiDepartments(faculty);
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

  const fetchAggregateStats = async () => {
    try {
      setStatsLoading(true);
      
      const params = { search: searchTerm };
      
      if (filterTipe !== 'all') {
        params.tipe = filterTipe;
      }
      
      if (filterTerindeks !== 'all') {
        params.terindeks = filterTerindeks;
      }
      
      if (yearStart) {
        params.year_start = yearStart;
      }
      
      if (yearEnd) {
        params.year_end = yearEnd;
      }

      if (selectedFaculty) {
        params.faculty = selectedFaculty;
      }

      if (selectedDepartment) {
        params.department = selectedDepartment;
      }
      
      const response = await apiService.getSintaPublikasiStats(params);

      if (response.success) {
        const fullParams = {
          page: 1,
          per_page: 10000,
          search: searchTerm
        };
        
        if (filterTipe !== 'all') fullParams.tipe = filterTipe;
        if (filterTerindeks !== 'all') fullParams.terindeks = filterTerindeks;
        if (yearStart) fullParams.year_start = yearStart;
        if (yearEnd) fullParams.year_end = yearEnd;
        if (selectedFaculty) fullParams.faculty = selectedFaculty;
        if (selectedDepartment) fullParams.department = selectedDepartment;
        
        const fullResponse = await apiService.getSintaPublikasi(fullParams);
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
          recentPublikasi
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
      
      if (filterTipe !== 'all') {
        params.tipe = filterTipe;
      }
      
      if (filterTerindeks !== 'all') {
        params.terindeks = filterTerindeks;
      }
      
      if (yearStart) {
        params.year_start = yearStart;
      }
      
      if (yearEnd) {
        params.year_end = yearEnd;
      }

      if (selectedFaculty) {
        params.faculty = selectedFaculty;
      }

      if (selectedDepartment) {
        params.department = selectedDepartment;
      }
      
      const response = await apiService.getSintaPublikasi(params);

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
      
      if (filterTipe !== 'all') {
        params.tipe = filterTipe;
      }
      
      if (yearStart) {
        params.year_start = yearStart;
      }
      
      if (yearEnd) {
        params.year_end = yearEnd;
      }

      if (selectedFaculty) {
        params.faculty = selectedFaculty;
      }

      if (selectedDepartment) {
        params.department = selectedDepartment;
      }
      
      const response = await apiService.getSintaPublikasi(params);

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
        toast.error('Gagal mengambil data publikasi SINTA');
        console.error('Error fetching SINTA publikasi data:', response.error);
      }
    } catch (error) {
      toast.error('Terjadi kesalahan saat mengambil data');
      console.error('Error fetching SINTA publikasi data:', error);
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

  const handleTerindeksChange = (e) => {
    setFilterTerindeks(e.target.value);
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

  const StatCard = ({ title, value, icon: Icon, color, subtitle, loading }) => (
    <div className="bg-white rounded-lg shadow-md p-6 border-l-4" style={{ borderColor: color }}>
      <div className="flex items-center justify-between">
        <div className="flex-1">
          <p className="text-sm font-medium text-gray-600">{title}</p>
          {loading ? (
            <div className="mt-2 h-8 w-24 bg-gray-200 animate-pulse rounded"></div>
          ) : (
            <>
              <p className="text-2xl font-bold text-gray-900">
                {typeof value === 'string' ? value : value.toLocaleString()}
              </p>
              {subtitle && (
                <p className="text-xs text-gray-500 mt-1">{subtitle}</p>
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

  const sortedData = getSortedData();

  return (
    <div className="min-h-screen bg-gray-50 py-8">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900">Data Publikasi SINTA</h1>
          <p className="mt-2 text-sm text-gray-600">
            Daftar publikasi dengan data dari SINTA
          </p>
        </div>

        {/* Stats Cards */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
          <StatCard
            title="Total Publikasi"
            value={aggregateStats.totalPublikasi}
            icon={FileText}
            color="#6366F1"
            loading={statsLoading}
          />
          <StatCard
            title="Total Sitasi"
            value={aggregateStats.totalSitasi}
            icon={Award}
            color="#059669"
            loading={statsLoading}
          />
          <StatCard
            title="Rata-rata Sitasi"
            value={aggregateStats.avgSitasi}
            icon={Award}
            color="#D97706"
            subtitle={`Median: ${aggregateStats.medianSitasi}`}
            loading={statsLoading}
          />
          <StatCard
            title="Publikasi Terbaru"
            value={aggregateStats.recentPublikasi}
            icon={Calendar}
            color="#7C3AED"
            subtitle="2 tahun terakhir"
            loading={statsLoading}
          />
        </div>

        {/* Data Table with Integrated Filters */}
        <div className="bg-white rounded-lg shadow-md overflow-hidden">
          {/* Table Header */}
          <div className="px-6 py-4 border-b border-gray-200">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-xl font-semibold text-gray-900">Daftar Publikasi SINTA</h2>
              <button
                onClick={fetchPublikasiData}
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
                  placeholder="Cari publikasi..."
                  value={searchTerm}
                  onChange={handleSearchChange}
                  className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                />
              </div>

              {/* Type, Terindeks and Year Filters */}
              <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                {/* Type Filter */}
                <div className="relative">
                  <label htmlFor="filter-tipe" className="block text-sm font-semibold text-gray-700 mb-2 flex items-center">
                    <FileText className="w-4 h-4 mr-1.5 text-indigo-600" />
                    Tipe Publikasi
                  </label>
                  <div className="relative">
                    <select
                      id="filter-tipe"
                      value={filterTipe}
                      onChange={handleFilterChange}
                      className="w-full pl-4 pr-10 py-2.5 border-2 border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 bg-white hover:border-gray-400 transition-all duration-200 appearance-none cursor-pointer shadow-sm"
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

                {/* Terindeks Filter */}
                <div className="relative">
                  <label htmlFor="filter-terindeks" className="block text-sm font-semibold text-gray-700 mb-2 flex items-center">
                    <Award className="w-4 h-4 mr-1.5 text-green-600" />
                    Terindeks
                  </label>
                  <div className="relative">
                    <select
                      id="filter-terindeks"
                      value={filterTerindeks}
                      onChange={handleTerindeksChange}
                      className="w-full pl-4 pr-10 py-2.5 border-2 border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-green-500 focus:border-green-500 bg-white hover:border-gray-400 transition-all duration-200 appearance-none cursor-pointer shadow-sm"
                      style={{
                        backgroundImage: `url("data:image/svg+xml,%3csvg xmlns='http://www.w3.org/2000/svg' fill='none' viewBox='0 0 20 20'%3e%3cpath stroke='%236b7280' stroke-linecap='round' stroke-linejoin='round' stroke-width='1.5' d='M6 8l4 4 4-4'/%3e%3c/svg%3e")`,
                        backgroundPosition: 'right 0.5rem center',
                        backgroundRepeat: 'no-repeat',
                        backgroundSize: '1.5em 1.5em'
                      }}
                    >
                      {terindeksOptions.map((option) => (
                        <option key={option.value} value={option.value}>
                          {option.label}
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
                    <GraduationCap className="w-4 h-4 mr-1.5 text-green-600" />
                    Jurusan
                  </label>
                  <div className="relative">
                    <select
                      id="department"
                      value={selectedDepartment}
                      onChange={handleDepartmentChange}
                      disabled={!selectedFaculty || loadingDepartments}
                      className="w-full pl-4 pr-10 py-2.5 border-2 border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-green-500 focus:border-green-500 bg-white hover:border-gray-400 transition-all duration-200 appearance-none cursor-pointer shadow-sm disabled:bg-gray-50 disabled:cursor-not-allowed disabled:border-gray-200 disabled:text-gray-500"
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
                      <RefreshCw className="w-3 h-3 text-green-500 animate-spin mr-1" />
                      <p className="text-xs text-green-600 font-medium">Memuat jurusan...</p>
                    </div>
                  )}
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
                    <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-blue-100 text-blue-800">
                      <Building2 className="w-4 h-4 mr-1" />
                      {selectedFaculty}
                    </span>
                  )}
                  {selectedDepartment && (
                    <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-green-100 text-green-800">
                      <GraduationCap className="w-4 h-4 mr-1" />
                      {selectedDepartment}
                    </span>
                  )}
                  {filterTipe !== 'all' && (
                    <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-indigo-100 text-indigo-800">
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
                <p className="text-gray-500">Tidak ada data publikasi SINTA ditemukan</p>
              </div>
            ) : (
              <>
                <table className="min-w-full divide-y divide-gray-200">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-100" onClick={() => handleSort('authors')}>
                        Author {sortConfig.key === 'authors' && (sortConfig.direction === 'asc' ? '↑' : '↓')}
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Fakultas
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Jurusan
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-100" onClick={() => handleSort('v_judul')}>
                        Judul Publikasi {sortConfig.key === 'v_judul' && (sortConfig.direction === 'asc' ? '↑' : '↓')}
                      </th>
                      <th className="px-6 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Tipe
                      </th>
                      <th className="px-6 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-100" onClick={() => handleSort('v_tahun_publikasi')}>
                        Tahun {sortConfig.key === 'v_tahun_publikasi' && (sortConfig.direction === 'asc' ? '↑' : '↓')}
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Venue/Jurnal
                      </th>
                      <th className="px-6 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Terindeks
                      </th>
                      <th className="px-6 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Ranking
                      </th>
                      <th className="px-6 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Vol/Issue
                      </th>
                      <th className="px-6 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Pages
                      </th>
                      <th className="px-6 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-100" onClick={() => handleSort('n_total_sitasi')}>
                        Sitasi {sortConfig.key === 'n_total_sitasi' && (sortConfig.direction === 'asc' ? '↑' : '↓')}
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
                          <div className="max-w-xs">
                            <p className="text-sm text-gray-900 truncate" title={row.authors}>
                              {row.authors || 'N/A'}
                            </p>
                          </div>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-700">
                          {row.v_nama_fakultas || 'N/A'}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <div className="max-w-xs">
                            <span className="inline-flex items-center px-2 py-1 rounded-md text-xs font-medium bg-indigo-100 text-indigo-800">
                              <Building2 className="w-3 h-3 mr-1" />
                              {row.v_nama_jurusan || 'N/A'}
                            </span>
                          </div>
                        </td>
                        <td className="px-6 py-4">
                          <div className="max-w-lg">
                            <p className="font-medium text-gray-900 line-clamp-2" title={row.v_judul}>
                              {row.v_judul || 'N/A'}
                            </p>
                          </div>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-center">
                          <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
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
                        <td className="px-6 py-4 whitespace-nowrap text-center">
                          <span className="inline-flex items-center px-2 py-1 rounded text-xs font-medium bg-blue-100 text-blue-800">
                            {row.v_tahun_publikasi || 'N/A'}
                          </span>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <div className="max-w-xs">
                            <p className="text-sm text-gray-900 truncate" title={row.venue}>
                              {row.venue || 'N/A'}
                            </p>
                          </div>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-center">
                          {!row.v_terindeks || row.v_terindeks.trim() === '' ? (
                            <span className="text-gray-400">-</span>
                          ) : (
                            <div className="flex flex-wrap gap-1 justify-center">
                              {row.v_terindeks.split(',').map((index, idx) => (
                                <span
                                  key={idx}
                                  className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${
                                    index.trim().toLowerCase().includes('scopus') ? 'bg-orange-100 text-orange-800' :
                                    index.trim().toLowerCase().includes('wos') || index.trim().toLowerCase().includes('web of science') ? 'bg-red-100 text-red-800' :
                                    index.trim().toLowerCase().includes('sinta') ? 'bg-indigo-100 text-indigo-800' :
                                    'bg-gray-100 text-gray-800'
                                  }`}
                                >
                                  {index.trim()}
                                </span>
                              ))}
                            </div>
                          )}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-center">
                          {!row.v_ranking || row.v_ranking.trim() === '' ? (
                            <span className="text-gray-400">-</span>
                          ) : (
                            <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-bold ${
                              row.v_ranking.toLowerCase().includes('q1') ? 'bg-green-100 text-green-800' :
                              row.v_ranking.toLowerCase().includes('q2') ? 'bg-blue-100 text-blue-800' :
                              row.v_ranking.toLowerCase().includes('q3') ? 'bg-yellow-100 text-yellow-800' :
                              row.v_ranking.toLowerCase().includes('q4') ? 'bg-orange-100 text-orange-800' :
                              'bg-purple-100 text-purple-800'
                            }`}>
                              {row.v_ranking}
                            </span>
                          )}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-center">
                          <span className="text-sm text-gray-600">
                            {row.vol_issue || '-'}
                          </span>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-center">
                          <span className="text-sm text-gray-600">
                            {row.pages ? `pp. ${row.pages}` : '-'}
                          </span>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-center">
                          <span className={`font-semibold ${
                            (row.n_total_sitasi || 0) > 100 ? 'text-red-600' :
                            (row.n_total_sitasi || 0) > 50 ? 'text-orange-600' :
                            (row.n_total_sitasi || 0) > 10 ? 'text-yellow-600' :
                            'text-gray-600'
                          }`}>
                            {(row.n_total_sitasi || 0).toLocaleString()}
                          </span>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-center text-sm text-gray-500">
                          {row.t_tanggal_unduh ? new Date(row.t_tanggal_unduh).toLocaleDateString('id-ID') : 'N/A'}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-center">
                          <div className="flex items-center justify-center space-x-2">
                            {row.v_link_url && (
                              <a
                                href={row.v_link_url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="text-indigo-600 hover:text-indigo-900 inline-flex items-center text-sm"
                                title="Lihat di SINTA"
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
                                  ? 'bg-indigo-600 text-white border-indigo-600'
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

export default SintaPublikasi;