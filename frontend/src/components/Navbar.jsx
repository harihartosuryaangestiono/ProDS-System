import { useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { Menu, X, User, LogOut, Home, Users, FileText, Download, ChevronDown } from 'lucide-react';

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
    <nav className="bg-white shadow-lg">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between h-16">
          {/* Logo and Brand */}
          <div className="flex items-center">
            <Link to="/dashboard" className="flex-shrink-0 flex items-center">
              <div className="h-8 w-8 bg-blue-600 rounded-lg flex items-center justify-center">
                <FileText className="h-5 w-5 text-white" />
              </div>
              <span className="ml-3 text-xl font-bold text-gray-900">ProDS System</span>
            </Link>
          </div>

          {/* Desktop Navigation */}
          <div className="hidden md:flex items-center space-x-4">
            <NavLink to="/dashboard">
              <Home className="inline w-4 h-4 mr-2" />
              Dashboard
            </NavLink>

            {/* SINTA Dropdown */}
            <div className="relative">
              <button
                onClick={() => handleDropdownToggle('sinta')}
                className={`px-3 py-2 rounded-md text-sm font-medium transition-colors duration-200 flex items-center ${
                  location.pathname.startsWith('/sinta')
                    ? 'bg-blue-100 text-blue-700'
                    : 'text-gray-700 hover:text-blue-600 hover:bg-gray-50'
                }`}
              >
                SINTA
                <ChevronDown className="ml-1 h-4 w-4" />
              </button>
              
              {isSintaDropdownOpen && (
                <div className="absolute left-0 mt-2 w-48 rounded-md shadow-lg bg-white ring-1 ring-black ring-opacity-5 z-50">
                  <div className="py-1">
                    <DropdownLink to="/sinta/dosen" onClick={closeDropdowns}>
                      <Users className="inline w-4 h-4 mr-2" />
                      Data Dosen
                    </DropdownLink>
                    <DropdownLink to="/sinta/publikasi" onClick={closeDropdowns}>
                      <FileText className="inline w-4 h-4 mr-2" />
                      Data Publikasi
                    </DropdownLink>
                  </div>
                </div>
              )}
            </div>

            {/* Google Scholar Dropdown */}
            <div className="relative">
              <button
                onClick={() => handleDropdownToggle('scholar')}
                className={`px-3 py-2 rounded-md text-sm font-medium transition-colors duration-200 flex items-center ${
                  location.pathname.startsWith('/scholar')
                    ? 'bg-blue-100 text-blue-700'
                    : 'text-gray-700 hover:text-blue-600 hover:bg-gray-50'
                }`}
              >
                Google Scholar
                <ChevronDown className="ml-1 h-4 w-4" />
              </button>
              
              {isScholarDropdownOpen && (
                <div className="absolute left-0 mt-2 w-48 rounded-md shadow-lg bg-white ring-1 ring-black ring-opacity-5 z-50">
                  <div className="py-1">
                    <DropdownLink to="/scholar/dosen" onClick={closeDropdowns}>
                      <Users className="inline w-4 h-4 mr-2" />
                      Data Dosen
                    </DropdownLink>
                    <DropdownLink to="/scholar/publikasi" onClick={closeDropdowns}>
                      <FileText className="inline w-4 h-4 mr-2" />
                      Data Publikasi
                    </DropdownLink>
                  </div>
                </div>
              )}
            </div>

            <NavLink to="/scraping">
              <Download className="inline w-4 h-4 mr-2" />
              Scraping
            </NavLink>

            {/* User Menu */}
            <div className="flex items-center space-x-3 border-l border-gray-200 pl-4">
              <div className="flex items-center space-x-2">
                <div className="h-8 w-8 bg-gray-300 rounded-full flex items-center justify-center">
                  <User className="h-5 w-5 text-gray-600" />
                </div>
                <span className="text-sm font-medium text-gray-700">{user.username}</span>
              </div>
              
              <button
                onClick={onLogout}
                className="text-gray-500 hover:text-red-600 transition-colors duration-200"
                title="Logout"
              >
                <LogOut className="h-5 w-5" />
              </button>
            </div>
          </div>

          {/* Mobile menu button */}
          <div className="md:hidden flex items-center">
            <button
              onClick={() => setIsMenuOpen(!isMenuOpen)}
              className="text-gray-600 hover:text-blue-600 focus:outline-none focus:text-blue-600"
            >
              {isMenuOpen ? (
                <X className="h-6 w-6" />
              ) : (
                <Menu className="h-6 w-6" />
              )}
            </button>
          </div>
        </div>

        {/* Mobile Navigation */}
        {isMenuOpen && (
          <div className="md:hidden">
            <div className="px-2 pt-2 pb-3 space-y-1 sm:px-3 border-t border-gray-200">
              <NavLink 
                to="/dashboard" 
                className="block"
                onClick={() => setIsMenuOpen(false)}
              >
                <Home className="inline w-4 h-4 mr-2" />
                Dashboard
              </NavLink>

              {/* SINTA Mobile Menu */}
              <div className="space-y-1">
                <div className="text-sm font-medium text-gray-600 px-3 py-2">SINTA</div>
                <NavLink 
                  to="/sinta/dosen" 
                  className="block pl-6"
                  onClick={() => setIsMenuOpen(false)}
                >
                  <Users className="inline w-4 h-4 mr-2" />
                  Data Dosen
                </NavLink>
                <NavLink 
                  to="/sinta/publikasi" 
                  className="block pl-6"
                  onClick={() => setIsMenuOpen(false)}
                >
                  <FileText className="inline w-4 h-4 mr-2" />
                  Data Publikasi
                </NavLink>
              </div>

              {/* Google Scholar Mobile Menu */}
              <div className="space-y-1">
                <div className="text-sm font-medium text-gray-600 px-3 py-2">Google Scholar</div>
                <NavLink 
                  to="/scholar/dosen" 
                  className="block pl-6"
                  onClick={() => setIsMenuOpen(false)}
                >
                  <Users className="inline w-4 h-4 mr-2" />
                  Data Dosen
                </NavLink>
                <NavLink 
                  to="/scholar/publikasi" 
                  className="block pl-6"
                  onClick={() => setIsMenuOpen(false)}
                >
                  <FileText className="inline w-4 h-4 mr-2" />
                  Data Publikasi
                </NavLink>
              </div>

              <NavLink 
                to="/scraping" 
                className="block"
                onClick={() => setIsMenuOpen(false)}
              >
                <Download className="inline w-4 h-4 mr-2" />
                Scraping
              </NavLink>

              <div className="border-t border-gray-200 pt-4 mt-4">
                <div className="flex items-center px-3">
                  <div className="h-8 w-8 bg-gray-300 rounded-full flex items-center justify-center">
                    <User className="h-5 w-5 text-gray-600" />
                  </div>
                  <span className="ml-3 text-base font-medium text-gray-700">{user.username}</span>
                </div>
                <button
                  onClick={() => {
                    onLogout();
                    setIsMenuOpen(false);
                  }}
                  className="block w-full text-left px-3 py-2 mt-2 text-base font-medium text-gray-700 hover:text-red-600 hover:bg-gray-50 rounded-md"
                >
                  <LogOut className="inline w-4 h-4 mr-2" />
                  Logout
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </nav>
  );
};

export default Navbar;