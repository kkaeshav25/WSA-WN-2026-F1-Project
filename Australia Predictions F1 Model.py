import fastf1
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.metrics import mean_absolute_error
#Loads the 2025 Australian GP race data such as LapTime
session_2025 = fastf1.get_session(2025, 1, 'R')
session_2025.load()
laps_2025 = session_2025.laps.pick_track_status('1')
laps_2025.dropna(subset = ["LapTime"], inplace= True)
laps_2025["LapTime (s)"] = laps_2025["LapTime"].dt.total_seconds()
#Sets up dataframe to contain qualifying time for drivers who stayed on from 2025 to 2026
qualifying_2026 = pd.DataFrame({
    "Driver": ["Lando Norris", "Oscar Piastri", "Max Verstappen", "Isack Hadjar",
                "George Russell", "Kimi Antonelli", "Lewis Hamilton", "Charles Leclerc",
                "Carlos Sainz Jr", "Alex Albon", "Liam Lawson", "Fernando Alonso", "Lance Stroll",
                "Esteban Ocon", "Nico Hulkenberg", "Gabriel Bortoleto", "Pierre Gasly"
                ],
    "QualifyingTime (s)":[77.096, 77.180, 77.481, 78.175, 77.546, 78.525,
                           77.973, 77.755, 78.062, 77.737, 77.094, 78.453, 78.483, 79.147, 78.579, 78.516, 77.980 ]
})
#Maps driver names to "driver codes" as tracked on the API
driver_mapping = {
    "Lando Norris" : "NOR", "Oscar Piastri" : "PIA", "Max Verstappen": "VER", "Isack Hadjar":"HAD",
                "George Russell":"RUS", "Kimi Antonelli":"ANT", "Lewis Hamilton":"HAM", "Charles Leclerc":"LEC",
                "Carlos Sainz Jr":"SAI", "Alex Albon":"ALB", "Liam Lawson":"LAW", "Fernando Alonso":"ALO", "Lance Stroll":"STR",
                "Esteban Ocon":"OCO", "Nico Hulkenberg":"HUL", "Gabriel Bortoleto":"BOR", "Pierre Gasly":"GAS"
}
qualifying_2026["DriverCode"] = qualifying_2026["Driver"].map(driver_mapping)
#Left-Joins the qualifying time with the individual laptimes for each driver
merged_data = qualifying_2026.merge(laps_2025, left_on = "DriverCode", right_on = "Driver")
#Sets up parameters for training/testing
X = merged_data[["QualifyingTime (s)"]]
y = merged_data["LapTime (s)"]

if X.shape[0] == 0:
     raise ValueError("Dataset is empty after preprocessing. Check data sources!")

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size = 0.2, random_state = 39)
model = GradientBoostingRegressor(n_estimators= 100, learning_rate=0.1, random_state=39)
model.fit(X_train, y_train)
#Predicts and prints the model
predicted_lap_times = model.predict(qualifying_2026[["QualifyingTime (s)"]])
qualifying_2026["PredictedRaceTime (s)"] = predicted_lap_times

qualifying_2026 = qualifying_2026.sort_values(by = "PredictedRaceTime (s)")

print("\n Predicted 2026 Australian GP Winner \n")
print(qualifying_2026[["Driver", "PredictedRaceTime (s)"]])
#Mean Absolute Error
y_pred = model.predict(X_test)
print(f"\n Model Error (MAE): {mean_absolute_error(y_test, y_pred):.2f} seconds")