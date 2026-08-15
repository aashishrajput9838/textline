"""
Logging utilities and Windows encoding helpers for Textline.
"""

import sys

# Reconfigure stdout/stderr on Windows to use UTF-8 and replace unencodable characters
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
if hasattr(sys.stderr, 'reconfigure'):
    try:
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

builtins_print = print

def safe_print(*args, **kwargs):
    """Safe print wrapper preventing UnicodeEncodeError on Windows terminals."""
    kwargs.setdefault('flush', True)
    try:
        builtins_print(*args, **kwargs)
    except UnicodeEncodeError:
        try:
            safe_args = [str(a).encode('ascii', 'replace').decode('ascii') for a in args]
            builtins_print(*safe_args, **kwargs)
        except Exception:
            pass
    except Exception:
        pass
