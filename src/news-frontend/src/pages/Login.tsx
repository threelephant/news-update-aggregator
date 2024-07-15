import React from 'react';

interface LoginProps {
  setUser: (user: any) => void;
}

const Login: React.FC<LoginProps> = ({ setUser }) => {
  const handleLogin = () => {
    // Simulate user login and set user
    const user = { name: "User" }; // Replace with actual user data
    setUser(user);
  };

  return (
    <div>
      <h1>Login</h1>
      <button onClick={handleLogin}>Login</button>
    </div>
  );
};

export default Login;
