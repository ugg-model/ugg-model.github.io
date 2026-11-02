"""Confidence ranking must handle ties, invalids and frames independently."""
import numpy as np
from prepare_text4d_confidence import confidence_mask, vae_depth

depth = np.ones((2,2,5),np.float32)
confidence = np.array([[[.9,.9,.1,.8,.7],[.6,.5,.4,.3,.2]],
                       [[.1,.2,.3,.4,.5],[.6,.7,.8,.9,1.]]],np.float32)
keep, counts = confidence_mask(depth, confidence)
assert keep.sum(axis=(1,2)).tolist() == [9,9]
assert np.flatnonzero(~keep[0]).tolist() == [2]
assert np.flatnonzero(~keep[1]).tolist() == [0]
keep, _ = confidence_mask(depth,np.ones_like(confidence))
assert np.flatnonzero(keep[0]).tolist() == list(range(9))
assert confidence_mask(np.ones((1,2,10)),np.ones((1,2,10)))[0].sum() == 19
depth[0,0,0] = np.nan
confidence[1,0,0] = np.nan
keep, counts = confidence_mask(depth,confidence)
assert [c['valid'] for c in counts] == [9,9]
assert keep.sum(axis=(1,2)).tolist() == [8,8]
assert not keep[:,0,0].any()
raw = np.repeat(np.array([[[[-.5,0,.5,1,-1]]]],np.float32),3,axis=0)
np.testing.assert_allclose(vae_depth(raw),[[[3,1,1/3,0,0]]],rtol=1e-6)
assert confidence_mask(np.ones((1,1,1)),np.ones((1,1,1)),1)[0].all()
for d,c in [(np.zeros((1,2,2)),np.ones((1,2,2))),(np.ones((1,2,2)),np.zeros((2,2)))]:
 try:
  confidence_mask(d,c)
  raise AssertionError('Invalid input accepted')
 except ValueError:
  pass
print('PASS: per-frame exact counts, independent ranking, stable ties, invalid points, raw VAE signed-disparity decoding')
