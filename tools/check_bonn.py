#!/usr/bin/env python
"""Bonn pose gate, done properly.

Bonn scenes contain MOVING PEOPLE, so a median nearest-neighbour distance is
dominated by dynamic content that can never align. Low percentiles are
dominated by the static background, which is what the poses should fix.
Identity-pose is the control: using poses must beat ignoring them.
"""
import numpy as np
from scipy.spatial import cKDTree

D="/n/lab_storage/ydu_lab/Lab/akiruga/curated_oracle/depth/bonn__dense/rgbd_bonn_person_tracking2"
K=np.array([[542.822841,0,315.593520],[0,542.576870,237.756098],[0,0,1.0]]); K[:2,:]*=0.5
gt=np.load(f"{D}/gt_depth.npy"); c2w=np.load(f"{D}/gt_c2w.npy")
H,W=gt.shape[1:]; uu,vv=np.meshgrid(np.arange(W),np.arange(H))
fx,fy,cx,cy=K[0,0],K[1,1],K[0,2],K[1,2]
print("depth",gt.shape,"c2w",c2w.shape)
print("path %.3f m  baseline 0->1 %.4f  0->10 %.4f"%(
  np.linalg.norm(np.diff(c2w[:,:3,3],axis=0),axis=1).sum(),
  np.linalg.norm(c2w[1,:3,3]-c2w[0,:3,3]), np.linalg.norm(c2w[10,:3,3]-c2w[0,:3,3])))
print("frame0 c2w[:3,3] =",np.round(c2w[0,:3,3],4)," (identity-gauged?" ,np.allclose(c2w[0],np.eye(4),atol=1e-6),")")

def pts(i,mode):
    d=gt[i]; m=np.isfinite(d)&(d>1e-3); z=d[m]
    P=np.stack([(uu[m]-cx)/fx*z,(vv[m]-cy)/fy*z,z],1)
    if mode=="identity": return P
    if mode=="opengl": P=P*np.array([1,-1,-1])
    if mode=="w2c":
        R=c2w[i,:3,:3].T; return (R@P.T).T - R@c2w[i,:3,3]
    return (c2w[i,:3,:3]@P.T).T+c2w[i,:3,3]

modes=("identity","opencv","opengl","w2c")
print(f"\n{'pair':9s}"+"".join(f"{m:>22s}" for m in modes))
print(f"{'':9s}"+"".join(f"{'p25 / median':>22s}" for _ in modes))
for i,j in [(0,10),(0,20),(0,30),(0,49),(10,40),(5,45)]:
    cells=[]
    for m in modes:
        A,B=pts(i,m),pts(j,m)
        d,_=cKDTree(A).query(B[::25])
        cells.append(f"{np.percentile(d,25):.4f} / {np.median(d):.4f}")
    print(f"{str((i,j)):9s}"+"".join(f"{c:>22s}" for c in cells))
