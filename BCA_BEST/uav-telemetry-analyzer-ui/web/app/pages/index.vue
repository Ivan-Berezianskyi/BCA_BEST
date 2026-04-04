<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'

const { isReady: isWasmReady, ensureRuntime: ensureWasm, initSession, applyReduction } = useWasmOptimizer()
const { isUploading, bytesRead, error, streamToWasm } = useTelemetryApi()
const { isPlotlyLoaded, ensurePlotly, drawChart, purgeChart } = usePlotly()


const selectedFile = ref<File | null>(null)
const toleranceEpsilon = ref(0.2)
const progressLabel = ref('Awaiting binary input')
const importModalOpen = ref(false)
const chartEl = ref<HTMLElement | null>(null)


const metrics = ref<TelemetryMetrics | null>(null)
const aiSummary = ref<string>('')


const canProcess = computed(() => Boolean(selectedFile.value) && !isUploading.value)
const toleranceLabel = computed(() => `${toleranceEpsilon.value.toFixed(2)} m`)
const selectedFileName = computed(() => selectedFile.value?.name ?? 'No file selected')
const selectedFileSize = computed(() => selectedFile.value ? formatBytes(selectedFile.value.size) : '0 B')

const lockOverlayVisible = computed(() => !metrics.value && !isUploading.value && !importModalOpen.value)

function formatBytes(value: number): string {
  if (value <= 0) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB']
  let unitIndex = 0
  let size = value
  while (size >= 1024 && unitIndex < units.length - 1) {
    size /= 1024
    unitIndex += 1
  }
  return `${size.toFixed(unitIndex === 0 ? 0 : 1)} ${units[unitIndex]}`
}

function openImportModal() {
  importModalOpen.value = true
}

function closeImportModal() {
  importModalOpen.value = false
}

function onFileChange(value: File | null | File[] | undefined) {
  selectedFile.value = Array.isArray(value) ? (value[0] ?? null) : (value ?? null)

  if (selectedFile.value) {
    progressLabel.value = 'File selected. Ready to upload'
  } else {
    progressLabel.value = 'Awaiting binary input'
  }
}

async function processFile() {
  if (!selectedFile.value || isUploading.value) return

  progressLabel.value = 'Streaming to backend and WASM...'

  try {
    const { metadata } = await streamToWasm(selectedFile.value, initSession)

    metrics.value = metadata.metrics
    aiSummary.value = metadata.aiSummary

    await renderTrajectory()

    progressLabel.value = 'Completed'
    closeImportModal()
  } catch (err) {
    progressLabel.value = 'Failed'
    console.error("Помилка обробки:", err)
  }
}

async function renderTrajectory() {
  if (!isWasmReady.value || !chartEl.value || !metrics.value) return

  progressLabel.value = 'Optimizing trajectory...'

  const optimizedFloats = applyReduction(toleranceEpsilon.value)

  await drawChart(chartEl.value, optimizedFloats)

  progressLabel.value = 'Visualization ready'
}

watch(toleranceEpsilon, () => {
  if (metrics.value) {
    renderTrajectory()
  }
})


onMounted(async () => {
  await ensureWasm()
  await ensurePlotly()
})
</script>

