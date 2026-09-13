#!/usr/bin/env python3
import runpy

# Keep the Tunisia verification, then test/import the M3U links supplied by the user.
runpy.run_path("tools/add_tunisia_extras_core.py", run_name="__main__")
runpy.run_path("tools/import_user_m3u_candidates.py", run_name="__main__")
