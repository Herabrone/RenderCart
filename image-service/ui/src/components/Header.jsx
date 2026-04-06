import { Link } from 'react-router-dom';

const Header = ({ apiKeyDraft, onApiKeyDraftChange, onApiKeySave, onApiKeyClear, hasApiKey }) => {
  const handleSubmit = (event) => {
    event.preventDefault();
    onApiKeySave();
  };

  return (
    <header className="header">
      <div className="header-content">
        <div className="header-brand">
          <Link to="/" className="logo">
            <span className="logo-text">RenderCart</span>
          </Link>
          <nav className="header-nav">
            <Link to="/" className="nav-link">Home</Link>
            <Link to="/gallery" className="nav-link">Gallery</Link>
            <Link to="/history" className="nav-link">History</Link>
          </nav>
        </div>

        <form className="auth-form" onSubmit={handleSubmit}>
          <label className="auth-label" htmlFor="api-key-input">API key</label>
          <input
            id="api-key-input"
            className="auth-input"
            type="password"
            placeholder="Enter API key"
            value={apiKeyDraft}
            onChange={(event) => onApiKeyDraftChange(event.target.value)}
            autoComplete="off"
          />
          <button type="submit" className="primary-button auth-button">Save</button>
          <button type="button" className="secondary-button auth-button" onClick={onApiKeyClear}>
            Clear
          </button>
          <div className={`auth-status ${hasApiKey ? 'auth-status--ready' : ''}`}>
            {hasApiKey ? 'Stored' : 'Required'}
          </div>
        </form>
      </div>
    </header>
  );
};

export default Header;
