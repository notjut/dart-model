"""Only publish static assets; keep caches and updater source out of the site."""
from pathlib import Path
import shutil
from io import BytesIO
from PIL import Image

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
        if path.name not in {'requirements.txt', 'refresh-failure.json', 'darkhorse-release.json'}:
            shutil.copy2(path, out/path.name)
for name in ['assets', 'forecast-archive']:
    if (root/name).exists():
        shutil.copytree(root/name, out/name)
# Small, local derivatives keep the original team artwork unchanged.
small = out/'assets/logos-small'
small.mkdir(exist_ok=True)
for source in (out/'assets/logos').glob('*.png'):
    with Image.open(source) as original:
        image = original.convert('RGBA')
        image.thumbnail((96, 96), Image.Resampling.LANCZOS)
        buffer = BytesIO()
        image.save(buffer, 'WEBP', quality=85, method=6)
        content = buffer.getvalue()
        if not content:
            raise ValueError(f'Empty optimized logo: {source.name}')
        (small/(source.stem+'.webp')).write_bytes(content)
print('Packaged public site')
