#!/usr/bin/env python3
import runpy

# Keep Tunisia verification, then test/import the M3U links supplied by the user,
# then verify every supplied candidate (including links already present) and clean aliases.
runpy.run_path("tools/add_tunisia_extras_core.py", run_name="__main__")
runpy.run_path("tools/import_user_m3u_candidates.py", run_name="__main__")
runpy.run_path("tools/verify_user_m3u_all.py", run_name="__main__")
