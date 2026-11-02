import numpy as np
from first_frame_camera import first_frame_camera
pose=np.array([[0,0,1,10],[1,0,0,20],[0,1,0,30],[0,0,0,1]],dtype=float)
k=np.array([[2,0,2],[0,2,1],[0,0,1]],dtype=float)
points=np.array([[12,20,30],[14,20,30],[16,20,30],[18,20,30]],dtype=float)
before=points.copy()
view=first_frame_camera(points,pose,k,width=4,height=2)
np.testing.assert_array_equal(view['position'],[8,20,30])
np.testing.assert_array_equal(view['look_at'],[15,20,30])
np.testing.assert_array_equal(view['up'],[0,0,-1])
np.testing.assert_array_equal(points,before)
assert view['median_depth']==5
assert view['fov']==2*np.arctan(.5)
assert view['horizontal_fov']==np.pi/2
try:
 first_frame_camera(np.array([[8,20,30]]),pose,k)
 raise AssertionError('Accepted first-frame points behind the camera')
except ValueError:
 pass
print('PASS: first-camera axes, median depth, exact 40% axial setback, calibration and unchanged geometry')
