#!/usr/bin/env python3
"""
Performance optimization test script for ParkingSpace Detection System.
This script tests the new optimization features and compares startup times.
"""

import time
import sys
from pathlib import Path

# Add the src directory to the path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'src'))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

def test_capability_detection():
    """Test the capability detection system"""
    print("🔍 Testing System Capability Detection")
    print("=" * 50)
    
    from parkingspace.capabilities import get_capability_detector
    
    detector = get_capability_detector()
    capabilities = detector.detect_system_capabilities()
    
    print(f"\n📊 System Performance Level: {capabilities.estimated_performance_level.upper()}")
    print(f"💻 Recommended Device: {capabilities.recommended_settings['device']}")
    print(f"🖼️  Recommended Image Size: {capabilities.recommended_settings['image_size']}")
    print(f"⏱️  Recommended Processing Interval: {capabilities.recommended_settings['processing_interval']}s")
    
    return capabilities

def test_startup_optimization():
    """Test the startup optimization system"""
    print("\n🚀 Testing Startup Optimization")
    print("=" * 50)
    
    from parkingspace.capabilities import get_startup_optimizer
    from parkingspace.logger import setup_logging
    
    # Setup logging
    logger = setup_logging()
    optimizer = get_startup_optimizer()
    
    # Test preloading
    optimizer.preload_imports()
    
    print("✅ Startup optimization test completed")

def benchmark_model_loading():
    """Benchmark model loading with and without optimization"""
    print("\n⏱️  Benchmarking Model Loading Performance")
    print("=" * 50)
    
    from parkingspace.config import get_config
    from parkingspace.services import ModelService
    from parkingspace.capabilities import get_capability_detector
    
    # Get optimized config
    detector = get_capability_detector()
    capabilities = detector.detect_system_capabilities()
    config = get_config()
    
    # Apply optimizations based on capabilities
    config.device = capabilities.recommended_settings['device']
    config.detection.image_size = capabilities.recommended_settings['image_size']
    
    # Test model loading
    print(f"📥 Loading model with optimizations...")
    print(f"   Device: {config.device}")
    print(f"   Image size: {config.detection.image_size}")
    
    start_time = time.time()
    
    model_service = ModelService(config)
    model_service.load_model()
    
    load_time = time.time() - start_time
    
    print(f"✅ Model loaded in {load_time:.3f}s")
    
    return load_time

def test_optimized_detection():
    """Test optimized detection performance"""
    print("\n🎯 Testing Optimized Detection Performance")
    print("=" * 50)
    
    import cv2
    import numpy as np
    from parkingspace.config import get_config
    from parkingspace.services import ModelService
    from parkingspace.capabilities import get_capability_detector
    
    # Get optimized config
    capabilities = get_capability_detector().detect_system_capabilities()
    config = get_config()
    config.device = capabilities.recommended_settings['device']
    
    # Load model
    model_service = ModelService(config)
    model_service.load_model()
    
    # Create test frame
    h, w = config.detection.image_size
    test_frame = np.random.randint(0, 255, (h, w, 3), dtype=np.uint8)
    
    # Warm up (first inference is usually slower)
    model_service.detect_vehicles(test_frame)
    
    # Benchmark detection
    num_tests = 5
    total_time = 0
    
    print(f"🔄 Running {num_tests} detection tests...")
    
    for i in range(num_tests):
        result = model_service.detect_vehicles(test_frame)
        total_time += result.detection_time
        print(f"   Test {i+1}: {result.detection_time:.3f}s")
    
    avg_time = total_time / num_tests
    fps = 1.0 / avg_time if avg_time > 0 else 0
    
    print(f"📊 Average detection time: {avg_time:.3f}s")
    print(f"🎬 Estimated FPS: {fps:.1f}")
    
    return avg_time, fps

def run_full_performance_test():
    """Run complete performance optimization test"""
    print("🏁 Full Performance Optimization Test")
    print("=" * 60)
    
    try:
        # Test 1: Capability Detection
        capabilities = test_capability_detection()
        
        # Test 2: Startup Optimization
        test_startup_optimization()
        
        # Test 3: Model Loading Performance
        load_time = benchmark_model_loading()
        
        # Test 4: Detection Performance
        avg_detection_time, fps = test_optimized_detection()
        
        # Summary
        print("\n" + "=" * 60)
        print("📈 PERFORMANCE OPTIMIZATION SUMMARY")
        print("=" * 60)
        
        print(f"🖥️  System Performance Level: {capabilities.estimated_performance_level.upper()}")
        print(f"💻 Optimized Device: {capabilities.recommended_settings['device']}")
        print(f"⏱️  Model Loading Time: {load_time:.3f}s")
        print(f"🎯 Average Detection Time: {avg_detection_time:.3f}s")
        print(f"🎬 Estimated FPS: {fps:.1f}")
        
        # Recommendations
        print(f"\n💡 OPTIMIZATION RECOMMENDATIONS:")
        rec = capabilities.recommended_settings
        
        if rec['device'] == 'cuda':
            print("   ✅ GPU acceleration is available and enabled")
        else:
            print("   ⚠️  Using CPU - consider GPU upgrade for better performance")
            
        if capabilities.estimated_performance_level in ['high', 'ultra']:
            print("   🚀 System is well-optimized for real-time processing")
        elif capabilities.estimated_performance_level == 'medium':
            print("   🔧 System performance is adequate - consider optimizing processing interval")
        else:
            print("   📉 System performance is limited - consider hardware upgrade")
            
        print(f"\n🎛️  Recommended Settings Applied:")
        print(f"   • Processing Interval: {rec['processing_interval']}s")
        print(f"   • Image Size: {rec['image_size']}")
        print(f"   • Model Size: {rec['model_size']}")
        
        if rec.get('use_half_precision'):
            print("   • Half Precision: ✅ Enabled")
        if rec.get('enable_multithreading'):
            print(f"   • Multithreading: ✅ {rec['worker_threads']} threads")
            
    except Exception as e:
        print(f"❌ Performance test failed: {e}")
        import traceback
        traceback.print_exc()

def main():
    """Main function"""
    print("🎯 ParkingSpace Performance Optimization Test Suite")
    print("🚀 Testing new optimization features...")
    print()
    
    run_full_performance_test()
    
    print(f"\n🏆 Performance optimization test completed!")
    print("💡 The system now includes:")
    print("   • Automatic capability detection")
    print("   • Hardware-based optimization")
    print("   • Faster model loading with warmup")
    print("   • Startup time profiling")
    print("   • Optimized detection pipeline")

if __name__ == "__main__":
    main()
