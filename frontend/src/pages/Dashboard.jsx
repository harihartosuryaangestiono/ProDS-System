import { useState, useEffect } from 'react';
import { BarChart, Bar, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts';
import { Users, FileText, TrendingUp, Award, Calendar, BookOpen, Search, ArrowUp, ArrowDown } from 'lucide-react';
import apiService from '../services/apiService';

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

  useEffect(() => {
    fetchDashboardStats();
  }, []);

  const fetchDashboardStats = async () => {
    try {
      setLoading(true);
      const response = await apiService.getDashboardStats();
      
      if (response.success) {
        setStats(response.data);
      } else {
        console.error('Error fetching dashboard stats:', response.error);
      }
    } catch (error) {
      console.error('Error fetching dashboard stats:', error);
    } finally {
      setLoading(false);
    }
  };

  // Colors for charts
  const COLORS = ['#0088FE', '#00C49F', '#FFBB28', '#FF8042', '#8884D8'];

  const StatCard = ({ title, value, icon: Icon, color, subtitle, previousValue, previousDate, valueKey }) => {
    // Extract numeric value from string (remove commas and parse)
    const getNumericValue = (val) => {
      if (typeof val === 'number') return val;
      if (typeof val === 'string') {
        // Remove commas and parse
        const cleaned = val.replace(/,/g, '');
        return parseFloat(cleaned) || 0;
      }
      return 0;
    };
    
    const currentValue = getNumericValue(value);
    const prevValue = previousValue || 0;
    const isIncreased = currentValue > prevValue;
    const isDecreased = currentValue < prevValue;
    const isEqual = Math.abs(currentValue - prevValue) < 0.01; // For floating point comparison
    
    // Format previous value for display
    const formatPrevValue = (val) => {
      if (typeof val === 'number') {
        // Check if it's a decimal (like h-index)
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

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="animate-spin rounded-full h-32 w-32 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  // Filter data per tahun berdasarkan rentang pilihan
  const filteredYearData = (() => {
    const currentYear = new Date().getFullYear();
    return (stats.publikasi_by_year || []).filter(item => {
      const year = parseInt(item.v_tahun_publikasi);
      return year >= currentYear - yearRange && year <= currentYear;
    });
  })();

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

        {/* Stats Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
          <StatCard
            title="Total Dosen"
            value={stats.total_dosen.toLocaleString()}
            icon={Users}
            color="#3B82F6"
            previousValue={stats.previous_values?.total_dosen}
            previousDate={stats.previous_date}
            valueKey="total_dosen"
          />
          <StatCard
            title="Total Publikasi"
            value={stats.total_publikasi.toLocaleString()}
            icon={FileText}
            color="#10B981"
            previousValue={stats.previous_values?.total_publikasi}
            previousDate={stats.previous_date}
            valueKey="total_publikasi"
          />
          <StatCard
            title="Total Sitasi"
            value={stats.total_sitasi.toLocaleString()}
            subtitle={`GS: ${stats.total_sitasi_gs?.toLocaleString() || 0} | GS-SINTA: ${stats.total_sitasi_gs_sinta?.toLocaleString() || 0} | Scopus: ${stats.total_sitasi_scopus?.toLocaleString() || 0}`}
            icon={Award}
            color="#F59E0B"
            previousValue={stats.previous_values?.total_sitasi}
            previousDate={stats.previous_date}
            valueKey="total_sitasi"
          />
          <StatCard
            title="H-Index Rata-rata"
            value={stats.avg_h_index ? stats.avg_h_index.toFixed(1) : '0.0'}
            subtitle={`Median: ${stats.median_h_index ? stats.median_h_index.toFixed(1) : '0.0'}`}
            icon={TrendingUp}
            color="#EF4444"
            previousValue={stats.previous_values?.avg_h_index}
            previousDate={stats.previous_date}
            valueKey="avg_h_index"
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
            valueKey="publikasi_internasional_q12"
          />
          <StatCard
            title="Internasional (Q3-Q4/noQ)"
            value={stats.publikasi_internasional_q34_noq.toLocaleString()}
            icon={Award}
            color="#10B981"
            previousValue={stats.previous_values?.publikasi_internasional_q34_noq}
            previousDate={stats.previous_date}
            valueKey="publikasi_internasional_q34_noq"
          />
          <StatCard
            title="Nasional (Sinta 1-2)"
            value={stats.publikasi_nasional_sinta12.toLocaleString()}
            icon={Award}
            color="#7C3AED"
            previousValue={stats.previous_values?.publikasi_nasional_sinta12}
            previousDate={stats.previous_date}
            valueKey="publikasi_nasional_sinta12"
          />
          <StatCard
            title="Nasional (Sinta 3-4)"
            value={stats.publikasi_nasional_sinta34.toLocaleString()}
            icon={Award}
            color="#8B5CF6"
            previousValue={stats.previous_values?.publikasi_nasional_sinta34}
            previousDate={stats.previous_date}
            valueKey="publikasi_nasional_sinta34"
          />
        </div>

        {/* Additional Sinta 5-6 combined */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
          <StatCard
            title="Nasional (Sinta 5-6)"
            value={(stats.publikasi_nasional_sinta5 + stats.publikasi_nasional_sinta6).toLocaleString()}
            icon={Award}
            color="#A78BFA"
            previousValue={(stats.previous_values?.publikasi_nasional_sinta5 || 0) + (stats.previous_values?.publikasi_nasional_sinta6 || 0)}
            previousDate={stats.previous_date}
            valueKey="publikasi_nasional_sinta56"
          />
        </div>

        {/* Charts Row */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 mb-8">
          {/* Publications by Year Chart - Single visualization with filter */}
          <div className="bg-white rounded-lg shadow-md p-6">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center">
                <Calendar className="w-5 h-5 text-blue-600 mr-2" />
                <h2 className="text-lg font-semibold text-gray-900">Publikasi per Tahun ({yearRange} Tahun Terakhir)</h2>
              </div>
              <select
                className="border border-gray-300 rounded-md text-sm px-2 py-1 text-gray-700"
                value={yearRange}
                onChange={(e) => setYearRange(parseInt(e.target.value))}
              >
                <option value={5}>5 Tahun</option>
                <option value={10}>10 Tahun</option>
                <option value={15}>15 Tahun</option>
              </select>
            </div>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={filteredYearData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="v_tahun_publikasi" />
                <YAxis />
                <Tooltip />
                <Legend />
                <Bar dataKey="count" fill="#3B82F6" name="Jumlah Publikasi" />
              </BarChart>
            </ResponsiveContainer>
          </div>

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
        </div>

        {/* Top Dosen by h-index (Google Scholar) */}
        <div className="grid grid-cols-1 lg:grid-cols-1 gap-8 mb-8">
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
              <h2 className="text-lg font-semibold text-gray-900">Scopus Breakdown (Q)</h2>
            </div>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={stats.scopus_q_breakdown}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="ranking" />
                <YAxis />
                <Tooltip />
                <Legend />
                <Bar dataKey="count" fill="#10B981" name="Jumlah" />
              </BarChart>
            </ResponsiveContainer>
          </div>
          {/* Sinta Rank Breakdown */}
          <div className="bg-white rounded-lg shadow-md p-6">
            <div className="flex items-center mb-4">
              <Award className="w-5 h-5 text-indigo-600 mr-2" />
              <h2 className="text-lg font-semibold text-gray-900">Sinta Breakdown (S1–S6)</h2>
            </div>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={stats.sinta_rank_breakdown}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="ranking" />
                <YAxis />
                <Tooltip />
                <Legend />
                <Bar dataKey="count" fill="#6366F1" name="Jumlah" />
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