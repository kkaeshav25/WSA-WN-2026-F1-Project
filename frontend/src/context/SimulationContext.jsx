import { createContext, useContext, useState, useRef, useEffect } from 'react';
import useRaceData from '../hooks/useOpenF1Data.js';
import usePlaybackController from '../hooks/usePlaybackController.js';

const SimulationContext = createContext(null);

/**
 * SimulationProvider — wraps the app with race data and playback state
 *
 * Adds smooth lerp interpolation: playback provides target positions at ~4Hz,
 * while a requestAnimationFrame loop interpolates at 60fps.
 * Also passes through track status and DNF info.
 */
export function SimulationProvider({ children }) {
    const { data, isLoading, error } = useRaceData();
    const playback = usePlaybackController(
        data?.timeline, data?.lapData, data?.raceEvents, data?.dnf
    );
    const [selectedDriverNumber, setSelectedDriverNumber] = useState(1);

    // ── Smooth interpolation layer ──
    const smoothStatesRef = useRef(new Map());
    const [smoothStates, setSmoothStates] = useState(new Map());
    const lerpFrameRef = useRef(null);

    useEffect(() => {
        const LERP_RATE = 0.15;

        const animate = () => {
            const targets = playback.driverStates;
            const smooth = smoothStatesRef.current;
            let changed = false;

            // Remove drivers that are no longer in targets (retired)
            for (const key of smooth.keys()) {
                if (!targets.has(key)) {
                    smooth.delete(key);
                    changed = true;
                }
            }

            for (const [drvNum, target] of targets) {
                const current = smooth.get(drvNum);

                if (!current) {
                    smooth.set(drvNum, { ...target });
                    changed = true;
                } else {
                    if (target.x != null && current.x != null) {
                        const newX = current.x + (target.x - current.x) * LERP_RATE;
                        const newY = current.y + (target.y - current.y) * LERP_RATE;
                        if (Math.abs(newX - current.x) > 0.01 || Math.abs(newY - current.y) > 0.01) {
                            current.x = newX;
                            current.y = newY;
                            changed = true;
                        }
                    } else if (target.x != null) {
                        current.x = target.x;
                        current.y = target.y;
                        changed = true;
                    }

                    if (target.speed != null) {
                        current.speed = current.speed + (target.speed - current.speed) * LERP_RATE;
                        current.rpm = current.rpm + (target.rpm - current.rpm) * LERP_RATE;
                        current.throttle = current.throttle + (target.throttle - current.throttle) * 0.2;
                    }

                    current.gear = target.gear;
                    current.brake = target.brake;
                    current.drs = target.drs;
                    current.lap = target.lap;
                }
            }

            if (changed) {
                smoothStatesRef.current = new Map(smooth);
                setSmoothStates(new Map(smooth));
            }

            lerpFrameRef.current = requestAnimationFrame(animate);
        };

        lerpFrameRef.current = requestAnimationFrame(animate);
        return () => { if (lerpFrameRef.current) cancelAnimationFrame(lerpFrameRef.current); };
    }, [playback.driverStates]);

    // ── Current weather based on playback time ──
    const weatherData = data?.weather || [];
    let currentWeather = weatherData[0] || null;
    const ct = playback.currentTime;
    for (let i = weatherData.length - 1; i >= 0; i--) {
        if (weatherData[i].t <= ct) {
            currentWeather = weatherData[i];
            break;
        }
    }

    // ── Sector timing & compound tracking ──
    const detailedLaps = data?.detailedLaps || [];
    const drivers = data?.drivers || new Map();
    const currentLap = playback.currentLap;

    // Compute: laps completed so far (within current session time)
    const completedLaps = detailedLaps.filter(l =>
        l.lap_end_time != null && l.lap_end_time <= ct
    );

    // Overall best sectors across ALL drivers
    const overallBestS1 = Math.min(...completedLaps.filter(l => l.sector1_time).map(l => l.sector1_time), Infinity);
    const overallBestS2 = Math.min(...completedLaps.filter(l => l.sector2_time).map(l => l.sector2_time), Infinity);
    const overallBestS3 = Math.min(...completedLaps.filter(l => l.sector3_time).map(l => l.sector3_time), Infinity);

    // Per-driver data: best lap, best sectors, current compound, sector colors
    const driverLapInfo = new Map();
    const allDriverNums = [...drivers.keys()];

    for (const drvNum of allDriverNums) {
        const drvLaps = completedLaps.filter(l => l.driver_number === drvNum);
        const validLaps = drvLaps.filter(l => l.lap_time != null && l.lap_time > 0);

        const bestLapTime = validLaps.length > 0
            ? Math.min(...validLaps.map(l => l.lap_time))
            : null;
        const bestLap = validLaps.find(l => l.lap_time === bestLapTime) || null;

        // Personal best sectors
        const pbS1 = Math.min(...drvLaps.filter(l => l.sector1_time).map(l => l.sector1_time), Infinity);
        const pbS2 = Math.min(...drvLaps.filter(l => l.sector2_time).map(l => l.sector2_time), Infinity);
        const pbS3 = Math.min(...drvLaps.filter(l => l.sector3_time).map(l => l.sector3_time), Infinity);

        // Latest completed lap for this driver
        const latestLap = drvLaps.length > 0 ? drvLaps[drvLaps.length - 1] : null;

        // Current lap (in progress) — the one that hasn't ended yet
        const currentDrvLaps = detailedLaps.filter(l =>
            l.driver_number === drvNum && l.lap_start_time != null && l.lap_start_time <= ct
        );
        const inProgressLap = currentDrvLaps.length > 0 ? currentDrvLaps[currentDrvLaps.length - 1] : null;

        // Sector colors for latest completed lap
        const sectorColors = [null, null, null];
        if (latestLap) {
            for (let s = 0; s < 3; s++) {
                const sectorKey = `sector${s + 1}_time`;
                const sTime = latestLap[sectorKey];
                if (sTime == null) continue;

                const overallBest = [overallBestS1, overallBestS2, overallBestS3][s];
                const personalBest = [pbS1, pbS2, pbS3][s];

                if (sTime <= overallBest) {
                    sectorColors[s] = 'purple'; // Overall best
                } else if (sTime <= personalBest) {
                    sectorColors[s] = 'green'; // Personal best
                } else {
                    sectorColors[s] = 'yellow'; // No improvement
                }
            }
        }

        // Current compound — from latest lap
        const compound = inProgressLap?.compound || latestLap?.compound || 'UNKNOWN';
        const tyreLife = inProgressLap?.tyre_life || latestLap?.tyre_life || 0;

        // Current lap elapsed time
        const lapStartTime = inProgressLap?.lap_start_time;
        const currentLapElapsed = lapStartTime != null ? Math.round((ct - lapStartTime) * 1000) / 1000 : null;

        driverLapInfo.set(drvNum, {
            bestLapTime,
            bestLapStr: bestLap?.lap_time_str || null,
            lastLapTime: latestLap?.lap_time,
            lastLapStr: latestLap?.lap_time_str || null,
            sectorColors,
            lastSectors: latestLap ? [latestLap.sector1_time, latestLap.sector2_time, latestLap.sector3_time] : [null, null, null],
            compound,
            tyreLife,
            currentLapElapsed,
        });
    }

    // Fastest lap overall
    let fastestLap = null;
    const allValidLaps = completedLaps.filter(l => l.lap_time != null && l.lap_time > 0);
    if (allValidLaps.length > 0) {
        const fastest = allValidLaps.reduce((best, l) => l.lap_time < best.lap_time ? l : best);
        const driver = drivers.get(fastest.driver_number);
        fastestLap = {
            time: fastest.lap_time,
            timeStr: fastest.lap_time_str,
            driverNumber: fastest.driver_number,
            driverName: driver?.name_acronym || '???',
            lap: fastest.lap_number,
        };
    }

    // ── Gap computation (interpolated between sector checkpoints) ──
    const positions = playback.positions;
    const driverGaps = new Map();

    if (positions.length > 0) {
        // Build per-driver checkpoint list: { lap, sector, time }
        const driverCheckpoints = new Map();
        for (const dl of detailedLaps) {
            const drvNum = dl.driver_number;
            if (!driverCheckpoints.has(drvNum)) driverCheckpoints.set(drvNum, []);
            const cps = driverCheckpoints.get(drvNum);

            if (dl.sector1_session_time != null) {
                cps.push({ lap: dl.lap_number, sector: 1, time: dl.sector1_session_time });
            }
            if (dl.sector2_session_time != null) {
                cps.push({ lap: dl.lap_number, sector: 2, time: dl.sector2_session_time });
            }
            if (dl.sector3_session_time != null) {
                cps.push({ lap: dl.lap_number, sector: 3, time: dl.sector3_session_time });
            }
        }

        // Sort all checkpoints by time for each driver
        for (const [, cps] of driverCheckpoints) {
            cps.sort((a, b) => a.time - b.time);
        }

        // Helper: find checkpoint by (lap, sector) for a driver
        const findCheckpoint = (drvNum, lap, sector) => {
            const cps = driverCheckpoints.get(drvNum);
            if (!cps) return null;
            return cps.find(c => c.lap === lap && c.sector === sector) || null;
        };

        // Helper: compute gap between two drivers at a given checkpoint
        const gapAtCheckpoint = (drvNum, refNum, lap, sector) => {
            const drvCP = findCheckpoint(drvNum, lap, sector);
            const refCP = findCheckpoint(refNum, lap, sector);
            if (drvCP && refCP) return drvCP.time - refCP.time;
            return null;
        };

        // For each driver: find last two passed checkpoints + next expected one
        const driverCPState = new Map();
        for (const [drvNum, cps] of driverCheckpoints) {
            const passed = cps.filter(c => c.time <= ct);
            const upcoming = cps.filter(c => c.time > ct);

            if (passed.length > 0) {
                const lastCP = passed[passed.length - 1];
                const prevCP = passed.length > 1 ? passed[passed.length - 2] : null;
                const nextCP = upcoming.length > 0 ? upcoming[0] : null;
                driverCPState.set(drvNum, { lastCP, prevCP, nextCP });
            }
        }

        const leaderNum = positions[0]?.driver_number;

        for (let i = 0; i < positions.length; i++) {
            const drvNum = positions[i].driver_number;
            const state = driverCPState.get(drvNum);

            let gapToLeader = null;
            let interval = null;

            if (i === 0) {
                gapToLeader = 0;
                interval = null;
            } else if (state) {
                const { lastCP, prevCP, nextCP } = state;

                // Gap at last checkpoint
                const gapAtLast = gapAtCheckpoint(drvNum, leaderNum, lastCP.lap, lastCP.sector);

                if (gapAtLast != null) {
                    if (prevCP && nextCP) {
                        // Interpolate: we know gap at lastCP, estimate gap at nextCP
                        const gapAtPrev = gapAtCheckpoint(drvNum, leaderNum, prevCP.lap, prevCP.sector);
                        if (gapAtPrev != null) {
                            // Linear trend: how much gap is changing per second
                            const timeBetweenCPs = lastCP.time - prevCP.time;
                            const gapDelta = gapAtLast - gapAtPrev;
                            if (timeBetweenCPs > 0) {
                                const rate = gapDelta / timeBetweenCPs;
                                const elapsed = ct - lastCP.time;
                                gapToLeader = Math.round((gapAtLast + rate * elapsed) * 1000) / 1000;
                            } else {
                                gapToLeader = Math.round(gapAtLast * 1000) / 1000;
                            }
                        } else {
                            gapToLeader = Math.round(gapAtLast * 1000) / 1000;
                        }
                    } else {
                        gapToLeader = Math.round(gapAtLast * 1000) / 1000;
                    }
                } else {
                    // Possibly lapped
                    const leaderState = driverCPState.get(leaderNum);
                    if (leaderState && leaderState.lastCP.lap > lastCP.lap) {
                        gapToLeader = -(leaderState.lastCP.lap - lastCP.lap);
                    }
                }

                // Interval to car ahead — same approach
                const aheadNum = positions[i - 1]?.driver_number;
                if (aheadNum) {
                    const intAtLast = gapAtCheckpoint(drvNum, aheadNum, lastCP.lap, lastCP.sector);
                    if (intAtLast != null) {
                        if (prevCP) {
                            const intAtPrev = gapAtCheckpoint(drvNum, aheadNum, prevCP.lap, prevCP.sector);
                            if (intAtPrev != null) {
                                const timeBetween = lastCP.time - prevCP.time;
                                const delta = intAtLast - intAtPrev;
                                if (timeBetween > 0) {
                                    const rate = delta / timeBetween;
                                    const elapsed = ct - lastCP.time;
                                    interval = Math.round((intAtLast + rate * elapsed) * 1000) / 1000;
                                } else {
                                    interval = Math.round(intAtLast * 1000) / 1000;
                                }
                            } else {
                                interval = Math.round(intAtLast * 1000) / 1000;
                            }
                        } else {
                            interval = Math.round(intAtLast * 1000) / 1000;
                        }
                    } else {
                        const aheadState = driverCPState.get(aheadNum);
                        if (aheadState && aheadState.lastCP.lap > lastCP.lap) {
                            interval = -(aheadState.lastCP.lap - lastCP.lap);
                        }
                    }
                }
            }

            driverGaps.set(drvNum, { gapToLeader, interval });
        }
    }

    const value = {
        // Static
        trackCoords: data?.trackCoords || [],
        corners: data?.corners || [],
        drivers,
        sessionInfo: data?.sessionInfo || null,
        isLoading,
        apiError: error,
        telemetry: data?.telemetry || null,
        lapStarts: data?.lapStarts || null,

        // Smoothly interpolated driver states
        driverStates: smoothStates,

        // Playback controls
        positions: playback.positions,
        currentTime: playback.currentTime,
        currentLap: playback.currentLap,
        isPlaying: playback.isPlaying,
        togglePlayback: playback.togglePlayback,
        restart: playback.restart,
        seekTo: playback.seekTo,
        speed: playback.speed,
        setPlaybackSpeed: playback.setPlaybackSpeed,
        progress: playback.progress,
        totalTicks: playback.totalTicks,
        currentTick: playback.currentTick,

        // Track status
        trackStatus: playback.trackStatus,
        trackMessage: playback.trackMessage,
        retiredDrivers: playback.retiredDrivers,

        // Weather
        currentWeather,

        // Lap timing & sectors
        driverLapInfo,
        fastestLap,
        driverGaps,

        // Selected driver
        selectedDriverNumber,
        setSelectedDriverNumber,
    };

    return (
        <SimulationContext.Provider value={value}>
            {children}
        </SimulationContext.Provider>
    );
}

export function useSimulation() {
    const ctx = useContext(SimulationContext);
    if (!ctx) throw new Error('useSimulation must be used within SimulationProvider');
    return ctx;
}
