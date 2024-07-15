import React, { useState } from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import Login from './pages/Login';
import News from './pages/News';
import Preferences from './pages/Preferences';

function App() {
  const [user, setUser] = useState<any>(null);

  return (
    <Router>
      <Routes>
        <Route path="/register" element={<Login setUser={setUser} />} />
        <Route path="/news" element={<News user={user} />} />
        <Route path="/preferences" element={<Preferences user={user} />} />
      </Routes>
    </Router>
  );
}

export default App;
