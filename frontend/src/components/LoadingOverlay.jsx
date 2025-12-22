import React from 'react';

const LoadingOverlay = ({ 
  isLoading = false, 
  message = 'Memuat data...',
  subMessage = 'Mohon tunggu sebentar'
}) => {
  if (!isLoading) return null;

  return (
    <div 
      className="fixed inset-0 z-[9999] flex items-center justify-center"
      style={{ animation: 'fadeIn 0.3s ease-out' }}
    >
      {/* Backdrop with blur and dark overlay */}
      <div 
        className="absolute inset-0 bg-black/50 backdrop-blur-md"
        style={{ animation: 'fadeIn 0.3s ease-out' }}
      ></div>
      
      {/* Loading Popup */}
      <div 
        className="relative bg-white rounded-2xl shadow-2xl p-8 flex flex-col items-center justify-center min-w-[300px] min-h-[220px] border-2 border-blue-200 overflow-hidden"
        style={{ 
          animation: 'slideUpFadeIn 0.4s ease-out',
          zIndex: 10000
        }}
      >
        {/* Animated Spinner Container */}
        <div className="relative mb-6 w-20 h-20">
          {/* Main Spinner */}
          <div 
            className="absolute inset-0 rounded-full border-4 border-blue-200 border-t-blue-600"
            style={{ 
              animation: 'spin 1s linear infinite',
              boxShadow: '0 0 20px rgba(59, 130, 246, 0.5)'
            }}
          ></div>
          {/* Pulse Ring */}
          <div 
            className="absolute inset-0 rounded-full border-4 border-blue-400/30"
            style={{ 
              animation: 'pulse 2s ease-in-out infinite'
            }}
          ></div>
          {/* Glowing Effect */}
          <div 
            className="absolute inset-0 rounded-full bg-blue-500/20 blur-xl"
            style={{ 
              animation: 'pulse 2s ease-in-out infinite'
            }}
          ></div>
        </div>
        
        {/* Animated Text */}
        <p 
          className="text-lg font-semibold text-gray-700 text-center mb-1"
          style={{ 
            animation: 'textPulse 2s ease-in-out infinite'
          }}
        >
          {message}
        </p>
        <p 
          className="text-sm text-gray-500 text-center"
          style={{ 
            animation: 'textPulse 2s ease-in-out 0.5s infinite'
          }}
        >
          {subMessage}
        </p>
        
        {/* Loading Dots Animation */}
        <div className="flex items-center gap-2 mt-6">
          <div 
            className="w-3 h-3 bg-blue-600 rounded-full"
            style={{ 
              animation: 'pulse 1.4s ease-in-out infinite'
            }}
          ></div>
          <div 
            className="w-3 h-3 bg-blue-600 rounded-full"
            style={{ 
              animation: 'pulse 1.4s ease-in-out 0.2s infinite'
            }}
          ></div>
          <div 
            className="w-3 h-3 bg-blue-600 rounded-full"
            style={{ 
              animation: 'pulse 1.4s ease-in-out 0.4s infinite'
            }}
          ></div>
        </div>
      </div>
    </div>
  );
};

export default LoadingOverlay;


