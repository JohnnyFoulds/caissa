# Fixture file used by test_ruff_config_enforces_e722.
# Contains a bare except: clause — ruff E722 must be reported on this file.
# This file is intentionally NOT a test file (no test_ prefix).

def _bad_function():
    try:
        pass
    except:
        pass
