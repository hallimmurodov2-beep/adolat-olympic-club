#!/usr/bin/env python3
"""Regenerate public derivatives from the exact school-supplied raster master.

No vector tracing, alpha claim or generative enlargement. Large icon canvases are
padded white; supply a higher-resolution approved master for sharper large icons.
"""
import argparse
import hashlib
import json
from pathlib import Path
from PIL import Image, ImageOps

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,default=ROOT/'static/brand/school-logo-original.png')
    args=parser.parse_args()
    out=ROOT/'static/brand';out.mkdir(exist_ok=True)
    source=args.source.read_bytes()
    original=out/'school-logo-original.png'
    if args.source.resolve()!=original.resolve():original.write_bytes(source)
    with Image.open(original) as source_image:
        image=source_image.convert('RGBA')
        def tile(width,height):
            scaled=ImageOps.contain(image,(min(width,image.width),min(height,image.height)),Image.Resampling.LANCZOS)
            result=Image.new('RGBA',(width,height),'white')
            result.alpha_composite(scaled,((width-scaled.width)//2,(height-scaled.height)//2))
            return result.convert('RGB')
        tile(64,52).save(out/'logo-header.png',optimize=True)
        tile(128,104).save(out/'logo-header-2x.png',optimize=True)
        image.convert('RGB').save(out/'logo-login.png',optimize=True)
        for size in (16,32,48,180,192,512):tile(size,size).save(out/f'icon-{size}.png',optimize=True)
        tile(48,48).save(out/'favicon.ico',sizes=[(16,16),(32,32),(48,48)])
        manifest={'product':'Adolat Olympic Club','source_file':original.name,'source_sha256':hashlib.sha256(source).hexdigest(),
                  'source_size':[image.width,image.height],'source_mode':source_image.mode,
                  'method':'Proportional Lanczos reduction, white padded tiles, no invented transparency or detail.',
                  'files':{}}
        for file in sorted(out.glob('*.png')):
            with Image.open(file) as part:
                manifest['files'][file.name]={'size':[part.width,part.height],'sha256':hashlib.sha256(file.read_bytes()).hexdigest()}
        (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')


if __name__=='__main__':main()
