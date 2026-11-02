"""Rebuild only the approved indoor scenes from raw VAE depth + confidence.

Run on a Slurm CPU allocation in the wan environment. Sources are read only.
The prior per-clip depth/pose gauge is retained; no ground truth is used.
"""
import argparse
from concurrent.futures import ProcessPoolExecutor
import gzip
import hashlib
import json
import re
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
RETAINED_FRACTION = 0.95


def selected_numbers():
    module = (ROOT / 'assets/text4d-showcase.mjs').read_text()
    return json.loads('[' + re.search(r'TEXT4D_WEBSITE_NUMBERS = Object.freeze\(\[([^]]+)\]', module).group(1).rstrip().rstrip(',') + ']')


def confidence_mask(depth, confidence, fraction=RETAINED_FRACTION):
    """Exact floor(95% * valid) per frame, with row-major tie breaking."""
    if depth.shape != confidence.shape or depth.ndim != 3:
        raise ValueError('Depth/confidence must be matching frame,height,width arrays')
    if not 0 < fraction <= 1:
        raise ValueError('Invalid retained fraction')
    mask = np.zeros(depth.shape, bool)
    records = []
    for f in range(len(depth)):
        valid = np.flatnonzero(np.isfinite(depth[f]) & (depth[f] > 0) & np.isfinite(confidence[f]))
        count = int(np.floor(len(valid) * fraction))
        if not count:
            raise ValueError(f'No retained points in frame {f}')
        scores = confidence[f].ravel()[valid]
        order = np.argsort(-scores, kind='stable')
        chosen = valid[order[:count]]
        mask[f].ravel()[chosen] = True
        records.append({'valid':len(valid), 'retained':count,
                        'minimum_retained_confidence':float(scores[order[count-1]])})
    return mask, records


