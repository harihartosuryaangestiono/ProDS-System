import PropTypes from 'prop-types';

/**
 * Layout Component - Apple-style Premium Design
 * Provides consistent layout structure with Apple aesthetics
 */
const Layout = ({ 
  children, 
  title, 
  description, 
  showHeader = true,
  bgColor = 'bg-[#F5F5F7]',
  maxWidth = 'max-w-7xl',
  headerActions,
  className = ''
}) => {
  return (
    <div className={`min-h-screen ${bgColor || 'bg-[#F5F5F7]'} ${className} page-enter-apple page-enter-active-apple`}>
      <div className={`${maxWidth} mx-auto px-4 sm:px-6 lg:px-8 py-8`}>
        {showHeader && (title || description || headerActions) && (
          <div className="mb-8 animate-slide-up-apple">
            <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-6">
              <div className="flex-1">
                {title && (
                  <h1 
                    className="text-4xl md:text-5xl font-semibold text-[#1D1D1F] mb-3"
                    style={{ 
                      letterSpacing: '-0.03em',
                      lineHeight: '1.1'
                    }}
                  >
                    {title}
                  </h1>
                )}
                {description && (
                  <p 
                    className="text-base text-[#6E6E73] leading-relaxed"
                    style={{ 
                      letterSpacing: '-0.011em',
                      lineHeight: '1.47059'
                    }}
                  >
                    {description}
                  </p>
                )}
              </div>
              {headerActions && (
                <div className="flex items-center gap-3 flex-shrink-0">
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
