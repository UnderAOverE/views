python -c "import sys, inspect; import sources.appd.controllers as m; print(sys.executable); print(m.__file__); print('NY' if 'replace(tzinfo=None)' in inspect.getsource(m.AppDCredential._normalize_to_utc) else 'OLD')"


# 1. Stop everything (so nothing holds the old code in memory)
bin/stop.sh ; bin/stop_dashboards.sh ; bin/stop_api.sh

# 2. Activate the venv
source .venv/bin/activate

# 3. Uninstall the package — run twice (pip sometimes leaves a duplicate)
pip uninstall -y platform-kpi
pip uninstall -y platform-kpi        # 2nd time should say "not installed"

# 4. PROVE it's gone — this should now ERROR (ModuleNotFoundError)
python -c "import sources.appd.controllers" 2>&1 | tail -1
#   - if it errors  -> good, clean. continue.
#   - if it STILL imports -> there's a stray hand-copied package shadowing it:
python -c "import sources, os; print(os.path.dirname(os.path.dirname(sources.__file__)))"
#     ^ that prints the dir to delete; rm -rf the leftover package dirs it shows under site-packages

# 5. Purge caches + stale build artifacts + bytecode
pip cache purge
rm -rf build/ dist/ .eggs/ *.egg-info src/*.egg-info
find . -type d -name "__pycache__" -prune -exec rm -rf {} +
# clear any leftover editable pointer files from a previous attempt:
find .venv -name "__editable__*platform*" -delete 2>/dev/null
find .venv -name "*platform*kpi*.pth" -delete 2>/dev/null

# 6. Fresh editable install, no cache
pip install -e . --no-cache-dir

# 7. VERIFY it loads from src (this is the gate — must show a .../src/... path, NOT site-packages)
python -c "import sources.appd.controllers as m; print(m.__file__)"

# 8. Start everything back up
bin/start.sh ; bin/start_dashboards.sh ; bin/start_api.sh

# 9. Confirm the daemon now loads the fix
grep appd.tz_normalization.status var/logs/daemon/daemon.log | tail -1
#   -> expect: active: true, applied_offset_hours: 5.0, controllers_module: .../src/...
The two checkpoints that matter
Step 4 must error. If import sources still works right after uninstalling, a stray copied package is shadowing everything — that's almost certainly your whole problem. The command there prints exactly which directory to delete.
Step 7 must print a .../src/... path. If it shows site-packages, the editable install didn't take — stop and tell me, don't start the services yet.
Notes
Adjust .venv if your prod venv lives elsewhere.
pip pull/git pull first if your prod src isn't already at commit 4aeaa83 — the editable install links to whatever's in src, so it must have the fix.
If pip install -e . errors on package discovery, that's the pyproject.toml packages=[...] issue — tell me and I'll switch it to [tool.setuptools.packages.find] where=["src"].
Run it and paste step 4's output and step 7's path — those two lines tell us if the wipe finally cleared the stale copy.


