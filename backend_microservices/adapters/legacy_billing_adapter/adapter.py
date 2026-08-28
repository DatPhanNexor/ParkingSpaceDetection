import sys
from pathlib import Path

# Add legacy code path to sys.path to allow imports
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.append(str(PROJECT_ROOT / "ParkingSpaceDesktopApp"))

from billing_manager import calculate_fee, BillingConfig