def vae_depth(raw):
    """VAE exports signed disparity in three channels, shape C,F,H,W."""
    if raw.ndim != 4 or raw.shape[0] != 3:
        raise ValueError(f'Unexpected VAE depth shape {raw.shape}')
    normalized = np.asarray(raw, dtype=np.float32).mean(axis=0)
    disparity = (normalized + 1) * 0.5
    valid = np.isfinite(disparity) & (disparity > 0) & (disparity < 1)
    depth = np.zeros(disparity.shape, np.float32)
    depth[valid] = 1 / disparity[valid] - 1
    return depth


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(task):
    source_root, output, previous, number, label = task
    sample_id = number - 22
    source = source_root / f'sample_{sample_id:03}'
    folder = output / source.name
    old = previous[f'text4d-indoor-{sample_id:03}']
    # Preserve the previously solved relative depth/pose gauge. Raw depth replaces
    # the quantized normalized export; no percentile floor, edges or distance cut.
    scale = old['depth_scale']
    depth = vae_depth(np.load(source / 'depth_vae_depth.npy', mmap_mode='r'))
    depth *= scale
    confidence = np.load(source / 'depth_vae_conf.npy', mmap_mode='r')
    keep, counts = confidence_mask(depth, confidence)
    depth[~keep] = 0
    depth = np.ascontiguousarray(depth, dtype='<f4')
    rgb = np.load(source / 'pred_rgb.npy', mmap_mode='r')
    colors = np.ascontiguousarray(rgb.transpose(0, 2, 3, 1))
    fcount, height, width = depth.shape
    assert (fcount, height, width) == (50,288,384) and colors.shape == (50,288,384,3)
    assert rgb.dtype == np.uint8
    c2w = np.load(source / 'pred_c2w.npy')
    intrinsics = np.load(source / 'pred_intrinsics.npy')
    assert np.isfinite(c2w).all() and np.isfinite(intrinsics).all()
    meta = json.loads((source / 'meta.json').read_text())
    prompt = (source / 'prompt.txt').read_text().strip()
    assert prompt == meta['prompt'].strip() and meta['hist_indexes_size'] == 0
    yy, xx = np.mgrid[:height, :width]
    pixels = np.stack([xx+.5,yy+.5,np.ones_like(xx)],axis=-1).reshape(-1,3)
    centers, radii, extent = [], [], 0.
    for f in range(fcount):
        values = depth[f].ravel()
        mask = values > 0
        world = (pixels[mask] @ np.linalg.inv(intrinsics[f]).T) * values[mask,None]
        world = world @ c2w[f,:3,:3].T + c2w[f,:3,3]
        assert np.isfinite(world).all()
        low, high = np.quantile(world,[.02,.98],axis=0)
        centers.append(((low+high)/2).tolist())
        radii.append(float(np.linalg.norm(high-low)/2))
        extent = max(extent,float(np.linalg.norm(world.max(axis=0)-world.min(axis=0))/2))
    info = json.loads((folder / 'scene.json').read_text())
    for key in ['display_filter','clipwide_radius']:
        info.pop(key,None)
    info.update(frame_count=fcount,fps=10,stride=1,grid_width=width,grid_height=height,
                c2w=c2w.tolist(),intrinsics=intrinsics.tolist(),frame_centers=centers,
                center=centers[0],radius=max(float(np.median(radii)),.05),extent_radius=extent,
                observer_fit='median robust per-frame radius; observer follows frame center',
                confidence_filter={'method':'per_frame_top_confidence','retained_fraction':RETAINED_FRACTION,
                                   'tie_break':'row-major pixel index','frame_counts':counts},
                depth_source='depth_vae_depth.npy: mean of 3 signed-disparity channels',
                depth_scale=scale)
    # Atomic replacements also prevent changes to any source-tree hardlinks.
    tmp = folder / 'pointmaps.bin.gz.tmp'
    with tmp.open('wb') as raw:
        with gzip.GzipFile(filename='',fileobj=raw,mode='wb',compresslevel=6,mtime=0) as stream:
            stream.write(depth.tobytes()); stream.write(colors.tobytes())
    tmp.replace(folder / 'pointmaps.bin.gz')
    tmp = folder / 'scene.json.tmp'
    tmp.write_text(json.dumps(info,separators=(',',':'))+'\n')
    tmp.replace(folder / 'scene.json')
    # Existing RGB/depth preview sprites and remuxed RGB video retain the same
    # frames. The depth inset remains the supplied colormapped depth rendering.
    prefix = folder.relative_to(ROOT).as_posix()
    case = {'id':old['id'],'kind':'text4d','short_title':f'Scene {label:02}',
            'title':f'Text-to-4D · Scene {label:02}','selection':'',
            'thumbnail':prefix+'/thumbnail.jpg','scene':prefix+'/scene.json',
            'video':prefix+'/rgb.mp4','prompt':prompt}
    record = {'id':old['id'],'source':str(source),'former_website_scene':number,
              'published_scene':label,'depth_scale':scale,
              'gauge_identifiable':old['gauge_identifiable'],
              'gauge_provenance':'retained from previous indoor build',
              'confidence_filter':info['confidence_filter'],
              'source_sha256':{name:sha(source/name) for name in [
                  'depth_vae_depth.npy','depth_vae_conf.npy','pred_rgb.npy',
                  'pred_c2w.npy','pred_intrinsics.npy','prompt.txt']},
              'published_sha256':{p.name:sha(p) for p in sorted(folder.iterdir()) if p.is_file()}}
    print(f"Scene {label:02}: former {number:02} -> {source.name}, "
          f"{min(c['retained'] for c in counts)}–{max(c['retained'] for c in counts)} points/frame",flush=True)
    return case, record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--output',type=Path,default=ROOT/'assets/text4d_indoor')
    parser.add_argument('--previous-provenance',type=Path,required=True)
    parser.add_argument('--workers',type=int,default=2)
    args = parser.parse_args()
    args.output = args.output.resolve()
    args.source = args.source.resolve()
    previous = {c['id']:c for c in json.loads(args.previous_provenance.read_text())['cases']}
    numbers = selected_numbers()
    tasks = [(args.source,args.output,previous,n,i+1) for i,n in enumerate(numbers)]
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        built = list(pool.map(build,tasks))
    cases, records = map(list,zip(*built))
    (args.output/'cases.json').write_text(json.dumps(cases,indent=2)+'\n')
    (args.output/'provenance.json').write_text(json.dumps({
        'source':str(args.source),'count':len(cases),'display_stride':1,
        'former_website_numbers':numbers,
        'depth_decode':'mean C of raw C,F,H,W VAE signed disparity; (1/((mean+1)/2)-1) * retained per-clip scale; no percentile floor',
        'filter':f'highest confidence floor({RETAINED_FRACTION} * valid points) independently per frame; stable row-major ties; no edge or far-depth filters',
        'history':False,'source_modified':False,'cases':records},indent=2)+'\n')
    manifest_path = ROOT/'examples.json'
    manifest = json.loads(manifest_path.read_text())
    if manifest['generation']['cases'] != cases:
        manifest['generation']['cases'] = cases
        manifest_path.write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+'\n')


if __name__ == '__main__':
    main()
