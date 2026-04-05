import json
import os
import hashlib
from fastapi import Security, HTTPException, status
from fastapi.security.api_key import APIKeyHeader
from dotenv import load_dotenv

load_dotenv()

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

class APIKeyAuth:
    """API Key authentication for business customers"""
    
    def __init__(self):
        # Load business API keys from config file
        # Use absolute path or default to current directory if not found in api/
        config_path = os.getenv('BUSINESS_API_KEYS_CONFIG', 'api/business_keys.json')
        
        if not os.path.exists(config_path):
            # Fallback for different container run contexts
            alt_path = 'business_keys.json'
            if os.path.exists(alt_path):
                config_path = alt_path
            else:
                # For local dev without keys, we can create a dummy one or handle it gracefully
                # But if NO_AUTH is handled elsewhere, we still need this to not crash on init
                self.business_keys = {}
                return
        
        with open(config_path, 'r') as f:
            self.business_keys = json.load(f)
    
    def get_api_key_hash(self, api_key: str) -> str:
        """Generate SHA-256 hash of API key"""
        return hashlib.sha256(api_key.encode()).hexdigest()

    def normalize_stored_hash(self, stored_hash: str) -> str:
        """Normalize hash formats like 'sha256:<hex>' or '<hex>' to plain hex."""
        if not stored_hash:
            return ""
        if stored_hash.startswith("sha256:"):
            return stored_hash.split(":", 1)[1]
        return stored_hash
    
    def verify_api_key(self, api_key: str) -> str:
        """
        Verify API key and return business_id
        
        Args:
            api_key: Raw API key from request header
            
        Returns:
            business_id if valid
            
        Raises:
            HTTPException: If API key is invalid
        """
        # Bypass for local development if NO_AUTH is set
        if os.getenv('NO_AUTH') == 'true':
            return 'local_dev'

        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing API Key"
            )
        
        api_key_hash = self.get_api_key_hash(api_key)
        
        # Find matching business
        for business_id, config in self.business_keys.items():
            stored_hash = self.normalize_stored_hash(config.get('api_key_hash', ''))
            if stored_hash == api_key_hash:
                return business_id
        
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API Key"
        )
    
    async def verify_api_key_dependency(self, api_key: str = Security(api_key_header)) -> str:
        """FastAPI dependency for API key verification"""
        return self.verify_api_key(api_key)
