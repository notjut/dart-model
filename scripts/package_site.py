"""Only publish static assets; keep caches and updater source out of the site."""
from pathlib import Path
import shutil

root = Path(__file__).resolve().parents[1]
import runpy
runpy.run_path(str(root/'scripts/build_dashboard.py'))
out = root/'dist'
out.mkdir(exist_ok=True)
for child in out.iterdir():
    if child.is_dir():
        shutil.rmtree(child)
    else:
        child.unlink()
for path in root.iterdir():
    if path.is_file() and (path.suffix in {'.html', '.css', '.js', '.json', '.zip', '.ico', '.txt'} or path.name == '.nojekyll'):
        if path.name not in {'requirements.txt', 'refresh-failure.json'}:
            shutil.copy2(path, out/path.name)
for name in ['assets', 'forecast-archive']:
    if (root/name).exists():
        shutil.copytree(root/name, out/name)
print('Packaged public site')
