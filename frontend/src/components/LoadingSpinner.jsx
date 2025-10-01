const LoadingSpinner = ({ 
  size = 'medium', 
  color = 'blue', 
  className = '',
  fullScreen = false,
  text = 'Loading...'
}) => {
  const sizeClasses = {
    small: 'h-4 w-4',
    medium: 'h-8 w-8',
    large: 'h-12 w-12',
    xlarge: 'h-16 w-16'
  };

  const colorClasses = {
    blue: 'border-blue-600',
    green: 'border-green-600',
    red: 'border-red-600',
    yellow: 'border-yellow-600',
    purple: 'border-purple-600',
    gray: 'border-gray-600'
  };

  const Spinner = () => (
    <div className="flex flex-col items-center justify-center">
      <div 
        className={`
          animate-spin rounded-full border-2 border-t-transparent
          ${sizeClasses[size]} 
          ${colorClasses[color]}
          ${className}
        `}
      />
      {text && (
        <p className={`mt-2 text-sm text-gray-600 ${size === 'small' ? 'text-xs' : ''}`}>
          {text}
        </p>
      )}
    </div>
  );

  if (fullScreen) {
    return (
      <div className="fixed inset-0 bg-white bg-opacity-80 flex items-center justify-center z-50">
        <Spinner />
      </div>
    );
  }

  return <Spinner />;
};

export default LoadingSpinner;