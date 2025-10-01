// file: src/pages/SintaPublikasi.jsx

import { useState, useEffect, useMemo, useCallback } from 'react';
import { FileText, Award, Calendar, ExternalLink, AlertCircle } from 'lucide-react';
import apiService from '../services/apiService';
import DataTable from '../components/DataTable';
import { toast } from 'react-hot-toast';

// Helper Hook untuk Debounce (dapat juga dipindah ke file terpisah)
const useDebounce = (value, delay) => {
  const [debouncedValue, setDebouncedValue] = useState(value);

  useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedValue(value);
    }, delay);

    return () => {
      clearTimeout(handler);
    };
  }, [value, delay]);

  return debouncedValue;
};

// Konstanta untuk item per halaman
const PER_PAGE = 20;

// Komponen StatCard (dipindah ke luar komponen utama agar tidak dirender ulang)
const StatCard = ({ title, value, icon: Icon, color, subtitle }) => (
    <div className="bg-white rounded-lg shadow-md p-6 border-l-4 hover:shadow-lg transition-shadow" style={{ borderColor: color }}>
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm font-medium text-gray-600">{title}</p>
          <p className="text-2xl font-bold text-gray-900 mt-1">{value}</p>
          {subtitle && (
            <p className="text-xs text-gray-500 mt-1">{subtitle}</p>
          )}
        </div>
        <div className="p-3 rounded-full" style={{ backgroundColor: `${color}20` }}>
          <Icon className="w-8 h-8" style={{ color }} />
        </div>
      </div>
    </div>
);

