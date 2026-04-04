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
      <h1>Image Generation</h1>

      <div className="upload-section">
        <h2>Upload Image</h2>
        <ImageUpload onImageUpload={handleImageUpload} />
      </div>

      {uploadedImage && (
        <div className="form-section">
          <h2>Generate Variations</h2>
          <GenerateForm
            imageUrl={uploadedImage}
            onJobCreated={handleJobCreated}
            onImagesGenerated={handleImagesGenerated}
          />
        </div>
      )}

      {jobId && (
        <div className="job-status-section">
          <h2>Generation Status</h2>
          <JobStatus
            jobId={jobId}
            onImagesGenerated={handleImagesGenerated}
          />
        </div>
      )}

      {generatedImages.length > 0 && (
        <div className="results-section">
          <h2>Generated Images</h2>
          <div className="image-grid">
            {generatedImages.map((image, index) => (
              <img
                key={index}
                src={image}
                alt={`Generated image ${index + 1}`}
                className="generated-image"
              />
            ))}
          </div>
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

        <div className="content">
          <Routes>
            <Route path="/" element={homePage} />
            <Route path="/gallery" element={galleryPage} />
          </Routes>
        </div>

        <nav className="navbar">
          <Link to="/" className="nav-link">Home</Link>
          <Link to="/gallery" className="nav-link">Gallery</Link>
        </nav>
      </div>
    </Router>
  );
}

export default App;
