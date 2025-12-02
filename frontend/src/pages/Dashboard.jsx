import { useState, useEffect } from 'react';
import { BarChart, Bar, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { Users, FileText, TrendingUp, Award, Calendar, Search, ArrowUp, ArrowDown, Filter, Building2, GraduationCap, RefreshCw } from 'lucide-react';
import apiService from '../services/apiService';
import Layout from '../components/Layout';

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
  
  // Filter states - changed to arrays for checkbox support
  const [selectedFaculties, setSelectedFaculties] = useState([]);
  const [selectedDepartments, setSelectedDepartments] = useState([]);
  const [faculties, setFaculties] = useState([]);
  const [departments, setDepartments] = useState([]);
  const [loadingDepartments, setLoadingDepartments] = useState(false);
  const [showFacultyFilter, setShowFacultyFilter] = useState(true);
  const [showDepartmentFilter, setShowDepartmentFilter] = useState(true);

  useEffect(() => {
    console.log('🎯 Component mounted, fetching faculties...');
    fetchFaculties();
  }, []);

  useEffect(() => {
    console.log('🔍 SelectedFaculties changed:', selectedFaculties);
    // Fetch departments for all selected faculties
    if (selectedFaculties.length > 0) {
      fetchDepartmentsForFaculties(selectedFaculties);
    } else {
      setDepartments([]);
      setSelectedDepartments([]);
    }
  }, [selectedFaculties]);

  useEffect(() => {
    console.log('🔍 Filter changed, fetching dashboard stats...');
    console.log('🔍 Current filters:', { selectedFaculties, selectedDepartments });
    fetchDashboardStats();
  }, [selectedFaculties, selectedDepartments]);

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

  const fetchDepartmentsForFaculties = async (facultiesList) => {
    try {
      setLoadingDepartments(true);
      // Fetch departments for each faculty and combine unique ones
      const allDepartments = new Set();
      
      for (const faculty of facultiesList) {
        try {
          const response = await apiService.getDashboardDepartments(faculty);
          if (response.success && response.data && Array.isArray(response.data)) {
            response.data.forEach(dept => allDepartments.add(dept));
          }
        } catch (error) {
          console.error(`Error fetching departments for ${faculty}:`, error);
        }
      }
      
      setDepartments(Array.from(allDepartments).sort());
    } catch (error) {
      console.error('Error fetching departments:', error);
      setDepartments([]);
    } finally {
      setLoadingDepartments(false);
    }
  };

  const fetchDashboardStats = async () => {
    console.log('🚀 fetchDashboardStats STARTED');
    console.log('🔍 Current filter state:', { selectedFaculties, selectedDepartments });
    
    try {
      setLoading(true);
      // Convert arrays to comma-separated strings for API
      const facultyParam = selectedFaculties.length > 0 ? selectedFaculties.join(',') : '';
      const departmentParam = selectedDepartments.length > 0 ? selectedDepartments.join(',') : '';
      console.log('🔍 Fetching stats with:', { 
        selectedFaculties, 
        selectedDepartments, 
        facultyParam, 
        departmentParam,
        hasFacultyFilter: facultyParam.length > 0,
        hasDepartmentFilter: departmentParam.length > 0
      });
      
      const response = await apiService.getDashboardStats(facultyParam, departmentParam);
      
      console.log('📦 Response received:', response);
      
      if (response && response.success && response.data) {
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
        if (response && response.error) {
          console.error('❌ API Error:', response.error);
        }
        // Don't reset stats completely, keep previous data
      }
    } catch (error) {
      console.error('❌ Catch error:', error);
      console.error('❌ Error details:', error.response?.data || error.message);
      console.error('❌ Error response:', error.response);
      console.error('❌ Error traceback:', error.response?.data?.traceback);
      
      // Show user-friendly error message
      if (error.response?.data) {
        console.error('❌ Backend error:', error.response.data.error);
        console.error('❌ Error type:', error.response.data.error_type);
        console.error('❌ Error details:', error.response.data.details);
        console.error('❌ Full error response:', JSON.stringify(error.response.data, null, 2));
        
        // Show alert with error details for debugging
        if (error.response.data.traceback) {
          console.error('❌ Full traceback:', error.response.data.traceback);
        }
      }
      
      // Don't reset stats on error, keep previous data
    } finally {
      setLoading(false);
    }
  };

  // Faculty to Department mapping (should match backend)
  const FACULTY_DEPT_MAP = {
    'Fakultas Ekonomi': ['Ekonomi Pembangunan', 'Ilmu Ekonomi', 'Manajemen', 'Akuntansi'],
    'Fakultas Hukum': ['Ilmu Hukum', 'Hukum'],
    'Fakultas Ilmu Sosial dan Ilmu Politik': ['Administrasi Publik', 'Administrasi Bisnis', 'Hubungan Internasional', 'Ilmu Administrasi Publik', 'Ilmu Administrasi Bisnis', 'Ilmu Hubungan Internasional'],
    'Fakultas Teknik': ['Teknik Sipil', 'Arsitektur', 'Doktor Arsitektur', 'Teknik Industri', 'Teknik Kimia', 'Teknik Mekatronika'],
    'Fakultas Filsafat': ['Filsafat', 'Ilmu Filsafat', 'Studi Humanitas'],
    'Fakultas Teknologi Informasi dan Sains': ['Matematika', 'Fisika', 'Informatika', 'Teknik Informatika', 'Ilmu Komputer'],
    'Fakultas Kedokteran': ['Kedokteran', 'Pendidikan Dokter'],
    'Fakultas Keguruan dan Ilmu Pendidikan': ['Pendidikan Kimia', 'Pendidikan Fisika', 'Pendidikan Matematika', 'Pendidikan Teknik Informatika dan Komputer', 'Pendidikan Bahasa Inggris', 'Pendidikan Guru Sekolah Dasar', 'PGSD'],
    'Fakultas Vokasi': ['Teknologi Rekayasa Pangan', 'Bisnis Kreatif', 'Agribisnis Pangan']
  };

  const handleFacultyCheckboxChange = (faculty, isChecked) => {
    console.log('🔍 Faculty checkbox changed:', { faculty, isChecked });
    if (isChecked) {
      setSelectedFaculties(prev => {
        const newFaculties = [...prev, faculty];
        console.log('✅ Added faculty, new list:', newFaculties);
        return newFaculties;
      });
    } else {
      setSelectedFaculties(prev => {
        const newFaculties = prev.filter(f => f !== faculty);
        console.log('❌ Removed faculty, new list:', newFaculties);
        
        // Remove departments that belong only to the unchecked faculty
        if (newFaculties.length > 0) {
          // Get all departments from remaining faculties
          const remainingDepts = new Set();
          newFaculties.forEach(f => {
            const depts = FACULTY_DEPT_MAP[f] || [];
            depts.forEach(d => remainingDepts.add(d));
          });
          
          // Remove departments that are not in any remaining faculty
          setSelectedDepartments(prevDepts => {
            const filtered = prevDepts.filter(dept => remainingDepts.has(dept));
            console.log('🔍 Filtered departments:', filtered);
            return filtered;
          });
        } else {
          // No faculties selected, clear all departments
          console.log('🔍 No faculties selected, clearing departments');
          setSelectedDepartments([]);
        }
        
        return newFaculties;
      });
    }
  };

  const handleDepartmentCheckboxChange = (department, isChecked) => {
    console.log('🔍 Department checkbox changed:', { department, isChecked });
    if (isChecked) {
      setSelectedDepartments(prev => {
        const newDepts = [...prev, department];
        console.log('✅ Added department, new list:', newDepts);
        return newDepts;
      });
    } else {
      setSelectedDepartments(prev => {
        const newDepts = prev.filter(d => d !== department);
        console.log('❌ Removed department, new list:', newDepts);
        return newDepts;
      });
    }
  };

  const handleSelectAllFaculties = () => {
    if (selectedFaculties.length === faculties.length) {
      setSelectedFaculties([]);
      setSelectedDepartments([]);
    } else {
      setSelectedFaculties([...faculties]);
    }
  };

  const handleSelectAllDepartments = () => {
    if (selectedDepartments.length === departments.length) {
      setSelectedDepartments([]);
    } else {
      setSelectedDepartments([...departments]);
    }
  };

  const handleResetFilters = () => {
    setSelectedFaculties([]);
    setSelectedDepartments([]);
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

  // Remove "Fakultas " prefix from faculty name for display
  const removeFakultasPrefix = (facultyName) => {
    if (!facultyName) return facultyName;
    return facultyName.replace(/^Fakultas\s+/i, '');
  };

  if (loading) {
    return (
      <Layout
        title="Dashboard"
        description="Overview sistem publikasi dosen SINTA & Google Scholar"
      >
        <div className="min-h-screen bg-gray-50 flex items-center justify-center">
          <div className="text-center">
            <div className="animate-spin rounded-full h-32 w-32 border-b-2 border-blue-600 mx-auto"></div>
            <p className="mt-4 text-gray-600">Memuat data dashboard...</p>
          </div>
        </div>
      </Layout>
    );
  }

  // Initialize stats with default values if not available
  const safeStats = {
    total_dosen: stats?.total_dosen || 0,
    total_publikasi: stats?.total_publikasi || 0,
    total_sitasi: stats?.total_sitasi || 0,
    total_sitasi_gs: stats?.total_sitasi_gs || 0,
    total_sitasi_gs_sinta: stats?.total_sitasi_gs_sinta || 0,
    total_sitasi_scopus: stats?.total_sitasi_scopus || 0,
    avg_h_index: stats?.avg_h_index || 0,
    median_h_index: stats?.median_h_index || 0,
    publikasi_by_year: stats?.publikasi_by_year || [],
    top_authors_scopus: stats?.top_authors_scopus || [],
    top_authors_gs: stats?.top_authors_gs || [],
    publikasi_internasional_q12: stats?.publikasi_internasional_q12 || 0,
    publikasi_internasional_q34_noq: stats?.publikasi_internasional_q34_noq || 0,
    publikasi_nasional_sinta12: stats?.publikasi_nasional_sinta12 || 0,
    publikasi_nasional_sinta34: stats?.publikasi_nasional_sinta34 || 0,
    publikasi_nasional_sinta5: stats?.publikasi_nasional_sinta5 || 0,
    publikasi_nasional_sinta6: stats?.publikasi_nasional_sinta6 || 0,
    scopus_q_breakdown: stats?.scopus_q_breakdown || [],
    sinta_rank_breakdown: stats?.sinta_rank_breakdown || [],
    top_dosen_international: stats?.top_dosen_international || [],
    top_dosen_national: stats?.top_dosen_national || [],
    previous_date: stats?.previous_date || null,
    previous_values: stats?.previous_values || {},
    has_filter: stats?.has_filter !== undefined ? stats.has_filter : (selectedFaculties.length > 0 || selectedDepartments.length > 0)
  };

  // Determine if filter is active based on frontend state (more reliable)
  const hasFilter = selectedFaculties.length > 0 || selectedDepartments.length > 0;
  
  console.log('🔍 Filter status:', {
    hasFilter,
    selectedFaculties,
    selectedDepartments,
    backendHasFilter: safeStats.has_filter
  });

  // Transform data for line chart (SINTA vs Google Scholar)
  const transformForLineChart = (data) => {
    if (!data || data.length === 0) {
      console.log('⚠️ No data for line chart');
      return [];
    }
    
    console.log('📊 Raw data for line chart:', data);
    
    const transformed = data.map(item => ({
      name: item.v_tahun_publikasi || item.name || '',
      SINTA: Number(item.count_sinta) || 0,
      'Google Scholar': Number(item.count_gs) || 0
    })).sort((a, b) => {
      const aYear = parseInt(a.name);
      const bYear = parseInt(b.name);
      if (!isNaN(aYear) && !isNaN(bYear)) {
        return aYear - bYear;
      }
      return a.name.localeCompare(b.name);
    });
    
    console.log('📊 Transformed data for line chart:', transformed);
    return transformed;
  };

  const filteredYearData = (() => {
    const currentYear = new Date().getFullYear();
    const yearData = safeStats.publikasi_by_year || [];
    console.log('📊 Raw publikasi_by_year data:', yearData);
    console.log('📊 Year range:', currentYear - yearRange, 'to', currentYear);
    
    if (!yearData || yearData.length === 0) {
      console.log('⚠️ No year data available');
      return [];
    }
    
    const filtered = yearData.filter(item => {
      const yearStr = item.v_tahun_publikasi || item.name || '';
      const year = parseInt(yearStr);
      const isValid = !isNaN(year) && year >= currentYear - yearRange && year <= currentYear;
      if (!isValid) {
        console.log(`⚠️ Filtered out year: ${yearStr} (parsed: ${year})`);
      }
      return isValid;
    });
    
    console.log('📊 Filtered year data:', filtered);
    console.log('📊 Filtered count:', filtered.length);
    
    // Use line chart transform for publikasi by year
    const transformed = transformForLineChart(filtered);
    console.log('📊 Final transformed data for chart:', transformed);
    console.log('📊 Transformed count:', transformed.length);
    
    if (transformed.length > 0) {
      console.log('📊 First item:', transformed[0]);
      console.log('📊 Last item:', transformed[transformed.length - 1]);
    }
    
    return transformed;
  })();

  const uniqueFacultiesYear = getUniqueFaculties(safeStats.publikasi_by_year || []);
  const scopusData = transformForStackedChart(safeStats.scopus_q_breakdown || [], hasFilter);
  const uniqueFacultiesScopus = getUniqueFaculties(safeStats.scopus_q_breakdown || []);
  const sintaData = transformForStackedChart(safeStats.sinta_rank_breakdown || [], hasFilter);
  const uniqueFacultiesSinta = getUniqueFaculties(safeStats.sinta_rank_breakdown || []);

  return (
    <Layout
      title="Dashboard"
      description="Overview sistem publikasi dosen SINTA & Google Scholar"
    >

        {/* Global Filters */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6 mb-8 hover:shadow-md transition-shadow duration-300">
          <div className="flex items-center gap-2 mb-6">
            <div className="p-2 bg-blue-50 rounded-lg">
              <Filter className="w-5 h-5 text-blue-600" />
            </div>
            <h2 className="text-lg font-semibold text-gray-900">Filter Data</h2>
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Faculty Filter - Checkbox */}
            <div className="relative">
              <div className="flex items-center justify-between mb-3">
                <label className="block text-sm font-semibold text-gray-700 flex items-center">
                  <Building2 className="w-4 h-4 mr-1.5 text-red-600" />
                  Fakultas ({selectedFaculties.length}/{faculties.length})
                </label>
                <div className="flex items-center gap-2">
                  <button
                    onClick={handleSelectAllFaculties}
                    className="text-xs text-blue-600 hover:text-blue-800 font-medium"
                  >
                    {selectedFaculties.length === faculties.length ? 'Batal Semua' : 'Pilih Semua'}
                  </button>
                  <button
                    onClick={() => setShowFacultyFilter(!showFacultyFilter)}
                    className="text-xs text-gray-600 hover:text-gray-800"
                  >
                    {showFacultyFilter ? 'Sembunyikan' : 'Tampilkan'}
                  </button>
                </div>
              </div>
              {showFacultyFilter && (
                <div className="border-2 border-gray-300 rounded-lg p-4 max-h-64 overflow-y-auto bg-white">
                  {loadingDepartments && faculties.length === 0 ? (
                    <div className="flex items-center justify-center py-4">
                      <RefreshCw className="w-4 h-4 text-blue-500 animate-spin mr-2" />
                      <p className="text-sm text-gray-600">Memuat fakultas...</p>
                    </div>
                  ) : Array.isArray(faculties) && faculties.length > 0 ? (
                    <div className="space-y-2">
                      {faculties.map((faculty) => (
                        <label
                          key={faculty}
                          className="flex items-center p-2 hover:bg-gray-50 rounded cursor-pointer group"
                        >
                          <input
                            type="checkbox"
                            checked={selectedFaculties.includes(faculty)}
                            onChange={(e) => handleFacultyCheckboxChange(faculty, e.target.checked)}
                            className="w-4 h-4 text-red-600 border-gray-300 rounded focus:ring-red-500 focus:ring-2 cursor-pointer"
                          />
                          <span className="ml-3 text-sm text-gray-700 group-hover:text-gray-900">
                            {faculty}
                          </span>
                        </label>
                      ))}
                    </div>
                  ) : (
                    <p className="text-sm text-gray-500 text-center py-4">Tidak ada fakultas tersedia</p>
                  )}
                </div>
              )}
            </div>

            {/* Department Filter - Checkbox */}
            <div className="relative">
              <div className="flex items-center justify-between mb-3">
                <label className="block text-sm font-semibold text-gray-700 flex items-center">
                  <GraduationCap className="w-4 h-4 mr-1.5 text-blue-600" />
                  Prodi ({selectedDepartments.length}/{departments.length})
                </label>
                <div className="flex items-center gap-2">
                  <button
                    onClick={handleSelectAllDepartments}
                    disabled={departments.length === 0 || selectedFaculties.length === 0}
                    className="text-xs text-blue-600 hover:text-blue-800 font-medium disabled:text-gray-400 disabled:cursor-not-allowed"
                  >
                    {selectedDepartments.length === departments.length ? 'Batal Semua' : 'Pilih Semua'}
                  </button>
                  <button
                    onClick={() => setShowDepartmentFilter(!showDepartmentFilter)}
                    disabled={departments.length === 0 || selectedFaculties.length === 0}
                    className="text-xs text-gray-600 hover:text-gray-800 disabled:text-gray-400 disabled:cursor-not-allowed"
                  >
                    {showDepartmentFilter ? 'Sembunyikan' : 'Tampilkan'}
                  </button>
                </div>
              </div>
              {showDepartmentFilter && (
                <div className="border-2 border-gray-300 rounded-lg p-4 max-h-64 overflow-y-auto bg-white">
                  {loadingDepartments ? (
                    <div className="flex items-center justify-center py-4">
                      <RefreshCw className="w-4 h-4 text-blue-500 animate-spin mr-2" />
                      <p className="text-sm text-blue-600 font-medium">Memuat prodi...</p>
                    </div>
                  ) : selectedFaculties.length === 0 ? (
                    <p className="text-sm text-gray-500 text-center py-4">🔒 Pilih fakultas terlebih dahulu</p>
                  ) : Array.isArray(departments) && departments.length > 0 ? (
                    <div className="space-y-2">
                      {departments.map((dept) => (
                        <label
                          key={dept}
                          className="flex items-center p-2 hover:bg-gray-50 rounded cursor-pointer group"
                        >
                          <input
                            type="checkbox"
                            checked={selectedDepartments.includes(dept)}
                            onChange={(e) => handleDepartmentCheckboxChange(dept, e.target.checked)}
                            className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500 focus:ring-2 cursor-pointer"
                          />
                          <span className="ml-3 text-sm text-gray-700 group-hover:text-gray-900">
                            {dept}
                          </span>
                        </label>
                      ))}
                    </div>
                  ) : (
                    <p className="text-sm text-gray-500 text-center py-4">Tidak ada prodi tersedia</p>
                  )}
                </div>
              )}
            </div>
          </div>

          {/* Reset Button and Active Filters Display */}
          <div className="mt-4 flex items-center justify-between flex-wrap gap-4">
            <button
              onClick={handleResetFilters}
              disabled={selectedFaculties.length === 0 && selectedDepartments.length === 0}
              className="px-4 py-2.5 bg-gradient-to-r from-gray-100 to-gray-200 text-gray-700 rounded-lg hover:from-gray-200 hover:to-gray-300 transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed font-medium shadow-sm flex items-center justify-center group"
            >
              <RefreshCw className="w-4 h-4 mr-2 group-hover:rotate-180 transition-transform duration-300" />
              Reset Filter
            </button>

            {/* Active Filters Display */}
            {(selectedFaculties.length > 0 || selectedDepartments.length > 0) && (
              <div className="flex items-center flex-wrap gap-2">
                <span className="text-sm text-gray-600 font-medium flex items-center">
                  <Filter className="w-4 h-4 mr-1 text-blue-600" />
                  Filter aktif:
                </span>
                {selectedFaculties.map((faculty) => (
                  <span
                    key={faculty}
                    className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-red-100 text-red-800"
                  >
                    <Building2 className="w-4 h-4 mr-1" />
                    {faculty}
                  </span>
                ))}
                {selectedDepartments.map((dept) => (
                  <span
                    key={dept}
                    className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-blue-100 text-blue-800"
                  >
                    <GraduationCap className="w-4 h-4 mr-1" />
                    {dept}
                  </span>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Filter Status Banner */}
        {hasFilter && (
          <div className="bg-blue-50 border-l-4 border-blue-500 p-4 mb-6 rounded-r-lg">
            <div className="flex items-center">
              <Filter className="w-5 h-5 text-blue-600 mr-2" />
              <p className="text-sm font-medium text-blue-900">
                Data yang ditampilkan sudah difilter berdasarkan:
                {selectedFaculties.length > 0 && (
                  <span className="ml-2">
                    {selectedFaculties.length} Fakultas
                    {selectedFaculties.length > 0 && selectedDepartments.length > 0 && ' dan '}
                  </span>
                )}
                {selectedDepartments.length > 0 && (
                  <span className="ml-2">
                    {selectedDepartments.length} Prodi
                  </span>
                )}
              </p>
            </div>
          </div>
        )}

        {/* Stats Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
          <StatCard
            title="Total Dosen"
            value={safeStats.total_dosen.toLocaleString()}
            icon={Users}
            color="#3B82F6"
            previousValue={safeStats.previous_values?.total_dosen}
            previousDate={safeStats.previous_date}
          />
          <StatCard
            title="Total Publikasi"
            value={safeStats.total_publikasi.toLocaleString()}
            icon={FileText}
            color="#10B981"
            previousValue={safeStats.previous_values?.total_publikasi}
            previousDate={safeStats.previous_date}
          />
          <StatCard
            title="Total Sitasi"
            value={safeStats.total_sitasi.toLocaleString()}
            subtitle={`GS: ${safeStats.total_sitasi_gs?.toLocaleString() || 0} | GS-SINTA: ${safeStats.total_sitasi_gs_sinta?.toLocaleString() || 0} | Scopus: ${safeStats.total_sitasi_scopus?.toLocaleString() || 0}`}
            icon={Award}
            color="#F59E0B"
            previousValue={safeStats.previous_values?.total_sitasi}
            previousDate={safeStats.previous_date}
          />
          <StatCard
            title="H-Index Rata-rata"
            value={safeStats.avg_h_index ? safeStats.avg_h_index.toFixed(1) : '0.0'}
            subtitle={`Median: ${safeStats.median_h_index ? safeStats.median_h_index.toFixed(1) : '0.0'}`}
            icon={TrendingUp}
            color="#EF4444"
            previousValue={safeStats.previous_values?.avg_h_index}
            previousDate={safeStats.previous_date}
          />
        </div>

        {/* International vs National Summary */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
          <StatCard
            title="Internasional (Scopus Q1-Q2)"
            value={safeStats.publikasi_internasional_q12.toLocaleString()}
            icon={Award}
            color="#059669"
            previousValue={stats.previous_values?.publikasi_internasional_q12}
            previousDate={stats.previous_date}
          />
          <StatCard
            title="Internasional (Q3-Q4/noQ)"
            value={safeStats.publikasi_internasional_q34_noq.toLocaleString()}
            icon={Award}
            color="#10B981"
            previousValue={stats.previous_values?.publikasi_internasional_q34_noq}
            previousDate={stats.previous_date}
          />
          <StatCard
            title="Nasional (Sinta 1-2)"
            value={safeStats.publikasi_nasional_sinta12.toLocaleString()}
            icon={Award}
            color="#7C3AED"
            previousValue={stats.previous_values?.publikasi_nasional_sinta12}
            previousDate={stats.previous_date}
          />
          <StatCard
            title="Nasional (Sinta 3-4)"
            value={safeStats.publikasi_nasional_sinta34.toLocaleString()}
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
            value={(safeStats.publikasi_nasional_sinta5 + safeStats.publikasi_nasional_sinta6).toLocaleString()}
            icon={Award}
            color="#A78BFA"
            previousValue={(safeStats.previous_values?.publikasi_nasional_sinta5 || 0) + (safeStats.previous_values?.publikasi_nasional_sinta6 || 0)}
            previousDate={safeStats.previous_date}
          />
        </div>

        {/* Publikasi by Year Charts - Separated by Source */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 mb-8">
          {/* Chart SINTA */}
          <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6 hover:shadow-md transition-shadow duration-300">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center">
                <Calendar className="w-5 h-5 text-blue-600 mr-2" />
                <h2 className="text-lg font-semibold text-gray-900">
                  Publikasi SINTA per Tahun ({yearRange} Tahun Terakhir)
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
            {(() => {
              const sintaData = filteredYearData.map(item => ({
                name: item.name,
                'Publikasi SINTA': item.SINTA || 0
              }));
              
              if (!sintaData || sintaData.length === 0 || sintaData.every(item => item['Publikasi SINTA'] === 0)) {
                return (
                  <div className="flex items-center justify-center h-64 text-gray-400">
                    <div className="text-center">
                      <p className="text-lg mb-2">Tidak ada data SINTA</p>
                      <p className="text-sm">Data publikasi SINTA per tahun belum tersedia</p>
                    </div>
                  </div>
                );
              }
              
              return (
                <div style={{ width: '100%', height: '350px' }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart 
                      data={sintaData}
                      margin={{ top: 5, right: 30, left: 20, bottom: 5 }}
                    >
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis 
                        dataKey="name" 
                        label={{ value: 'Tahun', position: 'insideBottom', offset: -5 }}
                        tick={{ fontSize: 12 }}
                      />
                      <YAxis 
                        label={{ value: 'Jumlah Publikasi', angle: -90, position: 'insideLeft' }}
                        tick={{ fontSize: 12 }}
                      />
                      <Tooltip 
                        formatter={(value, name) => [value, name]}
                        labelFormatter={(label) => `Tahun: ${label}`}
                      />
                      <Legend />
                      <Line 
                        type="monotone" 
                        dataKey="Publikasi SINTA" 
                        stroke="#3B82F6" 
                        strokeWidth={3}
                        dot={{ r: 5, fill: '#3B82F6' }}
                        activeDot={{ r: 7 }}
                        name="Publikasi SINTA"
                        connectNulls={false}
                      />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              );
            })()}
          </div>

          {/* Chart Google Scholar */}
          <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6 hover:shadow-md transition-shadow duration-300">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center">
                <Calendar className="w-5 h-5 text-green-600 mr-2" />
                <h2 className="text-lg font-semibold text-gray-900">
                  Publikasi Google Scholar per Tahun ({yearRange} Tahun Terakhir)
                </h2>
              </div>
            </div>
            {(() => {
              const gsData = filteredYearData.map(item => ({
                name: item.name,
                'Publikasi Google Scholar': item['Google Scholar'] || 0
              }));
              
              if (!gsData || gsData.length === 0 || gsData.every(item => item['Publikasi Google Scholar'] === 0)) {
                return (
                  <div className="flex items-center justify-center h-64 text-gray-400">
                    <div className="text-center">
                      <p className="text-lg mb-2">Tidak ada data Google Scholar</p>
                      <p className="text-sm">Data publikasi Google Scholar per tahun belum tersedia</p>
                    </div>
                  </div>
                );
              }
              
              return (
                <div style={{ width: '100%', height: '350px' }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart 
                      data={gsData}
                      margin={{ top: 5, right: 30, left: 20, bottom: 5 }}
                    >
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis 
                        dataKey="name" 
                        label={{ value: 'Tahun', position: 'insideBottom', offset: -5 }}
                        tick={{ fontSize: 12 }}
                      />
                      <YAxis 
                        label={{ value: 'Jumlah Publikasi', angle: -90, position: 'insideLeft' }}
                        tick={{ fontSize: 12 }}
                      />
                      <Tooltip 
                        formatter={(value, name) => [value, name]}
                        labelFormatter={(label) => `Tahun: ${label}`}
                      />
                      <Legend />
                      <Line 
                        type="monotone" 
                        dataKey="Publikasi Google Scholar" 
                        stroke="#10B981" 
                        strokeWidth={3}
                        dot={{ r: 5, fill: '#10B981' }}
                        activeDot={{ r: 7 }}
                        name="Publikasi Google Scholar"
                        connectNulls={false}
                      />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              );
            })()}
          </div>
        </div>

        {/* Top Authors - Scopus and GS */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 mb-8">
          {/* Top Dosen by h-index (Scopus) */}
          <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6 hover:shadow-md transition-shadow duration-300">
            <div className="flex items-center mb-4">
              <Award className="w-5 h-5 text-green-600 mr-2" />
              <h2 className="text-lg font-semibold text-gray-900">Top 10 Dosen (h-index Scopus)</h2>
            </div>
            {safeStats.top_authors_scopus && safeStats.top_authors_scopus.length > 0 ? (
              <ResponsiveContainer width="100%" height={400}>
                <BarChart
                  data={safeStats.top_authors_scopus.slice(0, 10)}
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
          <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6 hover:shadow-md transition-shadow duration-300">
            <div className="flex items-center mb-4">
              <Award className="w-5 h-5 text-red-600 mr-2" />
              <h2 className="text-lg font-semibold text-gray-900">Top 10 Dosen (h-index Google Scholar)</h2>
            </div>
            {safeStats.top_authors_gs && safeStats.top_authors_gs.length > 0 ? (
              <ResponsiveContainer width="100%" height={400}>
                <BarChart
                  data={safeStats.top_authors_gs.slice(0, 10)}
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
          <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6 hover:shadow-md transition-shadow duration-300">
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
                      name={removeFakultasPrefix(faculty)}
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
          <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6 hover:shadow-md transition-shadow duration-300">
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
                      name={removeFakultasPrefix(faculty)}
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
          <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6 hover:shadow-md transition-shadow duration-300">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">Ringkasan Statistik</h2>
            <div className="space-y-4">
              <div className="flex justify-between items-center p-3 bg-blue-50 rounded-lg">
                <span className="text-sm font-medium text-gray-600">Rata-rata Publikasi/Dosen</span>
                <span className="text-lg font-bold text-blue-600">
                  {safeStats.total_dosen > 0 ? Math.round(safeStats.total_publikasi / safeStats.total_dosen) : 0}
                </span>
              </div>
              
              <div className="flex justify-between items-center p-3 bg-green-50 rounded-lg">
                <span className="text-sm font-medium text-gray-600">Rata-rata Sitasi/Publikasi</span>
                <span className="text-lg font-bold text-green-600">
                  {safeStats.total_publikasi > 0 ? Math.round(safeStats.total_sitasi / safeStats.total_publikasi) : 0}
                </span>
              </div>
              
              <div className="flex justify-between items-center p-3 bg-yellow-50 rounded-lg">
                <span className="text-sm font-medium text-gray-600">Top h-index (GS)</span>
                <span className="text-sm font-bold text-yellow-600">
                  {safeStats.top_authors_gs?.[0]?.v_nama_dosen?.substring(0, 15)}...
                </span>
              </div>

              <div className="flex justify-between items-center p-3 bg-red-50 rounded-lg">
                <span className="text-sm font-medium text-gray-600">Tahun Paling Produktif</span>
                <div className="text-right">
                  <span className="text-sm font-bold text-red-600 block">
                    {(() => {
                      if (!safeStats.publikasi_by_year || safeStats.publikasi_by_year.length === 0) return '-';
                      
                      const maxCount = Math.max(...safeStats.publikasi_by_year.map(item => item.count));
                      if (maxCount === 0) return '-';
                      
                      const topYears = safeStats.publikasi_by_year
                        .filter(item => item.count === maxCount)
                        .map(item => item.v_tahun_publikasi)
                        .sort();
                      
                      return topYears.join(', ');
                    })()}
                  </span>
                  <span className="text-xs text-red-500">
                    {(() => {
                      const maxCount = Math.max(...safeStats.publikasi_by_year.map(item => item.count));
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
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {(safeStats.top_authors_gs || []).slice(0, 10).map((author, index) => (
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
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {(safeStats.top_dosen_international || []).slice(0, 10).map((author, index) => (
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
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {(safeStats.top_dosen_national || []).slice(0, 10).map((author, index) => (
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
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
    </Layout>
  );
};

export default Dashboard;