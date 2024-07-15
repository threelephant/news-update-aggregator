import React from 'react';

interface NewsProps {
  user: any;
}

const News: React.FC<NewsProps> = () => {
  return (
    <div>
      <h1>News</h1>
      <h2>Welcome, !</h2>
      {/* Display news here */}
    </div>
  );
};

export default News;
