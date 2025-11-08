import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { FileText, Award, Calendar, ExternalLink, Building2, GraduationCap } from 'lucide-react';
import apiService from '../services/apiService';
import DataTable from '../components/DataTable';
import { toast } from 'react-hot-toast';

const ScholarPublikasi = () => {
  const navigate = useNavigate();
  const [publikasiData, setPublikasiData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [statsLoading, setStatsLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [currentPage, setCurrentPage] = useState(1);
  const [pagination, setPagination] = useState(null);
  const [filterTipe, setFilterTipe] = useState('all');
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

  const currentYear = new Date().getFullYear();
  const yearOptions = [];
  for (let year = currentYear; year >= 1990; year--) {
    yearOptions.push(year);
  }

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

  const fetchFaculties = async () => {
    try {
      const response = await apiService.getScholarFaculties();
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
      const response = await apiService.getScholarDepartments(faculty);
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
      
      if (filterTipe !== 'all') params.tipe = filterTipe;
      if (yearStart) params.year_start = yearStart;
      if (yearEnd) params.year_end = yearEnd;
      if (selectedFaculty) params.faculty = selectedFaculty;
      if (selectedDepartment) params.department = selectedDepartment;
      
      console.log('📊 Fetching aggregate stats with params:', params);
      
      const response = await apiService.getScholarPublikasiStats(params);

      if (response.success) {
        // Get recent publications count from full data
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
      
      console.log('📤 Fetching Scholar publikasi with params:', params);
      
      const response = await apiService.getScholarPublikasi(params);
      
      console.log('📥 Scholar publikasi response:', response);

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

  const handleSearchChange = (value) => {
    setSearchTerm(value);
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

  const handlePageChange = (page) => {
    setCurrentPage(page);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const columns = [
    {
      key: 'authors',
      title: 'Author',
      render: (value) => (
        <div className="max-w-xs">
          <p className="text-sm text-gray-900 truncate" title={value}>
            {value || 'N/A'}
          </p>
        </div>
      )
    },
    {
      key: 'v_nama_jurusan',
      title: 'Jurusan',
      sortable: true,
      render: (value) => (
        <div className="max-w-xs">
          <span className="inline-flex items-center px-2 py-1 rounded-md text-xs font-medium bg-red-100 text-red-800">
            <Building2 className="w-3 h-3 mr-1" />
            {value || 'N/A'}
          </span>
        </div>
      )
    },
    {
      key: 'v_judul',
      title: 'Judul Publikasi',
      render: (value) => (
        <div className="max-w-lg">
          <p className="font-medium text-gray-900 line-clamp-2" title={value}>
            {value || 'N/A'}
          </p>
        </div>
      )
    },
    {
      key: 'tipe',
      title: 'Tipe',
      render: (value) => (
        <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
          value === 'Artikel' ? 'bg-green-100 text-green-800' :
          value === 'Prosiding' ? 'bg-yellow-100 text-yellow-800' :
          value === 'Buku' ? 'bg-purple-100 text-purple-800' :
          value === 'Penelitian' ? 'bg-blue-100 text-blue-800' :
          value === 'Lainnya' ? 'bg-indigo-100 text-indigo-800' :
          'bg-gray-100 text-gray-800'
        }`}>
          {value || 'N/A'}
        </span>
      )
    },
    {
      key: 'v_tahun_publikasi',
      title: 'Tahun',
      type: 'number',
      className: 'text-center',
      cellClassName: 'text-center',
      render: (value) => (
        <span className="inline-flex items-center px-2 py-1 rounded text-xs font-medium bg-blue-100 text-blue-800">
          {value || 'N/A'}
        </span>
      )
    },
    {
      key: 'venue',
      title: 'Venue/Jurnal',
      render: (value) => (
        <div className="max-w-xs">
          <p className="text-sm text-gray-900 truncate" title={value}>
            {value || 'N/A'}
          </p>
        </div>
      )
    },
    {
      key: 'publisher',
      title: 'Publisher',
      render: (value) => (
        <div className="max-w-xs">
          <p className="text-sm text-gray-700 truncate" title={value}>
            {value || '-'}
          </p>
        </div>
      )
    },
    {
      key: 'vol_issue',
      title: 'Vol/Issue',
      sortable: false,
      className: 'text-center',
      cellClassName: 'text-center',
      render: (value) => (
        <span className="text-sm text-gray-600">
          {value || '-'}
        </span>
      )
    },
    {
      key: 'pages',
      title: 'Pages',
      sortable: false,
      className: 'text-center',
      cellClassName: 'text-center',
      render: (value) => (
        <span className="text-sm text-gray-600">
          {value ? `pp. ${value}` : '-'}
        </span>
      )
    },
    {
      key: 'n_total_sitasi',
      title: 'Sitasi',
      type: 'number',
      className: 'text-center',
      cellClassName: 'text-center',
      render: (value) => (
        <span className={`font-semibold ${
          (value || 0) > 100 ? 'text-red-600' :
          (value || 0) > 50 ? 'text-orange-600' :
          (value || 0) > 10 ? 'text-yellow-600' :
          'text-gray-600'
        }`}>
          {(value || 0).toLocaleString()}
        </span>
      )
    },
    {
      key: 't_tanggal_unduh',
      title: 'Last Updated',
      type: 'date',
      className: 'text-center',
      cellClassName: 'text-center text-sm text-gray-500'
    },
    {
      key: 'actions',
      title: 'Aksi',
      sortable: false,
      className: 'text-center',
      cellClassName: 'text-center',
      render: (_, row) => (
        <div className="flex items-center justify-center space-x-2">
          {row.v_link_url && (
            <a
              href={row.v_link_url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-red-600 hover:text-red-900 inline-flex items-center text-sm"
              title="Lihat di Google Scholar"
            >
              <ExternalLink className="w-4 h-4 mr-1" />
              Scholar
            </a>
          )}
        </div>
      )
    }
  ];

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

  return (
    <div className="min-h-screen bg-gray-50 py-8">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900">Data Publikasi Google Scholar</h1>
          <p className="mt-2 text-sm text-gray-600">
            Daftar publikasi dengan data dari Google Scholar
          </p>
        </div>

        {/* Faculty Filter Section */}
        <div className="bg-white rounded-lg shadow-md p-6 mb-6">
          <div className="flex items-center mb-4">
            <Building2 className="h-5 w-5 text-gray-500 mr-2" />
            <h2 className="text-lg font-semibold text-gray-900">Filter Fakultas & Jurusan</h2>
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label htmlFor="faculty" className="block text-sm font-medium text-gray-700 mb-2">
                Fakultas
              </label>
              <select
                id="faculty"
                value={selectedFaculty}
                onChange={handleFacultyChange}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-red-500 focus:border-transparent"
              >
                <option value="">Semua Fakultas</option>
                {faculties.map((faculty) => (
                  <option key={faculty} value={faculty}>
                    {faculty}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label htmlFor="department" className="block text-sm font-medium text-gray-700 mb-2">
                Jurusan
              </label>
              <select
                id="department"
                value={selectedDepartment}
                onChange={handleDepartmentChange}
                disabled={!selectedFaculty || loadingDepartments}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-red-500 focus:border-transparent disabled:bg-gray-100 disabled:cursor-not-allowed"
              >
                <option value="">
                  {!selectedFaculty ? 'Pilih fakultas terlebih dahulu' : 'Semua Jurusan'}
                </option>
                {departments.map((dept) => (
                  <option key={dept} value={dept}>
                    {dept}
                  </option>
                ))}
              </select>
              {loadingDepartments && (
                <p className="text-xs text-gray-500 mt-1">Memuat jurusan...</p>
              )}
            </div>

            <div className="flex items-end">
              <button
                onClick={handleResetFilters}
                disabled={!selectedFaculty && !selectedDepartment && !searchTerm && !yearStart && !yearEnd && filterTipe === 'all'}
                className="w-full px-4 py-2 bg-gray-200 text-gray-700 rounded-md hover:bg-gray-300 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Reset Semua Filter
              </button>
            </div>
          </div>

          {(selectedFaculty || selectedDepartment) && (
            <div className="mt-4 flex items-center flex-wrap gap-2">
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

        <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
          <StatCard
            title="Total Publikasi"
            value={aggregateStats.totalPublikasi}
            icon={FileText}
            color="#DC2626"
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

        <DataTable
          title="Daftar Publikasi Google Scholar"
          data={publikasiData}
          columns={columns}
          loading={loading}
          searchTerm={searchTerm}
          onSearchChange={handleSearchChange}
          onRefresh={fetchPublikasiData}
          pagination={pagination}
          onPageChange={handlePageChange}
          emptyMessage="Tidak ada data publikasi Google Scholar ditemukan"
          emptyIcon={<FileText className="h-12 w-12" />}
          additionalFilters={
            <div className="flex items-center gap-3">
              <select
                id="filter-tipe"
                value={filterTipe}
                onChange={handleFilterChange}
                className="px-3 py-1.5 bg-white border-2 border-red-300 rounded-md shadow-sm 
                         text-sm text-gray-800 font-semibold
                         hover:border-red-400 hover:shadow-md
                         focus:border-red-500 focus:ring-2 focus:ring-red-200 focus:outline-none
                         transition-all duration-200 cursor-pointer
                         bg-gradient-to-br from-white to-red-50"
                style={{
                  backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' fill='none' viewBox='0 0 24 24' stroke='%23dc2626'%3E%3Cpath stroke-linecap='round' stroke-linejoin='round' stroke-width='2' d='M19 9l-7 7-7-7'%3E%3C/path%3E%3C/svg%3E")`,
                  backgroundRepeat: 'no-repeat',
                  backgroundPosition: 'right 0.5rem center',
                  backgroundSize: '1.5em 1.5em',
                  paddingRight: '2.5rem',
                  appearance: 'none'
                }}
              >
                {publikasiTypes.map((type) => (
                  <option key={type.value} value={type.value}>
                    {type.label}
                  </option>
                ))}
              </select>

              <div className="flex items-center gap-2 bg-white border-2 border-blue-300 rounded-md px-3 py-1.5 shadow-sm">
                <Calendar className="w-4 h-4 text-blue-600" />
                <span className="text-sm font-medium text-gray-700">Tahun Publikasi:</span>
                <select
                  value={yearStart}
                  onChange={handleYearStartChange}
                  className="px-2 py-0.5 border border-gray-300 rounded text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-200 focus:outline-none"
                >
                  <option value="">Dari</option>
                  {yearOptions.map((year) => (
                    <option key={year} value={year}>
                      {year}
                    </option>
                  ))}
                </select>
                <span className="text-gray-500">-</span>
                <select
                  value={yearEnd}
                  onChange={handleYearEndChange}
                  className="px-2 py-0.5 border border-gray-300 rounded text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-200 focus:outline-none"
                >
                  <option value="">Sampai</option>
                  {yearOptions.map((year) => (
                    <option key={year} value={year}>
                      {year}
                    </option>
                  ))}
                </select>
              </div>
            </div>
          }
        />
      </div>
    </div>
  );
};

export default ScholarPublikasi;