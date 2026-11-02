#!/usr/bin/env python
"""Do ScanNet++ scene_44 depth + per-frame K + c2w fuse into one cloud?
Identity-pose control: using the poses must beat ignoring them."""
import numpy as np
from scipy.spatial import cKDTree
D="/n/lab_storage/ydu_lab/Lab/akiruga/curated_oracle/depth/scannetpp__dense/scene_44"
gt=np.load(f"{D}/gt_depth.npy"); c2w=np.load(f"{D}/gt_c2w.npy"); K=np.load(f"{D}/pred_intrinsics.npy")
print("gt_depth",gt.shape,"c2w",c2w.shape,"K",K.shape)
print("K[0]\n",np.round(K[0],2))
print("gt depth range %.3f..%.3f"%(np.nanmin(gt[gt>0]),np.nanmax(gt)))
H,W=gt.shape[1:]; uu,vv=np.meshgrid(np.arange(W),np.arange(H))
print("path len %.3f m, baseline 0->1 %.4f m, 0->25 %.4f m"%(
  np.linalg.norm(np.diff(c2w[:,:3,3],axis=0),axis=1).sum(),
  np.linalg.norm(c2w[1,:3,3]-c2w[0,:3,3]), np.linalg.norm(c2w[25,:3,3]-c2w[0,:3,3])))
def pts(i,mode):
    d=gt[i]; m=np.isfinite(d)&(d>1e-3); z=d[m]
    k=K[i]; P=np.stack([(uu[m]-k[0,2])/k[0,0]*z,(vv[m]-k[1,2])/k[1,1]*z,z],1)
    if mode=="identity": return P
    if mode=="opengl": P=P*np.array([1,-1,-1])
    if mode=="inv":
        R=c2w[i,:3,:3].T; t=-R@c2w[i,:3,3]; return (R@P.T).T+t
    return (c2w[i,:3,:3]@P.T).T+c2w[i,:3,3]
print(f"\n{'pair':9s}"+"".join(f"{m:>11s}" for m in ("identity","opencv","opengl","inv")))
for i,j in [(0,1),(0,3),(0,10),(20,22),(30,33)]:
    out=[]
    for m in ("identity","opencv","opengl","inv"):
        A,B=pts(i,m),pts(j,m); d,_=cKDTree(A).query(B[::40]); out.append(np.median(d))
    print(f"{str((i,j)):9s}"+"".join(f"{v:11.4f}" for v in out))
