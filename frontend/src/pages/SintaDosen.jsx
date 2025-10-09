import { useState, useEffect } from 'react';
import { Users, TrendingUp, Award, Calendar, ExternalLink } from 'lucide-react';
import apiService from '../services/apiService';
import DataTable from '../components/DataTable';
import { toast } from 'react-hot-toast';

const SintaDosen = () => {
  const [dosenData, setDosenData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [statsLoading, setStatsLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [currentPage, setCurrentPage] = useState(1);
  const [pagination, setPagination] = useState(null);
  const [aggregateStats, setAggregateStats] = useState({
    totalDosen: 0,
    totalSitasi: 0,
    avgHIndex: 0
  });
  const perPage = 2;

  useEffect(() => {
    fetchDosenData();
  }, [currentPage, searchTerm]);

  // Fetch aggregate statistics
  useEffect(() => {
    fetchAggregateStats();
  }, [searchTerm]);

  const fetchAggregateStats = async () => {
    try {
      setStatsLoading(true);
      
      const response = await apiService.getSintaDosenStats({ search: searchTerm });

      if (response.success) {
        // If backend provides stats endpoint
        if (response.data.totalDosen !== undefined) {
          setAggregateStats({
            totalDosen: response.data.totalDosen || 0,
            totalSitasi: response.data.totalSitasi || 0,
            avgHIndex: response.data.avgHIndex || 0
          });
        } else {
          // Fallback: fetch all data for calculation
          await fetchAllDataForStats();
        }
      } else {
        // Fallback if stats endpoint doesn't exist
        await fetchAllDataForStats();
      }
    } catch (error) {
      console.error('Error fetching aggregate stats:', error);
      // Fallback to fetching all data
      await fetchAllDataForStats();
    } finally {
      setStatsLoading(false);
    }
  };

  const fetchAllDataForStats = async () => {
    try {
      const params = {
        page: 1,
        perPage: 10000,
        search: searchTerm
      };
      
      const response = await apiService.getSintaDosen(params);

      if (response.success) {
        const allData = response.data.data || [];
        const totalDosen = response.data.pagination?.total || allData.length;
        
        // Calculate total citations from both Google Scholar and Scopus
        const totalSitasi = allData.reduce((sum, dosen) => {
          const gsCitations = dosen.n_total_sitasi_gs || 0;
          const scopusCitations = dosen.n_sitasi_scopus || 0;
          return sum + gsCitations + scopusCitations;
        }, 0);
        
        const avgHIndex = allData.length > 0 
          ? (allData.reduce((sum, dosen) => sum + (dosen.n_h_index_gs || 0), 0) / allData.length).toFixed(1) 
          : 0;

        setAggregateStats({
          totalDosen,
          totalSitasi,
          avgHIndex
        });
      }
    } catch (error) {
      console.error('Error fetching all data for stats:', error);
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
      toast.error('Terjadi kesalahan saat mengambil data');
      console.error('Error fetching SINTA dosen data:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleSearchChange = (value) => {
    setSearchTerm(value);
    setCurrentPage(1);
  };

  const handlePageChange = (page) => {
    setCurrentPage(page);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const columns = [
    {
      key: 'v_nama_dosen',
      title: 'Nama Dosen',
      render: (value, row) => (
        <div className="flex items-center">
          <div className="h-10 w-10 bg-blue-100 rounded-full flex items-center justify-center">
            <Users className="h-5 w-5 text-blue-600" />
          </div>
          <div className="ml-3">
            <p className="text-sm font-medium text-gray-900">{value || 'N/A'}</p>
            {row.v_id_sinta && (
              <p className="text-xs text-gray-500">SINTA ID: {row.v_id_sinta}</p>
            )}
          </div>
        </div>
      )
    },
    {
      key: 'v_nama_jurusan',
      title: 'Jurusan',
      render: (value) => (
        <span className="text-sm text-gray-900">{value || 'N/A'}</span>
      )
    },
    {
      key: 'n_total_publikasi',
      title: 'Publikasi',
      type: 'number',
      className: 'text-center',
      cellClassName: 'text-center',
      render: (value) => (
        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
          {(value || 0).toLocaleString()}
        </span>
      )
    },
    {
      key: 'n_total_sitasi_gs',
      title: 'Sitasi',
      type: 'number',
      className: 'text-center',
      cellClassName: 'text-center',
      render: (value, row) => {
        const gsCitations = value || 0;
        const scopusCitations = row.n_sitasi_scopus || 0;
        const totalCitations = gsCitations + scopusCitations;
        
        return (
          <div className="text-center">
            <span className="font-semibold text-green-600 block mb-1">
              {totalCitations.toLocaleString()}
            </span>
            {(gsCitations > 0 || scopusCitations > 0) && (
              <div className="text-xs text-gray-500">
                {gsCitations > 0 && (
                  <span title="Google Scholar" className="inline-block">
                    GS: {gsCitations.toLocaleString()}
                  </span>
                )}
                {gsCitations > 0 && scopusCitations > 0 && (
                  <span className="mx-1">|</span>
                )}
                {scopusCitations > 0 && (
                  <span title="Scopus" className="inline-block">
                    Scopus: {scopusCitations.toLocaleString()}
                  </span>
                )}
              </div>
            )}
          </div>
        );
      }
    },
    {
      key: 'n_h_index_gs',
      title: 'H-Index',
      type: 'number',
      className: 'text-center',
      cellClassName: 'text-center',
      render: (value) => (
        <span className="inline-flex items-center px-2 py-1 rounded text-sm font-medium bg-yellow-100 text-yellow-800">
          {value || 0}
        </span>
      )
    },
    {
      key: 'n_skor_sinta',
      title: 'Skor SINTA',
      type: 'number',
      className: 'text-center',
      cellClassName: 'text-center',
      render: (value) => (
        <span className="text-sm font-medium text-purple-600">
          {(Number(value) || 0).toFixed(2)}
        </span>
      )
    },
    {
      key: 'actions',
      title: 'Aksi',
      sortable: false,
      className: 'text-center',
      cellClassName: 'text-center',
      render: (_, row) => (
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
                <p className="text-sm text-gray-500 mt-1">{subtitle}</p>
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
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900">Data Dosen SINTA</h1>
          <p className="mt-2 text-sm text-gray-600">
            Daftar dosen dengan data dari SINTA (Science and Technology Index)
          </p>
        </div>

        {/* Stats Cards */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
          <StatCard
            title="Total Dosen"
            value={aggregateStats.totalDosen}
            icon={Users}
            color="#3B82F6"
            loading={statsLoading}
          />
          <StatCard
            title="Total Sitasi"
            value={aggregateStats.totalSitasi}
            icon={Award}
            color="#10B981"
            subtitle="Google Scholar + Scopus"
            loading={statsLoading}
          />
          <StatCard
            title="Rata-rata H-Index"
            value={aggregateStats.avgHIndex}
            icon={TrendingUp}
            color="#F59E0B"
            subtitle="Keseluruhan"
            loading={statsLoading}
          />
          <StatCard
            title="Data Terbaru"
            value={dosenData.length > 0 ? new Date().toLocaleDateString('id-ID') : '-'}
            icon={Calendar}
            color="#EF4444"
            loading={false}
          />
        </div>

        {/* Data Table */}
        <DataTable
          title="Daftar Dosen SINTA"
          data={dosenData}
          columns={columns}
          loading={loading}
          searchTerm={searchTerm}
          onSearchChange={handleSearchChange}
          onRefresh={fetchDosenData}
          pagination={pagination}
          onPageChange={handlePageChange}
          emptyMessage="Tidak ada data dosen SINTA ditemukan"
          emptyIcon={<Users className="h-12 w-12" />}
        />
      </div>
    </div>
  );
};

export default SintaDosen;