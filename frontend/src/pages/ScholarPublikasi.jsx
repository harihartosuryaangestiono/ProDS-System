import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { FileText, Award, Calendar, ExternalLink, Users } from 'lucide-react';
import apiService from '../services/apiService';
import DataTable from '../components/DataTable';
import { toast } from 'react-hot-toast';

const ScholarPublikasi = () => {
  const navigate = useNavigate();
  const [publikasiData, setPublikasiData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [currentPage, setCurrentPage] = useState(1);
  const [pagination, setPagination] = useState(null);
  const perPage = 20;

  useEffect(() => {
    // Check if user is authenticated
    const token = localStorage.getItem('token');
    if (!token) {
      navigate('/login');
      return;
    }
    
    fetchPublikasiData();
  }, []);

  useEffect(() => {
    fetchPublikasiData();
  }, [currentPage, searchTerm]);

  const fetchPublikasiData = async () => {
    try {
      setLoading(true);
      
      const params = apiService.buildPaginationParams(currentPage, perPage, searchTerm);
      const response = await apiService.getScholarPublikasi(params);

      if (response.success) {
        setPublikasiData(response.data.data || []);
        setPagination(response.data.pagination || null);
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

  // Calculate statistics
  const totalPublikasi = pagination?.total || 0;
  const totalSitasi = publikasiData.reduce((sum, pub) => sum + (pub.n_total_sitasi || 0), 0);
  const avgSitasi = publikasiData.length > 0 ? (totalSitasi / publikasiData.length).toFixed(1) : 0;
  const currentYear = new Date().getFullYear();
  const recentPublikasi = publikasiData.filter(pub => pub.v_tahun_publikasi >= currentYear - 2).length;

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
          <h1 className="text-3xl font-bold text-gray-900">Data Publikasi Google Scholar</h1>
          <p className="mt-2 text-sm text-gray-600">
            Daftar publikasi dengan data dari Google Scholar
          </p>
        </div>

        {/* Stats Cards */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
          <StatCard
            title="Total Publikasi"
            value={totalPublikasi.toLocaleString()}
            icon={FileText}
            color="#DC2626"
          />
          <StatCard
            title="Total Sitasi"
            value={totalSitasi.toLocaleString()}
            icon={Award}
            color="#059669"
          />
          <StatCard
            title="Rata-rata Sitasi"
            value={avgSitasi}
            icon={Award}
            color="#D97706"
            subtitle="per publikasi"
          />
          <StatCard
            title="Publikasi Terbaru"
            value={recentPublikasi.toLocaleString()}
            icon={Calendar}
            color="#7C3AED"
            subtitle="2 tahun terakhir"
          />
        </div>

        {/* Data Table */}
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
        />
      </div>
    </div>
  );
};

export default ScholarPublikasi;