"""Run onvifcheck from anywhere: python thingino/tools/onvif/onvifcheck.py <camera> [options]"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from onvifcheck.cli import main  # noqa: E402

sys.exit(main())
