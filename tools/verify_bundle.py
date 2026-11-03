"""Verify the publication manifest using only the Python standard library."""
import hashlib
import json
from pathlib import Path


def main():
    root = Path(__file__).resolve().parents[1]
    manifest = json.loads((root/'manifest.json').read_text(encoding='utf-8'))
    errors = []
    for item in manifest['files']:
        path = (root/item['path']).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            errors.append(item['path'] + ': missing or unsafe path')
            continue
        data = path.read_bytes()
        if len(data) != item['bytes'] or hashlib.sha256(data).hexdigest() != item['sha256']:
            errors.append(item['path'] + ': content changed')
    if errors:
        raise SystemExit('\n'.join(errors))
    print(f"PASS: {len(manifest['files'])} publication files match SHA256 and size")
    print('Generated build/cache files are not covered; the manifest is not a signature.')


if __name__ == '__main__':
    main()
