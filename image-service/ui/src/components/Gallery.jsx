import { useState, useEffect } from 'react';
import axios from 'axios';

const Gallery = () => {
  const [images, setImages] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  
  useEffect(() => {
    const fetchImages = async () => {
      try {
        const apiKey = localStorage.getItem('apiKey');
        if (!apiKey) {
          setError('Please enter your API key in the header');
          setLoading(false);
          return;
        }

        const response = await axios.get('/api/gallery', {
          headers: {
            'X-API-Key': apiKey
          }
        });

        setImages(response.data.images || []);
      } catch (err) {
        setError(err.response?.data?.detail || 'Failed to fetch gallery');
      } finally {
        setLoading(false);
      }
    };

    fetchImages();
  }, []);

  const handleDelete = async (imageUrl) => {
    try {
      const apiKey = localStorage.getItem('apiKey');
      if (!apiKey) {
        setError('Please enter your API key in the header');
        return;
      }

      await axios.delete(`/api/image/${encodeURIComponent(imageUrl)}`, {
        headers: {
          'X-API-Key': apiKey
        }
      });

      setImages(images.filter(img => img !== imageUrl));
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to delete image');
    }
  };

  return (
    <div className="gallery-container">
      <div className="card">
        <div className="card-title">📦 Generation Gallery</div>
        
        {loading && (
          <div style={{ textAlign: 'center', padding: '40px' }}>
            <div className="spinner"></div>
            <p style={{ marginTop: '16px', color: 'var(--text-dim)' }}>Loading gallery...</p>
          </div>
        )}
        
        {!loading && images.length === 0 && (
          <div className="empty-state">
            <div style={{ fontSize: '48px', marginBottom: '16px' }}>🖼️</div>
            <p>Your generation history will appear here.</p>
          </div>
        )}
        
        {!loading && images.length > 0 && (
          <div className="image-grid">
            {images.map((image, index) => (
              <div key={index} className="grid-item" style={{ position: 'relative' }}>
                <img 
                  src={image} 
                  alt={`Gallery image ${index + 1}`} 
                  className="grid-image"
                  onClick={() => window.open(image, '_blank')}
                />
                <button
                  onClick={(e) => { e.stopPropagation(); handleDelete(image); }}
                  style={{
                    position: 'absolute',
                    top: '8px',
                    right: '8px',
                    background: 'rgba(0,0,0,0.6)',
                    border: 'none',
                    color: 'white',
                    borderRadius: '4px',
                    width: '24px',
                    height: '24px',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontSize: '18px'
                  }}
                  title="Delete"
                >
                  ×
                </button>
              </div>
            ))}
          </div>
        )}
        
        {error && <div className="error-message">{error}</div>}
      </div>
    </div>
  );
};

export default Gallery;