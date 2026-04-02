#!/usr/bin/env node

import fs from 'node:fs/promises'
import path from 'node:path'

function parseArgs(argv) {
  const defaults = {
    out: 'public/test-data.bin',
    count: 300,
    noise: 0.03
  }

  const args = { ...defaults }

  for (let i = 0; i < argv.length; i++) {
    const arg = argv[i]
    if (arg === '--out' && argv[i + 1]) {
      args.out = argv[++i]
    } else if (arg === '--count' && argv[i + 1]) {
      args.count = Number(argv[++i])
    } else if (arg === '--noise' && argv[i + 1]) {
      args.noise = Number(argv[++i])
    } else if (arg === '--help' || arg === '-h') {
      args.help = true
    }
  }

  return args
}

function usage() {
  console.log('Generate binary test payload for cord optimizer')
  console.log('Format: u32 count + count * [f32 x, f32 y, f32 h, f32 s]')
  console.log('')
  console.log('Usage: node scripts/generate-test-bin.mjs [options]')
  console.log('')
  console.log('Options:')
  console.log('  --out <path>     Output file (default: public/test-data.bin)')
  console.log('  --count <n>      Number of elements (default: 300)')
  console.log('  --noise <value>  Positional noise amplitude (default: 0.03)')
  console.log('  -h, --help       Show this help')
}

function randomNoise(amplitude) {
  return (Math.random() * 2 - 1) * amplitude
}

function generatePoint(i, count, noiseAmp) {
  const t = i / Math.max(1, count - 1)
  const angle = t * Math.PI * 8

  const radius = 3 + 0.8 * Math.sin(t * Math.PI * 3)
  const x = radius * Math.cos(angle) + randomNoise(noiseAmp)
  const y = radius * Math.sin(angle) + randomNoise(noiseAmp)
  const h = t * 8 + Math.sin(t * Math.PI * 6) * 0.6 + randomNoise(noiseAmp * 0.5)

  const dx = -radius * Math.sin(angle)
  const dy = radius * Math.cos(angle)
  const dh = 8 / Math.max(1, count - 1)
  const s = Math.sqrt(dx * dx + dy * dy + dh * dh)

  return { x, y, h, s }
}

async function main() {
  const args = parseArgs(process.argv.slice(2))

  if (args.help) {
    usage()
    return
  }

  if (!Number.isInteger(args.count) || args.count <= 0) {
    throw new Error('--count must be a positive integer')
  }

  if (!Number.isFinite(args.noise) || args.noise < 0) {
    throw new Error('--noise must be a non-negative number')
  }

  const totalBytes = 4 + args.count * 4 * 4
  const buffer = new ArrayBuffer(totalBytes)
  const view = new DataView(buffer)

  view.setUint32(0, args.count, true)

  let offset = 4
  for (let i = 0; i < args.count; i++) {
    const p = generatePoint(i, args.count, args.noise)
    view.setFloat32(offset, p.x, true)
    offset += 4
    view.setFloat32(offset, p.y, true)
    offset += 4
    view.setFloat32(offset, p.h, true)
    offset += 4
    view.setFloat32(offset, p.s, true)
    offset += 4
  }

  const outPath = path.resolve(process.cwd(), args.out)
  await fs.mkdir(path.dirname(outPath), { recursive: true })
  await fs.writeFile(outPath, new Uint8Array(buffer))

  console.log(`Wrote ${args.count} points to ${outPath}`)
  console.log(`Total bytes: ${totalBytes}`)
}

main().catch((error) => {
  console.error(error instanceof Error ? error.message : error)
  process.exitCode = 1
})
