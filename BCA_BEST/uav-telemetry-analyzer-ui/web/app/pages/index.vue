<script setup lang="ts">
import initWasm, { DataSession } from 'cords-optimizator'

type PlotlyModule = {
  newPlot: (el: HTMLElement, data: unknown[], layout: Record<string, unknown>, config: Record<string, unknown>) => Promise<unknown>
  purge: (el: HTMLElement) => void
}

const selectedFile = ref<File | null>(null)
const processing = ref(false)
const epsilon = ref(0.985)
const progressLabel = ref('Awaiting binary input')
const parsedPoints = ref(0)
const optimizedPoints = ref(0)
const bytesRead = ref(0)
const errorMessage = ref('')
const chartEl = ref<HTMLElement | null>(null)

let plotly: PlotlyModule | null = null
let wasmExports: Awaited<ReturnType<typeof initWasm>> | null = null

const canProcess = computed(() => Boolean(selectedFile.value) && !processing.value)

function onFileChange(value: File | null | File[] | undefined) {
  if (Array.isArray(value)) {
    selectedFile.value = value[0] ?? null
    return
  }
  selectedFile.value = value ?? null
}

async function ensureRuntime() {
  if (!wasmExports) {
    wasmExports = await initWasm()
  }

  if (!plotly) {
    const mod = await import('plotly.js-dist-min')
    plotly = mod.default as PlotlyModule
  }
}

async function createLoopbackResponse(file: File): Promise<Response> {
  const bytes = new Uint8Array(await file.arrayBuffer())
  let offset = 0

  const stream = new ReadableStream<Uint8Array>({
    pull(controller) {
      if (offset >= bytes.length) {
        controller.close()
        return
      }

      const chunkSize = Math.min(bytes.length - offset, 2048 + Math.floor(Math.random() * 4096))
      const next = bytes.subarray(offset, offset + chunkSize)
      offset += chunkSize
      controller.enqueue(next)
    }
  })

  return new Response(stream, {
    headers: {
      'content-type': 'application/octet-stream'
    }
  })
}

function concatBytes(left: Uint8Array, right: Uint8Array): Uint8Array {
  if (left.length === 0) {
    return right.slice()
  }

  const joined = new Uint8Array(left.length + right.length)
  joined.set(left)
  joined.set(right, left.length)
  return joined
}

function unpackOptimizedData(flattened: Float32Array) {
  if (flattened.length % 4 !== 0) {
    throw new Error('Optimizer output is corrupted: element stride must be 4 floats')
  }

  const pointsCount = flattened.length / 4
  const x = new Array<number>(pointsCount)
  const y = new Array<number>(pointsCount)
  const z = new Array<number>(pointsCount)
  const speed = new Array<number>(pointsCount)

  for (let i = 0; i < pointsCount; i++) {
    const start = i * 4
    x[i] = flattened[start]!
    y[i] = flattened[start + 1]!
    z[i] = flattened[start + 2]!
    speed[i] = flattened[start + 3]!
  }

  return { x, y, z, speed, pointsCount }
}

function getMinMax(values: number[]) {
  if (values.length === 0) {
    return { min: 0, max: 0 }
  }

  let min = values[0]!
  let max = values[0]!

  for (let i = 1; i < values.length; i++) {
    const value = values[i]!
    if (value < min) min = value
    if (value > max) max = value
  }

  return { min, max }
}

async function drawChart(flattened: Float32Array) {
  if (!chartEl.value || !plotly) {
    return
  }

  const { x, y, z, speed } = unpackOptimizedData(flattened)
  const { min: minSpeed, max: maxSpeed } = getMinMax(speed)

  await plotly.newPlot(
    chartEl.value,
    [
      {
        type: 'scatter3d',
        mode: 'lines+markers',
        x,
        y,
        z,
        marker: {
          size: 4,
          color: speed,
          colorscale: 'Turbo',
          cmin: minSpeed,
          cmax: maxSpeed,
          colorbar: { title: 'Speed (s)' }
        },
        line: {
          color: speed,
          colorscale: 'Turbo',
          cmin: minSpeed,
          cmax: maxSpeed,
          width: 5
        },
        customdata: speed,
        hovertemplate: 'x: %{x:.4f}<br>y: %{y:.4f}<br>h: %{z:.4f}<br>s: %{customdata:.4f}<extra></extra>'
      }
    ],
    {
      title: 'Optimized trajectory',
      margin: { l: 0, r: 0, b: 0, t: 48 },
      paper_bgcolor: 'rgba(0,0,0,0)',
      plot_bgcolor: 'rgba(0,0,0,0)',
      scene: {
        xaxis: { title: 'X' },
        yaxis: { title: 'Y' },
        zaxis: { title: 'H' }
      }
    },
    {
      responsive: true,
      displaylogo: false
    }
  )
}

