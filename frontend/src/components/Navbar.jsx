import { useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { Menu, X, User, LogOut, Home, Users, FileText, Download, ChevronDown, Info } from 'lucide-react';

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
      className={`px-3 py-2 rounded-md text-sm font-medium transition-colors duration-200 ${
        isActive(to)
          ? 'bg-blue-100 text-blue-700'
          : 'text-gray-700 hover:text-blue-600 hover:bg-gray-50'
      } ${className}`}
    >
      {children}
    </Link>
  );

  const DropdownLink = ({ to, children, onClick }) => (
    <Link
      to={to}
      onClick={onClick}
      className={`block px-4 py-2 text-sm transition-colors duration-200 ${
        isActive(to)
          ? 'bg-blue-100 text-blue-700'
          : 'text-gray-700 hover:bg-gray-50 hover:text-blue-600'
      }`}
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
    <nav className="bg-white/95 backdrop-blur-sm shadow-lg sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between h-16">
          {/* Logo and Brand dengan animasi */}
          <div className="flex items-center">
            <Link to="/dashboard" className="flex-shrink-0 flex items-center group">
              <div className="h-10 w-10 bg-gradient-to-br from-blue-500 to-indigo-600 rounded-xl flex items-center justify-center transform group-hover:scale-110 transition-all duration-300 shadow-lg">
                <FileText className="h-6 w-6 text-white" />
              </div>
              <span className="ml-3 text-xl font-bold bg-gradient-to-r from-blue-600 to-indigo-600 bg-clip-text text-transparent">
                ProDS System
              </span>
            </Link>
          </div>

          {/* Desktop Navigation dengan animasi */}
          <div className="hidden md:flex items-center space-x-6">
            <NavLink 
              to="/dashboard"
              className="px-4 py-2 rounded-lg text-sm font-medium transition-all duration-300 hover:bg-blue-50 hover:text-blue-600 flex items-center space-x-2 group"
            >
              <Home className="h-5 w-5 group-hover:scale-110 transition-transform duration-200" />
              <span>Dashboard</span>
            </NavLink>

            {/* SINTA Dropdown dengan animasi */}
            <div className="relative group">
              <button
                onClick={() => handleDropdownToggle('sinta')}
                className="px-4 py-2 rounded-lg text-sm font-medium transition-all duration-300 hover:bg-blue-50 hover:text-blue-600 flex items-center space-x-2"
              >
                <span>SINTA</span>
                <ChevronDown className={`h-4 w-4 transition-transform duration-200 ${
                  isSintaDropdownOpen ? 'rotate-180' : ''
                }`} />
              </button>
              
              {isSintaDropdownOpen && (
                <div className="absolute left-0 mt-2 w-56 rounded-xl shadow-xl bg-white/95 backdrop-blur-sm ring-1 ring-black ring-opacity-5 z-50 transform transition-all duration-200 origin-top-right">
                  <div className="py-2 px-2">
                    <DropdownLink 
                      to="/sinta/dosen" 
                      className="flex items-center space-x-3 px-4 py-3 rounded-lg hover:bg-blue-50 transition-colors duration-200"
                      onClick={closeDropdowns}
                    >
                      <Users className="h-5 w-5 text-blue-500" />
                      <span>Data Dosen</span>
                    </DropdownLink>
                    <DropdownLink 
                      to="/sinta/publikasi"
                      className="flex items-center space-x-3 px-4 py-3 rounded-lg hover:bg-blue-50 transition-colors duration-200"
                      onClick={closeDropdowns}
                    >
                      <FileText className="h-5 w-5 text-blue-500" />
                      <span>Data Publikasi</span>
                    </DropdownLink>
                  </div>
                </div>
              )}
            </div>

            {/* Google Scholar Dropdown dengan animasi */}
            <div className="relative group">
              <button
                onClick={() => handleDropdownToggle('scholar')}
                className="px-4 py-2 rounded-lg text-sm font-medium transition-all duration-300 hover:bg-blue-50 hover:text-blue-600 flex items-center space-x-2"
              >
                <span>Google Scholar</span>
                <ChevronDown className={`h-4 w-4 transition-transform duration-200 ${
                  isScholarDropdownOpen ? 'rotate-180' : ''
                }`} />
              </button>
              
              {isScholarDropdownOpen && (
                <div className="absolute left-0 mt-2 w-56 rounded-xl shadow-xl bg-white/95 backdrop-blur-sm ring-1 ring-black ring-opacity-5 z-50 transform transition-all duration-200 origin-top-right">
                  <div className="py-2 px-2">
                    <DropdownLink 
                      to="/scholar/dosen" 
                      className="flex items-center space-x-3 px-4 py-3 rounded-lg hover:bg-blue-50 transition-colors duration-200"
                      onClick={closeDropdowns}
                    >
                      <Users className="h-5 w-5 text-blue-500" />
                      <span>Data Dosen</span>
                    </DropdownLink>
                    <DropdownLink 
                      to="/scholar/publikasi"
                      className="flex items-center space-x-3 px-4 py-3 rounded-lg hover:bg-blue-50 transition-colors duration-200"
                      onClick={closeDropdowns}
                    >
                      <FileText className="h-5 w-5 text-blue-500" />
                      <span>Data Publikasi</span>
                    </DropdownLink>
                  </div>
                </div>
              )}
            </div>

            {/* Scraping dengan animasi */}
            <NavLink 
              to="/scraping"
              className="px-4 py-2 rounded-lg text-sm font-medium transition-all duration-300 hover:bg-blue-50 hover:text-blue-600 flex items-center space-x-2 group"
            >
              <Download className="h-5 w-5 group-hover:scale-110 transition-transform duration-200" />
              <span>Scraping</span>
            </NavLink>

            {/* User Menu dengan animasi */}
            <div className="flex items-center space-x-4 border-l border-gray-200 pl-6">
              <div className="flex items-center space-x-3 group">
                <div className="h-10 w-10 bg-gradient-to-br from-blue-500 to-indigo-600 rounded-full flex items-center justify-center transform group-hover:scale-105 transition-all duration-300 shadow-md">
                  <User className="h-6 w-6 text-white" />
                </div>
                <span className="text-sm font-medium text-gray-700">{user.username}</span>
              </div>
              
              <button
                onClick={onLogout}
                className="p-2 rounded-full hover:bg-red-50 text-gray-500 hover:text-red-600 transition-all duration-300"
                title="Logout"
              >
                <LogOut className="h-5 w-5" />
              </button>
              
              {/* About dengan animasi - icon + text */}
              <Link
                to="/about"
                className={`flex items-center space-x-2 px-3 py-2 rounded-lg transition-all duration-300 ${
                  isActive('/about')
                    ? 'bg-blue-50 text-blue-600'
                    : 'text-gray-700 hover:bg-blue-50 hover:text-blue-600'
                }`}
              >
                <Info className="h-5 w-5" />
                <span className="text-sm font-medium">About</span>
              </Link>
            </div>
          </div>

          {/* Mobile menu button dengan animasi */}
          <div className="md:hidden flex items-center">
            <button
              onClick={() => setIsMenuOpen(!isMenuOpen)}
              className="p-2 rounded-lg text-gray-600 hover:bg-blue-50 hover:text-blue-600 transition-all duration-300 focus:outline-none"
            >
              {isMenuOpen ? (
                <X className="h-6 w-6" />
              ) : (
                <Menu className="h-6 w-6" />
              )}
            </button>
          </div>
        </div>

        {/* Mobile Navigation dengan animasi */}
        {isMenuOpen && (
          <div className="md:hidden border-t border-gray-200">
            <div className="px-2 pt-2 pb-3 space-y-1">
              <NavLink 
                to="/dashboard"
                onClick={() => setIsMenuOpen(false)}
                className="flex items-center space-x-3 px-4 py-3 rounded-lg"
              >
                <Home className="h-5 w-5" />
                <span>Dashboard</span>
              </NavLink>

              <div className="px-4 py-2">
                <button
                  onClick={() => handleDropdownToggle('sinta')}
                  className="flex items-center justify-between w-full px-2 py-2 text-sm font-medium text-gray-700 rounded-lg hover:bg-blue-50"
                >
                  <span>SINTA</span>
                  <ChevronDown className={`h-4 w-4 transition-transform duration-200 ${
                    isSintaDropdownOpen ? 'rotate-180' : ''
                  }`} />
                </button>
                {isSintaDropdownOpen && (
                  <div className="pl-4 mt-1 space-y-1">
                    <DropdownLink 
                      to="/sinta/dosen"
                      onClick={() => {
                        closeDropdowns();
                        setIsMenuOpen(false);
                      }}
                      className="flex items-center space-x-3 px-4 py-2 rounded-lg"
                    >
                      <Users className="h-5 w-5 text-blue-500" />
                      <span>Data Dosen</span>
                    </DropdownLink>
                    <DropdownLink 
                      to="/sinta/publikasi"
                      onClick={() => {
                        closeDropdowns();
                        setIsMenuOpen(false);
                      }}
                      className="flex items-center space-x-3 px-4 py-2 rounded-lg"
                    >
                      <FileText className="h-5 w-5 text-blue-500" />
                      <span>Data Publikasi</span>
                    </DropdownLink>
                  </div>
                )}
              </div>

              <div className="px-4 py-2">
                <button
                  onClick={() => handleDropdownToggle('scholar')}
                  className="flex items-center justify-between w-full px-2 py-2 text-sm font-medium text-gray-700 rounded-lg hover:bg-blue-50"
                >
                  <span>Google Scholar</span>
                  <ChevronDown className={`h-4 w-4 transition-transform duration-200 ${
                    isScholarDropdownOpen ? 'rotate-180' : ''
                  }`} />
                </button>
                {isScholarDropdownOpen && (
                  <div className="pl-4 mt-1 space-y-1">
                    <DropdownLink 
                      to="/scholar/dosen"
                      onClick={() => {
                        closeDropdowns();
                        setIsMenuOpen(false);
                      }}
                      className="flex items-center space-x-3 px-4 py-2 rounded-lg"
                    >
                      <Users className="h-5 w-5 text-blue-500" />
                      <span>Data Dosen</span>
                    </DropdownLink>
                    <DropdownLink 
                      to="/scholar/publikasi"
                      onClick={() => {
                        closeDropdowns();
                        setIsMenuOpen(false);
                      }}
                      className="flex items-center space-x-3 px-4 py-2 rounded-lg"
                    >
                      <FileText className="h-5 w-5 text-blue-500" />
                      <span>Data Publikasi</span>
                    </DropdownLink>
                  </div>
                )}
              </div>

              <NavLink 
                to="/scraping"
                onClick={() => setIsMenuOpen(false)}
                className="flex items-center space-x-3 px-4 py-3 rounded-lg"
              >
                <Download className="h-5 w-5" />
                <span>Scraping</span>
              </NavLink>

              <div className="border-t border-gray-200 mt-2 pt-2">
                <div className="px-4 py-2 flex items-center space-x-3">
                  <div className="h-8 w-8 bg-gradient-to-br from-blue-500 to-indigo-600 rounded-full flex items-center justify-center">
                    <User className="h-5 w-5 text-white" />
                  </div>
                  <span className="text-sm font-medium text-gray-700">{user.username}</span>
                </div>
                <button
                  onClick={() => {
                    setIsMenuOpen(false);
                    onLogout();
                  }}
                  className="w-full flex items-center space-x-3 px-4 py-2 text-sm font-medium text-gray-700 rounded-lg hover:bg-red-50 hover:text-red-600"
                >
                  <LogOut className="h-5 w-5" />
                  <span>Logout</span>
                </button>
                <Link
                  to="/about"
                  onClick={() => setIsMenuOpen(false)}
                  className={`w-full flex items-center space-x-3 px-4 py-2 text-sm font-medium rounded-lg transition-colors duration-200 ${
                    isActive('/about')
                      ? 'bg-blue-50 text-blue-600'
                      : 'text-gray-700 hover:bg-blue-50 hover:text-blue-600'
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
  );
};

export default Navbar;