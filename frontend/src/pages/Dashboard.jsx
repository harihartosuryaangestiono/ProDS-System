import { useState, useEffect } from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { Users, FileText, TrendingUp, Award, Calendar, Search, ArrowUp, ArrowDown, Filter, Building2, GraduationCap, RefreshCw } from 'lucide-react';
import apiService from '../services/apiService';

// Faculty colors for stacked charts
const FACULTY_COLORS = {
  'Fakultas Ekonomi': '#3B82F6',
  'Fakultas Hukum': '#EF4444',
  'Fakultas Ilmu Sosial dan Ilmu Politik': '#F59E0B',
  'Fakultas Teknik': '#10B981',
  'Fakultas Filsafat': '#8B5CF6',
  'Fakultas Teknologi Informasi dan Sains': '#EC4899',
  'Fakultas Kedokteran': '#06B6D4',
  'Fakultas Keguruan dan Ilmu Pendidikan': '#F97316',
  'Fakultas Vokasi': '#14B8A6',
  'FTIS': '#EC4899',
  'FKIP': '#F97316',
  'Lainnya': '#6B7280'
};

const Dashboard = () => {
  const [stats, setStats] = useState({
    total_dosen: 0,
    total_publikasi: 0,
    total_sitasi: 0,
    total_sitasi_gs: 0,
    total_sitasi_gs_sinta: 0,
    total_sitasi_scopus: 0,
    avg_h_index: 0,
    median_h_index: 0,
    publikasi_by_year: [],
    top_authors_scopus: [],
    top_authors_gs: [],
    publikasi_internasional_q12: 0,
    publikasi_internasional_q34_noq: 0,
    publikasi_nasional_sinta12: 0,
    publikasi_nasional_sinta34: 0,
    publikasi_nasional_sinta5: 0,
    publikasi_nasional_sinta6: 0,
    scopus_q_breakdown: [],
    sinta_rank_breakdown: [],
    top_dosen_international: [],
    top_dosen_national: [],
    previous_date: null,
    previous_values: {}
  });
  const [loading, setLoading] = useState(true);
  const [yearRange, setYearRange] = useState(10);
  
  // Filter states
  const [selectedFaculty, setSelectedFaculty] = useState('');
  const [selectedDepartment, setSelectedDepartment] = useState('');
  const [faculties, setFaculties] = useState([]);
  const [departments, setDepartments] = useState([]);
  const [loadingDepartments, setLoadingDepartments] = useState(false);

  useEffect(() => {
    fetchFaculties();
  }, []);

  useEffect(() => {
    if (selectedFaculty) {
      fetchDepartments(selectedFaculty);
    } else {
      setDepartments([]);
      setSelectedDepartment('');
    }
  }, [selectedFaculty]);

  const fetchFaculties = async () => {
    try {
      const response = await apiService.getDashboardFaculties();
      console.log('📍 Faculties Response:', response); // Debug
      console.log('📍 Response Data:', response.data); // Debug
      
      if (response.success && response.data) {
        // Pastikan response.data adalah array
        const facultiesData = Array.isArray(response.data) ? response.data : [];
        console.log('📍 Faculties Array:', facultiesData); // Debug
        setFaculties(facultiesData);
      } else {
        console.error('❌ Invalid response:', response);
        setFaculties([]);
      }
    } catch (error) {
      console.error('Error fetching faculties:', error);
      setFaculties([]);
    }
  };

  const fetchDepartments = async (faculty) => {
    try {
      setLoadingDepartments(true);
      const response = await apiService.getDashboardDepartments(faculty);
      console.log('📍 Departments Response:', response); // Debug
      console.log('📍 Response Data:', response.data); // Debug
      
      if (response.success && response.data) {
        const departmentsData = Array.isArray(response.data) ? response.data : [];
        console.log('📍 Departments Array:', departmentsData); // Debug
        setDepartments(departmentsData);
      } else {
        console.error('❌ Invalid response:', response);
        setDepartments([]);
      }
    } catch (error) {
      console.error('Error fetching departments:', error);
      setDepartments([]);
    } finally {
      setLoadingDepartments(false);
    }
  };

  useEffect(() => {
  console.log('🎯 Component mounted, fetching stats...');
    fetchDashboardStats();
  }, [selectedFaculty, selectedDepartment]);

    const fetchDashboardStats = async () => {
    console.log('🚀 fetchDashboardStats STARTED');
    
    try {
      setLoading(true);
      console.log('🔍 Fetching stats with:', { selectedFaculty, selectedDepartment });
      
      const response = await apiService.getDashboardStats(selectedFaculty, selectedDepartment);
      
      console.log('📦 Response received:', response);
      
      if (response.success && response.data) {
        console.log('✅ Setting stats with data');
        
        const mergedStats = {
          total_dosen: 0,
          total_publikasi: 0,
          total_sitasi: 0,
          total_sitasi_gs: 0,
          total_sitasi_gs_sinta: 0,
          total_sitasi_scopus: 0,
          avg_h_index: 0,
          median_h_index: 0,
          publikasi_by_year: [],
          top_authors_scopus: [],
          top_authors_gs: [],
          publikasi_internasional_q12: 0,
          publikasi_internasional_q34_noq: 0,
          publikasi_nasional_sinta12: 0,
          publikasi_nasional_sinta34: 0,
          publikasi_nasional_sinta5: 0,
          publikasi_nasional_sinta6: 0,
          scopus_q_breakdown: [],
          sinta_rank_breakdown: [],
          top_dosen_international: [],
          top_dosen_national: [],
          previous_date: null,
          previous_values: {},
          ...response.data
        };
        
        setStats(mergedStats);
      } else {
        console.error('❌ Invalid response:', response);
        setStats({
          total_dosen: 0,
          total_publikasi: 0,
          total_sitasi: 0,
          total_sitasi_gs: 0,
          total_sitasi_gs_sinta: 0,
          total_sitasi_scopus: 0,
          avg_h_index: 0,
          median_h_index: 0,
          publikasi_by_year: [],
          top_authors_scopus: [],
          top_authors_gs: [],
          publikasi_internasional_q12: 0,
          publikasi_internasional_q34_noq: 0,
          publikasi_nasional_sinta12: 0,
          publikasi_nasional_sinta34: 0,
          publikasi_nasional_sinta5: 0,
          publikasi_nasional_sinta6: 0,
          scopus_q_breakdown: [],
          sinta_rank_breakdown: [],
          top_dosen_international: [],
          top_dosen_national: [],
          previous_date: null,
          previous_values: {}
        });
      }
    } catch (error) {
      console.error('❌ Catch error:', error);
      setStats({
        total_dosen: 0,
        total_publikasi: 0,
        total_sitasi: 0,
        total_sitasi_gs: 0,
        total_sitasi_gs_sinta: 0,
        total_sitasi_scopus: 0,
        avg_h_index: 0,
        median_h_index: 0,
        publikasi_by_year: [],
        top_authors_scopus: [],
        top_authors_gs: [],
        publikasi_internasional_q12: 0,
        publikasi_internasional_q34_noq: 0,
        publikasi_nasional_sinta12: 0,
        publikasi_nasional_sinta34: 0,
        publikasi_nasional_sinta5: 0,
        publikasi_nasional_sinta6: 0,
        scopus_q_breakdown: [],
        sinta_rank_breakdown: [],
        top_dosen_international: [],
        top_dosen_national: [],
        previous_date: null,
        previous_values: {}
      });
    } finally {
      setLoading(false);
    }
  };

  const handleFacultyChange = (e) => {
    setSelectedFaculty(e.target.value);
    setSelectedDepartment('');
  };

  const handleDepartmentChange = (e) => {
    setSelectedDepartment(e.target.value);
  };

  const handleResetFilters = () => {
    setSelectedFaculty('');
    setSelectedDepartment('');
  };

  const StatCard = ({ title, value, icon: Icon, color, subtitle, previousValue, previousDate }) => {
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
            <div className="flex items-center gap-2 mt-1">
              <p className="text-2xl font-bold text-gray-900">{value}</p>
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
          </div>
          <div className="p-3 rounded-full" style={{ backgroundColor: `${color}20` }}>
            <Icon className="w-8 h-8" style={{ color }} />
          </div>
        </div>
      </div>
    );
  };

  // Transform data for stacked charts
  const transformForStackedChart = (data, hasFilter) => {
    if (!data || data.length === 0) return [];
    
    // Check if data has faculty column
    const hasFacultyColumn = data.some(d => d.faculty);
    
    if (hasFilter || !hasFacultyColumn) {
      // With filter OR no faculty data - return simple format
      return data.map(item => ({
        name: item.ranking || item.v_tahun_publikasi || item.name,
        count: item.count || 0
      }));
    }
    
    // Without filter AND has faculty data - create stacked format
    const grouped = {};
    
    data.forEach(item => {
      const key = item.ranking || item.v_tahun_publikasi;
      const faculty = item.faculty || 'Lainnya';
      const count = item.count || 0;
      
      if (!grouped[key]) {
        grouped[key] = { name: key };
      }
      grouped[key][faculty] = (grouped[key][faculty] || 0) + count;
    });
    
    return Object.values(grouped).sort((a, b) => {
      const aKey = String(a.name);
      const bKey = String(b.name);
      
      // Try to sort numerically if both are numbers
      const aNum = parseFloat(aKey);
      const bNum = parseFloat(bKey);
      if (!isNaN(aNum) && !isNaN(bNum)) {
        return aNum - bNum;
      }
      
      // Otherwise sort alphabetically
      return aKey.localeCompare(bKey);
    });
  };

  // Get unique faculties from data
  const getUniqueFaculties = (data) => {
    const faculties = new Set();
    data.forEach(item => {
      if (item.faculty) {
        faculties.add(item.faculty);
      }
    });
    return Array.from(faculties).sort();
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="animate-spin rounded-full h-32 w-32 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  if (!stats || typeof stats.total_dosen === 'undefined') {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <p className="text-gray-600">Gagal memuat data dashboard</p>
          <button 
            onClick={fetchDashboardStats}
            className="mt-4 px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
          >
            Coba Lagi
          </button>
        </div>
      </div>
    );
  }

  const hasFilter = stats.has_filter !== undefined 
    ? stats.has_filter 
    : (selectedFaculty || selectedDepartment);

  const filteredYearData = (() => {
    const currentYear = new Date().getFullYear();
    const yearData = stats.publikasi_by_year || [];
    const filtered = yearData.filter(item => {
      const year = parseInt(item.v_tahun_publikasi || item.name);
      return year >= currentYear - yearRange && year <= currentYear;
    });
    return transformForStackedChart(filtered, hasFilter);
  })();

  const uniqueFacultiesYear = getUniqueFaculties(stats.publikasi_by_year || []);
  const scopusData = transformForStackedChart(stats.scopus_q_breakdown || [], hasFilter);
  const uniqueFacultiesScopus = getUniqueFaculties(stats.scopus_q_breakdown || []);
  const sintaData = transformForStackedChart(stats.sinta_rank_breakdown || [], hasFilter);
  const uniqueFacultiesSinta = getUniqueFaculties(stats.sinta_rank_breakdown || []);

  return (
    <div className="min-h-screen bg-gray-50 py-8">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900">Dashboard</h1>
          <p className="mt-2 text-sm text-gray-600">
            Overview sistem publikasi dosen SINTA & Google Scholar
          </p>
        </div>

        {/* Global Filters */}
        <div className="bg-white rounded-lg shadow-md p-6 mb-8">
          <div className="flex items-center gap-2 mb-4">
            <Filter className="w-5 h-5 text-blue-600" />
            <h2 className="text-lg font-semibold text-gray-900">Filter Data</h2>
          </div>
          
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
                >
                  <option value="">✨ Semua Fakultas</option>
                  {Array.isArray(faculties) && faculties.map((faculty) => (
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
                Jurusan
              </label>
              <div className="relative">
                <select
                  id="department"
                  value={selectedDepartment}
                  onChange={handleDepartmentChange}
                  disabled={!selectedFaculty || loadingDepartments}
                  className="w-full pl-4 pr-10 py-2.5 border-2 border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 bg-white hover:border-gray-400 transition-all duration-200 appearance-none cursor-pointer shadow-sm disabled:bg-gray-50 disabled:cursor-not-allowed disabled:border-gray-200 disabled:text-gray-500"
                >
                  <option value="">
                    {!selectedFaculty ? '🔒 Pilih fakultas terlebih dahulu' : loadingDepartments ? '⏳ Memuat...' : '✨ Semua Jurusan'}
                  </option>
                  {Array.isArray(departments) && departments.map((dept) => (
                    <option key={dept} value={dept}>
                      {dept}
                    </option>
                  ))}
                </select>
              </div>
              {loadingDepartments && (
                <div className="flex items-center mt-2">
                  <RefreshCw className="w-3 h-3 text-blue-500 animate-spin mr-1" />
                  <p className="text-xs text-blue-600 font-medium">Memuat jurusan...</p>
                </div>
              )}
            </div>

            {/* Reset Button */}
            <div className="flex items-end">
              <button
                onClick={handleResetFilters}
                disabled={!selectedFaculty && !selectedDepartment}
                className="w-full px-4 py-2.5 bg-gradient-to-r from-gray-100 to-gray-200 text-gray-700 rounded-lg hover:from-gray-200 hover:to-gray-300 transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed font-medium shadow-sm flex items-center justify-center group"
              >
                <RefreshCw className="w-4 h-4 mr-2 group-hover:rotate-180 transition-transform duration-300" />
                Reset Filter
              </button>
            </div>
          </div>

          {/* Active Filters Display */}
          {(selectedFaculty || selectedDepartment) && (
            <div className="flex items-center flex-wrap gap-2 mt-4">
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

        {/* Stats Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
          <StatCard
            title="Total Dosen"
            value={stats.total_dosen.toLocaleString()}
            icon={Users}
            color="#3B82F6"
            previousValue={stats.previous_values?.total_dosen}
            previousDate={stats.previous_date}
          />
          <StatCard
            title="Total Publikasi"
            value={stats.total_publikasi.toLocaleString()}
            icon={FileText}
            color="#10B981"
            previousValue={stats.previous_values?.total_publikasi}
            previousDate={stats.previous_date}
          />
          <StatCard
            title="Total Sitasi"
            value={stats.total_sitasi.toLocaleString()}
            subtitle={`GS: ${stats.total_sitasi_gs?.toLocaleString() || 0} | GS-SINTA: ${stats.total_sitasi_gs_sinta?.toLocaleString() || 0} | Scopus: ${stats.total_sitasi_scopus?.toLocaleString() || 0}`}
            icon={Award}
            color="#F59E0B"
            previousValue={stats.previous_values?.total_sitasi}
            previousDate={stats.previous_date}
          />
          <StatCard
            title="H-Index Rata-rata"
            value={stats.avg_h_index ? stats.avg_h_index.toFixed(1) : '0.0'}
            subtitle={`Median: ${stats.median_h_index ? stats.median_h_index.toFixed(1) : '0.0'}`}
            icon={TrendingUp}
            color="#EF4444"
            previousValue={stats.previous_values?.avg_h_index}
            previousDate={stats.previous_date}
          />
        </div>

        {/* International vs National Summary */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
          <StatCard
            title="Internasional (Scopus Q1-Q2)"
            value={stats.publikasi_internasional_q12.toLocaleString()}
            icon={Award}
            color="#059669"
            previousValue={stats.previous_values?.publikasi_internasional_q12}
            previousDate={stats.previous_date}
          />
          <StatCard
            title="Internasional (Q3-Q4/noQ)"
            value={stats.publikasi_internasional_q34_noq.toLocaleString()}
            icon={Award}
            color="#10B981"
            previousValue={stats.previous_values?.publikasi_internasional_q34_noq}
            previousDate={stats.previous_date}
          />
          <StatCard
            title="Nasional (Sinta 1-2)"
            value={stats.publikasi_nasional_sinta12.toLocaleString()}
            icon={Award}
            color="#7C3AED"
            previousValue={stats.previous_values?.publikasi_nasional_sinta12}
            previousDate={stats.previous_date}
          />
          <StatCard
            title="Nasional (Sinta 3-4)"
            value={stats.publikasi_nasional_sinta34.toLocaleString()}
            icon={Award}
            color="#8B5CF6"
            previousValue={stats.previous_values?.publikasi_nasional_sinta34}
            previousDate={stats.previous_date}
          />
        </div>

        {/* Additional Sinta 5-6 */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
          <StatCard
            title="Nasional (Sinta 5-6)"
            value={(stats.publikasi_nasional_sinta5 + stats.publikasi_nasional_sinta6).toLocaleString()}
            icon={Award}
            color="#A78BFA"
            previousValue={(stats.previous_values?.publikasi_nasional_sinta5 || 0) + (stats.previous_values?.publikasi_nasional_sinta6 || 0)}
            previousDate={stats.previous_date}
          />
        </div>

        {/* Publikasi by Year Chart */}
        <div className="bg-white rounded-lg shadow-md p-6 mb-8">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center">
              <Calendar className="w-5 h-5 text-blue-600 mr-2" />
              <h2 className="text-lg font-semibold text-gray-900">
                Publikasi per Tahun ({yearRange} Tahun Terakhir)
                {!hasFilter && ' - Per Fakultas'}
              </h2>
            </div>
            <div className="relative">
              <select
                className="pl-10 pr-10 py-2.5 border-2 border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 bg-white hover:border-gray-400 transition-all duration-200 appearance-none cursor-pointer shadow-sm text-sm font-medium text-gray-700"
                value={yearRange}
                onChange={(e) => setYearRange(parseInt(e.target.value))}
              >
                <option value={5}>5 Tahun</option>
                <option value={10}>10 Tahun</option>
                <option value={15}>15 Tahun</option>
              </select>
            </div>
          </div>
          <ResponsiveContainer width="100%" height={350}>
            <BarChart data={filteredYearData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="name" />
              <YAxis />
              <Tooltip />
              <Legend />
              {!hasFilter && uniqueFacultiesYear.length > 0 ? (
                // Stacked bars - no filter
                uniqueFacultiesYear.map((faculty) => (
                  <Bar 
                    key={faculty}
                    dataKey={faculty}
                    stackId="a"
                    fill={FACULTY_COLORS[faculty] || '#6B7280'}
                    name={faculty}
                  />
                ))
              ) : (
                // Simple bar - with filter
                <Bar dataKey="count" fill="#3B82F6" name="Jumlah Publikasi" />
              )}
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Top Authors - Scopus and GS */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 mb-8">
          {/* Top Dosen by h-index (Scopus) */}
          <div className="bg-white rounded-lg shadow-md p-6">
            <div className="flex items-center mb-4">
              <Award className="w-5 h-5 text-green-600 mr-2" />
              <h2 className="text-lg font-semibold text-gray-900">Top 10 Dosen (h-index Scopus)</h2>
            </div>
            {stats.top_authors_scopus && stats.top_authors_scopus.length > 0 ? (
              <ResponsiveContainer width="100%" height={400}>
                <BarChart
                  data={stats.top_authors_scopus.slice(0, 10)}
                  layout="vertical"
                  margin={{ top: 5, right: 30, left: -50, bottom: 5 }}
                >
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis type="number" />
                  <YAxis 
                    dataKey="v_nama_dosen" 
                    type="category" 
                    width={190}
                    interval={0}
                    tick={{ fontSize: 11 }}
                    tickFormatter={(value) => value.length > 25 ? value.substring(0, 25) + '...' : value}
                  />
                  <Tooltip 
                    formatter={(value) => value.toLocaleString()}
                    labelFormatter={(label) => `Dosen: ${label}`}
                  />
                  <Legend />
                  <Bar 
                    dataKey="n_h_index_scopus" 
                    fill="#10B981" 
                    name="h-index Scopus"
                    radius={[0, 8, 8, 0]}
                  />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className="flex items-center justify-center h-64 text-gray-400">
                <p>Tidak ada data dosen</p>
              </div>
            )}
          </div>

          {/* Top Dosen by h-index (Google Scholar) */}
          <div className="bg-white rounded-lg shadow-md p-6">
            <div className="flex items-center mb-4">
              <Award className="w-5 h-5 text-red-600 mr-2" />
              <h2 className="text-lg font-semibold text-gray-900">Top 10 Dosen (h-index Google Scholar)</h2>
            </div>
            {stats.top_authors_gs && stats.top_authors_gs.length > 0 ? (
              <ResponsiveContainer width="100%" height={400}>
                <BarChart
                  data={stats.top_authors_gs.slice(0, 10)}
                  layout="vertical"
                  margin={{ top: 5, right: 30, left: -50, bottom: 5 }}
                >
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis type="number" />
                  <YAxis 
                    dataKey="v_nama_dosen" 
                    type="category" 
                    width={190}
                    interval={0}
                    tick={{ fontSize: 11 }}
                    tickFormatter={(value) => value.length > 25 ? value.substring(0, 25) + '...' : value}
                  />
                  <Tooltip 
                    formatter={(value) => value.toLocaleString()}
                    labelFormatter={(label) => `Dosen: ${label}`}
                  />
                  <Legend />
                  <Bar 
                    dataKey="n_h_index_gs" 
                    fill="#EF4444" 
                    name="h-index GS"
                    radius={[0, 8, 8, 0]}
                  />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className="flex items-center justify-center h-64 text-gray-400">
                <p>Tidak ada data dosen</p>
              </div>
            )}
          </div>
        </div>

        {/* Breakdown Charts */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 mb-8">
          {/* Scopus Q Breakdown */}
          <div className="bg-white rounded-lg shadow-md p-6">
            <div className="flex items-center mb-4">
              <Award className="w-5 h-5 text-emerald-600 mr-2" />
              <h2 className="text-lg font-semibold text-gray-900">
                Scopus Breakdown (Q){!hasFilter && ' - Per Fakultas'}
              </h2>
            </div>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={scopusData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="name" />
                <YAxis />
                <Tooltip />
                <Legend />
                {!hasFilter && uniqueFacultiesScopus.length > 0 ? (
                  // Stacked bars - no filter
                  uniqueFacultiesScopus.map((faculty) => (
                    <Bar 
                      key={faculty}
                      dataKey={faculty}
                      stackId="a"
                      fill={FACULTY_COLORS[faculty] || '#6B7280'}
                      name={faculty}
                    />
                  ))
                ) : (
                  // Simple bar - with filter
                  <Bar dataKey="count" fill="#10B981" name="Jumlah" />
                )}
              </BarChart>
            </ResponsiveContainer>
          </div>
          
          {/* Sinta Rank Breakdown */}
          <div className="bg-white rounded-lg shadow-md p-6">
            <div className="flex items-center mb-4">
              <Award className="w-5 h-5 text-indigo-600 mr-2" />
              <h2 className="text-lg font-semibold text-gray-900">
                Sinta Breakdown (S1–S6){!hasFilter && ' - Per Fakultas'}
              </h2>
            </div>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={sintaData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="name" />
                <YAxis />
                <Tooltip />
                <Legend />
                {!hasFilter && uniqueFacultiesSinta.length > 0 ? (
                  // Stacked bars - no filter
                  uniqueFacultiesSinta.map((faculty) => (
                    <Bar 
                      key={faculty}
                      dataKey={faculty}
                      stackId="a"
                      fill={FACULTY_COLORS[faculty] || '#6B7280'}
                      name={faculty}
                    />
                  ))
                ) : (
                  // Simple bar - with filter
                  <Bar dataKey="count" fill="#6366F1" name="Jumlah" />
                )}
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Summary Statistics */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 mb-8">
          {/* Summary Card Column */}
          <div className="bg-white rounded-lg shadow-md p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">Ringkasan Statistik</h2>
            <div className="space-y-4">
              <div className="flex justify-between items-center p-3 bg-blue-50 rounded-lg">
                <span className="text-sm font-medium text-gray-600">Rata-rata Publikasi/Dosen</span>
                <span className="text-lg font-bold text-blue-600">
                  {stats.total_dosen > 0 ? Math.round(stats.total_publikasi / stats.total_dosen) : 0}
                </span>
              </div>
              
              <div className="flex justify-between items-center p-3 bg-green-50 rounded-lg">
                <span className="text-sm font-medium text-gray-600">Rata-rata Sitasi/Publikasi</span>
                <span className="text-lg font-bold text-green-600">
                  {stats.total_publikasi > 0 ? Math.round(stats.total_sitasi / stats.total_publikasi) : 0}
                </span>
              </div>
              
              <div className="flex justify-between items-center p-3 bg-yellow-50 rounded-lg">
                <span className="text-sm font-medium text-gray-600">Top h-index (GS)</span>
                <span className="text-sm font-bold text-yellow-600">
                  {stats.top_authors_gs?.[0]?.v_nama_dosen?.substring(0, 15)}...
                </span>
              </div>

              <div className="flex justify-between items-center p-3 bg-red-50 rounded-lg">
                <span className="text-sm font-medium text-gray-600">Tahun Paling Produktif</span>
                <div className="text-right">
                  <span className="text-sm font-bold text-red-600 block">
                    {(() => {
                      if (!stats.publikasi_by_year || stats.publikasi_by_year.length === 0) return '-';
                      
                      const maxCount = Math.max(...stats.publikasi_by_year.map(item => item.count));
                      if (maxCount === 0) return '-';
                      
                      const topYears = stats.publikasi_by_year
                        .filter(item => item.count === maxCount)
                        .map(item => item.v_tahun_publikasi)
                        .sort();
                      
                      return topYears.join(', ');
                    })()}
                  </span>
                  <span className="text-xs text-red-500">
                    {(() => {
                      const maxCount = Math.max(...stats.publikasi_by_year.map(item => item.count));
                      return maxCount > 0 ? `(${maxCount} publikasi)` : '';
                    })()}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Top 10 Dosen Berdasarkan h-index (Google Scholar) */}
        <div className="bg-white rounded-lg shadow-md p-6">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center">
              <Search className="w-5 h-5 text-indigo-600 mr-2" />
              <h2 className="text-lg font-semibold text-gray-900">Top 10 Dosen Berdasarkan h-index (Google Scholar)</h2>
            </div>
          </div>
          
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Ranking
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Nama Dosen
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    h-index (GS)
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Persentase
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {stats.top_authors_gs.slice(0, 10).map((author, index) => (
                  <tr key={index} className={index % 2 === 0 ? 'bg-white' : 'bg-gray-50'}>
                    <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                      <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                        index === 0 ? 'bg-yellow-100 text-yellow-800' :
                        index === 1 ? 'bg-gray-100 text-gray-800' :
                        index === 2 ? 'bg-orange-100 text-orange-800' :
                        'bg-blue-100 text-blue-800'
                      }`}>
                        #{index + 1}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      {author.v_nama_dosen}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      {author.n_h_index_gs?.toLocaleString() || 0}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {stats.top_authors_gs.length > 0 ? 
                        ((author.n_h_index_gs / Math.max(1, stats.top_authors_gs[0].n_h_index_gs)) * 100).toFixed(1) : 0}%
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Top 10 Dosen Internasional (Scopus) - styled like GS table */}
        <div className="bg-white rounded-lg shadow-md p-6 mt-8">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center">
              <Search className="w-5 h-5 text-emerald-600 mr-2" />
              <h2 className="text-lg font-semibold text-gray-900">Top 10 Dosen Berdasarkan Publikasi Internasional (Scopus)</h2>
            </div>
          </div>
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Ranking</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Nama Dosen</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Jumlah Publikasi</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Persentase</th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {stats.top_dosen_international.slice(0, 10).map((author, index) => (
                  <tr key={index} className={index % 2 === 0 ? 'bg-white' : 'bg-gray-50'}>
                    <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                      <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                        index === 0 ? 'bg-yellow-100 text-yellow-800' :
                        index === 1 ? 'bg-gray-100 text-gray-800' :
                        index === 2 ? 'bg-orange-100 text-orange-800' :
                        'bg-blue-100 text-blue-800'
                      }`}>
                        #{index + 1}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">{author.v_nama_dosen}</td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">{author.count_international?.toLocaleString() || 0}</td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {(() => {
                        const maxVal = stats.top_dosen_international?.[0]?.count_international || 0;
                        return maxVal > 0 ? ((author.count_international / maxVal) * 100).toFixed(1) : '0.0';
                      })()}%
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Top 10 Dosen Nasional (Sinta 1-6) - styled like GS table */}
        <div className="bg-white rounded-lg shadow-md p-6 mt-8">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center">
              <Search className="w-5 h-5 text-indigo-600 mr-2" />
              <h2 className="text-lg font-semibold text-gray-900">Top 10 Dosen Berdasarkan Publikasi Nasional (Sinta 1–6)</h2>
            </div>
          </div>
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Ranking</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Nama Dosen</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Jumlah Publikasi</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Persentase</th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {stats.top_dosen_national.slice(0, 10).map((author, index) => (
                  <tr key={index} className={index % 2 === 0 ? 'bg-white' : 'bg-gray-50'}>
                    <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                      <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                        index === 0 ? 'bg-yellow-100 text-yellow-800' :
                        index === 1 ? 'bg-gray-100 text-gray-800' :
                        index === 2 ? 'bg-orange-100 text-orange-800' :
                        'bg-blue-100 text-blue-800'
                      }`}>
                        #{index + 1}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">{author.v_nama_dosen}</td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">{author.count_national?.toLocaleString() || 0}</td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {(() => {
                        const maxVal = stats.top_dosen_national?.[0]?.count_national || 0;
                        return maxVal > 0 ? ((author.count_national / maxVal) * 100).toFixed(1) : '0.0';
                      })()}%
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;