// Komponen Utama
const SintaPublikasi = () => {
  const [publikasiData, setPublikasiData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [currentPage, setCurrentPage] = useState(1);
  const [pagination, setPagination] = useState(null);
  const [error, setError] = useState(null);

  const debouncedSearchTerm = useDebounce(searchTerm, 500); // Tunggu 500ms setelah user berhenti mengetik

  const fetchPublikasiData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = { page: currentPage, perPage: PER_PAGE, search: debouncedSearchTerm };
      const response = await apiService.getSintaPublikasi(params);

      if (response.success) {
        const responseData = response.data;
        const publikasiList = Array.isArray(responseData.data) ? responseData.data : [];
        setPublikasiData(publikasiList);
        setPagination(responseData.pagination || null);
      } else {
        const errorMsg = response.error || 'Gagal mengambil data publikasi SINTA';
        setError(errorMsg);
        toast.error(errorMsg);
        setPublikasiData([]);
        setPagination(null);
      }
    } catch (err) {
      const errorMsg = 'Terjadi kesalahan saat mengambil data.';
      setError(errorMsg);
      toast.error(errorMsg);
      console.error('Error fetching SINTA publikasi data:', err);
      setPublikasiData([]);
      setPagination(null);
    } finally {
      setLoading(false);
    }
  }, [currentPage, debouncedSearchTerm]);

  useEffect(() => {
    fetchPublikasiData();
  }, [fetchPublikasiData]);

  const handleSearchChange = (value) => {
    setSearchTerm(value);
    setCurrentPage(1);
  };

  const handlePageChange = (page) => {
    setCurrentPage(page);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const columns = useMemo(() => [
    {
      key: 'v_judul',
      title: 'Judul Publikasi',
      render: (value, row) => (
        <div className="max-w-md">
          <p className="font-medium text-gray-900 line-clamp-2" title={value}>{value || 'N/A'}</p>
          {row.authors && <p className="text-sm text-gray-500 truncate mt-1" title={row.authors}>{row.authors}</p>}
        </div>
      )
    },
    {
      key: 'v_jenis',
      title: 'Jenis',
      render: (value) => {
        const jenisMap = { 'artikel': { bg: 'bg-blue-100', text: 'text-blue-800', label: 'Artikel' }, 'buku': { bg: 'bg-green-100', text: 'text-green-800', label: 'Buku' }, 'prosiding': { bg: 'bg-yellow-100', text: 'text-yellow-800', label: 'Prosiding' }, 'penelitian': { bg: 'bg-purple-100', text: 'text-purple-800', label: 'Penelitian' } };
        const jenis = jenisMap[value?.toLowerCase()] || { bg: 'bg-gray-100', text: 'text-gray-800', label: value || 'N/A' };
        return <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${jenis.bg} ${jenis.text}`}>{jenis.label}</span>;
      }
    },
    { key: 'v_tahun_publikasi', title: 'Tahun', type: 'number', className: 'text-center', cellClassName: 'text-center', render: (value) => <span className="font-medium text-gray-900">{value || '-'}</span> },
    { key: 'n_total_sitasi', title: 'Total Sitasi', type: 'number', className: 'text-center', cellClassName: 'text-center', render: (value) => <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-semibold bg-indigo-50 text-indigo-700">{(value || 0).toLocaleString()}</span> },
    {
      key: 'v_sumber',
      title: 'Sumber',
      render: (value) => {
        const sumberMap = { 'Sinta_Scopus': { bg: 'bg-orange-100', text: 'text-orange-800', label: 'Scopus' }, 'Sinta_GoogleScholar': { bg: 'bg-red-100', text: 'text-red-800', label: 'Scholar' }, 'SINTA_Garuda': { bg: 'bg-purple-100', text: 'text-purple-800', label: 'Garuda' } };
        const sumber = sumberMap[value] || { bg: 'bg-gray-100', text: 'text-gray-800', label: value || 'N/A' };
        return <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${sumber.bg} ${sumber.text}`}>{sumber.label}</span>;
      }
    },
    {
      key: 'actions', title: 'Aksi', sortable: false, className: 'text-center', cellClassName: 'text-center',
      render: (_, row) => (
        <div className="flex items-center justify-center space-x-2">
          {row.v_link_url ? (
            <a href={row.v_link_url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center px-3 py-1 text-sm font-medium text-indigo-600 hover:text-indigo-900 hover:bg-indigo-50 rounded transition-colors" title="Lihat publikasi">
              <ExternalLink className="w-4 h-4 mr-1" /> Lihat
            </a>
          ) : (<span className="text-gray-400 text-sm">-</span>)}
        </div>
      )
    }
  ], []);

  const stats = useMemo(() => {
    const totalPublikasi = pagination?.total || 0;
    const totalSitasiHalamanIni = publikasiData.reduce((sum, pub) => sum + (pub.n_total_sitasi || 0), 0);
    const avgSitasi = publikasiData.length > 0 ? (totalSitasiHalamanIni / publikasiData.length).toFixed(1) : 0;
    const currentYear = new Date().getFullYear();
    const recentPublikasi = publikasiData.filter(pub => pub.v_tahun_publikasi >= currentYear - 2).length;
    return { totalPublikasi, totalSitasiHalamanIni, avgSitasi, recentPublikasi };
  }, [publikasiData, pagination]);

  return (
    <div className="min-h-screen bg-gray-50 py-8">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900">Data Publikasi SINTA</h1>
          <p className="mt-2 text-sm text-gray-600">Daftar publikasi dari berbagai sumber SINTA (Scopus, Google Scholar, Garuda)</p>
        </div>

        {error && (
          <div className="mb-6 bg-red-50 border-l-4 border-red-400 p-4 rounded">
            <div className="flex items-start">
              <AlertCircle className="h-5 w-5 text-red-400 mt-0.5" />
              <div className="ml-3">
                <h3 className="text-sm font-medium text-red-800">Error</h3>
                <p className="mt-1 text-sm text-red-700">{error}</p>
                <button onClick={fetchPublikasiData} className="mt-3 text-sm font-medium text-red-800 hover:text-red-900 underline">Coba lagi</button>
              </div>
            </div>
          </div>
        )}

        <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
          <StatCard title="Total Publikasi" value={stats.totalPublikasi.toLocaleString()} icon={FileText} color="#3B82F6" subtitle="dari semua sumber" />
          <StatCard title="Total Sitasi" value={stats.totalSitasiHalamanIni.toLocaleString()} icon={Award} color="#10B981" subtitle="pada halaman ini" />
          <StatCard title="Rata-rata Sitasi" value={stats.avgSitasi} icon={Award} color="#F59E0B" subtitle="per publikasi (halaman ini)" />
          <StatCard title="Publikasi Terbaru" value={stats.recentPublikasi.toLocaleString()} icon={Calendar} color="#EF4444" subtitle="2 tahun terakhir (halaman ini)" />
        </div>

        <DataTable
          title="Daftar Publikasi"
          data={publikasiData}
          columns={columns}
          loading={loading}
          searchTerm={searchTerm}
          onSearchChange={handleSearchChange}
          onRefresh={fetchPublikasiData}
          pagination={pagination}
          onPageChange={handlePageChange}
          emptyMessage="Tidak ada data publikasi ditemukan"
          emptyDescription={searchTerm ? "Coba ubah kata kunci pencarian Anda" : "Belum ada data publikasi yang tersedia"}
          emptyIcon={<FileText className="h-12 w-12" />}
        />
      </div>
    </div>
  );
};

export default SintaPublikasi;