#!/usr/bin/env python3
"""
Real startup time test - measures time until OpenCV window is displayed and first frame is shown.
This is the actual user-perceived startup time.
"""

import time
import sys
import os
import cv2
import threading
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

def measure_opencv_window_startup():
    """Measure time until OpenCV window actually appears"""
    print("🎬 Measuring REAL Startup Time (until OpenCV window)")
    print("=" * 60)
    
    # Test 1: Original method
    print("\n📊 Test 1: Original Startup Method")
    print("-" * 40)
    
    try:
        total_start = time.time()
        
        # pyrefly: ignore [missing-import]
        from src.parkingspace.main import main
        # pyrefly: ignore [missing-import]
        from src.parkingspace.logger import setup_logging
        
        logger = setup_logging()
        
        # Measure time to system ready
        system_start = time.time()
        
        # pyrefly: ignore [missing-import]
        from src.parkingspace.config import get_config
        # pyrefly: ignore [missing-import]
        from src.parkingspace.capabilities import get_capability_detector
        # pyrefly: ignore [missing-import]
        from src.parkingspace.services import ParkingSpaceService
        
        config = get_config()
        detector = get_capability_detector()
        capabilities = detector.detect_system_capabilities()
        
        parking_service = ParkingSpaceService(config)
        parking_service.initialize()
        
        system_ready_time = time.time() - system_start
        
        # Now measure time to first OpenCV window
        video_start = time.time()
        
        # Open video and get first frame
        parking_service.video_service.open_video()
        ret, first_frame = parking_service.video_service.read_frame()
        
        if ret:
            # Create a simple processed frame
            display_frame = first_frame.copy() # pyright: ignore[reportOptionalMemberAccess]
            cv2.putText(display_frame, "Original Method", (50, 50), 
                       cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
            
            # Show the window
            cv2.imshow("Parking Spaces", display_frame)
            cv2.waitKey(1000)  # Show for 1 second
            cv2.destroyAllWindows()
            
            window_display_time = time.time() - video_start
            total_time = time.time() - total_start
            
            print(f"  ⏱️  System ready: {system_ready_time:.3f}s")
            print(f"  📺 OpenCV window: {window_display_time:.3f}s")
            print(f"  🎯 Total to window: {total_time:.3f}s")
            
            return {
                'system_ready': system_ready_time,
                'window_display': window_display_time,
                'total': total_time
            }
        
    except Exception as e:
        print(f"❌ Original method failed: {e}")
        return None

def measure_ultra_fast_startup():
    """Measure ultra-fast startup time to OpenCV window"""
    print("\n🚀 Test 2: Ultra-Fast Startup Method")
    print("-" * 40)
    
    try:
        total_start = time.time()
        
        # pyrefly: ignore [missing-import]
        from src.parkingspace.fast_video_startup import FastParkingSpaceService # pyright: ignore[reportMissingImports]
        # pyrefly: ignore [missing-import]
        from src.parkingspace.config import get_config
        # pyrefly: ignore [missing-import]
        from src.parkingspace.capabilities import get_capability_detector
        # pyrefly: ignore [missing-import]
        from src.parkingspace.logger import setup_logging
        
        logger = setup_logging()
        
        # Quick setup
        config = get_config()
        detector = get_capability_detector()
        capabilities = detector.detect_system_capabilities()
        
        # Apply quick optimizations
        if capabilities:
            recommendations = capabilities.recommended_settings
            if recommendations.get("device"):
                config.device = recommendations["device"]
        
        system_ready_time = time.time() - total_start
        
        # Ultra-fast service
        fast_service = FastParkingSpaceService(config)
        
        # Initialize with preloading
        init_start = time.time()
        fast_service.initialize_fast()
        
        # Wait for video preload
        fast_service.video_service.wait_for_video_ready(timeout=3.0)
        fast_service.video_service.open_video()
        
        init_time = time.time() - init_start
        
        # Get first frame quickly
        window_start = time.time()
        
        first_frame = fast_service.video_service.get_first_frame()
        if first_frame is None:
            ret, first_frame = fast_service.video_service.read_frame()
            if not ret:
                print("❌ Cannot get first frame")
                return None
        
        # Create placeholder immediately
        placeholder = fast_service.first_frame_processor.create_placeholder_frame(first_frame)
        
        # Show window IMMEDIATELY
        cv2.imshow("Parking Spaces", placeholder)
        cv2.waitKey(1)
        
        window_display_time = time.time() - window_start
        total_time = time.time() - total_start
        
        # Show for demonstration
        cv2.waitKey(1000)
        cv2.destroyAllWindows()
        
        print(f"  ⏱️  System ready: {system_ready_time:.3f}s")
        print(f"  🔧 Service init: {init_time:.3f}s")
        print(f"  📺 OpenCV window: {window_display_time:.3f}s")
        print(f"  🚀 Total to window: {total_time:.3f}s")
        
        return {
            'system_ready': system_ready_time,
            'service_init': init_time,
            'window_display': window_display_time,
            'total': total_time
        }
        
    except Exception as e:
        print(f"❌ Ultra-fast method failed: {e}")
        import traceback
        traceback.print_exc()
        return None

def measure_incremental_optimizations():
    """Measure different levels of optimization"""
    print("\n🔧 Test 3: Incremental Optimization Analysis")
    print("-" * 40)
    
    measurements = {}
    
    # Baseline: Just imports
    print("📦 Measuring import time...")
    import_start = time.time()
    # pyrefly: ignore [missing-import]
    import src.parkingspace
    measurements['imports'] = time.time() - import_start
    print(f"  Import time: {measurements['imports']:.3f}s")
    
    # Config loading
    print("⚙️  Measuring config loading...")
    config_start = time.time()
    # pyrefly: ignore [missing-import]
    from src.parkingspace.config import get_config
    config = get_config()
    measurements['config'] = time.time() - config_start
    print(f"  Config time: {measurements['config']:.3f}s")
    
    # Capability detection
    print("🔍 Measuring capability detection...")
    cap_start = time.time()
    # pyrefly: ignore [missing-import]
    from src.parkingspace.capabilities import get_capability_detector
    detector = get_capability_detector()
    capabilities = detector.detect_system_capabilities()
    measurements['capabilities'] = time.time() - cap_start
    print(f"  Capability time: {measurements['capabilities']:.3f}s")
    
    # Model loading
    print("🧠 Measuring model loading...")
    model_start = time.time()
    # pyrefly: ignore [missing-import]
    from src.parkingspace.services import ModelService
    model_service = ModelService(config)
    model_service.load_model()
    measurements['model'] = time.time() - model_start
    print(f"  Model loading: {measurements['model']:.3f}s")
    
    # Video opening
    print("🎬 Measuring video opening...")
    video_start = time.time()
    cap = cv2.VideoCapture(config.video.input_file)
    ret, frame = cap.read()
    measurements['video'] = time.time() - video_start
    if ret:
        print(f"  Video opening: {measurements['video']:.3f}s")
    cap.release()
    
    # First OpenCV display
    if ret:
        print("📺 Measuring OpenCV window creation...")
        display_start = time.time()
        cv2.imshow("Test Window", frame)
        cv2.waitKey(1)
        measurements['opencv_display'] = time.time() - display_start
        print(f"  OpenCV display: {measurements['opencv_display']:.3f}s")
        
        cv2.waitKey(500)  # Show briefly
        cv2.destroyAllWindows()
    
    return measurements

def analyze_bottlenecks():
    """Analyze where the time is actually spent"""
    print("\n🔍 Bottleneck Analysis")
    print("=" * 60)
    
    # Get incremental measurements
    incremental = measure_incremental_optimizations()
    
    print(f"\n📊 Time Breakdown:")
    total_incremental = sum(incremental.values())
    
    for operation, time_taken in sorted(incremental.items(), key=lambda x: x[1], reverse=True):
        percentage = (time_taken / total_incremental) * 100 if total_incremental > 0 else 0
        print(f"  • {operation}: {time_taken:.3f}s ({percentage:.1f}%)")
    
    print(f"\n🎯 Total incremental time: {total_incremental:.3f}s")
    
    return incremental

def main():
    """Main test function"""
    print("⚡ REAL Startup Time Analysis")
    print("🎯 Measuring time until OpenCV window is displayed")
    print("This is what users actually perceive as 'startup time'")
    
    try:
        # Analyze bottlenecks first
        incremental_data = analyze_bottlenecks()
        
        # Test original method
        original_data = measure_opencv_window_startup()
        
        # Test ultra-fast method
        ultra_fast_data = measure_ultra_fast_startup()
        
        # Summary comparison
        print("\n" + "=" * 60)
        print("🏆 REAL STARTUP TIME COMPARISON")
        print("=" * 60)
        
        if original_data and ultra_fast_data:
            print(f"📊 Original Method:")
            print(f"  • Total to OpenCV window: {original_data['total']:.3f}s")
            
            print(f"\n🚀 Ultra-Fast Method:")
            print(f"  • Total to OpenCV window: {ultra_fast_data['total']:.3f}s")
            
            improvement = original_data['total'] - ultra_fast_data['total']
            percentage = (improvement / original_data['total']) * 100 if original_data['total'] > 0 else 0
            
            print(f"\n⚡ IMPROVEMENT:")
            print(f"  • Time saved: {improvement:.3f}s")
            print(f"  • Percentage faster: {percentage:.1f}%")
            
            if improvement > 0:
                print(f"  • ✅ Ultra-fast method is {percentage:.1f}% faster!")
            else:
                print(f"  • ⚠️  Ultra-fast method may need more optimization")
        
        print(f"\n💡 OPTIMIZATION RECOMMENDATIONS:")
        
        # Analyze biggest bottlenecks
        if incremental_data:
            max_time_op = max(incremental_data.items(), key=lambda x: x[1])
            print(f"  • Biggest bottleneck: {max_time_op[0]} ({max_time_op[1]:.3f}s)")
            
            if max_time_op[1] > 3.0:
                print(f"  • 🔧 Focus optimization on {max_time_op[0]}")
            
            model_time = incremental_data.get('model', 0)
            if model_time > 5.0:
                print("  • 🧠 Model loading is slow - consider model caching or smaller model")
            
            video_time = incremental_data.get('video', 0)
            if video_time > 1.0:
                print("  • 🎬 Video opening is slow - consider video preloading")
        
        print(f"\n🎯 TARGET: Get total time under 2 seconds for excellent user experience")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
