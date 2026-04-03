use wasm_bindgen::prelude::*;

const POINT_SIZE: usize = 4;

#[wasm_bindgen(start)]
pub fn init() {
    #[cfg(feature = "console_error_panic_hook")]
    console_error_panic_hook::set_once();
}

struct Vector {
    pub x: f32,
    pub y: f32,
    pub h: f32,
}

#[wasm_bindgen]
pub struct DataSession {
    buffer: Vec<f32>,
    size: usize,
}

#[wasm_bindgen]
impl DataSession {
    #[wasm_bindgen(constructor)]
    pub fn new(size: usize) -> DataSession {
        DataSession {
            buffer: vec![0.0; size * POINT_SIZE],
            size: size,
        }
    }

    pub fn ptr(&self) -> *const f32 {
        self.buffer.as_ptr()
    }

    fn create_vector(&self, start_idx: usize, end_idx: usize) -> Vector {
        let vec_start = start_idx * POINT_SIZE;
        let vec_end = end_idx * POINT_SIZE;

        let x = self.buffer[vec_end] - self.buffer[vec_start];
        let y = self.buffer[vec_end + 1] - self.buffer[vec_start + 1];
        let h = self.buffer[vec_end + 2] - self.buffer[vec_start + 2];

        let length = (x * x + y * y + h * h).sqrt();

        if length < 1e-6 {
            return Vector {
                x: 0.0,
                y: 0.0,
                h: 0.0,
            };
        }

        Vector {
            x: x / length,
            y: y / length,
            h: h / length,
        }
    }

    fn get_product(&self, vector_a: &Vector, vector_b: &Vector) -> f32 {
        return vector_a.x * vector_b.x + vector_a.y * vector_b.y + vector_a.h * vector_b.h;
    }

    pub fn optimize_cords(&self, epsilon: f32) -> Vec<f32> {
        let mut res: Vec<f32> = Vec::new();

        if self.size < 3 {
            res.extend_from_slice(&self.buffer);
            return res;
        }

        // Зберігаємо першу точку
        res.extend_from_slice(&self.buffer[0..POINT_SIZE]);

        let mut last_kept_idx = 0; // індекс останньої збереженої точки
        let mut v_prev = self.create_vector(0, 1);

        for i in 1..self.size {
            // Вектор від останньої збереженої точки до поточної
            let v_curr = self.create_vector(last_kept_idx, i);

            if v_curr.x == 0.0 && v_curr.y == 0.0 && v_curr.h == 0.0 {
                continue;
            }

            let product = self.get_product(&v_prev, &v_curr);

            let is_last = i == self.size - 1;

            if product <= epsilon || is_last {
                let start = i * POINT_SIZE;
                res.extend_from_slice(&self.buffer[start..(start + POINT_SIZE)]);

                last_kept_idx = i;
                v_prev = v_curr;
            }
        }

        res
    }
}
