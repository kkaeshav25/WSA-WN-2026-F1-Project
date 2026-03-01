import { useState, useEffect, useRef, useCallback } from 'react';
import { marshalSectorToTurnLabel } from '../data/constants.js';

/**
 * usePlaybackController — Steps through the telemetry timeline
 *
 * Tracks current track status with sector info (green, yellow sector 5, safety car, etc.).
 * Tracks retired drivers but keeps them in a separate map for leaderboard display.
 */
export default function usePlaybackController(timeline, lapData, raceEvents, dnfInfo) {
    const [currentIndex, setCurrentIndex] = useState(0);
    const [isPlaying, setIsPlaying] = useState(false);
    const [speed, setSpeed] = useState(1);

    const driverStatesRef = useRef(new Map());
    const [driverStates, setDriverStates] = useState(new Map());
    const [currentTime, setCurrentTime] = useState(0);
    const [currentLap, setCurrentLap] = useState(1);
    const [positions, setPositions] = useState([]);

    // Track status
    const [trackStatus, setTrackStatus] = useState('GREEN');
    const [trackMessage, setTrackMessage] = useState('');
    const [retiredDrivers, setRetiredDrivers] = useState(new Map()); // number -> { status, lap }
    const raceEventIndexRef = useRef(0);

    const intervalRef = useRef(null);

    // ── Apply a tick ──
    const applyTick = useCallback((index) => {
        if (!timeline || index >= timeline.length) {
            setIsPlaying(false);
            return;
        }

        const tick = timeline[index];
        const map = driverStatesRef.current;

        for (const s of tick.samples) {
            if (retiredDrivers.has(s.driver_number)) continue;
            map.set(s.driver_number, {
                x: s.x, y: s.y,
                speed: s.speed, rpm: s.rpm, gear: s.gear,
                throttle: s.throttle, brake: s.brake, drs: s.drs,
                lap: s.lap,
            });
        }

        const anyLap = tick.samples[0]?.lap || currentLap;
        const sessionTime = tick.t;

        // ── Process race events up to this time ──
        if (raceEvents) {
            let evtIdx = raceEventIndexRef.current;
            while (evtIdx < raceEvents.length && raceEvents[evtIdx].t <= sessionTime) {
                const evt = raceEvents[evtIdx];

                if (evt.category === 'SafetyCar') {
                    if (evt.message.includes('DEPLOYED')) {
                        setTrackStatus('SAFETY_CAR');
                        setTrackMessage('SAFETY CAR');
                    } else if (evt.message.includes('IN THIS LAP')) {
                        setTrackStatus('SC_ENDING');
                        setTrackMessage('SAFETY CAR IN THIS LAP');
                    }
                } else if (evt.category === 'Flag') {
                    const sector = evt.sector;
                    const turnStr = sector ? ` — ${marshalSectorToTurnLabel(sector)}` : '';

                    if (evt.flag === 'YELLOW') {
                        setTrackStatus('YELLOW');
                        setTrackMessage(`YELLOW FLAG${turnStr}`);
                    } else if (evt.flag === 'DOUBLE YELLOW') {
                        setTrackStatus('DOUBLE_YELLOW');
                        setTrackMessage(`DOUBLE YELLOW${turnStr}`);
                    } else if (evt.flag === 'GREEN' || evt.message.includes('TRACK CLEAR') || evt.message.includes('GREEN LIGHT')) {
                        setTrackStatus('GREEN');
                        setTrackMessage('');
                    } else if (evt.flag === 'CLEAR') {
                        // Sector clear — only clear if it's the same sector or track-wide
                        setTrackStatus('GREEN');
                        setTrackMessage('');
                    } else if (evt.message.includes('CHEQUERED')) {
                        setTrackStatus('CHEQUERED');
                        setTrackMessage('CHEQUERED FLAG');
                    }
                } else if (evt.category === 'TrackStatus') {
                    const statusCode = evt.flag;
                    if (statusCode === '1' || evt.message === 'AllClear') {
                        setTrackStatus('GREEN');
                        setTrackMessage('');
                    } else if (statusCode === '2' || evt.message === 'Yellow') {
                        setTrackStatus('YELLOW');
                        setTrackMessage('YELLOW FLAG');
                    } else if (statusCode === '4' || evt.message === 'SCDeployed') {
                        setTrackStatus('SAFETY_CAR');
                        setTrackMessage('SAFETY CAR');
                    } else if (statusCode === '5' || evt.message === 'Red') {
                        setTrackStatus('RED_FLAG');
                        setTrackMessage('RED FLAG');
                    } else if (statusCode === '6' || evt.message === 'VSCDeployed') {
                        setTrackStatus('VSC');
                        setTrackMessage('VIRTUAL SAFETY CAR');
                    } else if (statusCode === '7' || evt.message === 'VSCEnding') {
                        setTrackStatus('VSC_ENDING');
                        setTrackMessage('VSC ENDING');
                    }
                }

                evtIdx++;
            }
            raceEventIndexRef.current = evtIdx;
        }

        // ── Check retirements ──
        if (dnfInfo) {
            const newRetired = new Map(retiredDrivers);
            let changed = false;
            for (const [drvNum, info] of Object.entries(dnfInfo)) {
                const num = parseInt(drvNum, 10) || drvNum;
                if (!newRetired.has(num) && info.retirement_time > 0 && sessionTime >= info.retirement_time) {
                    newRetired.set(num, { status: info.status, lastLap: info.last_lap });
                    map.delete(num);
                    changed = true;
                }
            }
            if (changed) setRetiredDrivers(newRetired);
        }

        driverStatesRef.current = new Map(map);
        setDriverStates(new Map(map));
        setCurrentTime(sessionTime);
        setCurrentIndex(index);
        setCurrentLap(anyLap);

        // Positions from lap data — fill gaps from previous laps
        if (lapData) {
            const currentLapPositions = lapData
                .filter(l => l.lap_number === anyLap && l.position > 0)
                .map(l => ({ driver_number: l.driver_number, position: l.position }));

            const posMap = new Map();
            for (const p of currentLapPositions) {
                posMap.set(p.driver_number, p.position);
            }

            // Fill missing drivers from previous laps
            const activeDrivers = new Set(map.keys());
            for (const drvNum of activeDrivers) {
                if (!posMap.has(drvNum)) {
                    for (let lap = anyLap - 1; lap >= 1; lap--) {
                        const prevPos = lapData.find(l =>
                            l.driver_number === drvNum && l.lap_number === lap && l.position > 0
                        );
                        if (prevPos) {
                            posMap.set(drvNum, prevPos.position);
                            break;
                        }
                    }
                    if (!posMap.has(drvNum)) {
                        posMap.set(drvNum, 20);
                    }
                }
            }

            const sortedPositions = [...posMap.entries()]
                .map(([driver_number, position]) => ({ driver_number, position }))
                .sort((a, b) => a.position - b.position);

            if (sortedPositions.length > 0) setPositions(sortedPositions);
        }
    }, [timeline, lapData, raceEvents, dnfInfo, currentLap, retiredDrivers]);

    // Initialize
    useEffect(() => {
        if (timeline && timeline.length > 0) applyTick(0);
    }, [timeline]); // eslint-disable-line react-hooks/exhaustive-deps

    // Playback interval
    useEffect(() => {
        if (isPlaying && timeline && timeline.length > 0) {
            const tickMs = Math.max(16, 250 / speed);
            intervalRef.current = setInterval(() => {
                setCurrentIndex(prev => {
                    const next = prev + 1;
                    if (next >= timeline.length) { setIsPlaying(false); return prev; }
                    applyTick(next);
                    return next;
                });
            }, tickMs);
        }
        return () => {
            if (intervalRef.current) { clearInterval(intervalRef.current); intervalRef.current = null; }
        };
    }, [isPlaying, speed, timeline, applyTick]);

    // ── Controls ──
    const togglePlayback = useCallback(() => setIsPlaying(p => !p), []);

    const restart = useCallback(() => {
        setIsPlaying(false);
        setCurrentIndex(0);
        driverStatesRef.current = new Map();
        setRetiredDrivers(new Map());
        raceEventIndexRef.current = 0;
        setTrackStatus('GREEN');
        setTrackMessage('');
        if (timeline && timeline.length > 0) applyTick(0);
    }, [timeline, applyTick]);

    const seekTo = useCallback((targetIndex) => {
        // Seeking requires replaying events from the beginning up to targetIndex
        setIsPlaying(false);
        driverStatesRef.current = new Map();
        setRetiredDrivers(new Map());
        raceEventIndexRef.current = 0;
        setTrackStatus('GREEN');
        setTrackMessage('');

        // Fast-forward through all ticks up to target
        if (timeline) {
            const map = new Map();
            const retired = new Map();
            let evtIdx = 0;
            let lastLap = 1;

            for (let i = 0; i <= targetIndex && i < timeline.length; i++) {
                const tick = timeline[i];
                const sessionTime = tick.t;

                // Apply driver samples
                for (const s of tick.samples) {
                    if (retired.has(s.driver_number)) continue;
                    map.set(s.driver_number, {
                        x: s.x, y: s.y,
                        speed: s.speed, rpm: s.rpm, gear: s.gear,
                        throttle: s.throttle, brake: s.brake, drs: s.drs,
                        lap: s.lap,
                    });
                    if (s.lap) lastLap = s.lap;
                }

                // Process events
                if (raceEvents) {
                    while (evtIdx < raceEvents.length && raceEvents[evtIdx].t <= sessionTime) {
                        evtIdx++;
                    }
                }

                // Check retirements
                if (dnfInfo) {
                    for (const [drvNum, info] of Object.entries(dnfInfo)) {
                        const num = parseInt(drvNum, 10) || drvNum;
                        if (!retired.has(num) && info.retirement_time > 0 && sessionTime >= info.retirement_time) {
                            retired.set(num, { status: info.status, lastLap: info.last_lap });
                            map.delete(num);
                        }
                    }
                }
            }

            // Replay the last batch of events to set correct track status
            if (raceEvents) {
                let statusIdx = 0;
                const targetTime = timeline[targetIndex]?.t || 0;
                let lastStatus = 'GREEN';
                let lastMsg = '';
                while (statusIdx < raceEvents.length && raceEvents[statusIdx].t <= targetTime) {
                    const evt = raceEvents[statusIdx];
                    if (evt.category === 'SafetyCar') {
                        if (evt.message.includes('DEPLOYED')) { lastStatus = 'SAFETY_CAR'; lastMsg = 'SAFETY CAR'; }
                        else if (evt.message.includes('IN THIS LAP')) { lastStatus = 'SC_ENDING'; lastMsg = 'SC IN THIS LAP'; }
                    } else if (evt.category === 'Flag') {
                        const turnStr = evt.sector ? ` — ${marshalSectorToTurnLabel(evt.sector)}` : '';
                        if (evt.flag === 'YELLOW') { lastStatus = 'YELLOW'; lastMsg = `YELLOW FLAG${turnStr}`; }
                        else if (evt.flag === 'DOUBLE YELLOW') { lastStatus = 'DOUBLE_YELLOW'; lastMsg = `DOUBLE YELLOW${turnStr}`; }
                        else if (evt.flag === 'CLEAR' || evt.flag === 'GREEN' || evt.message.includes('TRACK CLEAR')) { lastStatus = 'GREEN'; lastMsg = ''; }
                        else if (evt.message.includes('CHEQUERED')) { lastStatus = 'CHEQUERED'; lastMsg = 'CHEQUERED FLAG'; }
                    } else if (evt.category === 'TrackStatus') {
                        if (evt.flag === '1' || evt.message === 'AllClear') { lastStatus = 'GREEN'; lastMsg = ''; }
                        else if (evt.flag === '2' || evt.message === 'Yellow') { lastStatus = 'YELLOW'; lastMsg = 'YELLOW FLAG'; }
                        else if (evt.flag === '4' || evt.message === 'SCDeployed') { lastStatus = 'SAFETY_CAR'; lastMsg = 'SAFETY CAR'; }
                    }
                    statusIdx++;
                }
                setTrackStatus(lastStatus);
                setTrackMessage(lastMsg);
                raceEventIndexRef.current = statusIdx;
            }

            driverStatesRef.current = map;
            setDriverStates(new Map(map));
            setRetiredDrivers(retired);
            setCurrentIndex(targetIndex);
            setCurrentTime(timeline[targetIndex]?.t || 0);
            setCurrentLap(lastLap);

            // Positions — fill gaps from previous laps
            if (lapData) {
                const currentLapPositions = lapData
                    .filter(l => l.lap_number === lastLap && l.position > 0)
                    .map(l => ({ driver_number: l.driver_number, position: l.position }));

                const posMap = new Map();
                for (const p of currentLapPositions) posMap.set(p.driver_number, p.position);

                for (const drvNum of map.keys()) {
                    if (!posMap.has(drvNum)) {
                        for (let lap = lastLap - 1; lap >= 1; lap--) {
                            const prev = lapData.find(l =>
                                l.driver_number === drvNum && l.lap_number === lap && l.position > 0
                            );
                            if (prev) { posMap.set(drvNum, prev.position); break; }
                        }
                        if (!posMap.has(drvNum)) posMap.set(drvNum, 20);
                    }
                }

                const sorted = [...posMap.entries()]
                    .map(([driver_number, position]) => ({ driver_number, position }))
                    .sort((a, b) => a.position - b.position);
                if (sorted.length > 0) setPositions(sorted);
            }
        }
    }, [timeline, lapData, raceEvents, dnfInfo]);

    const setPlaybackSpeed = useCallback((s) => setSpeed(s), []);
    const progress = timeline && timeline.length > 0 ? (currentIndex / (timeline.length - 1)) * 100 : 0;

    return {
        driverStates, positions, currentTime, currentLap,
        trackStatus, trackMessage, retiredDrivers,
        isPlaying, togglePlayback, restart, seekTo,
        speed, setPlaybackSpeed, progress,
        totalTicks: timeline?.length || 0, currentTick: currentIndex,
    };
}
