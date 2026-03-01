import { useRef, useEffect, useCallback } from 'react';
import { useSimulation } from '../context/SimulationContext.jsx';

const TRACK_PADDING = 40;
const DOT_RADIUS = 5;

function getBounds(coords) {
    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
    for (const p of coords) {
        if (p.x < minX) minX = p.x;
        if (p.y < minY) minY = p.y;
        if (p.x > maxX) maxX = p.x;
        if (p.y > maxY) maxY = p.y;
    }
    return { minX, minY, maxX, maxY, w: maxX - minX, h: maxY - minY };
}

/**
 * TrackMap — Canvas circuit renderer with REAL driver positions from telemetry
 *
 * Driver dots are placed at their actual X/Y from FastF1 telemetry data.
 * Circuit outline comes from the fastest lap telemetry.
 * Corner labels are drawn from FastF1 circuit info.
 */
export default function TrackMap() {
    const canvasRef = useRef(null);
    const animRef = useRef(null);
    const {
        trackCoords, corners, driverStates, drivers,
        isLoading, selectedDriverNumber, setSelectedDriverNumber,
    } = useSimulation();

    const boundsRef = useRef(null);

    // ── Map coordinate to canvas pixel ──
    const toPixel = useCallback((x, y, canvas, bounds) => {
        const dpr = window.devicePixelRatio || 1;
        const pad = TRACK_PADDING * dpr;
        const availW = canvas.width - pad * 2;
        const availH = canvas.height - pad * 2;
        const scale = Math.min(availW / bounds.w, availH / bounds.h);
        const drawW = bounds.w * scale;
        const drawH = bounds.h * scale;
        const offX = (canvas.width - drawW) / 2;
        const offY = (canvas.height - drawH) / 2;
        return {
            cx: (x - bounds.minX) * scale + offX,
            cy: (y - bounds.minY) * scale + offY,
        };
    }, []);

    // ── Render ──
    useEffect(() => {
        const resize = () => {
            const c = canvasRef.current;
            if (!c) return;
            const p = c.parentElement;
            const dpr = window.devicePixelRatio || 1;
            c.width = p.clientWidth * dpr;
            c.height = p.clientHeight * dpr;
            c.style.width = p.clientWidth + 'px';
            c.style.height = p.clientHeight + 'px';
        };
        resize();
        window.addEventListener('resize', resize);

        const render = () => {
            const canvas = canvasRef.current;
            if (!canvas) return;
            const ctx = canvas.getContext('2d');
            const dpr = window.devicePixelRatio || 1;

            ctx.clearRect(0, 0, canvas.width, canvas.height);

            // Background
            ctx.fillStyle = '#0a0a10';
            ctx.fillRect(0, 0, canvas.width, canvas.height);

            if (!trackCoords || trackCoords.length < 2) {
                ctx.font = `600 ${14 * dpr}px 'Outfit', sans-serif`;
                ctx.fillStyle = '#8888a0';
                ctx.textAlign = 'center';
                ctx.textBaseline = 'middle';
                ctx.fillText(
                    isLoading ? 'Loading race data...' : 'No track data',
                    canvas.width / 2, canvas.height / 2
                );
                animRef.current = requestAnimationFrame(render);
                return;
            }

            const bounds = getBounds(trackCoords);
            boundsRef.current = bounds;

            // ── Track outline ──
            // Outer
            ctx.beginPath();
            ctx.strokeStyle = '#2a2a3a';
            ctx.lineWidth = 18 * dpr;
            ctx.lineCap = 'round';
            ctx.lineJoin = 'round';
            for (let i = 0; i < trackCoords.length; i++) {
                const { cx, cy } = toPixel(trackCoords[i].x, trackCoords[i].y, canvas, bounds);
                i === 0 ? ctx.moveTo(cx, cy) : ctx.lineTo(cx, cy);
            }
            ctx.closePath();
            ctx.stroke();

            // Surface
            ctx.beginPath();
            ctx.strokeStyle = '#161624';
            ctx.lineWidth = 12 * dpr;
            for (let i = 0; i < trackCoords.length; i++) {
                const { cx, cy } = toPixel(trackCoords[i].x, trackCoords[i].y, canvas, bounds);
                i === 0 ? ctx.moveTo(cx, cy) : ctx.lineTo(cx, cy);
            }
            ctx.closePath();
            ctx.stroke();

            // Center line
            ctx.beginPath();
            ctx.strokeStyle = '#222238';
            ctx.lineWidth = 1 * dpr;
            ctx.setLineDash([5 * dpr, 8 * dpr]);
            for (let i = 0; i < trackCoords.length; i++) {
                const { cx, cy } = toPixel(trackCoords[i].x, trackCoords[i].y, canvas, bounds);
                i === 0 ? ctx.moveTo(cx, cy) : ctx.lineTo(cx, cy);
            }
            ctx.closePath();
            ctx.stroke();
            ctx.setLineDash([]);

            // ── Start/Finish line ──
            const sf = toPixel(trackCoords[0].x, trackCoords[0].y, canvas, bounds);
            const sf2 = toPixel(trackCoords[3].x, trackCoords[3].y, canvas, bounds);
            const dx = sf2.cx - sf.cx, dy = sf2.cy - sf.cy;
            const len = Math.sqrt(dx * dx + dy * dy) || 1;
            const nx = -dy / len, ny = dx / len;
            const hw = 12 * dpr;
            ctx.beginPath();
            ctx.strokeStyle = '#ffffff';
            ctx.lineWidth = 2.5 * dpr;
            ctx.moveTo(sf.cx + nx * hw, sf.cy + ny * hw);
            ctx.lineTo(sf.cx - nx * hw, sf.cy - ny * hw);
            ctx.stroke();
            ctx.font = `bold ${7 * dpr}px 'JetBrains Mono', monospace`;
            ctx.fillStyle = '#ffffff60';
            ctx.textAlign = 'center';
            ctx.fillText('S/F', sf.cx, sf.cy - hw - 3 * dpr);

            // ── Corner numbers ──
            if (corners && corners.length > 0) {
                ctx.font = `bold ${7 * dpr}px 'JetBrains Mono', monospace`;
                ctx.fillStyle = '#ffffff30';
                ctx.textAlign = 'center';
                ctx.textBaseline = 'middle';
                for (const c of corners) {
                    const { cx, cy } = toPixel(c.x, c.y, canvas, bounds);
                    ctx.fillText(`T${c.number}`, cx, cy - 12 * dpr);
                }
            }

            // ── Driver dots (real X/Y from telemetry) ──
            if (driverStates && driverStates.size > 0) {
                // Draw unselected first, then selected on top
                const entries = [...driverStates.entries()];
                const unselected = entries.filter(([n]) => n !== selectedDriverNumber);
                const selected = entries.filter(([n]) => n === selectedDriverNumber);

                for (const [drvNum, state] of [...unselected, ...selected]) {
                    if (state.x == null || state.y == null) continue;
                    const driver = drivers.get(drvNum);
                    if (!driver) continue;

                    const { cx, cy } = toPixel(state.x, state.y, canvas, bounds);
                    const color = driver.team_colour;
                    const isSel = drvNum === selectedDriverNumber;
                    const r = DOT_RADIUS * dpr * (isSel ? 1.4 : 1);

                    // Glow
                    ctx.beginPath();
                    ctx.arc(cx, cy, r + 4 * dpr, 0, Math.PI * 2);
                    const glow = ctx.createRadialGradient(cx, cy, r * 0.3, cx, cy, r + 5 * dpr);
                    glow.addColorStop(0, color + (isSel ? '90' : '50'));
                    glow.addColorStop(1, color + '00');
                    ctx.fillStyle = glow;
                    ctx.fill();

                    // Dot
                    ctx.beginPath();
                    ctx.arc(cx, cy, r, 0, Math.PI * 2);
                    ctx.fillStyle = color;
                    ctx.fill();
                    if (isSel) {
                        ctx.strokeStyle = '#ffffff';
                        ctx.lineWidth = 2 * dpr;
                        ctx.stroke();
                    }

                    // Label
                    ctx.font = `bold ${(isSel ? 9 : 7) * dpr}px 'JetBrains Mono', monospace`;
                    ctx.fillStyle = isSel ? '#ffffff' : '#b0b0c0';
                    ctx.textAlign = 'left';
                    ctx.textBaseline = 'middle';
                    ctx.save();
                    ctx.shadowColor = '#000000cc';
                    ctx.shadowBlur = 3 * dpr;
                    ctx.fillText(driver.name_acronym, cx + r + 3 * dpr, cy);
                    ctx.restore();
                }
            }

            animRef.current = requestAnimationFrame(render);
        };

        animRef.current = requestAnimationFrame(render);
        return () => {
            window.removeEventListener('resize', resize);
            if (animRef.current) cancelAnimationFrame(animRef.current);
        };
    }, [trackCoords, corners, driverStates, drivers, isLoading, selectedDriverNumber, toPixel]);

    // ── Click to select driver ──
    const handleClick = useCallback((e) => {
        if (!driverStates || driverStates.size === 0) return;
        const canvas = canvasRef.current;
        if (!canvas || !boundsRef.current) return;
        const rect = canvas.getBoundingClientRect();
        const dpr = window.devicePixelRatio || 1;
        const mx = (e.clientX - rect.left) * dpr;
        const my = (e.clientY - rect.top) * dpr;
        const bounds = boundsRef.current;

        let closest = null, closestDist = Infinity;
        for (const [num, state] of driverStates) {
            if (state.x == null) continue;
            const { cx, cy } = toPixel(state.x, state.y, canvas, bounds);
            const d = Math.sqrt((mx - cx) ** 2 + (my - cy) ** 2);
            if (d < 30 * dpr && d < closestDist) {
                closestDist = d;
                closest = num;
            }
        }
        if (closest !== null) setSelectedDriverNumber(closest);
    }, [driverStates, toPixel, setSelectedDriverNumber]);

    return (
        <div className="relative w-full h-full overflow-hidden rounded-2xl">
            <canvas ref={canvasRef} className="block cursor-pointer"
                style={{ width: '100%', height: '100%' }} onClick={handleClick} />
            <div className="absolute top-3 left-3 pointer-events-none">
                <div className="glass-panel-subtle px-3 py-1.5">
                    <span className="text-xs font-semibold text-f1-text-muted uppercase tracking-wider">
                        Circuit de Spa-Francorchamps
                    </span>
                </div>
            </div>
        </div>
    );
}
