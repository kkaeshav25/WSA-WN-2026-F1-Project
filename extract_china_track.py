"""
Extract the real Shanghai International Circuit track outline from FastF1.
Uses the fastest lap telemetry from the 2024 China GP qualifying session
to get real X/Y coordinates of the track.
"""
import fastf1
import json
import numpy as np

# Try 2024 China GP first (it returned to the calendar in 2024)
# If that doesn't work, try 2019 (last pre-COVID China GP)
YEARS_TO_TRY = [2024, 2019]
GP_NAME = 'China'

def extract_track(year, gp):
    """Extract track outline and corner data from a qualifying session."""
    print(f"Trying {year} {gp}...")
    session = fastf1.get_session(year, gp, 'Q')
    session.load(laps=True, telemetry=True)
    
    # Get the fastest lap for the best track outline
    fastest = session.laps.pick_fastest()
    if fastest is None:
        raise ValueError("No fastest lap found")
    
    # Get telemetry with position data
    tel = fastest.get_telemetry()
    
    if tel.empty or 'X' not in tel.columns or 'Y' not in tel.columns:
        raise ValueError("No position telemetry available")
    
    # Extract X, Y coordinates
    coords = tel[['X', 'Y']].dropna()
    
    # Downsample to ~300 points for smooth rendering without excessive data
    total_points = len(coords)
    step = max(1, total_points // 300)
    sampled = coords.iloc[::step]
    
    track_outline = [{'x': round(float(row.X), 1), 'y': round(float(row.Y), 1)} 
                     for _, row in sampled.iterrows()]
    
    print(f"  Extracted {len(track_outline)} track points from {total_points} telemetry samples")
    
    # Extract corner information
    corners = []
    try:
        circuit_info = session.get_circuit_info()
        if circuit_info is not None and hasattr(circuit_info, 'corners') and circuit_info.corners is not None:
            for _, c in circuit_info.corners.iterrows():
                corners.append({
                    'number': int(c['Number']),
                    'x': float(c['X']),
                    'y': float(c['Y']),
                    'angle': float(c.get('Angle', 0)),
                    'letter': str(c.get('Letter', '')),
                })
            print(f"  Extracted {len(corners)} corners")
    except Exception as e:
        print(f"  Could not extract corners: {e}")
    
    # Determine optimal rotation for display
    rotation = 0
    try:
        if circuit_info is not None and hasattr(circuit_info, 'rotation'):
            rotation = float(circuit_info.rotation)
            print(f"  Circuit rotation: {rotation}°")
    except:
        pass
    
    return {
        'outline': track_outline,
        'corners': corners,
        'rotation': rotation,
    }


if __name__ == '__main__':
    track_data = None
    
    for year in YEARS_TO_TRY:
        try:
            track_data = extract_track(year, GP_NAME)
            print(f"\nSuccessfully extracted China track from {year}!")
            break
        except Exception as e:
            print(f"  Failed for {year}: {e}")
            continue
    
    if track_data is None:
        print("ERROR: Could not extract China track from any year")
        exit(1)
    
    # Save standalone track file
    with open('frontend/public/china_track.json', 'w') as f:
        json.dump(track_data['outline'], f)
    print(f"Saved china_track.json ({len(track_data['outline'])} points)")
    
    # Update race_mock.json with real track
    with open('frontend/public/race_mock.json', 'r') as f:
        race_mock = json.load(f)
    
    race_mock['circuit'] = track_data
    
    with open('frontend/public/race_mock.json', 'w') as f:
        json.dump(race_mock, f, indent=2)
    print("Updated race_mock.json with real China track outline + corners + rotation")
    
    # Now regenerate telemetry to use the REAL track coordinates
    # We need to map each driver's telemetry points to the real track shape
    outline = track_data['outline']
    n_outline = len(outline)
    
    # Compute cumulative distances along real track
    cum_dist = [0.0]
    for i in range(1, n_outline):
        dx = outline[i]['x'] - outline[i-1]['x']
        dy = outline[i]['y'] - outline[i-1]['y']
        cum_dist.append(cum_dist[-1] + np.hypot(dx, dy))
    total_track_length = cum_dist[-1]
    
    def sample_real_track(frac):
        """Sample x,y on the real track at a given fraction [0, 1]."""
        target = frac * total_track_length
        for i in range(1, n_outline):
            if cum_dist[i] >= target:
                seg_frac = (target - cum_dist[i-1]) / (cum_dist[i] - cum_dist[i-1]) if cum_dist[i] != cum_dist[i-1] else 0
                x = outline[i-1]['x'] + seg_frac * (outline[i]['x'] - outline[i-1]['x'])
                y = outline[i-1]['y'] + seg_frac * (outline[i]['y'] - outline[i-1]['y'])
                return round(x, 1), round(y, 1)
        return outline[-1]['x'], outline[-1]['y']
    
    # Load existing telemetry and remap coordinates to real track
    with open('frontend/public/telemetry.json', 'r') as f:
        old_telemetry = json.load(f)
    
    N_POINTS = 24  # Same as original
    new_telemetry = {}
    for driver_name, points in old_telemetry.items():
        if not points:
            continue
        # Each driver has N_POINTS evenly spaced along the track
        # Keep the timing (t values) but replace x/y with real track coords
        max_t = points[-1]['t'] if points else 1.0
        new_points = []
        for p in points:
            frac = (p['t'] / max_t) if max_t > 0 else 0
            frac = min(frac, 0.999)  # Don't wrap to start
            x, y = sample_real_track(frac)
            new_points.append({
                'distance_m': p.get('distance_m', 0),
                't': p['t'],
                'lap': p.get('lap', 1),
                'x': x,
                'y': y,
            })
        new_telemetry[driver_name] = new_points
    
    with open('frontend/public/telemetry.json', 'w') as f:
        json.dump(new_telemetry, f, indent=2)
    print(f"Regenerated telemetry.json with real track coordinates for {len(new_telemetry)} drivers")
    print(f"Track length: {total_track_length:.0f} units")
