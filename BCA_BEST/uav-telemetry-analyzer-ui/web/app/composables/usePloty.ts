import { ref, shallowRef, readonly } from 'vue'

type PlotlyModule = {
    newPlot: (el: HTMLElement, data: any[], layout: any, config: any) => Promise<any>
    purge: (el: HTMLElement) => void
}

function unpackOptimizedData(flattened: Float32Array) {
    const pointsCount = flattened.length / 4
    const x = new Float32Array(pointsCount)
    const y = new Float32Array(pointsCount)
    const z = new Float32Array(pointsCount)
    const speed = new Float32Array(pointsCount)

    let minSpeed = Infinity
    let maxSpeed = -Infinity

    for (let i = 0; i < pointsCount; i++) {
        const start = i * 4
        x[i] = flattened[start]!
        y[i] = flattened[start + 1]!
        z[i] = flattened[start + 2]!

        const currentSpeed = flattened[start + 3]!
        speed[i] = currentSpeed

        if (currentSpeed < minSpeed) minSpeed = currentSpeed
        if (currentSpeed > maxSpeed) maxSpeed = currentSpeed
    }

    if (minSpeed === Infinity) {
        minSpeed = 0
        maxSpeed = 0
    }

    return { x, y, z, speed, minSpeed, maxSpeed }
}

export function usePlotly() {
    const isPlotlyLoaded = ref(false)
    const plotlyModule = shallowRef<PlotlyModule | null>(null)

    const ensurePlotly = async () => {
        if (!plotlyModule.value) {
            const mod = await import('plotly.js-dist-min')
            plotlyModule.value = mod.default as PlotlyModule
            isPlotlyLoaded.value = true
        }
    }

    const drawChart = async (el: HTMLElement, flattenedData: Float32Array) => {
        if (!plotlyModule.value) {
            throw new Error('Plotly is not loaded. Call ensurePlotly first.')
        }

        const { x, y, z, speed, minSpeed, maxSpeed } = unpackOptimizedData(flattenedData)

        const startPoint = {
            x: [x[0]],
            y: [y[0]],
            z: [z[0]],
            s: speed[0]
        };

        await plotlyModule.value.newPlot(
            el,
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
                        colorbar: { title: 'Speed (m/s)' }
                    },
                    line: {
                        color: speed,
                        colorscale: 'Turbo',
                        cmin: minSpeed,
                        cmax: maxSpeed,
                        width: 5
                    },
                    customdata: speed,
                    hovertemplate: 'E: %{x:.2f}m<br>N: %{y:.2f}m<br>H: %{z:.2f}m<br>V: %{customdata:.2f}m/s<extra></extra>'
                },
                {
                    type: 'scatter3d',
                    mode: 'markers', // Тільки маркер, без лінії
                    name: 'Start',
                    x: startPoint.x,
                    y: startPoint.y,
                    z: startPoint.z,
                    marker: {
                        size: 8,
                        color: '#FF5F1F',
                        symbol: 'circle',
                        line: {
                            color: 'white',
                            width: 2
                        },
                        opacity: 1
                    },
                    customdata: [startPoint.s],
                    hovertemplate: '<b>START POINT</b><br>' +
                        'E: %{x:.2f}m<br>N: %{y:.2f}m<br>H: %{z:.2f}m<extra></extra>',
                    showlegend: false
                }
            ],
            {
                margin: { l: 0, r: 0, b: 0, t: 0 },
                paper_bgcolor: 'rgba(0,0,0,0)',
                plot_bgcolor: 'rgba(0,0,0,0)',
                showlegend: false,
                scene: {
                    bgcolor: 'rgba(0,0,0,0)',
                    aspectmode: 'auto',
                    xaxis: {
                        title: 'East (m)',
                        color: 'rgba(233,242,255,0.55)',
                        gridcolor: 'rgba(233,242,255,0.28)',
                        zerolinecolor: 'rgba(233,242,255,0.2)'
                    },
                    yaxis: {
                        title: 'North (m)',
                        color: 'rgba(233,242,255,0.55)',
                        gridcolor: 'rgba(233,242,255,0.28)',
                        zerolinecolor: 'rgba(233,242,255,0.2)'
                    },
                    zaxis: {
                        title: 'Height (m)',
                        color: 'rgba(233,242,255,0.55)',
                        gridcolor: 'rgba(233,242,255,0.28)',
                        zerolinecolor: 'rgba(233,242,255,0.2)'
                    }
                }
            },
            {
                responsive: true,
                displaylogo: false,
                displayModeBar: false
            }
        )
    }


    const purgeChart = (el: HTMLElement) => {
        if (plotlyModule.value && el) {
            plotlyModule.value.purge(el)
        }
    }

    return {
        isPlotlyLoaded: readonly(isPlotlyLoaded),
        ensurePlotly,
        drawChart,
        purgeChart
    }
}