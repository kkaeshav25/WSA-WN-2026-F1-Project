import { useState, useEffect, useRef, useCallback } from 'react';
import { WS_CONFIG } from '../data/constants.js';
import { initialMockDrivers, simulateTick, simulatePositionChanges } from '../data/mockDrivers.js';

/**
 * useSimulationStream — Core WebSocket hook for F1 live data
 *
 * Connects to a WebSocket server and listens for "tick" messages.
 * Falls back to mock simulation when the WebSocket is unavailable.
 *
 * Performance strategy:
 *   - High-frequency data (x, y, speed, gear, etc.) stored in useRef
 *     to avoid triggering React re-renders on every frame
 *   - Leaderboard data (positions, gaps) stored in useState, updated
 *     only when positions change
 */
export default function useSimulationStream() {
    // ── State for React-rendered data (leaderboard) ──
    const [leaderboard, setLeaderboard] = useState(
        () => initialMockDrivers.sort((a, b) => a.position - b.position)
    );
    const [trackStatus, setTrackStatus] = useState(1); // 1 = Green
    const [isConnected, setIsConnected] = useState(false);
    const [selectedDriverId, setSelectedDriverId] = useState(1);

    // ── Ref for high-frequency telemetry data (no re-renders) ──
    const driversRef = useRef(initialMockDrivers);
    const wsRef = useRef(null);
    const reconnectAttemptsRef = useRef(0);
    const mockIntervalRef = useRef(null);
    const leaderboardTimerRef = useRef(null);

    // ── Process incoming tick data ──
    const processTick = useCallback((payload) => {
        if (payload.drivers) {
            // Update the ref (no re-render) with latest coordinates + telemetry
            driversRef.current = payload.drivers;
        }
        if (payload.trackStatus !== undefined) {
            setTrackStatus(payload.trackStatus);
        }
    }, []);

    // ── WebSocket connection ──
    const connect = useCallback(() => {
        try {
            const ws = new WebSocket(WS_CONFIG.url);
            wsRef.current = ws;

            ws.onopen = () => {
                setIsConnected(true);
                reconnectAttemptsRef.current = 0;
                // Stop mock simulation when real connection is established
                if (mockIntervalRef.current) {
                    clearInterval(mockIntervalRef.current);
                    mockIntervalRef.current = null;
                }
            };

            ws.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    processTick(data);
                } catch (err) {
                    console.warn('Failed to parse WebSocket message:', err);
                }
            };

            ws.onclose = () => {
                setIsConnected(false);
                wsRef.current = null;
                // Attempt reconnection
                if (reconnectAttemptsRef.current < WS_CONFIG.maxReconnectAttempts) {
                    reconnectAttemptsRef.current++;
                    setTimeout(connect, WS_CONFIG.reconnectInterval);
                } else {
                    // Fall back to mock mode
                    startMockSimulation();
                }
            };

            ws.onerror = () => {
                ws.close();
            };
        } catch {
            // WebSocket not available — start mock mode
            startMockSimulation();
        }
    }, [processTick]);

    // ── Mock simulation fallback ──
    const startMockSimulation = useCallback(() => {
        if (mockIntervalRef.current) return;

        mockIntervalRef.current = setInterval(() => {
            let drivers = simulateTick(driversRef.current);
            drivers = simulatePositionChanges(drivers);
            driversRef.current = drivers;
        }, 50); // ~20 FPS simulation
    }, []);

    // ── Periodic leaderboard sync (throttled to avoid excess re-renders) ──
    useEffect(() => {
        leaderboardTimerRef.current = setInterval(() => {
            const sorted = [...driversRef.current].sort((a, b) => a.position - b.position);
            setLeaderboard(sorted);
        }, 500); // Update leaderboard 2x per second

        return () => {
            if (leaderboardTimerRef.current) clearInterval(leaderboardTimerRef.current);
        };
    }, []);

    // ── Connect on mount ──
    useEffect(() => {
        connect();

        return () => {
            if (wsRef.current) wsRef.current.close();
            if (mockIntervalRef.current) clearInterval(mockIntervalRef.current);
        };
    }, [connect]);

    return {
        driversRef,
        leaderboard,
        trackStatus,
        isConnected,
        selectedDriverId,
        setSelectedDriverId,
    };
}
