import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { toast } from 'react-hot-toast';
import { Eye, EyeOff, LogIn, User, Lock } from 'lucide-react';
import authService from '../services/authService';

const Login = ({ onLogin }) => {
  const [formData, setFormData] = useState({
    email: '',
    password: ''
  });
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const handleChange = (e) => {
    setFormData(prev => ({
      ...prev,
      [e.target.name]: e.target.value
    }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);

    try {
      const response = await authService.login(formData.email, formData.password);
      
      if (response.success) {
        onLogin(response.data.user);
        toast.success('Login berhasil!');
        navigate('/dashboard');
      } else {
        toast.error(response.error || 'Login gagal');
      }
    } catch (error) {
      toast.error('Terjadi kesalahan saat login');
      console.error('Login error:', error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-400 to-indigo-600 flex items-center justify-center p-4">
      <div className="max-w-md w-full space-y-8">
        {/* Header dengan animasi */}
        <div className="text-center transform hover:scale-105 transition-transform duration-300">
          <div className="mx-auto h-20 w-20 bg-white rounded-full flex items-center justify-center shadow-lg">
            <User className="h-10 w-10 text-blue-600" />
          </div>
          <h2 className="mt-6 text-4xl font-extrabold text-white">
            Masuk ke ProDS
          </h2>
          <p className="mt-2 text-lg text-blue-100">
            Sistem Publikasi Dosen SINTA & Google Scholar
          </p>
        </div>

        {/* Form dengan efek hover dan animasi */}
        <form className="mt-8 space-y-6" onSubmit={handleSubmit}>
          <div className="bg-white/95 backdrop-blur-sm p-8 rounded-xl shadow-2xl space-y-6 transform hover:translate-y-[-2px] transition-all duration-300">
            <div className="space-y-5">
              {/* Email Field dengan animasi focus */}
              <div className="group">
                <label htmlFor="email" className="block text-sm font-medium text-gray-700 mb-1">Email</label>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                    <User className="h-5 w-5 text-gray-400 group-hover:text-blue-500 transition-colors duration-200" />
                  </div>
                  <input
                    id="email"
                    name="email"
                    type="email"
                    autoComplete="email"
                    required
                    className="appearance-none relative block w-full px-3 py-3 pl-10 border border-gray-300 rounded-lg placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all duration-200 text-gray-900"
                    placeholder="Alamat Email"
                    value={formData.email}
                    onChange={handleChange}
                  />
                </div>
              </div>

              {/* Password Field dengan animasi focus */}
              <div className="group">
                <label htmlFor="password" className="block text-sm font-medium text-gray-700 mb-1">Password</label>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                    <Lock className="h-5 w-5 text-gray-400 group-hover:text-blue-500 transition-colors duration-200" />
                  </div>
                  <input
                    id="password"
                    name="password"
                    type={showPassword ? 'text' : 'password'}
                    autoComplete="current-password"
                    required
                    className="appearance-none relative block w-full px-3 py-3 pl-10 border border-gray-300 rounded-lg placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all duration-200 text-gray-900"
                    placeholder="Kata Sandi"
                    value={formData.password}
                    onChange={handleChange}
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute inset-y-0 right-0 pr-3 flex items-center text-gray-400 hover:text-blue-500 transition-colors duration-200"
                  >
                    {showPassword ? (
                      <EyeOff className="h-5 w-5" />
                    ) : (
                      <Eye className="h-5 w-5" />
                    )}
                  </button>
                </div>
              </div>
            </div>

            {/* Remember Me dengan style baru */}
            <div className="flex items-center justify-between">
              <div className="flex items-center">
                <input
                  id="remember-me"
                  name="remember-me"
                  type="checkbox"
                  className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded transition-colors duration-200"
                />
                <label htmlFor="remember-me" className="ml-2 block text-sm text-gray-700">
                  Ingat saya
                </label>
              </div>
            </div>

            {/* Submit Button dengan animasi */}
            <div>
              <button
                type="submit"
                className={`group relative w-full flex justify-center py-3 px-4 border border-transparent text-sm font-medium rounded-lg text-white bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 transform hover:translate-y-[-1px] transition-all duration-200 ${
                  loading ? 'opacity-50 cursor-not-allowed' : ''
                }`}
                disabled={loading}
              >
                {loading ? (
                  <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                ) : (
                  <LogIn className="h-5 w-5 mr-2 group-hover:scale-110 transition-transform duration-200" />
                )}
                {loading ? 'Memuat...' : 'Masuk'}
              </button>
            </div>
          </div>
        </form>

        {/* Register Link dengan animasi */}
        <div className="text-center">
          <p className="text-sm text-blue-100">
            Belum punya akun?{' '}
            <Link to="/register" className="font-medium text-white hover:text-blue-200 underline decoration-2 decoration-blue-400 hover:decoration-blue-200 transition-all duration-200">
              Daftar sekarang
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}


export default Login;