#!/usr/bin/env python3
"""
GPU Hardware Detection Script
Detects available NVIDIA GPUs and generates Docker Compose overlay for workers.
"""

import subprocess
import json
import sys
from typing import List, Dict, Any


def get_gpu_info() -> List[Dict[str, Any]]:
    """Detect available NVIDIA GPUs using nvidia-smi."""
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=index,name,memory.total,compute_capability",
             "--format=csv,noheader"],
            capture_output=True,
            text=True,
            check=True
        )
        
        gpus = []
        for line in result.stdout.strip().split('\n'):
            if not line.strip():
                continue
            parts = [p.strip() for p in line.split(',')]
            if len(parts) >= 4:
                gpus.append({
                    'index': int(parts[0]),
                    'name': parts[1],
                    'memory': parts[2],
                    'compute_cap': parts[3]
                })
        
        return sorted(gpus, key=lambda x: x['index'])
    except subprocess.CalledProcessError as e:
        print(f"Error running nvidia-smi: {e}", file=sys.stderr)
        print("Make sure NVIDIA drivers are installed and nvidia-smi is available.", file=sys.stderr)
        sys.exit(1)
    except FileNotFoundError:
        print("nvidia-smi not found. Make sure NVIDIA drivers are installed.", file=sys.stderr)
        sys.exit(1)


def categorize_gpus(gpus: List[Dict[str, Any]]) -> Dict[str, List[int]]:
    """
    Categorize GPUs based on their capabilities.
    Returns a dictionary with categories as keys and lists of GPU indices as values.
    """
    categories = {
        'main': [],      # High-end GPUs (e.g., RTX 3060, 3070, 3080, 3090, 40xx)
        'light': [],     # Lower-end or multiple GPUs
        'preprocess': [] # Dedicated for preprocessing tasks
    }
    
    for gpu in gpus:
        gpu_name = gpu['name'].lower()
        
        # High-end GPUs (main category)
        if any(keyword in gpu_name for keyword in ['3060', '3070', '3080', '3090', '4060', '4070', '4080', '4090', 'a100', 'a5000']):
            categories['main'].append(gpu['index'])
        # Lower-end GPUs (light category)
        elif any(keyword in gpu_name for keyword in ['1660', '2060', '2070', '2080', '3050', '4050']):
            categories['light'].append(gpu['index'])
        # All other GPUs go to preprocess
        else:
            categories['preprocess'].append(gpu['index'])
    
    return categories


def generate_worker_services(categories: Dict[str, List[int]]) -> Dict[str, Any]:
    """Generate Docker Compose services for workers based on GPU categories."""
    services = {}
    
    # Create main workers (1 GPU each)
    for i, gpu_idx in enumerate(categories['main'], 1):
        service_name = f"worker-main-{i}"
        services[service_name] = {
            'build': {
                'context': '.',
                'dockerfile': 'worker/Dockerfile'
            },
            'environment': {
                'REDIS_HOST': 'redis',
                'REDIS_PORT': '6379',
                'R2_ENDPOINT': '${R2_ENDPOINT}',
                'R2_ACCESS_KEY_ID': '${R2_ACCESS_KEY_ID}',
                'R2_SECRET_ACCESS_KEY': '${R2_SECRET_ACCESS_KEY}',
                'R2_BUCKET_NAME': '${R2_BUCKET_NAME}',
                'NVIDIA_VISIBLE_DEVICES': str(gpu_idx),
                'NVIDIA_DRIVER_CAPABILITIES': 'compute,utility'
            },
            'deploy': {
                'resources': {
                    'reservations': {
                        'devices': [
                            {
                                'driver': 'nvidia',
                                'count': 1,
                                'capabilities': ['gpu']
                            }
                        ]
                    }
                }
            },
            'volumes': [
                'hf_cache:/cache/huggingface'
            ],
            'restart': 'unless-stopped'
        }
    
    # Create light worker (multiple GPUs)
    if categories['light']:
        services['worker-light'] = {
            'build': {
                'context': '.',
                'dockerfile': 'worker/Dockerfile'
            },
            'environment': {
                'REDIS_HOST': 'redis',
                'REDIS_PORT': '6379',
                'R2_ENDPOINT': '${R2_ENDPOINT}',
                'R2_ACCESS_KEY_ID': '${R2_ACCESS_KEY_ID}',
                'R2_SECRET_ACCESS_KEY': '${R2_SECRET_ACCESS_KEY}',
                'R2_BUCKET_NAME': '${R2_BUCKET_NAME}',
                'NVIDIA_VISIBLE_DEVICES': ','.join(str(idx) for idx in categories['light']),
                'NVIDIA_DRIVER_CAPABILITIES': 'compute,utility'
            },
            'deploy': {
                'resources': {
                    'reservations': {
                        'devices': [
                            {
                                'driver': 'nvidia',
                                'count': len(categories['light']),
                                'capabilities': ['gpu']
                            }
                        ]
                    }
                }
            },
            'volumes': [
                'hf_cache:/cache/huggingface'
            ],
            'restart': 'unless-stopped'
        }
    
    # Create preprocess worker (1 GPU)
    if categories['preprocess']:
        services['worker-preprocess'] = {
            'build': {
                'context': '.',
                'dockerfile': 'worker/Dockerfile'
            },
            'environment': {
                'REDIS_HOST': 'redis',
                'REDIS_PORT': '6379',
                'R2_ENDPOINT': '${R2_ENDPOINT}',
                'R2_ACCESS_KEY_ID': '${R2_ACCESS_KEY_ID}',
                'R2_SECRET_ACCESS_KEY': '${R2_SECRET_ACCESS_KEY}',
                'R2_BUCKET_NAME': '${R2_BUCKET_NAME}',
                'NVIDIA_VISIBLE_DEVICES': str(categories['preprocess'][0]),
                'NVIDIA_DRIVER_CAPABILITIES': 'compute,utility'
            },
            'deploy': {
                'resources': {
                    'reservations': {
                        'devices': [
                            {
                                'driver': 'nvidia',
                                'count': 1,
                                'capabilities': ['gpu']
                            }
                        ]
                    }
                }
            },
            'volumes': [
                'hf_cache:/cache/huggingface'
            ],
            'restart': 'unless-stopped'
        }
    
    return services


