import { ref, readonly } from 'vue'

export interface TelemetryMetrics {
    maxSpeedMs: number
    maxHorizontalSpeedMs: number
    maxVerticalSpeedMs: number
    maxAccelerationMs2: number
    maxHorizontalAccelerationMs2: number
    maxVerticalAccelerationMs2: number
    maxCleanAccelerationMs2: number
    maxHorizontalCleanAccelerationMs2: number
    maxVerticalCleanAccelerationMs2: number
    maxHeightM: number
    totalDistanceM: number
    totalTimeS: number
}

export interface TelemetryMetadata {
    filename: string
    metrics: TelemetryMetrics
    aiSummary: string
}

export interface StreamDecodeResult {
    metadata: TelemetryMetadata
    pointsCount: number
}

function concatBytes(left: Uint8Array, right: Uint8Array): Uint8Array {
    if (left.length === 0) return right
    const joined = new Uint8Array(left.length + right.length)
    joined.set(left)
    joined.set(right, left.length)
    return joined
}

export function useTelemetryApi() {
    const isUploading = ref(false)
    const bytesRead = ref(0)
    const error = ref<string | null>(null)

    const streamToWasm = async (
        file: File,
        allocateWasmMemory: (pointsCount: number) => Float32Array
    ): Promise<StreamDecodeResult> => {
        isUploading.value = true
        bytesRead.value = 0
        error.value = null

        try {
            const formData = new FormData()
            formData.append('file', file, file.name)

            const response = await fetch('/analyze/optimized', {
                method: 'POST',
                body: formData,
            })

            if (!response.ok) throw new Error(`API Error: ${response.status}`)
            if (!response.body) throw new Error('Streaming not supported')

            const reader = response.body.getReader()

            let carry = new Uint8Array(0)
            let receivedLength = 0

            let jsonLength: number | null = null
            let metadata: TelemetryMetadata | null = null
            let pointsCount: number | null = null

            let wasmBuffer: Float32Array | null = null
            let floatsWritten = 0

            while (true) {
                const { done, value } = await reader.read()
                if (done) break

                receivedLength += value.byteLength
                bytesRead.value = receivedLength

                let chunk = concatBytes(carry, value)
                let cursor = 0

                if (jsonLength === null) {
                    if (chunk.byteLength < 4) {
                        carry = chunk.slice(cursor)
                        continue
                    }
                    const view = new DataView(chunk.buffer, chunk.byteOffset, 4)
                    jsonLength = view.getUint32(0, true)
                    cursor += 4
                }

                if (jsonLength !== null && metadata === null) {
                    if (jsonLength !== null && metadata === null) {
                        if (chunk.byteLength - cursor < jsonLength) {
                            carry = chunk.slice(cursor)
                            continue
                        }

                        const jsonBytes = chunk.subarray(cursor, cursor + jsonLength)
                        const jsonString = new TextDecoder('utf-8').decode(jsonBytes)

                        // Парсимо сирий JSON (там ключі у snake_case)
                        const rawMetadata = JSON.parse(jsonString)
                        const rawMetrics = rawMetadata.metrics || {}

                        // Мапимо snake_case у camelCase
                        const mappedMetrics: TelemetryMetrics = {
                            maxSpeedMs: rawMetrics.max_speed_ms || 0,
                            maxHorizontalSpeedMs: rawMetrics.max_horizontal_speed_ms || 0,
                            maxVerticalSpeedMs: rawMetrics.max_vertical_speed_ms || 0,
                            maxAccelerationMs2: rawMetrics.max_acceleration_ms2 || 0,
                            maxHorizontalAccelerationMs2: rawMetrics.max_horizontal_acceleration_ms2 || 0,
                            maxVerticalAccelerationMs2: rawMetrics.max_vertical_acceleration_ms2 || 0,
                            maxCleanAccelerationMs2: rawMetrics.max_clean_acceleration_ms2 || 0,
                            maxHorizontalCleanAccelerationMs2: rawMetrics.max_horizontal_clean_acceleration_ms2 || 0,
                            maxVerticalCleanAccelerationMs2: rawMetrics.max_vertical_clean_acceleration_ms2 || 0,
                            maxHeightM: rawMetrics.max_height_m || 0,
                            totalDistanceM: rawMetrics.total_distance_m || 0,
                            totalTimeS: rawMetrics.total_time_s || 0,
                        }

                        // Формуємо фінальний чистий об'єкт метаданих
                        metadata = {
                            filename: rawMetadata.filename || 'telemetry.bin',
                            metrics: mappedMetrics,
                            aiSummary: rawMetadata.ai_summary || ''
                        }

                        cursor += jsonLength
                    }
                }

                if (metadata !== null && pointsCount === null) {
                    if (chunk.byteLength - cursor < 4) {
                        carry = chunk.slice(cursor)
                        continue
                    }
                    const view = new DataView(chunk.buffer, chunk.byteOffset + cursor, 4)
                    pointsCount = view.getUint32(0, true)
                    cursor += 4

                    wasmBuffer = allocateWasmMemory(pointsCount)
                }

                if (wasmBuffer !== null) {
                    const bytesLeft = chunk.byteLength - cursor
                    const completeFloatBytes = bytesLeft - (bytesLeft % 4)

                    if (completeFloatBytes > 0) {
                        const alignedBytes = chunk.slice(cursor, cursor + completeFloatBytes)
                        const asFloats = new Float32Array(alignedBytes.buffer)

                        wasmBuffer.set(asFloats, floatsWritten)
                        floatsWritten += asFloats.length
                        cursor += completeFloatBytes
                    }
                }

                carry = chunk.slice(cursor)
            }

            if (!metadata || pointsCount === null || floatsWritten !== pointsCount * 4) {
                throw new Error('Stream ended prematurely or data is corrupted')
            }

            return { metadata, pointsCount }

        } catch (err) {
            const msg = err instanceof Error ? err.message : 'Unknown streaming error'
            console.error(err)
            error.value = msg
            throw err
        } finally {
            isUploading.value = false
        }
    }

    return {
        isUploading: readonly(isUploading),
        bytesRead: readonly(bytesRead),
        error: readonly(error),
        streamToWasm
    }
}