import { DRIVERS } from './constants.js';
import MONZA_TRACK from './mockTrack.js';

/**
 * Generate initial mock driver state
 * Each driver is placed at a different position along the track
 */
function generateMockDrivers() {
    const totalPoints = MONZA_TRACK.length;

    return DRIVERS.map((driver, index) => {
        // Distribute drivers evenly around the track
        const trackIndex = Math.floor((index / DRIVERS.length) * totalPoints);
        const pos = MONZA_TRACK[trackIndex];

        return {
            id: driver.id,
            abbr: driver.abbr,
            name: driver.name,
            team: driver.team,
            number: driver.number,
            position: index + 1,

            // Location
            x: pos.x,
            y: pos.y,
            trackIndex: trackIndex,

            // Telemetry
            speed: 200 + Math.random() * 150,
            gear: Math.floor(3 + Math.random() * 5),
            rpm: 8000 + Math.random() * 4000,
            throttle: Math.random() * 100,
            brake: Math.random() * 30,
            drs: Math.random() > 0.7,

            // Timing
            lastLap: formatLapTime(80 + Math.random() * 5),
            bestLap: formatLapTime(79 + Math.random() * 3),
            gapToLeader: index === 0 ? null : `+${(index * 1.2 + Math.random()).toFixed(3)}`,
            interval: index === 0 ? null : `+${(0.3 + Math.random() * 2).toFixed(3)}`,

            // Stint
            compound: ['SOFT', 'MEDIUM', 'HARD'][Math.floor(Math.random() * 3)],
            lapNumber: Math.floor(15 + Math.random() * 30),
            pitStops: Math.floor(Math.random() * 3),
        };
    });
}

function formatLapTime(totalSeconds) {
    const minutes = Math.floor(totalSeconds / 60);
    const seconds = (totalSeconds % 60).toFixed(3);
    return `${minutes}:${seconds.padStart(6, '0')}`;
}

/**
 * Simulate a single tick — move drivers along the track
 */
export function simulateTick(drivers) {
    const totalPoints = MONZA_TRACK.length - 1; // Last point = first point

    return drivers.map((driver) => {
        // Speed varies by position on track (faster on straights)
        const speedFactor = 0.08 + Math.random() * 0.12;
        const newTrackIndex = (driver.trackIndex + speedFactor) % totalPoints;
        const floorIndex = Math.floor(newTrackIndex);
        const fraction = newTrackIndex - floorIndex;

        // Interpolate between track points for smooth movement
        const p1 = MONZA_TRACK[floorIndex];
        const p2 = MONZA_TRACK[(floorIndex + 1) % totalPoints];

        const newX = p1.x + (p2.x - p1.x) * fraction;
        const newY = p1.y + (p2.y - p1.y) * fraction;

        // Simulate telemetry variations
        const baseSpeed = 180 + Math.random() * 170;
        const isCorner = floorIndex % 5 < 2;

        return {
            ...driver,
            x: newX,
            y: newY,
            trackIndex: newTrackIndex,
            speed: isCorner ? baseSpeed * 0.6 : baseSpeed,
            gear: isCorner ? Math.floor(2 + Math.random() * 3) : Math.floor(5 + Math.random() * 3),
            rpm: 6000 + Math.random() * 6000,
            throttle: isCorner ? Math.random() * 40 : 70 + Math.random() * 30,
            brake: isCorner ? 40 + Math.random() * 60 : Math.random() * 5,
            drs: !isCorner && Math.random() > 0.6,
        };
    });
}

/**
 * Occasionally shuffle positions to simulate overtakes
 */
export function simulatePositionChanges(drivers) {
    const newDrivers = [...drivers];
    // ~3% chance of a position swap each tick
    if (Math.random() > 0.97) {
        const idx = Math.floor(Math.random() * (newDrivers.length - 1)) + 1;
        const temp = newDrivers[idx].position;
        newDrivers[idx] = { ...newDrivers[idx], position: newDrivers[idx - 1].position };
        newDrivers[idx - 1] = { ...newDrivers[idx - 1], position: temp };

        // Recalculate gaps
        newDrivers.sort((a, b) => a.position - b.position);
        newDrivers.forEach((d, i) => {
            d.gapToLeader = i === 0 ? null : `+${(i * 1.1 + Math.random() * 0.5).toFixed(3)}`;
            d.interval = i === 0 ? null : `+${(0.1 + Math.random() * 1.5).toFixed(3)}`;
        });
    }
    return newDrivers;
}

export const initialMockDrivers = generateMockDrivers();
