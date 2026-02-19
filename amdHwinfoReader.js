/**
 * AMD HWiNFO Reader for Wallpaper Engine
 * 
 * This script reads AMD GPU metrics from HWiNFO Shared Memory
 * and exposes them as a global object `window.amdStats`.
 * 
 * Metrics provided:
 * - gpuUsage: GPU Core Load (%) 
 * - vramUsage: GPU Memory Usage (%) 
 * - gpuTemp: GPU Temperature (°C)
 * - gpuPower: GPU Power (W)
 * 
 * Requirements:
 * - HWiNFO installed with Shared Memory enabled
 * - AMD GPU present
 * 
 * Usage:
 * 1. Include this script in your wallpaper folder:
 *      <script src="amdHwinfoReader.js"></script>
 * 2. Read metrics from `window.amdStats`:
 *      const gpuUsage = window.amdStats.gpuUsage;
 */

window.amdStats = {
    gpuUsage: 0,
    vramUsage: 0,
    gpuTemp: 0,
    gpuPower: 0
};

// Poll interval in milliseconds
const POLL_INTERVAL = 500; // 0.5s

// Helper function to safely get a sensor value
function getSensorValue(hwinfoData, sensorLabel) {
    if (!hwinfoData) return 0;

    // HWiNFO exposes multiple nodes/adapters; pick first AMD GPU
    // This assumes HWiNFO adapter 0 is the RX 6750 XT
    const gpuNode = hwinfoData['GPU0'] || hwinfoData['GPU 0'] || hwinfoData['GPU'];
    if (!gpuNode) return 0;

    const sensor = gpuNode[sensorLabel];
    if (!sensor) return 0;

    return sensor.valueraw || 0;
}

// Main update loop
function updateAMDStats() {
    try {
        // HWiNFO exposes data via window.hwinfo (PerformanceMonitor style)
        const hwinfoData = window.hwinfo || null;
        if (!hwinfoData) {
            // no HWiNFO detected
            window.amdStats.gpuUsage = 0;
            window.amdStats.vramUsage = 0;
            window.amdStats.gpuTemp = 0;
            window.amdStats.gpuPower = 0;
            return;
        }

        // Update global AMD stats
        window.amdStats.gpuUsage = getSensorValue(hwinfoData, 'GPU Utilization');
        window.amdStats.vramUsage = getSensorValue(hwinfoData, 'GPU Memory Usage');
        window.amdStats.gpuTemp = getSensorValue(hwinfoData, 'GPU Temperature');
        window.amdStats.gpuPower = getSensorValue(hwinfoData, 'GPU Power');

    } catch (err) {
        console.error("AMD HWiNFO Reader error:", err);
    }
}

// Start polling
setInterval(updateAMDStats, POLL_INTERVAL);