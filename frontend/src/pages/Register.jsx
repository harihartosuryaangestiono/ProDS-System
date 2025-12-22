import { Navigate } from 'react-router-dom';

// Register page now redirects to login with signup tab
// The Login component handles both sign in and sign up
const Register = () => {
  return <Navigate to="/login?signup" replace />;
};

export default Register;