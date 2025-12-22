import { useState, useEffect } from 'react';
import { BarChart, Bar, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { Users, FileText, TrendingUp, Award, Calendar, Search, ArrowUp, ArrowDown, Filter, Building2, GraduationCap, RefreshCw, BarChart3 } from 'lucide-react';
import apiService from '../services/apiService';
import Layout from '../components/Layout';
import LiquidEther from '../components/LiquidEther';
import LoadingOverlay from '../components/LoadingOverlay';

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
    total_dosen_aktif: 0,
    total_publikasi: 0,
    total_sitasi: 0,
    total_sitasi_gs: 0,
    total_sitasi_gs_sinta: 0,
    total_sitasi_scopus: 0,
    avg_h_index: 0,
    median_h_index: 0,
    avg_h_index_scopus: 0,
    median_h_index_scopus: 0,
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
  const [loadingMessage, setLoadingMessage] = useState('Memuat data dashboard...');
  const [yearRange, setYearRange] = useState(10);
  
  // Filter states - changed to arrays for checkbox support
  // Pending filters: what user is currently selecting (not yet applied)
  const [pendingFaculties, setPendingFaculties] = useState([]);
  const [pendingDepartments, setPendingDepartments] = useState([]);
  // Applied filters: what's actually being used to fetch data
  const [appliedFaculties, setAppliedFaculties] = useState([]);
  const [appliedDepartments, setAppliedDepartments] = useState([]);
  const [faculties, setFaculties] = useState([]);
  const [departments, setDepartments] = useState([]);
  const [loadingDepartments, setLoadingDepartments] = useState(false);
  const [showFacultyFilter, setShowFacultyFilter] = useState(true);
  const [showDepartmentFilter, setShowDepartmentFilter] = useState(true);
  const [facultyDeptMap, setFacultyDeptMap] = useState({});

  useEffect(() => {
    console.log('🎯 Component mounted, fetching mapping...');
    
    const fetchMapping = async () => {
      try {
        setLoadingDepartments(true);
        const response = await apiService.getDashboardMapping();
        
        if (response.success && response.data) {
          console.log("✅ Mapping loaded from DB:", response.data);
          setFacultyDeptMap(response.data);
          // Set daftar Fakultas untuk checkbox berdasarkan keys dari response
          // Urutan sudah diatur oleh backend berdasarkan kode_fakultas
          setFaculties(Object.keys(response.data));
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

  useEffect(() => {
    console.log('🔍 PendingFaculties changed:', pendingFaculties);
    
    if (pendingFaculties.length > 0) {
      const allDepts = new Set();
      pendingFaculties.forEach(fac => {
        // Ambil data dari State facultyDeptMap, bukan hardcoded variable
        const depts = facultyDeptMap[fac] || [];
        depts.forEach(d => allDepts.add(d));
      });
      // Urutan sudah diatur oleh backend berdasarkan kode_prodi
      setDepartments(Array.from(allDepts));
      
      // Remove pending departments that don't belong to selected faculties
      setPendingDepartments(prev => {
        return prev.filter(dept => allDepts.has(dept));
      });
    } else {
      setDepartments([]);
      setPendingDepartments([]);
    }
  }, [pendingFaculties, facultyDeptMap]);

  // Fetch data only when applied filters change (not pending filters)
  useEffect(() => {
    console.log('🔍 Applied filter changed, fetching dashboard stats...');
    console.log('🔍 Current applied filters:', { appliedFaculties, appliedDepartments });
    fetchDashboardStats();
  }, [appliedFaculties, appliedDepartments]);

  // const fetchFaculties = async () => {
  //   try {
  //     const response = await apiService.getDashboardFaculties();
  //     console.log('📍 Faculties Response:', response); // Debug
  //     console.log('📍 Response Data:', response.data); // Debug
      
  //     if (response.success && response.data) {
  //       // Pastikan response.data adalah array
  //       const facultiesData = Array.isArray(response.data) ? response.data : [];
  //       console.log('📍 Faculties Array:', facultiesData); // Debug
  //       setFaculties(facultiesData);
  //     } else {
  //       console.error('❌ Invalid response:', response);
  //       setFaculties([]);
  //     }
  //   } catch (error) {
  //     console.error('Error fetching faculties:', error);
  //     setFaculties([]);
  //   }
  // };

  // const fetchDepartmentsForFaculties = async (facultiesList) => {
  //   try {
  //     setLoadingDepartments(true);
  //     // Fetch departments for each faculty and combine unique ones
  //     const allDepartments = new Set();
      
  //     for (const faculty of facultiesList) {
  //       try {
  //         const response = await apiService.getDashboardDepartments(faculty);
  //         if (response.success && response.data && Array.isArray(response.data)) {
  //           response.data.forEach(dept => allDepartments.add(dept));
  //         }
  //       } catch (error) {
  //         console.error(`Error fetching departments for ${faculty}:`, error);
  //       }
  //     }
      
  //     setDepartments(Array.from(allDepartments).sort());
  //   } catch (error) {
  //     console.error('Error fetching departments:', error);
  //     setDepartments([]);
  //   } finally {
  //     setLoadingDepartments(false);
  //   }
  // };

  const fetchDashboardStats = async () => {
    console.log('🚀 fetchDashboardStats STARTED');
    console.log('🔍 Current applied filter state:', { appliedFaculties, appliedDepartments });
    
    try {
      // Update loading message based on whether filters are applied
      if (appliedFaculties.length > 0 || appliedDepartments.length > 0) {
        setLoadingMessage('Memuat data berdasarkan filter yang dipilih...');
      } else {
        setLoadingMessage('Memuat data dashboard...');
      }
      setLoading(true);
      // Convert arrays to comma-separated strings for API
      const facultyParam = appliedFaculties.length > 0 ? appliedFaculties.join(',') : '';
      const departmentParam = appliedDepartments.length > 0 ? appliedDepartments.join(',') : '';
      console.log('🔍 Fetching stats with:', { 
        appliedFaculties, 
        appliedDepartments, 
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
          total_dosen_aktif: 0,
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

  const [loadingFilters, setLoadingFilters] = useState(true);

  useEffect(() => {
    const fetchMapping = async () => {
      try {
        setLoadingFilters(true);
        // Panggil endpoint baru yang kita buat di atas
        // Asumsi: Anda sudah menambahkan method ini di apiService
        const response = await apiService.getDashboardMapping(); 
        
        if (response.success && response.data) {
          console.log("✅ Mapping loaded from DB:", response.data);
          setFacultyDeptMap(response.data);
          
          // Set daftar Fakultas untuk checkbox berdasarkan keys dari response
          setFaculties(Object.keys(response.data).sort());
        }
      } catch (error) {
        console.error("❌ Failed to load mapping:", error);
      } finally {
        setLoadingFilters(false);
      }
    };

    fetchMapping();
  }, []);

  const handleFacultyCheckboxChange = (faculty, isChecked) => {
    console.log('🔍 Faculty checkbox changed:', { faculty, isChecked });
    if (isChecked) {
      setPendingFaculties(prev => {
        const newFaculties = [...prev, faculty];
        return newFaculties;
      });
    } else {
      setPendingFaculties(prev => {
        const newFaculties = prev.filter(f => f !== faculty);
        
        // Remove departments that belong only to the unchecked faculty
        if (newFaculties.length > 0) {
          // Get all departments from remaining faculties
          const remainingDepts = new Set();
          newFaculties.forEach(f => {
            // PERBAIKAN: Gunakan state facultyDeptMap
            const depts = facultyDeptMap[f] || [];
            depts.forEach(d => remainingDepts.add(d));
          });
          
          // Remove departments that are not in any remaining faculty
          setPendingDepartments(prevDepts => {
            return prevDepts.filter(dept => remainingDepts.has(dept));
          });
        } else {
          setPendingDepartments([]);
        }
        
        return newFaculties;
      });
    }
  };

  // Handle apply filters button
  const handleApplyFilters = () => {
    console.log('✅ Applying filters:', { pendingFaculties, pendingDepartments });
    // Set loading immediately when apply button is clicked with specific message
    setLoadingMessage('Memuat data berdasarkan filter yang dipilih...');
    // Force loading to true immediately
    setLoading(true);
    console.log('🔄 Loading state set to true');
    
    // Use setTimeout to ensure state update happens before filter update
    setTimeout(() => {
      // Update applied filters which will trigger useEffect to fetch data
      setAppliedFaculties([...pendingFaculties]);
      setAppliedDepartments([...pendingDepartments]);
    }, 10);
  };

  // const handleFacultyCheckboxChange = (faculty, isChecked) => {
  //   console.log('🔍 Faculty checkbox changed:', { faculty, isChecked });
  //   if (isChecked) {
  //     setSelectedFaculties(prev => {
  //       const newFaculties = [...prev, faculty];
  //       console.log('✅ Added faculty, new list:', newFaculties);
  //       return newFaculties;
  //     });
  //   } else {
  //     setSelectedFaculties(prev => {
  //       const newFaculties = prev.filter(f => f !== faculty);
  //       console.log('❌ Removed faculty, new list:', newFaculties);
        
  //       // Remove departments that belong only to the unchecked faculty
  //       if (newFaculties.length > 0) {
  //         // Get all departments from remaining faculties
  //         const remainingDepts = new Set();
  //         newFaculties.forEach(f => {
  //           const depts = FACULTY_DEPT_MAP[f] || [];
  //           depts.forEach(d => remainingDepts.add(d));
  //         });
          
  //         // Remove departments that are not in any remaining faculty
  //         setSelectedDepartments(prevDepts => {
  //           const filtered = prevDepts.filter(dept => remainingDepts.has(dept));
  //           console.log('🔍 Filtered departments:', filtered);
  //           return filtered;
  //         });
  //       } else {
  //         // No faculties selected, clear all departments
  //         console.log('🔍 No faculties selected, clearing departments');
  //         setSelectedDepartments([]);
  //       }
        
  //       return newFaculties;
  //     });
  //   }
  // };

  const handleDepartmentCheckboxChange = (department, isChecked) => {
    console.log('🔍 Department checkbox changed:', { department, isChecked });
    if (isChecked) {
      setPendingDepartments(prev => {
        const newDepts = [...prev, department];
        console.log('✅ Added department, new list:', newDepts);
        return newDepts;
      });
    } else {
      setPendingDepartments(prev => {
        const newDepts = prev.filter(d => d !== department);
        console.log('❌ Removed department, new list:', newDepts);
        return newDepts;
      });
    }
  };

  const handleSelectAllFaculties = () => {
    if (pendingFaculties.length === faculties.length) {
      setPendingFaculties([]);
      setPendingDepartments([]);
    } else {
      setPendingFaculties([...faculties]);
    }
  };

  const handleSelectAllDepartments = () => {
    if (pendingDepartments.length === departments.length) {
      setPendingDepartments([]);
    } else {
      setPendingDepartments([...departments]);
    }
  };

  const handleResetFilters = () => {
    setPendingFaculties([]);
    setPendingDepartments([]);
    setAppliedFaculties([]);
    setAppliedDepartments([]);
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
      <div className="bg-white rounded-xl shadow-sm hover:shadow-md border border-gray-200 p-5 transition-all duration-300 group h-full flex flex-col min-h-[140px]">
        <div className="flex items-start justify-between mb-4 flex-shrink-0">
          <div className="flex-1 min-w-0 pr-2">
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2.5 leading-tight">{title}</p>
            <div className="flex items-baseline gap-2 flex-wrap">
              <p className="text-2xl font-bold text-gray-900 leading-tight">
                {typeof value === 'string' ? value : value.toLocaleString('id-ID')}
              </p>
              {previousDate && !isEqual && (
                <div className="flex items-center pb-0.5">
                  {isIncreased ? (
                    <ArrowUp className="w-3.5 h-3.5 text-green-600" />
                  ) : isDecreased ? (
                    <ArrowDown className="w-3.5 h-3.5 text-red-600" />
                  ) : null}
                </div>
              )}
            </div>
          </div>
          <div className="flex-shrink-0">
            <div className="w-10 h-10 rounded-lg flex items-center justify-center transition-all duration-300 group-hover:scale-110" style={{ backgroundColor: `${color}15` }}>
              <Icon className="w-5 h-5" style={{ color }} />
            </div>
          </div>
        </div>
        
        <div className="space-y-1 pt-3 border-t border-gray-100 mt-auto">
          {subtitle && (
            <p className="text-xs font-medium text-gray-600 leading-tight line-clamp-2">{subtitle}</p>
          )}
          {previousDate && (
            <p className="text-xs text-gray-500 leading-tight">
              sebelumnya {previousDate}: {formatPrevValue(prevValue)}
            </p>
          )}
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


  // Initialize stats with default values if not available
  const safeStats = {
    total_dosen: stats?.total_dosen || 0,
    total_dosen_aktif: stats?.total_dosen_aktif || 0,
    total_publikasi: stats?.total_publikasi || 0,
    total_sitasi: stats?.total_sitasi || 0,
    total_sitasi_gs: stats?.total_sitasi_gs || 0,
    total_sitasi_gs_sinta: stats?.total_sitasi_gs_sinta || 0,
    total_sitasi_scopus: stats?.total_sitasi_scopus || 0,
    avg_h_index: stats?.avg_h_index || 0,
    median_h_index: stats?.median_h_index || 0,
    avg_h_index_scopus: stats?.avg_h_index_scopus || 0,
    median_h_index_scopus: stats?.median_h_index_scopus || 0,
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
    has_filter: stats?.has_filter !== undefined ? stats.has_filter : (appliedFaculties.length > 0 || appliedDepartments.length > 0)
  };

  // Determine if filter is active based on frontend state (more reliable)
  const hasFilter = appliedFaculties.length > 0 || appliedDepartments.length > 0;
  
  console.log('🔍 Filter status:', {
    hasFilter,
    appliedFaculties,
    appliedDepartments,
    pendingFaculties,
    pendingDepartments,
    backendHasFilter: safeStats.has_filter
  });

  // Transform data for line chart
  const transformForLineChart = (data, sourceType = 'both') => {
    if (!data || data.length === 0) {
      return [];
    }
    
    // DETEKSI LOGIKA BERDASARKAN DATA DARI BACKEND
    // 1. Jika ada key 'department' -> Backend sedang menjalankan Skenario A (Kondisi 3, 4, 6)
    // 2. Jika ada key 'faculty'    -> Backend sedang menjalankan Skenario B (Kondisi 5)
    // 3. Jika tidak ada keduanya   -> Backend sedang menjalankan Skenario C (Kondisi 1, 2)
    
    const isDepartmentGroup = data.some(item => item.department);
    const isFacultyGroup = data.some(item => item.faculty);
    
    const groupedByYear = {};

    data.forEach(item => {
      const year = item.v_tahun_publikasi || item.name || '';
      
      // Tentukan label untuk Legend/Garis
      let groupLabel = '';
      
      if (isDepartmentGroup) {
         // Kondisi: Per Jurusan
         groupLabel = item.department; 
      } else if (isFacultyGroup) {
         // Kondisi: Per Fakultas
         groupLabel = item.faculty;
      } else {
         // Kondisi: Agregasi Total (1 Garis)
         // Biarkan kosong agar nanti menjadi "SINTA" atau "Google Scholar" saja
         groupLabel = ''; 
      }
      
      // Skip data jika label grouping tidak valid (kecuali untuk mode agregasi)
      if ((isDepartmentGroup || isFacultyGroup) && !groupLabel) return;

      if (!groupedByYear[year]) {
        groupedByYear[year] = { name: year };
      }

      // Logic Penamaan Key di Object Akhir
      if (sourceType === 'sinta' || sourceType === 'both') {
        // Jika ada label -> "SINTA - Manajemen"
        // Jika label kosong -> "SINTA"
        const finalKey = groupLabel ? `SINTA - ${groupLabel}` : 'SINTA';
        groupedByYear[year][finalKey] = (groupedByYear[year][finalKey] || 0) + (Number(item.count_sinta) || 0);
      }
      
      if (sourceType === 'gs' || sourceType === 'both') {
        const finalKey = groupLabel ? `Google Scholar - ${groupLabel}` : 'Google Scholar';
        groupedByYear[year][finalKey] = (groupedByYear[year][finalKey] || 0) + (Number(item.count_gs) || 0);
      }
    });

    // Sorting berdasarkan Tahun
    const transformed = Object.values(groupedByYear).sort((a, b) => {
      const aYear = parseInt(a.name);
      const bYear = parseInt(b.name);
      if (!isNaN(aYear) && !isNaN(bYear)) {
        return aYear - bYear;
      }
      return a.name.localeCompare(b.name);
    });
    
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
    
    return filtered;
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
        {/* Loading Overlay */}
        <LoadingOverlay 
          isLoading={loading} 
          message={loadingMessage}
          subMessage="Mohon tunggu sebentar"
        />

        {/* Main Content with Loading State */}
        <div className={loading ? 'loading-content-disabled pointer-events-none' : ''}>
          {/* Welcome Section with Liquid Ether Background */}
        <div className="rounded-2xl shadow-xl p-8 mb-8 text-white relative overflow-hidden" style={{ minHeight: '280px' }}>
          {/* Liquid Ether Animated Background */}
          <div className="absolute inset-0 rounded-2xl">
            <LiquidEther
              colors={['#0A84FF', '#5856D6', '#AF52DE']}
              mouseForce={25}
              cursorSize={120}
              isViscous={false}
              viscous={30}
              iterationsViscous={32}
              iterationsPoisson={32}
              resolution={0.5}
              isBounce={false}
              autoDemo={true}
              autoSpeed={0.6}
              autoIntensity={2.5}
              takeoverDuration={0.2}
              autoResumeDelay={500}
              autoRampDuration={0.4}
              style={{ width: '100%', height: '100%' }}
            />
            {/* Dark Overlay for item background with white text */}
            <div className="absolute inset-0 bg-gradient-to-br from-gray-900/90 via-gray-800/85 to-gray-900/90 backdrop-blur-[1px] rounded-2xl pointer-events-none"></div>
          </div>
          
          <div className="relative z-10">
            <div className="flex items-center gap-3 mb-4">
              <div className="p-3 bg-white/10 rounded-xl backdrop-blur-md shadow-lg border border-white/20">
                <FileText className="w-6 h-6 text-white drop-shadow-lg" />
              </div>
              <h1 
                className="text-3xl font-bold text-white drop-shadow-[0_2px_8px_rgba(0,0,0,0.3)]" 
                style={{ 
                  letterSpacing: '-0.02em',
                  textShadow: '0 2px 12px rgba(0, 0, 0, 0.4), 0 0 2px rgba(0, 0, 0, 0.2)'
                }}
              >
                Selamat Datang di UNPAR Scraper
              </h1>
            </div>
            <p 
              className="text-lg text-white mb-2 max-w-3xl font-semibold drop-shadow-[0_1px_4px_rgba(0,0,0,0.3)]"
              style={{ textShadow: '0 1px 6px rgba(0, 0, 0, 0.35)' }}
            >
              Sistem Manajemen Publikasi Dosen Terintegrasi
            </p>
            <p 
              className="text-base text-white/95 max-w-3xl leading-relaxed drop-shadow-[0_1px_3px_rgba(0,0,0,0.25)]"
              style={{ textShadow: '0 1px 4px rgba(0, 0, 0, 0.3)' }}
            >
              Platform komprehensif untuk mengelola, menganalisis, dan memantau data publikasi dosen dari 
              <span className="font-semibold text-white"> SINTA (Science and Technology Index)</span> dan 
              <span className="font-semibold text-white"> Google Scholar</span>. Akses statistik real-time, visualisasi data, 
              dan laporan detail untuk mendukung pengambilan keputusan akademik yang lebih baik.
            </p>
            <div className="flex items-center gap-6 mt-6">
              <div className="flex items-center gap-2 bg-white/10 px-4 py-2.5 rounded-lg backdrop-blur-md shadow-lg border border-white/20 hover:bg-white/20 transition-all duration-300 cursor-pointer group">
                <BarChart3 className="w-5 h-5 text-white drop-shadow-md group-hover:scale-110 transition-transform" />
                <span className="text-sm font-semibold text-white drop-shadow-md">Analisis Data</span>
              </div>
              <div className="flex items-center gap-2 bg-white/10 px-4 py-2.5 rounded-lg backdrop-blur-md shadow-lg border border-white/20 hover:bg-white/20 transition-all duration-300 cursor-pointer group">
                <TrendingUp className="w-5 h-5 text-white drop-shadow-md group-hover:scale-110 transition-transform" />
                <span className="text-sm font-semibold text-white drop-shadow-md">Statistik Real-time</span>
              </div>
              <div className="flex items-center gap-2 bg-white/10 px-4 py-2.5 rounded-lg backdrop-blur-md shadow-lg border border-white/20 hover:bg-white/20 transition-all duration-300 cursor-pointer group">
                <Users className="w-5 h-5 text-white drop-shadow-md group-hover:scale-110 transition-transform" />
                <span className="text-sm font-semibold text-white drop-shadow-md">Manajemen Dosen</span>
              </div>
            </div>
          </div>
        </div>

        {/* Global Filters */}
        <div className="apple-card p-8 mb-8 chart-container-apple">
          <div className="flex items-center gap-3 mb-6">
            <div className="p-2.5 bg-[#0A84FF]/10 rounded-[12px]">
              <Filter className="w-5 h-5 text-[#0A84FF]" />
            </div>
            <h2 
              className="text-xl font-semibold text-[#1D1D1F]"
              style={{ letterSpacing: '-0.022em' }}
            >
              Filter Data
            </h2>
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Faculty Filter - Checkbox */}
            <div className="relative">
              <div className="flex items-center justify-between mb-3">
                <label className="block text-sm font-semibold text-gray-700 flex items-center">
                  <Building2 className="w-4 h-4 mr-1.5 text-red-600" />
                  Fakultas ({pendingFaculties.length}/{faculties.length})
                </label>
                <div className="flex items-center gap-2">
                  <button
                    onClick={handleSelectAllFaculties}
                    className="text-xs text-blue-600 hover:text-blue-800 font-medium"
                  >
                    {pendingFaculties.length === faculties.length ? 'Batal Semua' : 'Pilih Semua'}
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
                            checked={pendingFaculties.includes(faculty)}
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
                  Prodi ({pendingDepartments.length}/{departments.length})
                </label>
                <div className="flex items-center gap-2">
                  <button
                    onClick={handleSelectAllDepartments}
                    disabled={departments.length === 0 || pendingFaculties.length === 0}
                    className="text-xs text-blue-600 hover:text-blue-800 font-medium disabled:text-gray-400 disabled:cursor-not-allowed"
                  >
                    {pendingDepartments.length === departments.length ? 'Batal Semua' : 'Pilih Semua'}
                  </button>
                  <button
                    onClick={() => setShowDepartmentFilter(!showDepartmentFilter)}
                    disabled={departments.length === 0 || pendingFaculties.length === 0}
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
                  ) : pendingFaculties.length === 0 ? (
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
                            checked={pendingDepartments.includes(dept)}
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

          {/* Apply, Reset Button and Active Filters Display */}
          <div className="mt-4 flex items-center justify-between flex-wrap gap-4">
            <div className="flex items-center gap-3">
              <button
                onClick={handleApplyFilters}
                disabled={
                  (pendingFaculties.length === 0 && pendingDepartments.length === 0) ||
                  (JSON.stringify(pendingFaculties) === JSON.stringify(appliedFaculties) &&
                   JSON.stringify(pendingDepartments) === JSON.stringify(appliedDepartments))
                }
                className="px-5 py-2.5 bg-gradient-to-r from-blue-600 to-blue-700 text-white rounded-lg hover:from-blue-700 hover:to-blue-800 transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed font-medium shadow-sm flex items-center justify-center group"
              >
                <Filter className="w-4 h-4 mr-2 group-hover:scale-110 transition-transform" />
                Apply Filter
              </button>
              <button
                onClick={handleResetFilters}
                disabled={pendingFaculties.length === 0 && pendingDepartments.length === 0 && appliedFaculties.length === 0 && appliedDepartments.length === 0}
                className="px-4 py-2.5 bg-gradient-to-r from-gray-100 to-gray-200 text-gray-700 rounded-lg hover:from-gray-200 hover:to-gray-300 transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed font-medium shadow-sm flex items-center justify-center group"
              >
                <RefreshCw className="w-4 h-4 mr-2 group-hover:rotate-180 transition-transform duration-300" />
                Reset Filter
              </button>
            </div>

            {/* Active Filters Display (showing applied filters) */}
            {(appliedFaculties.length > 0 || appliedDepartments.length > 0) && (
              <div className="flex items-center flex-wrap gap-2">
                <span className="text-sm text-gray-600 font-medium flex items-center">
                  <Filter className="w-4 h-4 mr-1 text-blue-600" />
                  Filter aktif:
                </span>
                {appliedFaculties.map((faculty) => (
                  <span
                    key={faculty}
                    className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-red-100 text-red-800"
                  >
                    <Building2 className="w-4 h-4 mr-1" />
                    {faculty}
                  </span>
                ))}
                {appliedDepartments.map((dept) => (
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
                {appliedFaculties.length > 0 && (
                  <span className="ml-2">
                    {appliedFaculties.length} Fakultas
                    {appliedFaculties.length > 0 && appliedDepartments.length > 0 && ' dan '}
                  </span>
                )}
                {appliedDepartments.length > 0 && (
                  <span className="ml-2">
                    {appliedDepartments.length} Prodi
                  </span>
                )}
              </p>
            </div>
          </div>
        )}

        {/* Stats Cards - Row 1: 6 Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-6 gap-4 mb-6">
          <StatCard
            title="Total Dosen Aktif"
            value={safeStats.total_dosen_aktif.toLocaleString()}
            icon={Users}
            color="#8B5CF6"
            previousValue={safeStats.previous_values?.total_dosen_aktif}
            previousDate={safeStats.previous_date}
          />
          <StatCard
            title="Total Author"
            value={safeStats.total_dosen.toLocaleString()}
            icon={Users}
            color="#3B82F6"
            previousValue={safeStats.previous_values?.total_dosen}
            previousDate={safeStats.previous_date}
          />
          <StatCard
            title="TOTAL PUBLIKASI TERSITASI"
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
            title="H-Index Rata-rata (Google Scholar)"
            value={safeStats.avg_h_index ? safeStats.avg_h_index.toFixed(1) : '0.0'}
            subtitle={`Median: ${safeStats.median_h_index ? safeStats.median_h_index.toFixed(1) : '0.0'}`}
            icon={TrendingUp}
            color="#EF4444"
            previousValue={safeStats.previous_values?.avg_h_index}
            previousDate={safeStats.previous_date}
          />
          <StatCard
            title="H-Index Rata-Rata (Scopus)"
            value={safeStats.avg_h_index_scopus ? safeStats.avg_h_index_scopus.toFixed(1) : '0.0'}
            subtitle={`Median: ${safeStats.median_h_index_scopus ? safeStats.median_h_index_scopus.toFixed(1) : '0.0'}`}
            icon={TrendingUp}
            color="#DC2626"
            previousValue={safeStats.previous_values?.avg_h_index_scopus}
            previousDate={safeStats.previous_date}
          />
        </div>

        {/* International vs National Summary - Row 2: 4 Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
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

        {/* Additional Sinta 5-6 - Row 3: 1 Card (aligned with Row 2) */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
          <StatCard
            title="Nasional (Sinta 5-6)"
            value={(safeStats.publikasi_nasional_sinta5 + safeStats.publikasi_nasional_sinta6).toLocaleString()}
            icon={Award}
            color="#A78BFA"
            previousValue={(safeStats.previous_values?.publikasi_nasional_sinta5 || 0) + (safeStats.previous_values?.publikasi_nasional_sinta6 || 0)}
            previousDate={safeStats.previous_date}
          />
          <div></div>
          <div></div>
          <div></div>
        </div>

        {/* Publikasi by Year Charts - Separated by Source */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
          {/* Chart SINTA */}
          <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6 hover:shadow-md transition-shadow duration-300">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center">
                <Calendar className="w-5 h-5 text-blue-600 mr-2" />
                <h2 className="text-xl font-semibold text-[#1D1D1F] mb-2">
                  Publikasi SINTA per Tahun ({yearRange} Tahun Terakhir)
                </h2>
              </div>
              <select
                className="pl-3 pr-8 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                value={yearRange}
                onChange={(e) => setYearRange(parseInt(e.target.value))}
              >
                <option value={5}>5 Tahun</option>
                <option value={10}>10 Tahun</option>
                <option value={15}>15 Tahun</option>
              </select>
            </div>
            
            {(() => {
              const sintaData = transformForLineChart(filteredYearData, 'sinta');
              
              if (!sintaData || sintaData.length === 0) {
                return (
                  <div className="flex items-center justify-center h-64 text-gray-400">
                    <p>Data publikasi SINTA belum tersedia</p>
                  </div>
                );
              }
              
              // ============================================================
              // PERBAIKAN DI SINI:
              // Mengumpulkan keys dari SELURUH data, bukan hanya data[0]
              // ============================================================
              const allKeys = new Set();
              sintaData.forEach(item => {
                Object.keys(item).forEach(key => {
                  if (key !== 'name' && key !== 'v_tahun_publikasi' && (key.includes('SINTA') || key === 'Publikasi SINTA')) {
                    allKeys.add(key);
                  }
                });
              });
              
              // Konversi Set kembali ke Array
              let sintaKeys = Array.from(allKeys);

              // Fallback jika kosong
              if (sintaKeys.length === 0) sintaKeys = ['SINTA'];
              
              const colors = ['#3B82F6', '#EF4444', '#10B981', '#F59E0B', '#8B5CF6', '#EC4899', '#06B6D4'];
              
              return (
                <div style={{ width: '100%', height: '350px' }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={sintaData} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="name" tick={{ fontSize: 12 }} padding={{ left: 10, right: 10 }}/>
                      <YAxis tick={{ fontSize: 12 }} />
                      <Tooltip formatter={(value, name) => [value, name]} />
                      <Legend />
                      
                      {sintaKeys.map((key, index) => (
                        <Line 
                          key={key}
                          type="monotone" 
                          dataKey={key} 
                          stroke={colors[index % colors.length]} 
                          strokeWidth={3}
                          dot={{ r: 4 }}
                          activeDot={{ r: 6 }}
                          name={key.includes(' - ') ? key.split(' - ')[1] : key}
                          connectNulls={true}
                        />
                      ))}
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
                <h2 className="text-xl font-semibold text-[#1D1D1F] mb-2">
                  Publikasi Google Scholar per Tahun ({yearRange} Tahun Terakhir)
                </h2>
              </div>
            </div>

            {(() => {
              const gsData = transformForLineChart(filteredYearData, 'gs');
              
              if (!gsData || gsData.length === 0) {
                return (
                  <div className="flex items-center justify-center h-64 text-gray-400">
                    <p>Data publikasi Google Scholar belum tersedia</p>
                  </div>
                );
              }
              
              // ============================================================
              // PERBAIKAN DI SINI:
              // ============================================================
              const allKeys = new Set();
              gsData.forEach(item => {
                Object.keys(item).forEach(key => {
                  if (key !== 'name' && key !== 'v_tahun_publikasi' && (key.includes('Google Scholar') || key.includes('Scholar'))) {
                    allKeys.add(key);
                  }
                });
              });
              
              let gsKeys = Array.from(allKeys);
              if (gsKeys.length === 0) gsKeys = ['Google Scholar'];
              
              const colors = ['#10B981', '#EF4444', '#3B82F6', '#F59E0B', '#8B5CF6', '#EC4899', '#06B6D4'];
              
              return (
                <div style={{ width: '100%', height: '350px' }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={gsData} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="name" tick={{ fontSize: 12 }} padding={{ left: 10, right: 10 }} />
                      <YAxis tick={{ fontSize: 12 }} />
                      <Tooltip formatter={(value, name) => [value, name]} />
                      <Legend />
                      
                      {gsKeys.map((key, index) => (
                        <Line 
                          key={key}
                          type="monotone" 
                          dataKey={key} 
                          stroke={colors[index % colors.length]} 
                          strokeWidth={3}
                          dot={{ r: 4 }}
                          activeDot={{ r: 6 }}
                          name={key.includes(' - ') ? key.split(' - ')[1] : key}
                          connectNulls={true}
                        />
                      ))}
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
              <h2 
                className="text-xl font-semibold text-[#1D1D1F] mb-2"
                style={{ letterSpacing: '-0.022em' }}
              >
                Top 10 Dosen (h-index Scopus)
              </h2>
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
              <h2 
                className="text-xl font-semibold text-[#1D1D1F] mb-2"
                style={{ letterSpacing: '-0.022em' }}
              >
                Top 10 Dosen (h-index Google Scholar)
              </h2>
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
        <div className="grid grid-cols-1 lg:grid-cols-1 gap-8 mb-8">
          {/* Summary Card Column - Made Wider */}
          <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6 hover:shadow-md transition-shadow duration-300">
            <h2 
              className="text-xl font-semibold text-[#1D1D1F] mb-4"
              style={{ letterSpacing: '-0.022em' }}
            >
              Ringkasan Statistik
            </h2>
            {/* Make cards wider: 4 cols only on very wide screens */}
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-6">
              <div className="flex flex-col sm:flex-row sm:justify-between sm:items-center gap-2 p-5 bg-blue-50 rounded-lg">
                <span className="text-sm font-medium text-gray-600">Rata-rata Publikasi/Dosen</span>
                <span className="text-xl font-bold text-blue-600 whitespace-nowrap">
                  {safeStats.total_dosen > 0 ? Math.round(safeStats.total_publikasi / safeStats.total_dosen) : 0}
                </span>
              </div>
              
              <div className="flex flex-col sm:flex-row sm:justify-between sm:items-center gap-2 p-5 bg-green-50 rounded-lg">
                <span className="text-sm font-medium text-gray-600">Rata-rata Sitasi/Publikasi</span>
                <span className="text-xl font-bold text-green-600 whitespace-nowrap">
                  {safeStats.total_publikasi > 0 ? Math.round(safeStats.total_sitasi / safeStats.total_publikasi) : 0}
                </span>
              </div>
              
              <div className="flex flex-col sm:flex-row sm:justify-between sm:items-center gap-2 p-5 bg-yellow-50 rounded-lg">
                <span className="text-sm font-medium text-gray-600">Top h-index (GS)</span>
                <span className="text-sm font-bold text-yellow-600 sm:text-right">
                  {safeStats.top_authors_gs?.[0]?.v_nama_dosen ? (
                    safeStats.top_authors_gs[0].v_nama_dosen.length > 20 
                      ? safeStats.top_authors_gs[0].v_nama_dosen.substring(0, 20) + '...'
                      : safeStats.top_authors_gs[0].v_nama_dosen
                  ) : '-'}
                </span>
              </div>

              <div className="flex flex-col sm:flex-row sm:justify-between sm:items-center gap-2 p-5 bg-red-50 rounded-lg">
                <span className="text-sm font-medium text-gray-600">Tahun Paling Produktif</span>
                <div className="sm:text-right">
                  <span className="text-sm font-bold text-red-600 block">
                    {(() => {
                      if (!safeStats.publikasi_by_year || safeStats.publikasi_by_year.length === 0) return '-';
                      
                      // Calculate total publications per year (combine SINTA and GS)
                      const yearTotals = {};
                      safeStats.publikasi_by_year.forEach(item => {
                        const year = item.v_tahun_publikasi || item.name || '';
                        if (!year) return;
                        
                        // Sum count_sinta and count_gs, or use count if available
                        const count = (item.count_sinta || 0) + (item.count_gs || 0) + (item.count || 0);
                        if (count > 0) {
                          yearTotals[year] = (yearTotals[year] || 0) + count;
                        }
                      });
                      
                      if (Object.keys(yearTotals).length === 0) return '-';
                      
                      // Find year(s) with maximum count
                      const maxCount = Math.max(...Object.values(yearTotals));
                      if (maxCount === 0) return '-';
                      
                      const topYears = Object.keys(yearTotals)
                        .filter(year => yearTotals[year] === maxCount)
                        .sort((a, b) => parseInt(b) - parseInt(a)); // Sort descending
                      
                      return topYears.length > 0 ? topYears[0] : '-';
                    })()}
                  </span>
                  <span className="text-xs text-red-500">
                    {(() => {
                      if (!safeStats.publikasi_by_year || safeStats.publikasi_by_year.length === 0) return '';
                      
                      const yearTotals = {};
                      safeStats.publikasi_by_year.forEach(item => {
                        const year = item.v_tahun_publikasi || item.name || '';
                        if (!year) return;
                        
                        const count = (item.count_sinta || 0) + (item.count_gs || 0) + (item.count || 0);
                        if (count > 0) {
                          yearTotals[year] = (yearTotals[year] || 0) + count;
                        }
                      });
                      
                      const maxCount = Math.max(...Object.values(yearTotals));
                      return maxCount > 0 ? `(${maxCount} publikasi)` : '';
                    })()}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Top 10 Dosen Berdasarkan h-index (Google Scholar) */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6 hover:shadow-md transition-shadow duration-300">
          <div className="flex items-center justify-between mb-6">
            <div className="flex items-center">
              <Search className="w-5 h-5 text-indigo-600 mr-2" />
              <h2 
                className="text-xl font-semibold text-[#1D1D1F]"
                style={{ letterSpacing: '-0.022em' }}
              >
                Top 10 Dosen Berdasarkan h-index (Google Scholar)
              </h2>
            </div>
          </div>
          
          <div className="overflow-x-auto rounded-lg border border-gray-200">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gradient-to-r from-gray-50 to-gray-100">
                <tr>
                  <th className="px-6 py-4 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider border-r border-gray-200">
                    Ranking
                  </th>
                  <th className="px-6 py-4 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider border-r border-gray-200">
                    Nama Dosen
                  </th>
                  <th className="px-6 py-4 text-center text-xs font-semibold text-gray-700 uppercase tracking-wider">
                    h-index (GS)
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {(safeStats.top_authors_gs || []).slice(0, 10).map((author, index) => (
                  <tr key={index} className={`transition-colors duration-150 ${index % 2 === 0 ? 'bg-white hover:bg-gray-50' : 'bg-gray-50 hover:bg-gray-100'}`}>
                    <td className="px-6 py-4 whitespace-nowrap border-r border-gray-200">
                      <span className={`inline-flex items-center justify-center px-3 py-1.5 rounded-full text-xs font-semibold ${
                        index === 0 ? 'bg-yellow-100 text-yellow-800 border border-yellow-200' :
                        index === 1 ? 'bg-gray-100 text-gray-800 border border-gray-200' :
                        index === 2 ? 'bg-orange-100 text-orange-800 border border-orange-200' :
                        'bg-blue-100 text-blue-800 border border-blue-200'
                      }`}>
                        #{index + 1}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-sm font-medium text-gray-900 border-r border-gray-200">
                      {author.v_nama_dosen}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-center">
                      <span className="inline-flex items-center justify-center px-3 py-1 rounded-md text-sm font-semibold bg-indigo-50 text-indigo-700">
                        {author.n_h_index_gs?.toLocaleString() || 0}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Top 10 Dosen Internasional (Scopus) - styled like GS table */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6 mt-8 hover:shadow-md transition-shadow duration-300">
          <div className="flex items-center justify-between mb-6">
            <div className="flex items-center">
              <Search className="w-5 h-5 text-emerald-600 mr-2" />
              <h2 className="text-xl font-semibold text-[#1D1D1F]" style={{ letterSpacing: '-0.022em' }}>
                Top 10 Dosen Berdasarkan Publikasi Internasional (Scopus)
              </h2>
            </div>
          </div>
          <div className="overflow-x-auto rounded-lg border border-gray-200">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gradient-to-r from-gray-50 to-gray-100">
                <tr>
                  <th className="px-6 py-4 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider border-r border-gray-200">Ranking</th>
                  <th className="px-6 py-4 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider border-r border-gray-200">Nama Dosen</th>
                  <th className="px-6 py-4 text-center text-xs font-semibold text-gray-700 uppercase tracking-wider">Jumlah Publikasi</th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {(safeStats.top_dosen_international || []).slice(0, 10).map((author, index) => (
                  <tr key={index} className={`transition-colors duration-150 ${index % 2 === 0 ? 'bg-white hover:bg-gray-50' : 'bg-gray-50 hover:bg-gray-100'}`}>
                    <td className="px-6 py-4 whitespace-nowrap border-r border-gray-200">
                      <span className={`inline-flex items-center justify-center px-3 py-1.5 rounded-full text-xs font-semibold ${
                        index === 0 ? 'bg-yellow-100 text-yellow-800 border border-yellow-200' :
                        index === 1 ? 'bg-gray-100 text-gray-800 border border-gray-200' :
                        index === 2 ? 'bg-orange-100 text-orange-800 border border-orange-200' :
                        'bg-blue-100 text-blue-800 border border-blue-200'
                      }`}>
                        #{index + 1}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-sm font-medium text-gray-900 border-r border-gray-200">{author.v_nama_dosen}</td>
                    <td className="px-6 py-4 whitespace-nowrap text-center">
                      <span className="inline-flex items-center justify-center px-3 py-1 rounded-md text-sm font-semibold bg-emerald-50 text-emerald-700">
                        {author.count_international?.toLocaleString() || 0}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Top 10 Dosen Nasional (Sinta 1-6) - styled like GS table */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6 mt-8 hover:shadow-md transition-shadow duration-300">
          <div className="flex items-center justify-between mb-6">
            <div className="flex items-center">
              <Search className="w-5 h-5 text-indigo-600 mr-2" />
              <h2 className="text-xl font-semibold text-[#1D1D1F]" style={{ letterSpacing: '-0.022em' }}>
                Top 10 Dosen Berdasarkan Publikasi Nasional (Sinta 1–6)
              </h2>
            </div>
          </div>
          <div className="overflow-x-auto rounded-lg border border-gray-200">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gradient-to-r from-gray-50 to-gray-100">
                <tr>
                  <th className="px-6 py-4 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider border-r border-gray-200">Ranking</th>
                  <th className="px-6 py-4 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider border-r border-gray-200">Nama Dosen</th>
                  <th className="px-6 py-4 text-center text-xs font-semibold text-gray-700 uppercase tracking-wider">Jumlah Publikasi</th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {(safeStats.top_dosen_national || []).slice(0, 10).map((author, index) => (
                  <tr key={index} className={`transition-colors duration-150 ${index % 2 === 0 ? 'bg-white hover:bg-gray-50' : 'bg-gray-50 hover:bg-gray-100'}`}>
                    <td className="px-6 py-4 whitespace-nowrap border-r border-gray-200">
                      <span className={`inline-flex items-center justify-center px-3 py-1.5 rounded-full text-xs font-semibold ${
                        index === 0 ? 'bg-yellow-100 text-yellow-800 border border-yellow-200' :
                        index === 1 ? 'bg-gray-100 text-gray-800 border border-gray-200' :
                        index === 2 ? 'bg-orange-100 text-orange-800 border border-orange-200' :
                        'bg-blue-100 text-blue-800 border border-blue-200'
                      }`}>
                        #{index + 1}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-sm font-medium text-gray-900 border-r border-gray-200">{author.v_nama_dosen}</td>
                    <td className="px-6 py-4 whitespace-nowrap text-center">
                      <span className="inline-flex items-center justify-center px-3 py-1 rounded-md text-sm font-semibold bg-indigo-50 text-indigo-700">
                        {author.count_national?.toLocaleString() || 0}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
        </div>
    </Layout>
  );
};

export default Dashboard;