#!/usr/bin/env python3
"""Cross-platform name for mapping normalized OCR candidates onto TAB strings.

The implementation remains in map_vision_tab_ocr.py for backward
compatibility with existing macOS workflows. It accepts output from either the
Apple Vision helper or the cross-platform Tesseract helper.
"""

from map_vision_tab_ocr import main


if __name__ == "__main__":
    main()
