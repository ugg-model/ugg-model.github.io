// Pure frame decoding: one caller-owned buffer is reused for every pointmap.
export function firstFrameCamera(info, data) {
  const pose = info.c2w[0], k = info.intrinsics[0];
  const unit = vector => {
    const norm = Math.hypot(...vector);
    if (!(norm > 0)) throw new Error("Invalid first-frame camera orientation");
    return vector.map(value => value / norm);
  };
  const forward = unit(pose.slice(0,3).map(row => row[2]));
  const up = unit(pose.slice(0,3).map(row => -row[1]));
  const origin = pose.slice(0,3).map(row => row[3]);
  const depths = data.depth.slice(0,info.grid_width*info.grid_height)
    .filter(value => Number.isFinite(value) && value > 0).sort();
  if (!depths.length) throw new Error("First frame has no valid depths");
  const mid = Math.floor(depths.length/2);
  const median = depths.length%2 ? depths[mid] : (depths[mid-1]+depths[mid])/2;
  return {
    position:origin.map((value,i) => value-forward[i]*median*0.40),
    look_at:origin.map((value,i) => value+forward[i]*median), up,
    fov:2*Math.atan(info.height/(2*k[1][1])),
    horizontal_fov:2*Math.atan(info.width/(2*k[0][0])),
    median_depth:median, backoff_fraction:0.40,
  };
}

// IEEE half -> float, exact for every finite/zero/subnormal half.
function halfToFloat(h) {
  const s = (h & 0x8000) ? -1 : 1, e = (h >> 10) & 0x1f, f = h & 0x3ff;
  if (e === 0) return s * f * 5.960464477539063e-8;            // 2^-24
  if (e === 31) return f ? NaN : s * Infinity;
  return s * (1 + f / 1024) * Math.pow(2, e - 15);
}

export function unpackPointmaps(buffer, info) {
  const samples = info.frame_count * info.grid_width * info.grid_height;
  if (info.depth_dtype === "float16") {
    // Published payloads store depth as little-endian float16 (half the bytes; <0.05% error).
    if (buffer.byteLength !== samples * 5) throw new Error("Pointmap payload size mismatch");
    const half = new Uint16Array(buffer, 0, samples), table = new Float32Array(65536), depth = new Float32Array(samples);
    for (let i = 0; i < 65536; i++) table[i] = halfToFloat(i);
    for (let i = 0; i < samples; i++) depth[i] = table[half[i]];
    return {depth, colors: new Uint8Array(buffer, samples * 2, samples * 3)};
  }
  if (buffer.byteLength !== samples * 7) throw new Error("Pointmap payload size mismatch");
  return {depth: new Float32Array(buffer, 0, samples), colors: new Uint8Array(buffer, samples * 4, samples * 3)};
}

export function inverse3(m) {
  const [a,b,c] = m[0], [d,e,f] = m[1], [g,h,i] = m[2];
  const det = a*(e*i-f*h)-b*(d*i-f*g)+c*(d*h-e*g);
  if (!Number.isFinite(det) || Math.abs(det) < 1e-12) throw new Error("Invalid intrinsics");
  return [(e*i-f*h)/det, (c*h-b*i)/det, (b*f-c*e)/det,
    (f*g-d*i)/det, (a*i-c*g)/det, (c*d-a*f)/det,
    (d*h-e*g)/det, (b*g-a*h)/det, (a*e-b*d)/det];
}

const linear = Float32Array.from({length:256}, (_, i) => {
  const value = i/255;
  return value <= 0.04045 ? value/12.92 : ((value+0.055)/1.055)**2.4;
});

export function writePointmap(info, data, frame, positions, colors, maxDepth = Infinity) {
  if (!Number.isInteger(frame) || frame < 0 || frame >= info.frame_count) throw new Error("Invalid frame");
  const n = info.grid_width * info.grid_height, inv = inverse3(info.intrinsics[frame]);
  const pose = info.c2w[frame];
  let count = 0;
  for (let row = 0; row < info.grid_height; row++) {
    for (let column = 0; column < info.grid_width; column++) {
      const index = frame*n + row*info.grid_width + column, depth = data.depth[index];
      if (!(depth > 0) || !Number.isFinite(depth) || depth > maxDepth) continue;
      // Export recovery uses pixel centers (x+0.5,y+0.5), including K's skew.
      const u = column*info.stride+0.5, v = row*info.stride+0.5;
      const x = (inv[0]*u+inv[1]*v+inv[2])*depth;
      const y = (inv[3]*u+inv[4]*v+inv[5])*depth;
      const z = (inv[6]*u+inv[7]*v+inv[8])*depth;
      for (let axis = 0; axis < 3; axis++) {
        positions[count*3+axis] = pose[axis][0]*x+pose[axis][1]*y+pose[axis][2]*z+pose[axis][3];
        colors[count*3+axis] = linear[data.colors[index*3+axis]];
      }
      count++;
    }
  }
  return count;
}
