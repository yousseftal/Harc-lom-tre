#!/usr/bin/env python3
import runpy

# Keep Tunisia verification, then test/import the M3U links supplied by the user,
# verify every supplied candidate, and finally scan M3U.CL for additional
# Arabic/French free/public streams. Each stage tests streams before keeping them.
# M3U.CL uses its canonical www URL with normal browser request headers.
runpy.run_path("tools/add_tunisia_extras_core.py", run_name="__main__")
runpy.run_path("tools/import_user_m3u_candidates.py", run_name="__main__")
runpy.run_path("tools/verify_user_m3u_all.py", run_name="__main__")
runpy.run_path("tools/add_m3ucl_extras.py", run_name="__main__")
