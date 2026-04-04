use wasm_bindgen::prelude::*;

const POINT_SIZE: usize = 4; // x, y, h, s

#[wasm_bindgen(start)]
pub fn init() {
    #[cfg(feature = "console_error_panic_hook")]
    console_error_panic_hook::set_once();
}

#[wasm_bindgen]
pub struct DataSession {
    buffer: Vec<f32>,
    size: usize,
}

fn point_line_distance(p: &[f32], p1: &[f32], p2: &[f32]) -> f32 {
    let dx = p2[0] - p1[0];
    let dy = p2[1] - p1[1];
    let dz = p2[2] - p1[2];
    
    let line_len_sq = dx * dx + dy * dy + dz * dz;

    if line_len_sq == 0.0 {
        let px = p[0] - p1[0];
        let py = p[1] - p1[1];
        let pz = p[2] - p1[2];
        return (px * px + py * py + pz * pz).sqrt();
    }

    let t = ((p[0] - p1[0]) * dx + (p[1] - p1[1]) * dy + (p[2] - p1[2]) * dz) / line_len_sq;
    let t = t.clamp(0.0, 1.0);

    let proj_x = p1[0] + t * dx;
    let proj_y = p1[1] + t * dy;
    let proj_z = p1[2] + t * dz;

    let px = p[0] - proj_x;
    let py = p[1] - proj_y;
    let pz = p[2] - proj_z;

    (px * px + py * py + pz * pz).sqrt()
}

#[wasm_bindgen]
impl DataSession {
    #[wasm_bindgen(constructor)]
    pub fn new(size: usize) -> DataSession {
        DataSession {
            buffer: vec![0.0; size * POINT_SIZE],
            size,
        }
    }

    pub fn ptr(&self) -> *const f32 {
        self.buffer.as_ptr()
    }

    pub fn optimize_cords(&self, epsilon: f32) -> Vec<f32> {
        if self.size <= 2 {
            return self.buffer.clone();
        }

        let mut keep = vec![false; self.size];
        keep[0] = true;
        keep[self.size - 1] = true;

        let mut stack = vec![(0, self.size - 1)];

        while let Some((start_idx, end_idx)) = stack.pop() {
            let mut max_dist = 0.0;
            let mut max_idx = start_idx;

            let p1 = &self.buffer[start_idx * POINT_SIZE..(start_idx + 1) * POINT_SIZE];
            let p2 = &self.buffer[end_idx * POINT_SIZE..(end_idx + 1) * POINT_SIZE];

            for i in (start_idx + 1)..end_idx {
                let p = &self.buffer[i * POINT_SIZE..(i + 1) * POINT_SIZE];
                let dist = point_line_distance(p, p1, p2);

                if dist > max_dist {
                    max_dist = dist;
                    max_idx = i;
                }
            }

            if max_dist > epsilon {
                keep[max_idx] = true;
                stack.push((start_idx, max_idx));
                stack.push((max_idx, end_idx));
            }
        }

        let mut res = Vec::with_capacity(self.size * POINT_SIZE);
        for i in 0..self.size {
            if keep[i] {
                let start = i * POINT_SIZE;
                res.extend_from_slice(&self.buffer[start..(start + POINT_SIZE)]);
            }
        }

        res
    }
}