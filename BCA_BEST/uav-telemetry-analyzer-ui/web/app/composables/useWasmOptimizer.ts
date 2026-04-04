import { ref, shallowRef, readonly } from 'vue'
import initWasm, { DataSession } from 'cords-optimizator'

export function useWasmOptimizer() {
  const wasmModule = shallowRef<Awaited<ReturnType<typeof initWasm>> | null>(null)
  const activeSession = shallowRef<DataSession | null>(null)
  const isReady = ref(false)

  const ensureRuntime = async () => {
    if (!wasmModule.value) {
      wasmModule.value = await initWasm()
      isReady.value = true
    }
  }

  const initSession = (pointsCount: number): Float32Array => {
    if (!wasmModule.value) {
      throw new Error('WASM runtime is not initialized. Call ensureRuntime first.')
    }

    releaseSession()

    const session = new DataSession(pointsCount)
    activeSession.value = session

    const ptr = session.ptr()
    const expectedFloatCount = pointsCount * 4

    const floatBuffer = new Float32Array(
      wasmModule.value.memory.buffer,
      ptr,
      expectedFloatCount
    )

    return floatBuffer
  }

  const applyReduction = (epsilonMeters: number): Float32Array => {
    const session = activeSession.value
    if (!session) {
      throw new Error('No active WASM session. Upload and parse data first.')
    }
    return session.optimize_cords(epsilonMeters)
  }

  const releaseSession = () => {
    if (activeSession.value) {
      activeSession.value.free()
      activeSession.value = null
    }
  }

  return {
    isReady: readonly(isReady),
    ensureRuntime,
    initSession,
    applyReduction,
    releaseSession
  }
}