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
    <div className="gallery">
      <h2 className="gallery-title">My Gallery</h2>
      
      {loading && <div className="loading">Loading...</div>}
      
      {!loading && images.length === 0 && (
        <div className="empty-gallery">No images in gallery</div>
      )}
      
      {!loading && images.length > 0 && (
        <div className="gallery-grid">
          {images.map((image, index) => (
            <div key={index} className="gallery-item">
              <img src={image} alt={`Gallery image ${index + 1}`} className="gallery-image" />
              <button
                onClick={() => handleDelete(image)}
                className="delete-button"
                title="Delete"
              >
                <span className="delete-icon">×</span>
              </button>
            </div>
          ))}
        </div>
      )}
      
      {error && <div className="error-message">{error}</div>}
    </div>
  );
};

export default Gallery;