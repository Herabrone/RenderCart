import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';

const Header = () => {
  const [apiKey, setApiKey] = useState('');
  
  useEffect(() => {
    // Load API key from localStorage
    const savedKey = localStorage.getItem('apiKey');
    if (savedKey) {
      setApiKey(savedKey);
    }
  }, []);

  const handleApiKeyChange = (e) => {
    const key = e.target.value;
    setApiKey(key);
    localStorage.setItem('apiKey', key);
  };

  return (
    <header className="header">
      <div className="header-content">
        <Link to="/" className="logo">
          <svg className="logo-icon" role="presentation" aria-hidden="true">
            <use href="/icons.svg#logo-icon"></use>
          </svg>
          <span className="logo-text">RenderCart</span>
        </Link>
        <div className="api-key-input">
          <label htmlFor="apiKey">API Key</label>
          <input
            id="apiKey"
            type="text"
            value={apiKey}
            onChange={handleApiKeyChange}
            placeholder="Enter your API key"
          />
        </div>
      </div>
    </header>
  );
};

export default Header;