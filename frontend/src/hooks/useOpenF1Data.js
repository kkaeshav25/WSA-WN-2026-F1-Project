import { useState, useEffect } from 'react';

/**
 * useRaceData — Loads race_mock.json and telemetry.json
 *
 * Provides:
 *   - Circuit outline (rotated), corners
 *   - Driver info (abbreviation, team, team_color)
 *   - Lap timing data for leaderboard position tracking
 *   - Generated driver telemetry timeline from X/Y positions
 *   - Simulated telemetry per driver (t, x, y)
 */
export default function useRaceData() {
    const [data, setData] = useState(null);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState(null);

    useEffect(() => {
        let cancelled = false;

        async function load() {
            try {
                setIsLoading(true);
                const [raceRes, telemetryRes, lapStartsRes] = await Promise.all([
                    fetch('/race_mock.json'),
                    fetch('/telemetry.json').catch(() => null),  // Optional, don't fail if missing
                    fetch('/lap_starts.json').catch(() => null),  // Optional
                ]);
                if (!raceRes.ok) throw new Error(`Failed to load race data: ${raceRes.status}`);
                const raw = await raceRes.json();
                const telemetryRaw = telemetryRes && telemetryRes.ok ? await telemetryRes.json() : null;
                const lapStartsRaw = lapStartsRes && lapStartsRes.ok ? await lapStartsRes.json() : null;

                if (cancelled) return;

                // ── Apply rotation to circuit outline ──
                const rotDeg = raw.circuit.rotation || 0;
                const rotRad = (rotDeg * Math.PI) / 180;
                const cosR = Math.cos(rotRad);
                const sinR = Math.sin(rotRad);

                const rotatePoint = (x, y) => ({
                    x: x * cosR - y * sinR,
                    y: -(x * sinR + y * cosR),  // Negate Y to unmirror
                });

                const trackCoords = raw.circuit.outline.map(p => rotatePoint(p.x, p.y));

                // Rotate corners too
                const corners = (raw.circuit.corners || []).map(c => ({
                    ...c,
                    ...rotatePoint(c.x, c.y),
                }));

                // ── Build drivers Map ──
                const drivers = new Map();
                for (const [num, info] of Object.entries(raw.drivers)) {
                    const driverNum = parseInt(num, 10) || num;
                    drivers.set(driverNum, {
                        driver_number: driverNum,
                        name_acronym: info.abbreviation,
                        full_name: info.full_name,
                        first_name: info.first_name,
                        last_name: info.last_name,
                        team_name: info.team,
                        team_colour: info.team_color,
                    });
                }

                // ── Build telemetry timeline ──
                // Use telemetry.json for the real driver position timeline if available.
                const telemetrySource = telemetryRaw || raw.telemetry || {};
                const allSamples = [];
                for (const [drvNum, samples] of Object.entries(telemetrySource)) {
                    const num = parseInt(drvNum, 10) || drvNum;
                    for (const s of samples) {
                        const t = s.t != null ? s.t : s.time_s;
                        if (t == null) continue;
                        const rotated = (s.x != null && s.y != null) ? rotatePoint(s.x, s.y) : {};
                        allSamples.push({
                            t,
                            driver_number: num,
                            x: rotated.x,
                            y: rotated.y,
                            speed: s.spd ?? s.speed ?? 0,
                            rpm: s.rpm ?? 0,
                            gear: s.gear ?? 0,
                            throttle: s.thr ?? s.throttle ?? 0,
                            brake: s.brk ?? s.brake ?? false,
                            drs: s.drs != null ? s.drs : false,
                            lap: s.lap || 0,
                        });
                    }
                }
                allSamples.sort((a, b) => a.t - b.t);

                // Group by timestamp (rounded to 0.25s for synchronization)
                const grouped = new Map();
                for (const s of allSamples) {
                    const key = Math.round(s.t * 4) / 4; // 0.25s buckets
                    if (!grouped.has(key)) grouped.set(key, []);
                    grouped.get(key).push(s);
                }

                const timeline = [...grouped.entries()]
                    .sort(([a], [b]) => a - b)
                    .map(([t, samples]) => ({ t, samples }));

                // ── Lap timing for leaderboard ──
                const lapData = raw.laps || [];

                // ── Race events (safety car, flags, etc.) ──
                const raceEvents = (raw.race_events || []).sort((a, b) => a.t - b.t);

                // ── DNF info ──
                const dnf = {};
                if (raw.dnf) {
                    for (const [num, info] of Object.entries(raw.dnf)) {
                        dnf[parseInt(num, 10) || num] = info;
                    }
                }

                // ── Weather data ──
                const weather = (raw.weather || []).sort((a, b) => a.t - b.t);

                // ── Detailed laps (sector times, compounds, etc.) ──
                const detailedLaps = (raw.detailed_laps || []).sort((a, b) =>
                    a.driver_number - b.driver_number || a.lap_number - b.lap_number
                );

                setData({
                    trackCoords,
                    corners,
                    drivers,
                    timeline,
                    lapData,
                    raceEvents,
                    dnf,
                    weather,
                    detailedLaps,
                    sessionInfo: raw.session,
                    telemetry: telemetryRaw,
                    lapStarts: lapStartsRaw,
                });

            } catch (err) {
                if (!cancelled) setError(err.message);
            } finally {
                if (!cancelled) setIsLoading(false);
            }
        }

        load();
        return () => { cancelled = true; };
    }, []);

    return { data, isLoading, error };
}
