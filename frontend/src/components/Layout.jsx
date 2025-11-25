import PropTypes from 'prop-types';

/**
 * Layout Component - Konsisten untuk semua halaman
 * Menyediakan struktur layout yang seragam dengan spacing dan styling yang konsisten
 */
const Layout = ({ 
  children, 
  title, 
  description, 
  showHeader = true,
  bgColor = 'bg-gray-50',
  maxWidth = 'max-w-7xl',
  headerActions,
  className = ''
}) => {
  return (
    <div className={`min-h-screen ${bgColor} ${className}`}>
      <div className={`${maxWidth} mx-auto px-4 sm:px-6 lg:px-8 py-8`}>
        {showHeader && (title || description || headerActions) && (
          <div className="mb-8">
            <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
              <div className="flex-1">
                {title && (
                  <h1 className="text-3xl font-bold text-gray-900 mb-2">
                    {title}
                  </h1>
                )}
                {description && (
                  <p className="text-sm text-gray-600">
                    {description}
                  </p>
                )}
              </div>
              {headerActions && (
                <div className="flex items-center gap-2 flex-shrink-0">
                  {headerActions}
                </div>
              )}
            </div>
          </div>
        )}
        <div className="w-full">
          {children}
        </div>
      </div>
    </div>
  );
};

Layout.propTypes = {
  children: PropTypes.node.isRequired,
  title: PropTypes.string,
  description: PropTypes.string,
  showHeader: PropTypes.bool,
  bgColor: PropTypes.string,
  maxWidth: PropTypes.string,
  headerActions: PropTypes.node,
  className: PropTypes.string
};

export default Layout;

