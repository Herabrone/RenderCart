import { useState } from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';

import AuthPage from './components/AuthPage';
import Header from './components/Header';
import LeftPanel from './components/LeftPanel';
import RightPanel from './components/RightPanel';
import JobStatus from './components/JobStatus';
import BatchStatus from './components/BatchStatus';
import Gallery from './components/Gallery';
import JobHistory from './components/JobHistory';
import JobView from './components/JobView';
import {
  clearStoredApiKey,
  clearStoredToken,
  getStoredApiKey,
  getStoredToken,
  getStoredUser,
  loginUser,
  registerUser,
  setStoredApiKey,
  setStoredToken,
  setStoredUser,
} from './lib/apiClient';
import './App.css';

function App() {
  const [uploadedImages, setUploadedImages] = useState([]);
  const [jobId, setJobId] = useState(null);
  const [batchId, setBatchId] = useState(null);
  const [generatedImages, setGeneratedImages] = useState([]);
  const [batchStatus, setBatchStatus] = useState(null);
  const [apiKeyDraft, setApiKeyDraft] = useState(getStoredApiKey());
  const [hasApiKey, setHasApiKey] = useState(Boolean(getStoredApiKey()));
  const [stores, setStores] = useState([]);

  const [user, setUser] = useState(getStoredUser());
  const isLoggedIn = Boolean(getStoredToken()) || Boolean(getStoredApiKey());

  const handleAuth = async ({ isLogin, email, password, displayName }) => {
    const res = isLogin
      ? await loginUser(email, password)
      : await registerUser(email, password, displayName);
    setStoredToken(res.data.token);
    setStoredUser(res.data.user);
    setUser(res.data.user);
  };

  const handleLogout = () => {
    clearStoredToken();
    clearStoredApiKey();
    setUser(null);
    setApiKeyDraft('');
    setHasApiKey(false);
  };

  const handleImageUpload = (images) => {
    setUploadedImages(images);
    setJobId(null);
    setBatchId(null);
    setGeneratedImages([]);
    setBatchStatus(null);
  };

  const handleJobCreated = (newJobId) => {
    setJobId(newJobId);
    setBatchId(null);
    setBatchStatus(null);
  };

  const handleBatchCreated = (newBatchId) => {
    setBatchId(newBatchId);
    setJobId(null);
    setGeneratedImages([]);
  };

  const handleStatusUpdate = (statusUpdate) => {
    if (statusUpdate?.batchId || statusUpdate?.batch_id) {
      setBatchStatus(statusUpdate);
    }
    const images = statusUpdate?.result_urls || statusUpdate?.output_urls;
    if (Array.isArray(images) && images.length > 0) {
      setGeneratedImages(images);
    }
  };

  const handleApiKeySave = () => {
    setStoredApiKey(apiKeyDraft);
    setHasApiKey(Boolean(apiKeyDraft.trim()));
  };

  const handleApiKeyClear = () => {
    clearStoredApiKey();
    setApiKeyDraft('');
    setHasApiKey(false);
  };

  const homePage = (
    <div className="home-layout">
      <LeftPanel
        uploadedImages={uploadedImages}
        onImageUpload={handleImageUpload}
        onJobCreated={handleJobCreated}
        onBatchCreated={handleBatchCreated}
        onStatusChange={handleStatusUpdate}
        onStoresUpdated={setStores}
      />

      <div className="right-column">
        <div className="status-card">
          <div className="panel-title">Job status</div>
          {batchId ? (
            <BatchStatus
              batchId={batchId}
              onStatusChange={(status) => handleStatusUpdate({ ...status, batchId })}
            />
          ) : jobId ? (
            <JobStatus
              jobId={jobId}
              onImagesGenerated={setGeneratedImages}
              onStatusChange={handleStatusUpdate}
            />
          ) : (
            <div className="status-placeholder">Start a generation to view progress and results.</div>
          )}
        </div>

        <RightPanel
          previewImage={uploadedImages.length === 1 ? uploadedImages[0].url : null}
          generatedImages={generatedImages}
          batchStatus={batchStatus}
          uploadedImages={uploadedImages}
          stores={stores}
        />
      </div>
    </div>
  );

  if (!isLoggedIn) {
    return <AuthPage onAuth={handleAuth} />;
  }

  return (
    <Router>
      <div className="app">
        <Header
          user={user}
          onLogout={handleLogout}
          apiKeyDraft={apiKeyDraft}
          onApiKeyDraftChange={setApiKeyDraft}
          onApiKeySave={handleApiKeySave}
          onApiKeyClear={handleApiKeyClear}
          hasApiKey={hasApiKey}
        />

        <main className="content">
          <Routes>
            <Route path="/" element={homePage} />
            <Route path="/gallery" element={<div className="gallery-page"><Gallery /></div>} />
          <Route path="/jobs" element={<div className="history-page"><JobHistory /></div>} />
          <Route path="/jobs/:jobId" element={<div className="job-view-page"><JobView /></div>} />
          <Route path="/history" element={<div className="history-page"><JobHistory /></div>} />
          </Routes>
        </main>

        <footer className="footer">
          <p>&copy; {new Date().getFullYear()} RenderCart. Powered by local GPU acceleration.</p>
        </footer>
      </div>
    </Router>
  );
}

export default App;
