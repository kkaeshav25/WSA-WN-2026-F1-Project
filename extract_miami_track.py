import fastf1
import numpy as np
import json

# Load 2024 Miami qualifying session for track data
session = fastf1.get_session(2024, 'Monaco', 'Q')
session.load(laps=True, telemetry=True)

# Get the fastest qualifying lap
fastest_lap = session.laps.pick_fastest()
telemetry = fastest_lap.get_telemetry()

# Extract X and Y coordinates
x_coords = telemetry['X'].values
y_coords = telemetry['Y'].values

# Combine into points
points = np.column_stack([x_coords, y_coords])

# Downsample to approximately 300 points using uniform spacing
target_points = 300
step = max(1, len(points) // target_points)
downsampled_points = points[::step]

# Ensure we're close to 300 points
if len(downsampled_points) > target_points:
    indices = np.linspace(0, len(points)-1, target_points, dtype=int)
    downsampled_points = points[indices]

# Convert to list of dictionaries
miami_track_outline = [{'x': float(p[0]), 'y': float(p[1])} for p in downsampled_points]

# Print as Python code that can be assigned
print("MIAMI_GP = " + json.dumps(miami_track_outline, indent=2))

print(f"\nExtracted {len(miami_track_outline)} points from Miami track")