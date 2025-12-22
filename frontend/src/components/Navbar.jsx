import { useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { Menu, X, User, LogOut, Home, Users, FileText, Download, ChevronDown, Info, BarChart3, TrendingUp, Sparkles, Database } from 'lucide-react';
import sintaLogo from '../assets/image.png';
import googleScholarLogo from '../assets/Google_Scholar_logo.png';

const Navbar = ({ user, onLogout }) => {
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const [isSintaDropdownOpen, setIsSintaDropdownOpen] = useState(false);
  const [isScholarDropdownOpen, setIsScholarDropdownOpen] = useState(false);
  const location = useLocation();

  const isActive = (path) => location.pathname === path;

  const NavLink = ({ to, children, className = "", onClick }) => (
    <Link
      to={to}
      onClick={onClick}
      className={`px-4 py-2.5 rounded-[12px] text-sm font-semibold transition-all duration-300 ${
        isActive(to)
          ? 'bg-[#0A84FF] text-white shadow-sm'
          : 'text-[#6E6E73] hover:text-[#1D1D1F] hover:bg-[#F5F5F7]'
      } ${className}`}
      style={{ transition: 'all 0.3s cubic-bezier(0.2, 0.9, 0.2, 1)' }}
    >
      {children}
    </Link>
  );

  const DropdownLink = ({ to, children, onClick }) => (
    <Link
      to={to}
      onClick={onClick}
      className={`block px-4 py-2.5 text-sm font-medium rounded-[12px] transition-all duration-300 ${
        isActive(to)
          ? 'bg-[#0A84FF]/10 text-[#0A84FF] font-semibold'
          : 'text-[#6E6E73] hover:bg-[#F5F5F7] hover:text-[#1D1D1F]'
      }`}
      style={{ transition: 'all 0.3s cubic-bezier(0.2, 0.9, 0.2, 1)' }}
    >
      {children}
    </Link>
  );

  const handleDropdownToggle = (dropdown) => {
    if (dropdown === 'sinta') {
      setIsSintaDropdownOpen(!isSintaDropdownOpen);
      setIsScholarDropdownOpen(false);
    } else if (dropdown === 'scholar') {
      setIsScholarDropdownOpen(!isScholarDropdownOpen);
      setIsSintaDropdownOpen(false);
    }
  };

  const closeDropdowns = () => {
    setIsSintaDropdownOpen(false);
    setIsScholarDropdownOpen(false);
  };

  return (
    <>
      {/* Backdrop Overlay - Fixed position untuk menutupi seluruh layar */}
      {isMenuOpen && (
        <div 
          className="fixed inset-0 bg-black/20 backdrop-blur-sm z-40 cursor-pointer"
          onClick={() => setIsMenuOpen(false)}
          style={{
            animation: 'fadeIn 0.2s ease-out',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            pointerEvents: 'auto'
          }}
        />
      )}
      
      <nav className="sticky top-0 z-50 py-4" style={{ 
        background: 'transparent',
        backgroundImage: `radial-gradient(circle, rgba(210, 210, 215, 0.3) 1px, transparent 1px)`,
        backgroundSize: '20px 20px',
        backgroundPosition: '0 0'
      }}>
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Pill-shaped Navigation Bar */}
        <div 
          className="bg-white rounded-full shadow-lg flex items-center justify-between px-4 py-3"
          style={{
            boxShadow: '0 4px 20px rgba(0, 0, 0, 0.08)'
          }}
        >
          {/* Hamburger Menu - Left */}
          <div className="flex items-center">
            <button
              onClick={() => setIsMenuOpen(!isMenuOpen)}
              className="p-2 rounded-full hover:bg-gray-100 transition-all duration-300 focus:outline-none group"
              style={{ transition: 'all 0.3s cubic-bezier(0.16, 1, 0.3, 1)' }}
            >
              {isMenuOpen ? (
                <X 
                  className="h-5 w-5 text-black transition-all duration-300"
                  style={{ 
                    animation: 'rotateIn 0.3s cubic-bezier(0.16, 1, 0.3, 1)',
                    transform: 'rotate(0deg)'
                  }}
                />
              ) : (
                <div 
                  className="flex flex-col gap-1.5 transition-all duration-300 group-hover:gap-2"
                  style={{ transition: 'all 0.3s cubic-bezier(0.16, 1, 0.3, 1)' }}
                >
                  <div 
                    className="w-5 h-0.5 bg-black rounded-full transition-all duration-300"
                    style={{ transform: 'translateY(0)' }}
                  ></div>
                  <div 
                    className="w-5 h-0.5 bg-black rounded-full transition-all duration-300"
                    style={{ transform: 'translateY(0)' }}
                  ></div>
                </div>
              )}
            </button>
          </div>

          {/* Logo - Center */}
          <div className="flex-1 flex justify-center">
            <Link 
              to="/dashboard" 
              className="flex items-center group"
              style={{ transition: 'all 0.3s cubic-bezier(0.2, 0.9, 0.2, 1)' }}
            >
              <div className="relative mr-2">
                <div 
                  className="relative h-8 w-8 bg-gradient-to-br from-[#0A84FF] via-[#5856D6] to-[#AF52DE] rounded-lg flex items-center justify-center transform group-hover:scale-110 transition-all duration-300"
                  style={{ 
                    boxShadow: '0 2px 8px rgba(10, 132, 255, 0.25)'
                  }}
                >
                  <Database className="h-4 w-4 text-white" />
                </div>
              </div>
              <span className="text-lg font-semibold text-black" style={{ letterSpacing: '-0.022em' }}>
                UNPAR Scraper
              </span>
            </Link>
          </div>

          {/* User Button - Right */}
          <div className="flex items-center">
            <div className="flex items-center space-x-2">
              <div className="hidden sm:flex items-center space-x-2 px-3 py-1.5 rounded-full hover:bg-gray-100 transition-all duration-200">
                <div className="h-7 w-7 bg-[#0A84FF] rounded-full flex items-center justify-center" style={{ boxShadow: '0 2px 6px rgba(10, 132, 255, 0.25)' }}>
                  <User className="h-4 w-4 text-white" />
                </div>
                <span className="text-sm font-semibold text-black">{user.username}</span>
              </div>
              <Link
                to="/about"
                className={`flex items-center space-x-2 px-4 py-2 rounded-xl text-sm font-semibold transition-all duration-300 focus:outline-none ${
                  isActive('/about')
                    ? 'bg-gradient-to-r from-[#0A84FF] to-[#5856D6] text-white shadow-lg shadow-[#0A84FF]/30'
                    : 'bg-white text-gray-700 hover:bg-gradient-to-r hover:from-[#0A84FF]/10 hover:to-[#5856D6]/10 hover:text-[#0A84FF] border border-gray-200 hover:border-[#0A84FF]/30 shadow-sm'
                }`}
                style={{ 
                  letterSpacing: '-0.011em',
                  transition: 'all 0.3s cubic-bezier(0.2, 0.9, 0.2, 1)'
                }}
              >
                <Info className={`h-4 w-4 ${isActive('/about') ? 'text-white' : 'text-[#0A84FF]'}`} />
                <span>About</span>
              </Link>
            </div>
          </div>
        </div>

        {/* Dropdown Menu - Appears below navbar when menu is open */}
        {isMenuOpen && (
          <div 
            className="relative mt-4 bg-white rounded-2xl shadow-xl border border-gray-100 overflow-hidden"
            style={{
              boxShadow: '0 8px 32px rgba(0, 0, 0, 0.12)',
              animation: 'menuSlideDown 0.4s cubic-bezier(0.16, 1, 0.3, 1)',
              zIndex: 50
            }}
          >
            <div className="p-4 space-y-1">
              <NavLink 
                to="/dashboard"
                onClick={() => setIsMenuOpen(false)}
                className="flex items-center space-x-3 px-4 py-3 rounded-xl menu-item hover:bg-gray-50 transition-all duration-200 group"
                style={{ animationDelay: '0.05s' }}
              >
                <Home className="h-5 w-5 transition-transform duration-200 group-hover:scale-110" />
                <span>Dashboard</span>
              </NavLink>

              {/* SINTA Dropdown */}
              <div className="menu-item" style={{ animationDelay: '0.1s' }}>
                <button
                  onClick={() => handleDropdownToggle('sinta')}
                  className="w-full flex items-center justify-between px-4 py-3 text-sm font-semibold text-gray-700 rounded-xl hover:bg-gray-50 transition-all duration-200"
                >
                  <div className="flex items-center space-x-3">
                    <img 
                      src={sintaLogo} 
                      alt="SINTA Logo" 
                      className="h-5 w-5 object-contain"
                    />
                    <span>SINTA</span>
                  </div>
                  <ChevronDown 
                    className={`h-4 w-4 transition-all duration-300 ease-out ${
                      isSintaDropdownOpen ? 'rotate-180' : ''
                    }`}
                    style={{ transformOrigin: 'center' }}
                  />
                </button>
                {isSintaDropdownOpen && (
                  <div 
                    className="pl-12 mt-1 space-y-1 overflow-hidden"
                    style={{
                      animation: 'submenuSlideDown 0.3s cubic-bezier(0.16, 1, 0.3, 1)'
                    }}
                  >
                    <DropdownLink 
                      to="/sinta/dosen"
                      onClick={() => {
                        closeDropdowns();
                        setIsMenuOpen(false);
                      }}
                      className="flex items-center space-x-3 px-4 py-2 rounded-lg submenu-item"
                      style={{ animationDelay: '0.05s' }}
                    >
                      <Users className="h-4 w-4 text-[#0A84FF]" />
                      <span>Data Dosen</span>
                    </DropdownLink>
                    <DropdownLink 
                      to="/sinta/publikasi"
                      onClick={() => {
                        closeDropdowns();
                        setIsMenuOpen(false);
                      }}
                      className="flex items-center space-x-3 px-4 py-2 rounded-lg submenu-item"
                      style={{ animationDelay: '0.1s' }}
                    >
                      <FileText className="h-4 w-4 text-[#0A84FF]" />
                      <span>Data Publikasi</span>
                    </DropdownLink>
                  </div>
                )}
              </div>

              {/* Google Scholar Dropdown */}
              <div className="menu-item" style={{ animationDelay: '0.15s' }}>
                <button
                  onClick={() => handleDropdownToggle('scholar')}
                  className="w-full flex items-center justify-between px-4 py-3 text-sm font-semibold text-gray-700 rounded-xl hover:bg-gray-50 transition-all duration-200"
                >
                  <div className="flex items-center space-x-3">
                    <img 
                      src={googleScholarLogo} 
                      alt="Google Scholar Logo" 
                      className="h-5 w-5 object-contain"
                    />
                    <span>Google Scholar</span>
                  </div>
                  <ChevronDown 
                    className={`h-4 w-4 transition-all duration-300 ease-out ${
                      isScholarDropdownOpen ? 'rotate-180' : ''
                    }`}
                    style={{ transformOrigin: 'center' }}
                  />
                </button>
                {isScholarDropdownOpen && (
                  <div 
                    className="pl-12 mt-1 space-y-1 overflow-hidden"
                    style={{
                      animation: 'submenuSlideDown 0.3s cubic-bezier(0.16, 1, 0.3, 1)'
                    }}
                  >
                    <DropdownLink 
                      to="/scholar/dosen"
                      onClick={() => {
                        closeDropdowns();
                        setIsMenuOpen(false);
                      }}
                      className="flex items-center space-x-3 px-4 py-2 rounded-lg submenu-item"
                      style={{ animationDelay: '0.05s' }}
                    >
                      <Users className="h-4 w-4 text-[#0A84FF]" />
                      <span>Data Dosen</span>
                    </DropdownLink>
                    <DropdownLink 
                      to="/scholar/publikasi"
                      onClick={() => {
                        closeDropdowns();
                        setIsMenuOpen(false);
                      }}
                      className="flex items-center space-x-3 px-4 py-2 rounded-lg submenu-item"
                      style={{ animationDelay: '0.1s' }}
                    >
                      <FileText className="h-4 w-4 text-[#0A84FF]" />
                      <span>Data Publikasi</span>
                    </DropdownLink>
                  </div>
                )}
              </div>

              <NavLink 
                to="/scraping"
                onClick={() => setIsMenuOpen(false)}
                className="flex items-center space-x-3 px-4 py-3 rounded-xl menu-item"
                style={{ animationDelay: '0.2s' }}
              >
                <Download className="h-5 w-5" />
                <span>Scraping</span>
              </NavLink>

              <div className="border-t border-gray-100 mt-2 pt-2 menu-item" style={{ animationDelay: '0.25s' }}>
                <div className="px-4 py-3 flex items-center space-x-3">
                  <div className="h-8 w-8 bg-[#0A84FF] rounded-full flex items-center justify-center" style={{ boxShadow: '0 2px 8px rgba(10, 132, 255, 0.25)' }}>
                    <User className="h-4.5 w-4.5 text-white" />
                  </div>
                  <span className="text-sm font-semibold text-gray-900">{user.username}</span>
                </div>
                <button
                  onClick={() => {
                    setIsMenuOpen(false);
                    onLogout();
                  }}
                  className="w-full flex items-center space-x-3 px-4 py-3 text-sm font-semibold text-gray-700 rounded-xl hover:bg-red-50 hover:text-red-600 transition-all duration-200"
                >
                  <LogOut className="h-5 w-5" />
                  <span>Logout</span>
                </button>
                <Link
                  to="/about"
                  onClick={() => setIsMenuOpen(false)}
                  className={`w-full flex items-center space-x-3 px-4 py-3 text-sm font-semibold rounded-xl transition-all duration-200 ${
                    isActive('/about')
                      ? 'bg-[#0A84FF]/10 text-[#0A84FF]'
                      : 'text-gray-700 hover:bg-gray-50'
                  }`}
                >
                  <Info className="h-5 w-5" />
                  <span>About</span>
                </Link>
              </div>
            </div>
          </div>
        )}
      </div>
    </nav>
    </>
  );
};

export default Navbar;
