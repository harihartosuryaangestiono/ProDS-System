import { useState, useEffect } from 'react';
import { Users, TrendingUp, Award, Calendar, ExternalLink } from 'lucide-react';
import apiService from '../services/apiService';
import DataTable from '../components/DataTable';
import { toast } from 'react-hot-toast';

const ScholarDosen = () => {
  const [dosenData, setDosenData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [currentPage, setCurrentPage] = useState(1);
  const [pagination, setPagination] = useState(null);
  const perPage = 50; // ✅ Changed from 20 to 50

  useEffect(() => {
    fetchDosenData();
  }, [currentPage, searchTerm]);

  const fetchDosenData = async () => {
    try {
      setLoading(true);
      
      // ✅ FIX: Pass parameters as an object
      const params = {
        page: currentPage,
        perPage: perPage,
        search: searchTerm
      };
      
      const response = await apiService.getScholarDosen(params);

      if (response.success) {
        setDosenData(response.data.data || []);
        
        // ✅ FIX: Transform pagination data to match DataTable expectations
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
          <div className="h-10 w-10 bg-red-100 rounded-full flex items-center justify-center">
            <Users className="h-5 w-5 text-red-600" />
          </div>
          <div className="ml-3">
            <p className="text-sm font-medium text-gray-900">{value || 'N/A'}</p>
            {row.v_id_googleScholar && (
              <p className="text-xs text-gray-500">ID: {row.v_id_googleScholar}</p>
            )}
          </div>
        </div>
      )
    },
    {
      key: 'n_total_publikasi',
      title: 'Total Publikasi',
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
      title: 'Total Sitasi',
      type: 'number',
      className: 'text-center',
      cellClassName: 'text-center',
      render: (value) => (
        <span className="font-semibold text-green-600">
          {(value || 0).toLocaleString()}
        </span>
      )
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
      key: 'n_i10_index_gs',
      title: 'i10-Index',
      type: 'number',
      className: 'text-center',
      cellClassName: 'text-center',
      render: (value) => (
        <span className="text-sm font-medium text-purple-600">
          {value || 0}
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
              title="Lihat profil Google Scholar"
            >
              <ExternalLink className="w-4 h-4 mr-1" />
              Scholar
            </a>
          )}
          {row.v_id_googleScholar && !row.v_link_url && (
            <a
              href={`https://scholar.google.com/citations?user=${row.v_id_googleScholar}`}
              target="_blank"
              rel="noopener noreferrer"
              className="text-red-600 hover:text-red-900 inline-flex items-center text-sm"
              title="Lihat profil Google Scholar"
            >
              <ExternalLink className="w-4 h-4 mr-1" />
              Scholar
            </a>
          )}
        </div>
      )
    }
  ];

  const totalDosen = pagination?.totalRecords || 0;
  const totalSitasi = dosenData.reduce((sum, dosen) => sum + (dosen.n_sitasi_gs || 0), 0);
  const totalPublikasi = dosenData.reduce((sum, dosen) => sum + (dosen.n_total_publikasi || 0), 0);
  const avgHIndex = dosenData.length > 0 ? (dosenData.reduce((sum, dosen) => sum + (dosen.n_h_index_gs || 0), 0) / dosenData.length).toFixed(1) : 0;

  const StatCard = ({ title, value, icon: Icon, color, subtitle }) => (
    <div className="bg-white rounded-lg shadow-md p-6 border-l-4" style={{ borderColor: color }}>
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm font-medium text-gray-600">{title}</p>
          <p className="text-2xl font-bold text-gray-900">{value}</p>
          {subtitle && (
            <p className="text-sm text-gray-500 mt-1">{subtitle}</p>
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
          <h1 className="text-3xl font-bold text-gray-900">Data Dosen Google Scholar</h1>
          <p className="mt-2 text-sm text-gray-600">
            Daftar dosen dengan data dari Google Scholar
          </p>
        </div>

        {/* Stats Cards */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
          <StatCard
            title="Total Dosen"
            value={totalDosen.toLocaleString()}
            icon={Users}
            color="#DC2626"
          />
          <StatCard
            title="Total Publikasi"
            value={totalPublikasi.toLocaleString()}
            icon={TrendingUp}
            color="#059669"
          />
          <StatCard
            title="Total Sitasi"
            value={totalSitasi.toLocaleString()}
            icon={Award}
            color="#D97706"
          />
          <StatCard
            title="Rata-rata H-Index"
            value={avgHIndex}
            icon={Award}
            color="#7C3AED"
            subtitle="Google Scholar"
          />
        </div>

        {/* Data Table */}
        <DataTable
          title="Daftar Dosen Google Scholar"
          data={dosenData}
          columns={columns}
          loading={loading}
          searchTerm={searchTerm}
          onSearchChange={handleSearchChange}
          onRefresh={fetchDosenData}
          pagination={pagination}
          onPageChange={handlePageChange}
          emptyMessage="Tidak ada data dosen Google Scholar ditemukan"
          emptyIcon={<Users className="h-12 w-12" />}
        />
      </div>
    </div>
  );
};

export default ScholarDosen;