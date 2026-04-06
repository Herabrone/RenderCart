import { useState, useCallback } from 'react';
import axios from 'axios';

const ImageUpload = ({ onImageUpload }) => {
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

  const handleFiles = useCallback(async (files) => {
    const selectedFiles = Array.from(files);
    if (selectedFiles.length > 20) {
      setError('Please upload no more than 20 images at once.');
      return;
    }

    setUploading(true);
    setError(null);

    try {
      const uploaded = [];
      for (const file of selectedFiles) {
        if (!['image/jpeg', 'image/png', 'image/gif', 'image/webp'].includes(file.type)) {
          throw new Error('Please upload valid image files (JPEG, PNG, GIF, or WebP).');
        }
        if (file.size > 10 * 1024 * 1024) {
          throw new Error('File size exceeds the 10MB limit.');
        }

        const formData = new FormData();
        formData.append('file', file);

        const apiKey = localStorage.getItem('apiKey');
        const response = await axios.post('/api/upload', formData, {
          headers: {
            'Content-Type': 'multipart/form-data',
            ...(apiKey && { 'X-API-Key': apiKey }),
          },
        });

        uploaded.push({ url: response.data.url, name: file.name });
      }
      onImageUpload(uploaded);
    } catch (err) {
      setError(err.message || err.response?.data?.detail || 'Upload failed. Please try again.');
    } finally {
      setUploading(false);
    }
  }, [onImageUpload]);

  const handleDrop = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
    
    const files = e.dataTransfer.files;
    if (files.length) {
      handleFiles(files);
    }
  }, [handleFiles]);

  const handleFileChange = useCallback((e) => {
    const files = e.target.files;
    if (files.length) {
      handleFiles(files);
    }
  }, [handleFiles]);

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
          multiple
          onChange={handleFileChange}
          disabled={uploading}
        />
        <label htmlFor="file-upload" className="upload-label">
          <svg className="upload-icon" role="presentation" aria-hidden="true">
            <use href="/icons.svg#upload-icon"></use>
          </svg>
          <span className="upload-text">
            {uploading ? 'Uploading...' : 'Drag & drop up to 20 images or click to browse'}
          </span>
        </label>
      </div>
      {error && <div className="error-message">{error}</div>}
    </div>
  );
};

export default ImageUpload;