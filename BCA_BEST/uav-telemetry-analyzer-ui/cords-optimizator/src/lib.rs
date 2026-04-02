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

    fn create_vector(&self, element_index: usize) -> Vector {
        let vec_start = (element_index - 1) * 4;
        let vec_end = element_index * 4;

        let x = self.buffer[vec_end] - self.buffer[vec_start];
        let y = self.buffer[vec_end + 1] - self.buffer[vec_start + 1];
        let h = self.buffer[vec_end + 2] - self.buffer[vec_start + 2];

        let mut length = (x * x + y * y + h * h).sqrt();

        if length < 1e-6 { length = 0.0 }

        Vector {
            x: x / length,
            y: y / length,
            h: h / length,
        }
    }

    fn get_product(&self, element_index: usize) -> f32 {
        if element_index <= 1 || element_index >= self.size {
            return 0.0;
        }

        let vector_a = self.create_vector(element_index - 1);
        let vector_b = self.create_vector(element_index);

        return vector_a.x * vector_b.x + vector_a.y * vector_b.y + vector_a.h * vector_b.h;
    }

    pub fn optimize_cords(&self, epsilon: f32) -> Vec<f32> {
        let mut res: Vec<f32> = Vec::new();

        res.extend_from_slice(&self.buffer[0..(POINT_SIZE)]);

        for i in 1..(self.size-1) {
            if self.get_product(i).abs() < epsilon {
                let data_start = i * POINT_SIZE;
                res.extend_from_slice(&self.buffer[data_start..(data_start + POINT_SIZE)]);
            }
        }

        if self.size > 1 {
            res.extend_from_slice(&self.buffer[self.buffer.len()-POINT_SIZE..(self.buffer.len())]);
        }

        return res;
    }
}
