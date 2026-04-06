import { useState } from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import Header from './components/Header';
import LeftPanel from './components/LeftPanel';
import RightPanel from './components/RightPanel';
import JobStatus from './components/JobStatus';
import BatchStatus from './components/BatchStatus';
import Gallery from './components/Gallery';
import JobHistory from './components/JobHistory';
import './App.css';

function App() {
  const [uploadedImages, setUploadedImages] = useState([]);
  const [jobId, setJobId] = useState(null);
  const [batchId, setBatchId] = useState(null);
  const [generatedImages, setGeneratedImages] = useState([]);
  const [jobStatus, setJobStatus] = useState(null);
  const [batchStatus, setBatchStatus] = useState(null);

  const handleImageUpload = (images) => {
    setUploadedImages(images);
    setJobId(null);
    setBatchId(null);
    setGeneratedImages([]);
    setJobStatus(null);
    setBatchStatus(null);
  };

  const handleJobCreated = (newJobId) => {
    setJobId(newJobId);
    setBatchId(null);
  };

  const handleBatchCreated = (newBatchId) => {
    setBatchId(newBatchId);
    setJobId(null);
  };

  const handleImagesGenerated = (images) => {
    setGeneratedImages(images);
  };

  const handleStatusUpdate = (statusUpdate) => {
    if (statusUpdate?.batchId || statusUpdate?.batch_id) {
      setBatchStatus(statusUpdate);
    } else {
      setJobStatus(statusUpdate);
    }
  };

  const homePage = (
    <div className="home-layout">
      <LeftPanel
        uploadedImages={uploadedImages}
        onImageUpload={handleImageUpload}
        onJobCreated={handleJobCreated}
        onBatchCreated={handleBatchCreated}
        onStatusChange={handleStatusUpdate}
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
                onImagesGenerated={handleImagesGenerated}
                onStatusChange={handleStatusUpdate}
              />
            ) : (
            <div className="status-placeholder">Start a generation to view progress and results.</div>
          )}
        </div>

        <RightPanel
          previewImage={uploadedImages.length === 1 ? uploadedImages[0].url : null}
          generatedImages={generatedImages}
          jobStatus={jobStatus}
          batchStatus={batchStatus}
          uploadedImages={uploadedImages}
        />
      </div>
    </div>
  );

  const galleryPage = (
    <div className="gallery-page">
      <Gallery />
    </div>
  );

  const historyPage = (
    <div className="history-page">
      <JobHistory />
    </div>
  );

  return (
    <Router>
      <div className="app">
        <Header />

        <main className="content">
          <Routes>
            <Route path="/" element={homePage} />
            <Route path="/gallery" element={galleryPage} />
            <Route path="/history" element={historyPage} />
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
