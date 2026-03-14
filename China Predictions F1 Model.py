import fastf1
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error
#Loads the 2026 Australian GP free practice and qualifying such as LapTime
FP1_laps = fastf1.get_session(2026, 2, 'FP1')
FP1_laps.load()
FP1_26 = FP1_laps.laps.pick_track_status('1')
FP1_26.dropna(subset = ["LapTime"], inplace= True)
FP1_26["LapTime (s)"] = FP1_26["LapTime"].dt.total_seconds()

FP2_laps = fastf1.get_session(2026, 2, 'S')
FP2_laps.load()
FP2_26= FP2_laps.laps.pick_track_status('1')
FP2_26.dropna(subset = ["LapTime"], inplace= True)
FP2_26["LapTime (s)"] = FP2_26["LapTime"].dt.total_seconds()
#Sets up dataframe to contain qualifying time for drivers who stayed on from 2025 to 2026
qualifying_2026 = pd.DataFrame({
    "Driver": ["Lando Norris", "Oscar Piastri", "Max Verstappen", "Isack Hadjar",
                "George Russell", "Kimi Antonelli", "Lewis Hamilton", "Charles Leclerc",
                "Carlos Sainz Jr", "Alex Albon", "Liam Lawson", "Fernando Alonso", "Lance Stroll",
                "Esteban Ocon", "Nico Hulkenberg", "Gabriel Bortoleto", "Pierre Gasly",
                "Ollie Bearman", "Arvid Lindblad", "Franco Colapinto", "Sergio Perez", "Valterri Bottas"
                ],
    "QualifyingTime (s)":[92.608, 92.550, 93.002, 93.121, 92.286, 92.064,
                           92.415, 92.428, 94.317, 94.772, 93.765, 95.203, 95.995, 93.538, 93.354, 93.965, 92.873,
                           93.292, 93.784, 93.357, 96.906, 95.436]
})
#Maps driver names to "driver codes" as tracked on the API
driver_mapping = {
    "Lando Norris":"NOR", "Oscar Piastri" : "PIA", "Max Verstappen": "VER", "Isack Hadjar":"HAD",
                "George Russell":"RUS", "Kimi Antonelli":"ANT", "Lewis Hamilton":"HAM", "Charles Leclerc":"LEC",
                "Carlos Sainz Jr":"SAI", "Alex Albon":"ALB", "Liam Lawson":"LAW", "Fernando Alonso":"ALO", "Lance Stroll":"STR",
                "Esteban Ocon":"OCO", "Nico Hulkenberg":"HUL", "Gabriel Bortoleto":"BOR", "Pierre Gasly":"GAS",
                "Ollie Bearman":"BEA", "Arvid Lindblad":"LIN", "Franco Colapinto":"COL", "Sergio Perez":"PER", "Valterri Bottas":"BOT"
}
qualifying_2026["DriverCode"] = qualifying_2026["Driver"].map(driver_mapping)
#Left-Joins the qualifying time with the individual laptimes for each driver
all_fp = pd.concat([FP1_26, FP2_26], ignore_index=True)
merged_data = qualifying_2026.merge(all_fp, left_on = "DriverCode", right_on = "Driver")
# Convert sector times to seconds
merged_data["Sector1Time (s)"] = merged_data["Sector1Time"].dt.total_seconds()
merged_data["Sector2Time (s)"] = merged_data["Sector2Time"].dt.total_seconds()
merged_data["Sector3Time (s)"] = merged_data["Sector3Time"].dt.total_seconds()
# Compute average features per driver
driver_features = merged_data.groupby("DriverCode")[["Sector1Time (s)", "Sector2Time (s)", "Sector3Time (s)", "TyreLife"]].mean().reset_index()
qualifying_2026 = qualifying_2026.merge(driver_features, on="DriverCode")
#Sets up parameters for training/testing
X = merged_data[["QualifyingTime (s)", "Sector1Time (s)", "Sector2Time (s)", "Sector3Time (s)", "TyreLife"]]
y = merged_data["LapTime (s)"] - merged_data["QualifyingTime (s)"]  # Predict the delta between race lap time and qualifying time

if X.shape[0] == 0:
     raise ValueError("Dataset is empty after preprocessing. Check data sources!")

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size = 0.2, random_state = 39)
model = RandomForestRegressor(n_estimators=1000, random_state=39)
model.fit(X_train, y_train)
#Predicts and prints the model
predicted_deltas = model.predict(qualifying_2026[["QualifyingTime (s)", "Sector1Time (s)", "Sector2Time (s)", "Sector3Time (s)", "TyreLife"]]) * 0.1  # Scale down the delta adjustment to give more respect to qualifying grid
qualifying_2026["PredictedRaceTime (s)"] = qualifying_2026["QualifyingTime (s)"] + predicted_deltas

qualifying_2026 = qualifying_2026.sort_values(by = "PredictedRaceTime (s)")

print("\n Predicted 2026 Chinese GP Winner \n")
print(qualifying_2026[["Driver", "PredictedRaceTime (s)"]])
#Mean Absolute Error
y_pred = model.predict(X_test)
print(f"\n Model Error (MAE): {mean_absolute_error(y_test, y_pred):.2f} seconds")