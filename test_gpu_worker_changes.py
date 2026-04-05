#!/usr/bin/env python3
"""
Test script to verify GPU detection and worker configuration changes.
"""

import os
import sys

def test_worker_file():
    """Test worker.py has GPU preflight checks."""
    print("Testing worker.py GPU preflight checks...")
    
    worker_path = "image-service/worker/worker.py"
    if not os.path.exists(worker_path):
        print("ERROR: worker.py not found")
        return False
    
    with open(worker_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    checks = [
        ("check_gpu_availability function", "def check_gpu_availability():"),
        ("torch.cuda.is_available() check", "torch.cuda.is_available()"),
        ("GPU memory check", "torch.cuda.mem_get_info"),
        ("GPU startup check", "if __name__ == \"__main__\":"),
        ("GPU preflight execution", "check_gpu_availability()"),
    ]
    
    all_passed = True
    for check_name, check_str in checks:
        if check_str in content:
            print(f"PASS: Found {check_name}")
        else:
            print(f"FAIL: Missing {check_name}")
            all_passed = False
    
    return all_passed

def test_dockerfile():
    """Test worker Dockerfile has correct CMD."""
    print("\nTesting worker Dockerfile...")
    
    dockerfile_path = "image-service/worker/Dockerfile"
    if not os.path.exists(dockerfile_path):
        print("ERROR: Dockerfile not found")
        return False
    
    with open(dockerfile_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    if "--concurrency=1" in content:
        print("PASS: Worker Dockerfile has concurrency setting")
        return True
    else:
        print("FAIL: Worker Dockerfile missing concurrency setting")
        return False

def test_deploy_script():
    """Test deploy.sh has hardened health checks."""
    print("\nTesting deploy.sh health checks...")
    
    deploy_path = "image-service/deploy.sh"
    if not os.path.exists(deploy_path):
        print("ERROR: deploy.sh not found")
        return False
    
    with open(deploy_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    checks = [
        ("Redis health check", "docker compose exec redis redis-cli ping"),
        ("Worker service check", "worker-"),
        ("Celery ping check", "celery -A worker inspect ping"),
        ("Queue verification", "active_queues"),
        ("API health check", "curl -s http://localhost:8000/api/health"),
    ]
    
    all_passed = True
    for check_name, check_str in checks:
        if check_str in content:
            print(f"PASS: Found {check_name}")
        else:
            print(f"FAIL: Missing {check_name}")
            all_passed = False
    
    return all_passed

def test_gpu_detection():
    """Test detect_gpus.py has fallback logic."""
    print("\nTesting detect_gpus.py fallback logic...")
    
    gpu_path = "image-service/detect_gpus.py"
    if not os.path.exists(gpu_path):
        print("ERROR: detect_gpus.py not found")
        return False
    
    with open(gpu_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    checks = [
        ("Generate queue check", "has_generate_worker = any(gpu.role in"),
        ("Fallback promotion", "self.gpus[0].role = \"light\""),
        ("Fallback settings - max_resolution", "max_resolution"),
        ("Fallback settings - max_batch_size", "max_batch_size"),
        ("Fallback settings - priority", "priority"),
    ]
    
    all_passed = True
    for check_name, check_str in checks:
        if check_str in content:
            print(f"PASS: Found {check_name}")
        else:
            print(f"FAIL: Missing {check_name}")
            all_passed = False
    
    return all_passed

def main():
    """Run all tests."""
    print("=" * 60)
    print("Testing GPU Worker Configuration Changes")
    print("=" * 60)
    print()
    
    tests = [
        ("GPU Detection Fallback", test_gpu_detection),
        ("Worker GPU Preflight", test_worker_file),
        ("Worker Dockerfile", test_dockerfile),
        ("Deploy Health Checks", test_deploy_script),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"ERROR: Test '{test_name}' failed with exception: {str(e)}")
            results.append((test_name, False))
    
    print()
    print("=" * 60)
    print("Test Summary")
    print("=" * 60)
    
    passed = 0
    failed = 0
    
    for test_name, result in results:
        status = "PASS" if result else "FAIL"
        print(f"{test_name}: {status}")
        if result:
            passed += 1
        else:
            failed += 1
    
    print()
    print(f"Total: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("\nAll tests passed!")
        return 0
    else:
        print(f"\n{failed} test(s) failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())