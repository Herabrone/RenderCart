#!/usr/bin/env python3
"""
GPU Hardware Detection Script
Detects available NVIDIA GPUs and generates Docker Compose overlay for workers.

Classifies GPUs by memory/model to assign roles:
- 3060-class: preprocess/light queue
- 3080-class: light generation queue
- 3090/4090-class: main SDXL queue
- Unknown cards: safe fallback to light queue with conservative settings
"""

import subprocess
import json
import sys
import re
from typing import List, Dict, Any, Optional


class GPUSpec:
    """Represents GPU specifications and capabilities."""
    
    def __init__(self, index: int, name: str, memory_mb: int, compute_cap: str = "unknown"):
        self.index = index
        self.name = name
        self.memory_mb = memory_mb
        self.compute_cap = compute_cap
        self.role = "unknown"
        self.settings = {}
    
    def __str__(self) -> str:
        return f"{self.name} ({self.memory_mb}MB, CC {self.compute_cap}, role: {self.role})"


class GPUPlanner:
    """Manages GPU discovery and worker planning."""
    
    def __init__(self):
        self.gpus: List[GPUSpec] = []
        self.plan: Dict[str, Any] = {}
    
    def detect_gpus(self) -> None:
        """Detect available NVIDIA GPUs using nvidia-smi."""
        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=index,name,memory.total,compute_cap",
                 "--format=csv,noheader"],
                capture_output=True,
                text=True,
                check=True
            )
            
            self.gpus = []
            for line in result.stdout.strip().split('\n'):
                if not line.strip():
                    continue
                parts = [p.strip() for p in line.split(',')]
                if len(parts) >= 3:
                    # Parse memory from "MiB" format
                    memory_match = re.search(r'(\d+)', parts[2])
                    memory_mb = int(memory_match.group(1)) if memory_match else 0
                    compute_cap = parts[3] if len(parts) >= 4 else "unknown"
                    
                    gpu = GPUSpec(
                        index=int(parts[0]),
                        name=parts[1],
                        memory_mb=memory_mb,
                        compute_cap=compute_cap
                    )
                    self.gpus.append(gpu)
            
            self.gpus = sorted(self.gpus, key=lambda gpu: gpu.index)
            
        except subprocess.CalledProcessError as e:
            self._fail_fast(f"Error running nvidia-smi: {e}", 
                          "Make sure NVIDIA drivers are installed and nvidia-smi is available.")
        except FileNotFoundError:
            self._fail_fast("nvidia-smi not found", 
                          "Make sure NVIDIA drivers are installed.")
    
    def _fail_fast(self, error: str, hint: str) -> None:
        """Fail fast with clear diagnostics."""
        print(f"\n❌ ERROR: {error}", file=sys.stderr)
        print(f"💡 HINT: {hint}", file=sys.stderr)
        print("\n🚫 No usable GPU detected. Exiting.", file=sys.stderr)
        sys.exit(1)
    
    def classify_gpus(self) -> None:
        """
        Classify GPUs based on their capabilities.
        
        Classification hierarchy:
        1. 3090/4090-class: main SDXL queue (high VRAM, high performance)
        2. 3080-class: light generation queue (medium VRAM, good performance)
        3. 3060-class: preprocess/light queue (lower VRAM, basic tasks)
        4. Unknown: safe fallback to light queue with conservative settings
        """
        if not self.gpus:
            self._fail_fast("No GPUs detected", 
                          "Check that GPUs are properly installed and drivers are working.")
        
        for gpu in self.gpus:
            gpu_name = gpu.name.lower()
            
            # 3090/4090-class: main SDXL queue
            if any(keyword in gpu_name for keyword in ['3090', '4090']):
                gpu.role = "main"
                gpu.settings = {
                    'max_resolution': '2048x2048',
                    'max_batch_size': 4,
                    'priority': 1
                }
            # 3080-class: light generation queue
            elif any(keyword in gpu_name for keyword in ['3080', '4080']):
                gpu.role = "light"
                gpu.settings = {
                    'max_resolution': '1536x1536',
                    'max_batch_size': 2,
                    'priority': 2
                }
            # 3060-class: preprocess/light queue
            elif any(keyword in gpu_name for keyword in ['3060', '4060']):
                gpu.role = "preprocess"
                gpu.settings = {
                    'max_resolution': '1024x1024',
                    'max_batch_size': 1,
                    'priority': 3
                }
            # Safe fallback for unknown cards
            else:
                print(f"\n⚠️  WARNING: Unknown GPU detected: {gpu.name}", file=sys.stderr)
                print(f"   Falling back to 'light' role with conservative settings.", file=sys.stderr)
                gpu.role = "light"
                gpu.settings = {
                    'max_resolution': '1024x1024',
                    'max_batch_size': 1,
                    'priority': 4
                }

        # Ensure a single 3060-like host can still process full generation workloads.
        if len(self.gpus) == 1 and self.gpus[0].role == "preprocess":
            self.gpus[0].role = "light"
        
        # Ensure at least one worker can handle the generate queue
        has_generate_worker = any(gpu.role in ["main", "light"] for gpu in self.gpus)
        if not has_generate_worker and self.gpus:
            # If all GPUs are preprocess-only, promote the first one to light
            self.gpus[0].role = "light"
            self.gpus[0].settings = {
                'max_resolution': '1024x1024',
                'max_batch_size': 1,
                'priority': 2
            }

    def generate_plan(self) -> Dict[str, Any]:
        """Generate worker plan based on GPU classification."""
        self.plan = {
            'gpus': [],
            'workers': {
                'main': [],
                'light': [],
                'preprocess': []
            },
            'summary': {}
        }
        
        for gpu in self.gpus:
            gpu_info = {
                'index': gpu.index,
                'name': gpu.name,
                'memory': f"{gpu.memory_mb}MB",
                'compute_cap': gpu.compute_cap,
                'role': gpu.role,
                'settings': gpu.settings
            }
            self.plan['gpus'].append(gpu_info)
            self.plan['workers'][gpu.role].append(gpu_info)
        
        # Generate summary statistics
        self.plan['summary'] = {
            'total_gpus': len(self.gpus),
            'main_workers': len(self.plan['workers']['main']),
            'light_workers': len(self.plan['workers']['light']),
            'preprocess_workers': len(self.plan['workers']['preprocess'])
        }
        
        return self.plan
    
    def print_diagnostics(self) -> None:
        """Print detailed GPU diagnostics."""
        print("\n🔍 GPU Discovery Results:", file=sys.stderr)
        print("=" * 60, file=sys.stderr)
        
        for gpu in self.gpus:
            print(f"\n📊 GPU: {gpu.name}", file=sys.stderr)
            print(f"   Memory: {gpu.memory_mb}MB", file=sys.stderr)
            print(f"   Compute Capability: {gpu.compute_cap}", file=sys.stderr)
            print(f"   Role: {gpu.role}", file=sys.stderr)
            print(f"   Settings: {json.dumps(gpu.settings, indent=6)}", file=sys.stderr)
        
        print("\n" + "=" * 60, file=sys.stderr)
        print("📋 Worker Plan Summary:", file=sys.stderr)
        print(f"   Main SDXL Workers: {len(self.plan['workers']['main'])}", file=sys.stderr)
        print(f"   Light Generation Workers: {len(self.plan['workers']['light'])}", file=sys.stderr)
        print(f"   Preprocess Workers: {len(self.plan['workers']['preprocess'])}", file=sys.stderr)
        print("=" * 60, file=sys.stderr)
    
    def generate_worker_services(self) -> Dict[str, Any]:
        """Generate Docker Compose services for workers based on GPU roles."""
        services = {}

        def command_for_role(role: str) -> List[str]:
            if role == "main":
                queues = "generate"
            elif role == "light":
                queues = "download,generate,preprocess,upload,status"
            else:
                queues = "download,preprocess,status"

            return [
                "celery",
                "-A",
                "worker",
                "worker",
                "--loglevel=info",
                "--concurrency=1",
                f"--queues={queues}",
            ]

        # Create main workers (1 GPU each)
        for i, gpu in enumerate(self.gpus, 1):
            if gpu.role != 'main':
                continue
            service_name = f"worker-main-{i}"
            services[service_name] = {
                'build': {
                    'context': '.',
                    'dockerfile': 'worker/Dockerfile'
                },
                'command': command_for_role('main'),
                'environment': {
                    'REDIS_HOST': 'redis',
                    'REDIS_PORT': '6379',
                    'R2_ENDPOINT': '${R2_ENDPOINT}',
                    'R2_ACCESS_KEY_ID': '${R2_ACCESS_KEY_ID}',
                    'R2_SECRET_ACCESS_KEY': '${R2_SECRET_ACCESS_KEY}',
                    'R2_BUCKET_NAME': '${R2_BUCKET_NAME}',
                    'WORKER_ROLE': 'main',
                    'MAX_RESOLUTION': gpu.settings['max_resolution'],
                    'MAX_BATCH_SIZE': str(gpu.settings['max_batch_size']),
                    'NVIDIA_VISIBLE_DEVICES': str(gpu.index),
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
                    'huggingface_cache:/cache/huggingface'
                ],
                'restart': 'unless-stopped'
            }

        # Create light workers (1 GPU each)
        for i, gpu in enumerate(self.gpus, 1):
            if gpu.role != 'light':
                continue
            service_name = f"worker-light-{i}"
            services[service_name] = {
                'build': {
                    'context': '.',
                    'dockerfile': 'worker/Dockerfile'
                },
                'command': command_for_role('light'),
                'environment': {
                    'REDIS_HOST': 'redis',
                    'REDIS_PORT': '6379',
                    'R2_ENDPOINT': '${R2_ENDPOINT}',
                    'R2_ACCESS_KEY_ID': '${R2_ACCESS_KEY_ID}',
                    'R2_SECRET_ACCESS_KEY': '${R2_SECRET_ACCESS_KEY}',
                    'R2_BUCKET_NAME': '${R2_BUCKET_NAME}',
                    'WORKER_ROLE': 'light',
                    'MAX_RESOLUTION': gpu.settings['max_resolution'],
                    'MAX_BATCH_SIZE': str(gpu.settings['max_batch_size']),
                    'NVIDIA_VISIBLE_DEVICES': str(gpu.index),
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
                    'huggingface_cache:/cache/huggingface'
                ],
                'restart': 'unless-stopped'
            }

        # Create preprocess workers (1 GPU each)
        for i, gpu in enumerate(self.gpus, 1):
            if gpu.role != 'preprocess':
                continue
            service_name = f"worker-preprocess-{i}"
            services[service_name] = {
                'build': {
                    'context': '.',
                    'dockerfile': 'worker/Dockerfile'
                },
                'command': command_for_role('preprocess'),
                'environment': {
                    'REDIS_HOST': 'redis',
                    'REDIS_PORT': '6379',
                    'R2_ENDPOINT': '${R2_ENDPOINT}',
                    'R2_ACCESS_KEY_ID': '${R2_ACCESS_KEY_ID}',
                    'R2_SECRET_ACCESS_KEY': '${R2_SECRET_ACCESS_KEY}',
                    'R2_BUCKET_NAME': '${R2_BUCKET_NAME}',
                    'WORKER_ROLE': 'preprocess',
                    'MAX_RESOLUTION': gpu.settings['max_resolution'],
                    'MAX_BATCH_SIZE': str(gpu.settings['max_batch_size']),
                    'NVIDIA_VISIBLE_DEVICES': str(gpu.index),
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
                    'huggingface_cache:/cache/huggingface'
                ],
                'restart': 'unless-stopped'
            }

        return services
    
    def generate_compose_overlay(self, services: Dict[str, Any]) -> str:
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
            if 'command' in service_config:
                yaml_lines.append('    command:')
                for item in service_config['command']:
                    yaml_lines.append(f'      - {item}')

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

        yaml_lines.append('')
        yaml_lines.append('volumes:')
        yaml_lines.append('  huggingface_cache:')
        
        return '\n'.join(yaml_lines)


def main():
    """Main entry point."""
    planner = GPUPlanner()
    
    print("🔍 Detecting GPU hardware...", file=sys.stderr)
    planner.detect_gpus()
    
    if not planner.gpus:
        print("❌ No GPUs detected. Exiting.", file=sys.stderr)
        sys.exit(0)
    
    print(f"✅ Found {len(planner.gpus)} GPU(s)", file=sys.stderr)
    
    print("\n📊 GPU Information:", file=sys.stderr)
    for gpu in planner.gpus:
        print(f"  GPU: {gpu.name} ({gpu.memory_mb}MB, CC {gpu.compute_cap})", file=sys.stderr)
    
    print("\n🏷️ Classifying GPUs...", file=sys.stderr)
    planner.classify_gpus()
    
    print("\n📋 Generating worker plan...", file=sys.stderr)
    plan = planner.generate_plan()
    planner.print_diagnostics()
    
    services = planner.generate_worker_services()
    
    print(f"\n✅ Generating Docker Compose overlay with {len(services)} worker service(s)...", file=sys.stderr)
    
    compose_content = planner.generate_compose_overlay(services)
    print(compose_content)


if __name__ == "__main__":
    main()