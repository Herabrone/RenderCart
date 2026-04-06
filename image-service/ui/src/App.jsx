import { useState } from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import Header from './components/Header';
import LeftPanel from './components/LeftPanel';
import RightPanel from './components/RightPanel';
import JobStatus from './components/JobStatus';
import Gallery from './components/Gallery';
import JobHistory from './components/JobHistory';
import './App.css';

function App() {
  const [uploadedImage, setUploadedImage] = useState(null);
  const [jobId, setJobId] = useState(null);
  const [generatedImages, setGeneratedImages] = useState([]);
  const [jobStatus, setJobStatus] = useState(null);

  const handleImageUpload = (imageUrl) => {
    setUploadedImage(imageUrl);
    setJobId(null);
    setGeneratedImages([]);
    setJobStatus(null);
  };

  const handleJobCreated = (newJobId) => {
    setJobId(newJobId);
  };

  const handleImagesGenerated = (images) => {
    setGeneratedImages(images);
  };

  const handleStatusUpdate = (statusUpdate) => {
    setJobStatus(statusUpdate);
  };

  const homePage = (
    <div className="home-layout">
      <LeftPanel
        uploadedImage={uploadedImage}
        onImageUpload={handleImageUpload}
        onJobCreated={handleJobCreated}
        onStatusChange={handleStatusUpdate}
      />

      <div className="right-column">
        <div className="status-card">
          <div className="panel-title">Job status</div>
          {jobId ? (
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
          previewImage={uploadedImage}
          generatedImages={generatedImages}
          jobStatus={jobStatus}
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
