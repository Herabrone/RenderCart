import { useState } from 'react';
import { BrowserRouter as Router, Routes, Route, Link } from 'react-router-dom';
import Header from './components/Header';
import ImageUpload from './components/ImageUpload';
import GenerateForm from './components/GenerateForm';
import JobStatus from './components/JobStatus';
import Gallery from './components/Gallery';
import './App.css';

function App() {
  const [uploadedImage, setUploadedImage] = useState(null);
  const [jobId, setJobId] = useState(null);
  const [generatedImages, setGeneratedImages] = useState([]);

  const handleImageUpload = (imageUrl) => {
    setUploadedImage(imageUrl);
    setJobId(null);
    setGeneratedImages([]);
  };

  const handleJobCreated = (newJobId) => {
    setJobId(newJobId);
  };

  const handleImagesGenerated = (images) => {
    setGeneratedImages(images);
  };

  const homePage = (
    <div className="main-content">
      <div className="main-grid">
        <div className="card">
          <div className="card-title">1. Upload Context</div>
          <ImageUpload onImageUpload={handleImageUpload} />
          {uploadedImage && (
            <div className="preview-container" style={{ marginTop: '20px' }}>
              <img src={uploadedImage} alt="Preview" className="preview-image" />
            </div>
          )}
        </div>

        <div className="card">
          <div className="card-title">2. Generation Settings</div>
          <GenerateForm
            imageUrl={uploadedImage}
            onJobCreated={handleJobCreated}
          />
        </div>
      </div>

      {(jobId || generatedImages.length > 0) && (
        <div className="card" style={{ marginTop: '30px' }}>
          <div className="card-title">3. Results & Status</div>
          {jobId && (
            <div className="job-status-section">
              <JobStatus
                jobId={jobId}
                onImagesGenerated={handleImagesGenerated}
              />
            </div>
          )}

          {generatedImages.length > 0 && (
            <div className="results-section">
              <div className="image-grid">
                {generatedImages.map((image, index) => (
                  <div key={index} className="grid-item">
                    <img
                      src={image}
                      alt={`Generated image ${index + 1}`}
                      className="grid-image"
                      onClick={() => window.open(image, '_blank')}
                    />
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );

  const galleryPage = (
    <div className="gallery-page">
      <Gallery />
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
