/**
 * AMD HWiNFO Reader for Node.js
 * This version polls HWiNFO via `window.hwinfo` if available (browser) or simulates Node polling.
 * For Node, it writes current stats to stdout so the batch can read them.
 */

(function() {
    const POLL_INTERVAL = 500; // ms
    const MAX_POLLS = 10;      // poll 10 times (5 sec)

    let polls = 0;

    // Default stats object
    const amdStats = {
        gpuUsage: 0,
        vramUsage: 0,
        gpuTemp: 0,
        gpuPower: 0
    };

    function getStats() {
        // Browser version
        if (typeof window !== 'undefined' && window.hwinfo) {
            const hwinfoData = window.hwinfo;
            const gpuNode = hwinfoData['GPU0'] || hwinfoData['GPU 0'] || hwinfoData['GPU'];
            if (gpuNode) {
                amdStats.gpuUsage = gpuNode['GPU Utilization']?.valueraw || 0;
                amdStats.vramUsage = gpuNode['GPU Memory Usage']?.valueraw || 0;
                amdStats.gpuTemp = gpuNode['GPU Temperature']?.valueraw || 0;
                amdStats.gpuPower = gpuNode['GPU Power']?.valueraw || 0;
            }
        }
        // Node version: just simulate (since Node cannot access HWiNFO without helper)
        else if (typeof process !== 'undefined') {
            // For now, output 0; this will at least let batch run and parse
            amdStats.gpuUsage = 0;
            amdStats.vramUsage = 0;
            amdStats.gpuTemp = 0;
            amdStats.gpuPower = 0;
        }
        return amdStats;
    }

    function pollAndPrint() {
        const stats = getStats();
        console.log(JSON.stringify(stats)); // batch can read this
        polls++;
        if (polls >= MAX_POLLS) process.exit(0);
    }

    setInterval(pollAndPrint, POLL_INTERVAL);
})();
