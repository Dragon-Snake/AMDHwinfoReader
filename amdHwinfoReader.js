/**
 * Node.js AMD HWiNFO Reader
 * Polls HWiNFO shared memory and prints stats to console
 */

const POLL_INTERVAL = 500; // ms
const MAX_POLLS = 10; // 5 seconds total

let polls = 0;

// Simulate hwinfo window object (replace with actual HWiNFO node access if available)
const hwinfo = require('hwinfo-node'); // hypothetical Node package, see note below

function getAMDStats() {
    // Replace this logic with actual Node HWiNFO reading API
    // Example structure (mocked)
    const gpuNode = hwinfo['GPU0'] || hwinfo['GPU 0'] || hwinfo['GPU'];
    if (!gpuNode) return { gpuUsage: 0, vramUsage: 0, gpuTemp: 0, gpuPower: 0 };

    return {
        gpuUsage: gpuNode['GPU Utilization']?.valueraw || 0,
        vramUsage: gpuNode['GPU Memory Usage']?.valueraw || 0,
        gpuTemp: gpuNode['GPU Temperature']?.valueraw || 0,
        gpuPower: gpuNode['GPU Power']?.valueraw || 0
    };
}

const interval = setInterval(() => {
    const stats = getAMDStats();
    console.log(JSON.stringify(stats));
    polls++;
    if (polls >= MAX_POLLS) {
        clearInterval(interval);
        const success = stats.gpuUsage > 0;
        if (success) {
            console.log('AMD HWiNFO Reader test SUCCESS: GPU values updating.');
            process.exit(0);
        } else {
            console.log('AMD HWiNFO Reader test FAILED: GPU values not updating.');
            process.exit(1);
        }
    }
}, POLL_INTERVAL);
