"""Update opening-view metadata only; source arrays and recordings stay unchanged.

Run on an allocated CPU node in wan, from the website checkout.
"""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
from first_frame_camera import first_frame_camera

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = Path('/n/lab_storage/ydu_lab/Lab/akiruga/world_model_4d/final-website/assets/pointcloud/recon24')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=DEFAULT_SOURCE)
    parser.add_argument('--evidence', type=Path, required=True)
    args = parser.parse_args()
    manifest_path = ROOT / 'examples.json'
    cases_path = ROOT / 'tools/reconstruction_cases.json'
    manifest = json.loads(manifest_path.read_text())
    case_doc = json.loads(cases_path.read_text())
    cases_by_id = {c['id']: c for c in case_doc['cases']}
    before = json.loads(manifest_path.read_text())
    evidence = []
    for case in manifest['reconstruction']['cases']:
        p = case['provenance']
        path = args.source / f"{p['dataset']}__{p['scene']}.npz"
        with np.load(path, allow_pickle=True) as z:
            pose = z['c2w'][0]
            k = z['K']; k = k[0] if k.ndim == 3 else k
            points = z['points'][:int(z['counts'][0])]
            view = first_frame_camera(points, pose, k)
        case['initial_camera'] = view
        cases_by_id[case['id']]['initial_camera'] = view
        digest = hashlib.sha256((ROOT / case['src']).read_bytes()).hexdigest()
        evidence.append({'id': case['id'], 'source': str(path), 'pose': pose.tolist(),
                         'intrinsics': k.tolist(), 'view': view, 'recording_sha256': digest})
        print(case['id'], 'depth', round(view['median_depth'], 3), 'backoff', round(view['median_depth']*view['backoff_fraction'], 3), flush=True)
    for old, new in zip(before['reconstruction']['cases'], manifest['reconstruction']['cases']):
        old.pop('initial_camera', None); new_copy = dict(new); new_copy.pop('initial_camera', None)
        assert old == new_copy
    assert all(before[key] == manifest[key] for key in before if key != 'reconstruction')
    # Preserve the manifest's existing JSON formatting (one-space indentation).
    manifest_path.write_text(json.dumps(manifest, indent=1) + '\n')
    cases_path.write_text(json.dumps(case_doc, indent=1) + '\n')
    args.evidence.parent.mkdir(parents=True, exist_ok=True)
    args.evidence.write_text(json.dumps(evidence, indent=2) + '\n')


if __name__ == '__main__':
    main()