async function processFile() {
  if (!selectedFile.value) {
    return
  }

  processing.value = true
  errorMessage.value = ''
  progressLabel.value = 'Preparing loopback backend stream'
  parsedPoints.value = 0
  optimizedPoints.value = 0
  bytesRead.value = 0

  let session: DataSession | null = null

  try {
    await ensureRuntime()

    const response = await createLoopbackResponse(selectedFile.value)
    if (!response.body) {
      throw new Error('Readable stream is not available in this browser')
    }

    const reader = response.body.getReader()

    let carry = new Uint8Array(0)
    let totalElements: number | null = null
    let expectedFloatCount = 0
    let floatsWritten = 0
    let wasmFloatBuffer: Float32Array | null = null

    progressLabel.value = 'Streaming binary payload and writing into WASM memory'

    while (true) {
      const { done, value } = await reader.read()
      if (done) {
        break
      }

      bytesRead.value += value.byteLength
      let chunk = concatBytes(carry, value)
      let cursor = 0

      if (totalElements === null) {
        if (chunk.byteLength < 4) {
          carry = chunk.slice()
          continue
        }

        const headerView = new DataView(chunk.buffer, chunk.byteOffset, 4)
        totalElements = headerView.getUint32(0, true)
        expectedFloatCount = totalElements * 4
        session = new DataSession(totalElements)

        const ptr = session.ptr()
        wasmFloatBuffer = new Float32Array(wasmExports!.memory.buffer, ptr, expectedFloatCount)
        parsedPoints.value = totalElements
        cursor = 4
      }

      const bytesForFloats = chunk.byteLength - cursor
      const completeFloatBytes = bytesForFloats - (bytesForFloats % 4)

      if (completeFloatBytes > 0) {
        const asFloats = new Float32Array(chunk.buffer, chunk.byteOffset + cursor, completeFloatBytes / 4)

        if (!wasmFloatBuffer) {
          throw new Error('WASM memory buffer was not allocated')
        }

        wasmFloatBuffer.set(asFloats, floatsWritten)
        floatsWritten += asFloats.length
        cursor += completeFloatBytes
      }

      carry = chunk.slice(cursor)
    }

    if (!session) {
      throw new Error('No header found in stream (first 4 bytes with u32 count are required)')
    }

    if (carry.byteLength !== 0) {
      throw new Error('Stream ended with incomplete float bytes')
    }

    if (floatsWritten !== expectedFloatCount) {
      throw new Error(`Unexpected payload length. Expected ${expectedFloatCount} floats, received ${floatsWritten}`)
    }

    progressLabel.value = 'Running optimizer in WASM and rendering plot'

    const optimized = session.optimize_cords(epsilon.value)
    optimizedPoints.value = optimized.length / 4
    await drawChart(optimized)
    progressLabel.value = 'Completed'
  } catch (error) {
    progressLabel.value = 'Failed'
    errorMessage.value = error instanceof Error ? error.message : 'Unknown processing error'
  } finally {
    session?.free()
    processing.value = false
  }
}

onBeforeUnmount(() => {
  if (chartEl.value && plotly) {
    plotly.purge(chartEl.value)
  }
})
</script>

<template>
  <ClientOnly>
    <UContainer>
      <section class="hero">
        <p>Cord Optimizer Pipeline</p>
        <h1>Binary stream to optimized 3D trajectory</h1>
        <p>
          Input format: first 4 bytes as <strong>u32 count</strong>, then repeating
          <strong>[f32 x, f32 y, f32 h, f32 s]</strong> blocks. The page emulates backend loopback and streams data directly into WASM memory.
        </p>
      </section>

      <UCard class="panel" variant="subtle">
        <template #header>
          <div>
            <h2>Input</h2>
            <UBadge :label="processing ? 'Processing' : 'Idle'" :color="processing ? 'info' : 'neutral'" variant="subtle" />
          </div>
        </template>

        <div class="panel__body">
          <UFileUpload
            accept=".bin,application/octet-stream"
            :model-value="selectedFile"
            label="Drop .bin payload"
            description="Structure: u32 totalElements + totalElements * 4 f32 values"
            class="upload"
            @update:model-value="onFileChange"
          />

          <div class="epsilon-row">
            <div>
              <p class="epsilon-row__label">Optimization epsilon</p>
              <p class="epsilon-row__value">{{ epsilon.toFixed(3) }}</p>
            </div>
            <USlider v-model="epsilon" :min="0" :max="1" :step="0.01" tooltip class="epsilon-row__slider" />
          </div>

          <UButton :disabled="!canProcess" :loading="processing" size="lg" @click="processFile">
            Process Binary Data
          </UButton>
        </div>

        <template #footer>
          <div class="stats">
            <UBadge color="neutral" variant="outline">{{ progressLabel }}</UBadge>
            <UBadge color="neutral" variant="outline">bytes read: {{ bytesRead }}</UBadge>
            <UBadge color="success" variant="outline">input points: {{ parsedPoints }}</UBadge>
            <UBadge color="info" variant="outline">optimized points: {{ optimizedPoints }}</UBadge>
          </div>
          <p v-if="errorMessage" class="error">{{ errorMessage }}</p>
        </template>
      </UCard>

      <UCard class="panel chart-panel" variant="outline">
        <template #header>
          <h2>Plotly 3D Scatter + Path</h2>
        </template>
        <div ref="chartEl" class="plot"></div>
      </UCard>
    </UContainer>
  </ClientOnly>
</template>
