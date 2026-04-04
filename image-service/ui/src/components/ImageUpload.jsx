import { useState, useCallback } from 'react';
import axios from 'axios';

const ImageUpload = ({ onUploadSuccess }) => {
  const [isDragging, setIsDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState(null);
  
  const handleDragEnter = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  }, []);

  const handleDragOver = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    e.dataTransfer.dropEffect = 'copy';
  }, []);

  const handleDrop = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
    
    const files = e.dataTransfer.files;
    if (files.length) {
      handleFiles(files);
    }
  }, []);

  const handleFileChange = useCallback((e) => {
    const files = e.target.files;
    if (files.length) {
      handleFiles(files);
    }
  }, []);

  const handleFiles = useCallback(async (files) => {
    const file = files[0];
    
    // Validate file type
    const validTypes = ['image/jpeg', 'image/png', 'image/gif', 'image/webp'];
    if (!validTypes.includes(file.type)) {
      setError('Please upload a valid image file (JPEG, PNG, GIF, or WebP)');
      return;
    }

    // Validate file size (10MB max)
    if (file.size > 10 * 1024 * 1024) {
      setError('File size exceeds 10MB limit');
      return;
    }

    setUploading(true);
    setError(null);
    
    try {
      const apiKey = localStorage.getItem('apiKey');
      if (!apiKey) {
        setError('Please enter your API key in the header');
        return;
      }

      const formData = new FormData();
      formData.append('file', file);
      
      const response = await axios.post('/api/upload', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
          'X-API-Key': apiKey
        }
      });

      onUploadSuccess(response.data.image_url);
    } catch (err) {
      setError(err.response?.data?.detail || 'Upload failed. Please try again.');
    } finally {
      setUploading(false);
    }
  }, [onUploadSuccess]);

  return (
    <div className="image-upload">
      <div
        className={`upload-area ${isDragging ? 'dragging' : ''} ${uploading ? 'uploading' : ''}`}
        onDragEnter={handleDragEnter}
        onDragLeave={handleDragLeave}
        onDragOver={handleDragOver}
        onDrop={handleDrop}
      >
        <input
          type="file"
          id="file-upload"
          accept="image/*"
          onChange={handleFileChange}
          disabled={uploading}
        />
        <label htmlFor="file-upload" className="upload-label">
          <svg className="upload-icon" role="presentation" aria-hidden="true">
            <use href="/icons.svg#upload-icon"></use>
          </svg>
          <span className="upload-text">
            {uploading ? 'Uploading...' : 'Drag & drop image here or click to browse'}
          </span>
        </label>
      </div>
      {error && <div className="error-message">{error}</div>}
    </div>
  );
};

export default ImageUpload;