import redis
import time
from typing import Optional
from datetime import datetime, timedelta
from dotenv import load_dotenv

from config import settings

load_dotenv()

class UsageTracker:
    """Track API usage by business ID"""
    
    def __init__(self):
        self.redis = redis.Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            password=settings.redis_password,
            decode_responses=True
        )
    
    def track_request(self, business_id: str, endpoint: str, success: bool = True) -> None:
        """Track a single API request"""
        timestamp = int(time.time())
        
        # Track individual request
        request_key = f"usage:{business_id}:requests"
        self.redis.hset(request_key, timestamp, 1)
        
        # Track by endpoint
        endpoint_key = f"usage:{business_id}:endpoints:{endpoint}"
        self.redis.hset(endpoint_key, timestamp, 1)
        
        # Track success/failure
        if success:
            success_key = f"usage:{business_id}:success"
        else:
            success_key = f"usage:{business_id}:failure"
        self.redis.hset(success_key, timestamp, 1)
    
    def get_usage_stats(self, business_id: str, days: int = 7) -> dict:
        """Get usage statistics for a business"""
        cutoff = int(time.time()) - (days * 24 * 60 * 60)
        
        # Get all request timestamps
        requests_key = f"usage:{business_id}:requests"
        request_timestamps = self.redis.hkeys(requests_key) or []
        
        # Filter by time period
        recent_requests = [ts for ts in request_timestamps if int(ts) > cutoff]
        
        # Count requests
        total_requests = len(recent_requests)
        
        # Get endpoint statistics
        endpoints = ['/generate', '/upload', '/job', '/gallery']
        endpoint_stats = {}
        for endpoint in endpoints:
            endpoint_key = f"usage:{business_id}:endpoints:{endpoint}"
            endpoint_timestamps = self.redis.hkeys(endpoint_key) or []
            recent_endpoint = [ts for ts in endpoint_timestamps if int(ts) > cutoff]
            endpoint_stats[endpoint] = len(recent_endpoint)
        
        # Get success/failure statistics
        success_key = f"usage:{business_id}:success"
        failure_key = f"usage:{business_id}:failure"
        
        success_timestamps = self.redis.hkeys(success_key) or []
        failure_timestamps = self.redis.hkeys(failure_key) or []
        
        recent_success = [ts for ts in success_timestamps if int(ts) > cutoff]
        recent_failure = [ts for ts in failure_timestamps if int(ts) > cutoff]
        
        return {
            'business_id': business_id,
            'total_requests': total_requests,
            'successful_requests': len(recent_success),
            'failed_requests': len(recent_failure),
            'success_rate': (len(recent_success) / total_requests * 100) if total_requests > 0 else 0,
            'endpoints': endpoint_stats,
            'time_period': {
                'days': days,
                'start': datetime.fromtimestamp(cutoff).isoformat(),
                'end': datetime.fromtimestamp(int(time.time())).isoformat()
            }
        }
    
    def get_daily_stats(self, business_id: str, days: int = 7) -> list:
        """Get daily usage statistics"""
        cutoff = int(time.time()) - (days * 24 * 60 * 60)
        
        requests_key = f"usage:{business_id}:requests"
        all_timestamps = self.redis.hkeys(requests_key) or []
        
        # Group by day
        daily_counts = {}
        for ts in all_timestamps:
            ts_int = int(ts)
            if ts_int > cutoff:
                day = datetime.fromtimestamp(ts_int).strftime('%Y-%m-%d')
                daily_counts[day] = daily_counts.get(day, 0) + 1
        
        # Fill in missing days
        result = []
        for i in range(days):
            day = (datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d')
            result.append({
                'date': day,
                'requests': daily_counts.get(day, 0)
            })
        
        return result
    
    def get_top_businesses(self, limit: int = 10) -> list:
        """Get top businesses by usage"""
        # This is a simplified version - in production you'd want to scan all business IDs
        # For now, we'll just return an empty list
        return []