<template>
  <ClientOnly>
    <div class="dashboard-shell pb-8">
      <header
        class="mx-auto flex w-full max-w-350 flex-col gap-4 px-4 pt-6 sm:px-6 lg:flex-row lg:items-center lg:justify-between lg:pt-8">
        <div class="flex items-center gap-3">
          <div>
            <p class="text-[2rem] font-extrabold leading-none tracking-tight text-white sm:text-[2.2rem]">UAV Telemetry
              Analyzer</p>
            <p class="text-sm text-(--text-muted)">ArduPilot log parser and 3D visualizer</p>
          </div>
        </div>

        <div class="team-pill">
          <div class="flex h-7 w-7 items-center justify-center rounded-full bg-white/20 text-xs font-bold">BCA</div>
          <div>
            <p class="text-sm font-semibold text-white">BCA TEAM</p>
          </div>
        </div>
      </header>

      <main class="relative mx-auto mt-4 w-full max-w-350 px-4 sm:px-6">
        <div class="glass-stage relative overflow-hidden rounded-3xl border border-white/15">
          <div
            class="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_20%_10%,rgba(57,81,181,0.14),transparent_46%),radial-gradient(circle_at_85%_5%,rgba(17,105,205,0.18),transparent_34%)]" />
          <div ref="chartEl" class="dashboard-plot h-[52vh] min-h-90 w-full sm:min-h-115 lg:h-[68vh]" />
        </div>

        <section class="relative mt-4">
          <div class="grid gap-4 transition-opacity duration-300 lg:grid-cols-4"
            :class="lockOverlayVisible ? 'opacity-70' : 'opacity-100'">
            <UCard class="glass-card min-h-64">
              <template #header>
                <div class="flex items-center justify-between">
                  <h2 class="card-title">Mission Manager and Log Upload</h2>
                </div>
              </template>

              <div class="space-y-4">
                <UButton size="lg"
                  class="w-full rounded-xl! bg-transparent! text-white! ring-1 ring-white/30 hover:bg-white/10!"
                  @click="openImportModal">
                  Upload New Log (.bin)
                </UButton>

                <div class="space-y-2 text-sm">
                  <div class="flex justify-between gap-4 text-(--text-muted)">
                    <span>Current file</span>
                    <span class="max-w-[64%] truncate text-right text-white">{{ selectedFileName }}</span>
                  </div>
                  <div class="flex justify-between gap-4 text-(--text-muted)">
                    <span>Size</span>
                    <span class="text-white">{{ selectedFileSize }}</span>
                  </div>
                  <div class="flex justify-between gap-4 text-(--text-muted)">
                    <span>Status</span>
                    <span class="text-white">{{ progressLabel }}</span>
                  </div>
                  <div class="flex justify-between gap-4 text-(--text-muted)">
                    <span>Duration</span>
                    <span class="text-white">{{ 10 }}</span>
                  </div>
                </div>
              </div>
            </UCard>

            <UCard class="glass-card min-h-64">
              <template #header>
                <h2 class="card-title">Key Metrics</h2>
              </template>

              <div class="space-y-2 text-sm">
                <div class="flex justify-between gap-4 text-(--text-muted)">
                  <span>Total Distance</span>
                  <span class="font-semibold text-white">{{ (metrics?.totalDistanceM || 0).toFixed(2) }} m</span>
                </div>
                <div class="flex justify-between gap-4 text-(--text-muted)">
                  <span>Max Altitude</span>
                  <span class="font-semibold text-white">{{ (metrics?.maxHeightM || 0).toFixed(2) }} m</span>
                </div>
                <div class="flex justify-between gap-4 text-(--text-muted)">
                  <span>Vertical Speed</span>
                  <span class="font-semibold text-white">{{ (metrics?.maxVerticalSpeedMs || 0).toFixed(2) }} m/s</span>
                </div>
                <div class="flex justify-between gap-4 text-(--text-muted)">
                  <span>Horizontal Speed</span>
                  <span class="font-semibold text-white">{{ (metrics?.maxHorizontalSpeedMs || 0).toFixed(2) }}
                    m/s</span>
                </div>
                <div class="flex justify-between gap-4 text-(--text-muted)">
                  <span>Max Speed</span>
                  <span class="font-semibold text-white">{{ (metrics?.maxSpeedMs || 0).toFixed(2) }} m/s</span>
                </div>
                <div class="flex justify-between gap-4 text-(--text-muted)">
                  <span>Max Horizontal Acceleration</span>
                  <span class="font-semibold text-white">{{ (metrics?.maxHorizontalCleanAccelerationMs2 || 0).toFixed(2)
                    }}
                    m/s²</span>
                </div>
                <div class="flex justify-between gap-4 text-(--text-muted)">
                  <span>Max Vertical Acceleration</span>
                  <span class="font-semibold text-white">{{ (metrics?.maxVerticalCleanAccelerationMs2 || 0).toFixed(2)
                    }}
                    m/s²</span>
                </div>
                <div class="flex justify-between gap-4 text-(--text-muted)">
                  <span>Max Acceleration</span>
                  <span class="font-semibold text-white">{{ (metrics?.maxCleanAccelerationMs2 || 0).toFixed(2) }}
                    m/s²</span>
                </div>
                <div class="flex justify-between gap-4 text-(--text-muted)">
                  <span>Bytes streamed</span>
                  <span class="font-semibold text-white">{{ formatBytes(bytesRead) }}</span>
                </div>
              </div>
            </UCard>

            <UCard class="glass-card min-h-64">
              <template #header>
                <h2 class="card-title">Visualization settings</h2>
              </template>

              <div class="space-y-4">
                <div>
                  <div class="mb-2 flex items-center justify-between text-sm text-(--text-muted)">
                    <span>Trajectory by</span>
                    <span class="text-white">speed</span>
                  </div>
                  <div class="flex flex-wrap gap-2">
                    <UBadge class="accent-pill">speed</UBadge>
                  </div>
                </div>

                <div>
                  <div class="mb-2 flex items-center justify-between text-sm text-(--text-muted)">
                    <span>Point reduction</span>
                  </div>
                  <USlider v-model="toleranceEpsilon" :min="0" :max="5" :step="0.01"
                    :disabled="!isWasmReady || isUploading" class="mb-2" />
                  <div class="flex items-center justify-between text-xs text-(--text-muted)">
                    <span>{{ toleranceLabel }}</span>
                  </div>
                </div>
              </div>
            </UCard>

            <UCard class="glass-card min-h-64">
              <template #header>
                <h2 class="card-title">AI Insights and Analytics</h2>
              </template>

              <div class="space-y-3">
                <UButton size="lg"
                  class="w-full justify-between! rounded-xl! bg-transparent! text-white! ring-1 ring-white/30 hover:bg-white/10!"
                  :disabled="!isUploading">
                  <span>Create an AI flight report</span>
                  <span>></span>
                </UButton>
                <UButton size="lg"
                  class="w-full justify-between! rounded-xl! bg-transparent! text-white! ring-1 ring-white/30 hover:bg-white/10!"
                  :disabled="!isUploading">
                  <span>Mathematical justification</span>
                  <span>></span>
                </UButton>
                <div class="mt-4 flex items-center justify-between text-xs text-(--text-muted)">
                  <span>Mission conclusion:</span>
                  <span class="font-semibold" :class="isUploading ? 'text-(--primary-500)' : 'text-(--text-muted)'">
                    {{ isUploading ? 'Mission successful' : 'Awaiting upload' }}
                  </span>
                </div>
              </div>
            </UCard>
          </div>
          <div class="pointer-events-none absolute inset-x-6 bottom-8 z-20 sm:inset-x-12 lg:inset-x-16">
            <Transition appear enter-active-class="transition duration-300 ease-out"
              enter-from-class="opacity-0 translate-y-4 scale-98" enter-to-class="opacity-100 translate-y-0 scale-100"
              leave-active-class="transition duration-220 ease-in"
              leave-from-class="opacity-100 translate-y-0 scale-100" leave-to-class="opacity-0 translate-y-3 scale-99">
              <div v-show="lockOverlayVisible"
                class="pointer-events-auto rounded-2xl border border-white/15 bg-[rgba(11,18,31,0.74)] px-6 py-8 text-center backdrop-blur-xl">
                <p class="text-base font-bold text-white sm:text-xl">Upload a log .bin file to unlock analytics</p>
                <p class="mt-2 text-sm text-(--text-muted)">
                  The system will automatically decompress GPS and IMU data
                </p>
                <UButton class="mt-5 rounded-xl! bg-(--primary-500)! px-8 py-2.5 text-black! hover:bg-(--primary-600)!"
                  @click="openImportModal">
                  Upload Log (.bin) file
                </UButton>
              </div>
            </Transition>
          </div>
        </section>

        <p v-if="error" class="mt-4 rounded-xl border border-red-400/30 bg-red-500/10 px-4 py-3 text-sm text-red-200">
          {{ error }}
        </p>
      </main>

      <Transition enter-active-class="transition duration-200 ease-out" enter-from-class="opacity-0"
        enter-to-class="opacity-100" leave-active-class="transition duration-150 ease-in" leave-from-class="opacity-100"
        leave-to-class="opacity-0">
        <div v-if="importModalOpen"
          class="fixed inset-0 z-50 flex items-start justify-center p-4 pt-16 sm:p-8 sm:pt-20">
          <button class="absolute inset-0 bg-[rgba(5,8,15,0.78)] backdrop-blur-sm" type="button"
            aria-label="Close import modal" @click="closeImportModal" />

          <UCard class="glass-modal relative z-10 w-full max-w-5xl">
            <template #header>
              <div class="flex items-center justify-between gap-3">
                <div>
                  <h2 class="text-3xl font-bold text-white">Import logs</h2>
                  <p class="mt-1 text-sm text-(--text-muted)">Drag and drop a binary log file or choose from disk</p>
                </div>
                <UButton variant="ghost" color="neutral" icon="i-lucide-x" @click="closeImportModal" />
              </div>
            </template>

            <div class="space-y-5">
              <UFileUpload accept=".BIN,.bin,application/octet-stream" :model-value="selectedFile"
                label="Drop ArduPilot .BIN log" description="ArduPilot .bin files up to 50 MB are supported"
                class="upload-zone" @update:model-value="onFileChange" />
              <div class="flex flex-wrap gap-3">
                <UButton :disabled="!canProcess" :loading="isUploading"
                  class="rounded-xl! bg-(--primary-500)! px-6 py-2.5 text-black! hover:bg-(--primary-600)!"
                  @click="processFile">
                  Parse and visualize
                </UButton>

                <UButton variant="outline" color="neutral" class="rounded-xl! px-6 py-2.5" @click="closeImportModal">
                  Close
                </UButton>
              </div>
            </div>
          </UCard>
        </div>
      </Transition>
    </div>
  </ClientOnly>
</template>
