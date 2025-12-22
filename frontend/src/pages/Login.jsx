import { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { toast } from 'react-hot-toast';
import { Eye, EyeOff, X, Mail, Lock } from 'lucide-react';
import authService from '../services/authService';
import ColorBends from '../components/ColorBends';
import LoadingOverlay from '../components/LoadingOverlay';
import unparLogo from '../assets/image copy.png';

const Login = ({ onLogin }) => {
  const location = useLocation();
  // Check if coming from register route or has signup query param
  const [activeTab, setActiveTab] = useState(
    location.pathname === '/register' || location.search === '?signup' ? 'signup' : 'signin'
  );
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  // Sign in form data
  const [signInData, setSignInData] = useState({
    email: '',
    password: ''
  });

  // Sign up form data
  const [signUpData, setSignUpData] = useState({
    email: '',
    username: '',
    password: '',
    confirmPassword: ''
  });

  const handleSignInChange = (e) => {
    setSignInData(prev => ({
      ...prev,
      [e.target.name]: e.target.value
    }));
  };

  const handleSignUpChange = (e) => {
    setSignUpData(prev => ({
      ...prev,
      [e.target.name]: e.target.value
    }));
  };

  const handleSignInSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);

    try {
      const response = await authService.login(signInData.email, signInData.password);
      
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

  const validateSignUpForm = () => {
    if (!signUpData.email || !signUpData.username || !signUpData.password || !signUpData.confirmPassword) {
      toast.error('Semua field harus diisi');
      return false;
    }

    if (signUpData.email && !/\S+@\S+\.\S+/.test(signUpData.email)) {
      toast.error('Format email tidak valid');
      return false;
    }

    if (signUpData.username.length < 3) {
      toast.error('Username minimal 3 karakter');
      return false;
    }

    if (signUpData.password.length < 6) {
      toast.error('Password minimal 6 karakter');
      return false;
    }

    if (signUpData.password !== signUpData.confirmPassword) {
      toast.error('Password dan konfirmasi password tidak sama');
      return false;
    }

    return true;
  };

  const handleSignUpSubmit = async (e) => {
    e.preventDefault();
    
    if (!validateSignUpForm()) return;

    setLoading(true);

    try {
      const response = await authService.register(
        signUpData.username,
        signUpData.email,
        signUpData.password
      );
      
      if (response.success) {
        toast.success('Registrasi berhasil! Silakan login');
        setActiveTab('signin');
        setSignInData({ email: signUpData.email, password: '' });
        navigate('/login');
      } else {
        toast.error(response.error || 'Registrasi gagal');
      }
    } catch (error) {
      toast.error('Terjadi kesalahan saat registrasi');
      console.error('Registration error:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleClose = () => {
    navigate('/');
  };

  return (
    <>
      <LoadingOverlay 
        isLoading={loading} 
        message={activeTab === 'signin' ? 'Masuk ke akun...' : 'Mendaftar akun baru...'}
        subMessage="Mohon tunggu sebentar"
      />
      <div className="min-h-screen flex items-center justify-center p-4 relative overflow-hidden">
      {/* ColorBends Background */}
      <div className="absolute inset-0">
        <ColorBends
          colors={["#ff5c7a", "#8a5cff", "#00ffd1"]}
          rotation={30}
          speed={0.3}
          scale={1.2}
          frequency={1.4}
          warpStrength={1.2}
          mouseInfluence={0.8}
          parallax={0.6}
          noise={0.08}
          transparent
        />
      </div>
      
      {/* Dark Modal Card */}
      <div className="max-w-md w-full relative z-10">
        <div 
          className="bg-[#2A2A2A] rounded-2xl shadow-2xl overflow-hidden"
          style={{
            boxShadow: '0 20px 60px rgba(0, 0, 0, 0.5)'
          }}
        >
          {/* Top Bar with Tabs and Close Button */}
          <div className="flex items-center justify-between px-6 pt-6 pb-4 border-b border-[#3A3A3A]">
            <div className="flex gap-2">
              <button
                onClick={() => setActiveTab('signup')}
                className={`px-4 py-2 rounded-lg text-sm font-medium transition-all duration-200 ${
                  activeTab === 'signup'
                    ? 'bg-[#3A3A3A] text-white'
                    : 'text-[#A0A0A0] hover:text-white'
                }`}
              >
                Sign up
              </button>
              <button
                onClick={() => setActiveTab('signin')}
                className={`px-4 py-2 rounded-lg text-sm font-medium transition-all duration-200 ${
                  activeTab === 'signin'
                    ? 'bg-[#3A3A3A] text-white'
                    : 'text-[#A0A0A0] hover:text-white'
                }`}
              >
                Sign in
              </button>
            </div>
            <button
              onClick={handleClose}
              className="w-8 h-8 flex items-center justify-center rounded-full hover:bg-[#3A3A3A] transition-colors duration-200 text-white"
            >
              <X className="h-5 w-5" />
            </button>
          </div>

          {/* Content */}
          <div className="px-6 py-6">
            {/* Logo UNPAR */}
            <div className="flex justify-center mb-6">
              <img 
                src={unparLogo} 
                alt="Universitas Parahyangan" 
                className="h-20 w-auto object-contain"
              />
            </div>
            
            {/* Title */}
            <h2 className="text-3xl font-bold text-white mb-6 text-center">
              {activeTab === 'signup' ? 'Create an account' : 'Sign in to your account'}
            </h2>

            {/* Sign Up Form */}
            {activeTab === 'signup' && (
              <form onSubmit={handleSignUpSubmit} className="space-y-4">
                {/* Email */}
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
                    <Mail className="h-5 w-5 text-[#6E6E73]" />
                  </div>
                  <input
                    type="email"
                    name="email"
                    placeholder="Enter your email"
                    value={signUpData.email}
                    onChange={handleSignUpChange}
                    className="w-full pl-12 pr-4 py-3 bg-[#1F1F1F] border border-[#3A3A3A] rounded-lg text-white placeholder-[#6E6E73] focus:outline-none focus:border-[#4A4A4A] transition-colors"
                    required
                  />
                </div>

                {/* Username */}
                <div>
                  <input
                    type="text"
                    name="username"
                    placeholder="Username"
                    value={signUpData.username}
                    onChange={handleSignUpChange}
                    className="w-full px-4 py-3 bg-[#1F1F1F] border border-[#3A3A3A] rounded-lg text-white placeholder-[#6E6E73] focus:outline-none focus:border-[#4A4A4A] transition-colors"
                    required
                  />
                </div>

                {/* Password */}
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
                    <Lock className="h-5 w-5 text-[#6E6E73]" />
                  </div>
                  <input
                    type={showPassword ? 'text' : 'password'}
                    name="password"
                    placeholder="Password"
                    value={signUpData.password}
                    onChange={handleSignUpChange}
                    className="w-full pl-12 pr-12 py-3 bg-[#1F1F1F] border border-[#3A3A3A] rounded-lg text-white placeholder-[#6E6E73] focus:outline-none focus:border-[#4A4A4A] transition-colors"
                    required
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute inset-y-0 right-0 pr-4 flex items-center text-[#6E6E73] hover:text-white transition-colors"
                  >
                    {showPassword ? <EyeOff className="h-5 w-5" /> : <Eye className="h-5 w-5" />}
                  </button>
                </div>

                {/* Confirm Password */}
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
                    <Lock className="h-5 w-5 text-[#6E6E73]" />
                  </div>
                  <input
                    type={showConfirmPassword ? 'text' : 'password'}
                    name="confirmPassword"
                    placeholder="Confirm password"
                    value={signUpData.confirmPassword}
                    onChange={handleSignUpChange}
                    className="w-full pl-12 pr-12 py-3 bg-[#1F1F1F] border border-[#3A3A3A] rounded-lg text-white placeholder-[#6E6E73] focus:outline-none focus:border-[#4A4A4A] transition-colors"
                    required
                  />
                  <button
                    type="button"
                    onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                    className="absolute inset-y-0 right-0 pr-4 flex items-center text-[#6E6E73] hover:text-white transition-colors"
                  >
                    {showConfirmPassword ? <EyeOff className="h-5 w-5" /> : <Eye className="h-5 w-5" />}
                  </button>
                </div>

                {/* Submit Button */}
                <button
                  type="submit"
                  disabled={loading}
                  className="w-full py-3 bg-[#E5E5E5] text-[#1F1F1F] font-semibold rounded-lg hover:bg-[#D0D0D0] transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {loading ? 'Creating...' : 'Create an account'}
                </button>
              </form>
            )}

            {/* Sign In Form */}
            {activeTab === 'signin' && (
              <form onSubmit={handleSignInSubmit} className="space-y-4">
                {/* Email */}
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
                    <Mail className="h-5 w-5 text-[#6E6E73]" />
                  </div>
                  <input
                    type="email"
                    name="email"
                    placeholder="Enter your email"
                    value={signInData.email}
                    onChange={handleSignInChange}
                    className="w-full pl-12 pr-4 py-3 bg-[#1F1F1F] border border-[#3A3A3A] rounded-lg text-white placeholder-[#6E6E73] focus:outline-none focus:border-[#4A4A4A] transition-colors"
                    required
                  />
                </div>

                {/* Password */}
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
                    <Lock className="h-5 w-5 text-[#6E6E73]" />
                  </div>
                  <input
                    type={showPassword ? 'text' : 'password'}
                    name="password"
                    placeholder="Password"
                    value={signInData.password}
                    onChange={handleSignInChange}
                    className="w-full pl-12 pr-12 py-3 bg-[#1F1F1F] border border-[#3A3A3A] rounded-lg text-white placeholder-[#6E6E73] focus:outline-none focus:border-[#4A4A4A] transition-colors"
                    required
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute inset-y-0 right-0 pr-4 flex items-center text-[#6E6E73] hover:text-white transition-colors"
                  >
                    {showPassword ? <EyeOff className="h-5 w-5" /> : <Eye className="h-5 w-5" />}
                  </button>
                </div>

                {/* Submit Button */}
                <button
                  type="submit"
                  disabled={loading}
                  className="w-full py-3 bg-[#E5E5E5] text-[#1F1F1F] font-semibold rounded-lg hover:bg-[#D0D0D0] transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {loading ? 'Signing in...' : 'Sign in'}
                </button>
              </form>
            )}
          </div>
        </div>
      </div>
    </div>
    </>
  );
}

export default Login;