def generate_compose_overlay(services: Dict[str, Any]) -> str:
    """Generate Docker Compose YAML for worker services."""
    yaml_lines = []
    
    yaml_lines.append('services:')
    
    for service_name, service_config in services.items():
        yaml_lines.append(f'  {service_name}:')
        
        # Build
        if 'build' in service_config:
            yaml_lines.append('    build:')
            yaml_lines.append(f'      context: {service_config["build"]["context"]}')
            yaml_lines.append(f'      dockerfile: {service_config["build"]["dockerfile"]}')
        
        # Environment
        if 'environment' in service_config:
            yaml_lines.append('    environment:')
            for key, value in service_config['environment'].items():
                yaml_lines.append(f'      - {key}={value}')
        
        # Deploy
        if 'deploy' in service_config:
            yaml_lines.append('    deploy:')
            if 'resources' in service_config['deploy']:
                yaml_lines.append('      resources:')
                if 'reservations' in service_config['deploy']['resources']:
                    yaml_lines.append('        reservations:')
                    if 'devices' in service_config['deploy']['resources']['reservations']:
                        yaml_lines.append('          devices:')
                        for device in service_config['deploy']['resources']['reservations']['devices']:
                            yaml_lines.append('            - driver: nvidia')
                            yaml_lines.append(f'              count: {device["count"]}')
                            yaml_lines.append(f'              capabilities: {json.dumps(device["capabilities"])}')
        
        # Volumes
        if 'volumes' in service_config:
            yaml_lines.append('    volumes:')
            for volume in service_config['volumes']:
                yaml_lines.append(f'      - {volume}')
        
        # Restart
        if 'restart' in service_config:
            yaml_lines.append(f'    restart: {service_config["restart"]}')
    
    return '\n'.join(yaml_lines)


def main():
    """Main entry point."""
    print("Detecting GPU hardware...", file=sys.stderr)
    
    gpus = get_gpu_info()
    print(f"Found {len(gpus)} GPU(s)", file=sys.stderr)
    
    for gpu in gpus:
        print(f"  GPU {gpu['index']}: {gpu['name']} ({gpu['memory']}, CC {gpu['compute_cap']})", file=sys.stderr)
    
    if not gpus:
        print("No GPUs detected. Exiting.", file=sys.stderr)
        sys.exit(0)
    
    categories = categorize_gpus(gpus)
    print("\nGPU Categories:", file=sys.stderr)
    for category, indices in categories.items():
        print(f"  {category}: {indices}", file=sys.stderr)
    
    services = generate_worker_services(categories)
    
    print(f"\nGenerating Docker Compose overlay with {len(services)} worker service(s)...", file=sys.stderr)
    
    compose_content = generate_compose_overlay(services)
    print(compose_content)


if __name__ == "__main__":
    main()