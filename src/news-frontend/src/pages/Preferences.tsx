import React, { useState } from 'react';

const Preferences: React.FC<{ user: any }> = ({ user }) => {
  const [preferences, setPreferences] = useState<string[]>([]);

  const handleChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const { value, checked } = event.target;
    setPreferences((prev) =>
      checked ? [...prev, value] : prev.filter((pref) => pref !== value)
    );
  };

  const handleSubmit = () => {
    // Here you would send the preferences to your backend
    console.log('Preferences submitted:', preferences);
  };

  return (
    <div>
      <h1>{user ? `${user.name}'s Preferences` : 'Set Your Preferences'}</h1>
      <div>
        <label>
          <input
            type="checkbox"
            value="technology"
            onChange={handleChange}
          />
          Technology
        </label>
        <label>
          <input
            type="checkbox"
            value="health"
            onChange={handleChange}
          />
          Health
        </label>
        <label>
          <input
            type="checkbox"
            value="business"
            onChange={handleChange}
          />
          Business
        </label>
        {/* Add more preferences as needed */}
      </div>
      <button onClick={handleSubmit}>Save Preferences</button>
    </div>
  );
};

export default Preferences;
