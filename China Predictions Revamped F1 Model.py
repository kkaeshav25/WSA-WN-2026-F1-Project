import os
import fastf1
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error
import json

YEAR = 2026
GP_EVENT = 2
N_LAPS = 56

DRIVER_MAPPING = {
    'Lando Norris':'NOR', 'Oscar Piastri':'PIA', 'Max Verstappen':'VER', 'Isack Hadjar':'HAD',
    'George Russell':'RUS', 'Kimi Antonelli':'ANT', 'Lewis Hamilton':'HAM', 'Charles Leclerc':'LEC',
    'Carlos Sainz Jr':'SAI', 'Alex Albon':'ALB', 'Liam Lawson':'LAW', 'Fernando Alonso':'ALO', 'Lance Stroll':'STR',
    'Esteban Ocon':'OCO', 'Nico Hulkenberg':'HUL', 'Gabriel Bortoleto':'BOR', 'Pierre Gasly':'GAS',
    'Ollie Bearman':'BEA', 'Arvid Lindblad':'LIN', 'Franco Colapinto':'COL', 'Sergio Perez':'PER', 'Valterri Bottas':'BOT'
}

# Helper functions

def as_seconds(timedelta_series):
    if hasattr(timedelta_series, 'dt'):
        return timedelta_series.dt.total_seconds()
    return pd.to_numeric(timedelta_series, errors='coerce')


def extract_pre_race_features(year, gp):
    sessions = {}
    for label, sname in [('FP1','FP1'), ('FP2','FP2'), ('Q','Q')]:
        try:
            s = fastf1.get_session(year, gp, sname)
            s.load(laps=True)
            sessions[label] = s
        except Exception as e:
            print(f'WARNING: cannot load {label}: {e}')
            sessions[label] = None

    # Save session data for front-end
    q_session = sessions.get('Q')
    metadata = {
        'circuit_data': None,
        'drivers_data': {},
        'session_data': {},
        'driver_name_map': {},
    }
    if q_session:
        # Extract circuit info
        circuit_data = {
            'outline': CHINA_TRACK,
            'corners': [],  # Can add corners if needed
            'rotation': 0  # Assume no rotation for now
        }

        # Extract driver info
        drivers_data = {}
        for drv_num in q_session.drivers:
            drv_info = q_session.get_driver(drv_num)
            drivers_data[str(drv_num)] = {
                'abbreviation': drv_info.Abbreviation,
                'full_name': drv_info.FullName,
                'first_name': drv_info.FirstName,
                'last_name': drv_info.LastName,
                'team': drv_info.TeamName,
                'team_color': drv_info.TeamColor
            }

        # Extract telemetry timeline
        telemetry_data = {}
        for drv_num in q_session.drivers:
            try:
                tel = q_session.car_data[str(drv_num)]
                if not tel.empty:
                    telemetry_data[str(drv_num)] = tel[['Time', 'X', 'Y', 'Speed', 'RPM', 'Gear', 'Throttle', 'Brake', 'DRS']].dropna().to_dict('records')
                    # Rename columns to match expected format
                    for sample in telemetry_data[str(drv_num)]:
                        sample['t'] = sample.pop('Time').total_seconds()
                        sample['spd'] = sample.pop('Speed')
                        sample['rpm'] = sample.pop('RPM')
                        sample['gear'] = sample.pop('Gear')
                        sample['thr'] = sample.pop('Throttle')
                        sample['brk'] = sample.pop('Brake')
                        sample['drs'] = sample.pop('DRS')
            except:
                pass

        # Extract lap data
        laps_data = []
        for _, lap in q_session.laps.iterrows():
            laps_data.append({
                'driver_number': lap['DriverNumber'],
                'lap_number': lap['LapNumber'],
                'lap_time': lap['LapTime'].total_seconds() if pd.notna(lap['LapTime']) else None,
                'sector1_time': lap['Sector1Time'].total_seconds() if pd.notna(lap['Sector1Time']) else None,
                'sector2_time': lap['Sector2Time'].total_seconds() if pd.notna(lap['Sector2Time']) else None,
                'sector3_time': lap['Sector3Time'].total_seconds() if pd.notna(lap['Sector3Time']) else None,
                'compound': lap['Compound'],
                'tyre_life': lap['TyreLife'],
                'position': lap['Position']
            })

        # Session info
        session_data = {
            'name': q_session.name,
            'event': q_session.event['EventName'],
            'year': year
        }

        driver_name_to_number = {}
        for drv_num in q_session.drivers:
            drv_info = q_session.get_driver(drv_num)
            if drv_info is not None:
                driver_name_to_number[drv_info.FullName] = drv_num
                driver_name_to_number[drv_info.Abbreviation] = drv_num
                driver_name_to_number[str(drv_num)] = drv_num

        metadata = {
            'circuit_data': circuit_data,
            'drivers_data': drivers_data,
            'session_data': session_data,
            'driver_name_map': driver_name_to_number,
        }

    fp_laps = pd.DataFrame()
    for label in ['FP1','FP2']:
        s = sessions.get(label)
        if s is None or s.laps.empty:
            continue
        laps = s.laps.pick_track_status('1').copy().dropna(subset=['LapTime'])
        fp_laps = pd.concat([fp_laps, laps], ignore_index=True)

    q_laps = pd.DataFrame()
    if sessions.get('Q') is not None and not sessions['Q'].laps.empty:
        q_laps = sessions['Q'].laps.pick_track_status('1').copy().dropna(subset=['LapTime'])

    def summary_features(laps, prefix):
        if laps.empty:
            return pd.DataFrame(columns=['Driver'])
        df = laps.copy()
        df['LapTime_s'] = as_seconds(df['LapTime'])
        df['TyreLife_f'] = df['TyreLife'].fillna(0)
        summary = df.groupby('Driver').agg(**{
            f'{prefix}_lap_mean': ('LapTime_s','mean'),
            f'{prefix}_lap_std': ('LapTime_s','std'),
            f'{prefix}_tyre': ('TyreLife_f','mean')
        }).reset_index()
        return summary

    fp_features = summary_features(fp_laps,'fp')
    q_features = summary_features(q_laps,'q')

    if not q_laps.empty:
        q_best = q_laps.groupby('Driver').agg(q_best=('LapTime', lambda x: x.dt.total_seconds().min())).reset_index()
        q_features = q_features.merge(q_best, on='Driver', how='left')
    else:
        q_features['q_best'] = np.nan

    features = fp_features.merge(q_features, on='Driver', how='outer')
    features['DriverCode'] = features['Driver'].map(DRIVER_MAPPING).fillna('UNK')

    for col in ['fp_lap_mean','fp_lap_std','fp_tyre','q_lap_mean','q_lap_std','q_tyre','q_best']:
        if col not in features.columns:
            features[col] = 0.0
        features[col] = features[col].fillna(features[col].mean() if features[col].notna().any() else 0.0)

    return features, metadata


def train_historical_model(historical_df):
    cols = ['q_best','q_lap_mean','q_lap_std','fp_lap_mean','fp_lap_std','fp_tyre']
    X = historical_df[cols].fillna(0)
    y = historical_df['lap_time'].fillna(0)
    X_train,X_test,y_train,y_test = train_test_split(X,y,test_size=0.25,random_state=42)
    model=RandomForestRegressor(n_estimators=300,random_state=42,n_jobs=-1)
    model.fit(X_train,y_train)
    print('historical model MAE',mean_absolute_error(y_test,model.predict(X_test)))
    return model


def simulate_race(pre_features, model, n_laps, sc_laps=None):
    sc_laps=set(sc_laps or [])
    rows=[]
    rank_frame = pre_features.sort_values('q_best',na_position='last').reset_index(drop=True)

    for idx,row in pre_features.iterrows():
        driver=row['Driver']
        cum=0.0
        pit_laps=[int(n_laps*0.33),int(n_laps*0.67)] if idx<14 else [int(n_laps*0.35),int(n_laps*0.72)]

        for lap in range(1,n_laps+1):
            X=pd.DataFrame([{'q_best':row['q_best'],'q_lap_mean':row['q_lap_mean'],'q_lap_std':row['q_lap_std'],
                             'fp_lap_mean':row['fp_lap_mean'],'fp_lap_std':row['fp_lap_std'],'fp_tyre':row['fp_tyre']}])
            lap_base=model.predict(X)[0]
            lap_time=lap_base*(1+0.00075*lap)
            if lap in sc_laps: lap_time*=1.2
            if lap in pit_laps: lap_time+=22.0
            lap_time*=1.0-min(0.04,0.0007*lap)
            cum+=lap_time
            rows.append({'Driver':driver,'lap':lap,'lap_time':lap_time,'cum_time':cum,'pit':int(lap in pit_laps),'sc':int(lap in sc_laps)})

    sim=pd.DataFrame(rows)
    sim['position']=sim.groupby('lap')['cum_time'].rank(method='min')
    return sim

CHINA_TRACK = [
    {'x': 100, 'y': 120}, {'x': 220, 'y': 100}, {'x': 320, 'y': 140}, {'x': 380, 'y': 220},
    {'x': 400, 'y': 320}, {'x': 380, 'y': 420}, {'x': 300, 'y': 470}, {'x': 200, 'y': 500},
    {'x': 120, 'y': 470}, {'x': 80, 'y': 380}, {'x': 90, 'y': 280}, {'x': 130, 'y': 190},
    {'x': 180, 'y': 140}, {'x': 240, 'y': 120}, {'x': 320, 'y': 130}, {'x': 380, 'y': 180},
    {'x': 420, 'y': 240}, {'x': 430, 'y': 320}, {'x': 400, 'y': 390}, {'x': 320, 'y': 430},
    {'x': 220, 'y': 430}, {'x': 140, 'y': 390}, {'x': 120, 'y': 300}, {'x': 140, 'y': 210},
    {'x': 180, 'y': 160}, {'x': 240, 'y': 140}, {'x': 320, 'y': 150}, {'x': 380, 'y': 200},
    {'x': 410, 'y': 260}, {'x': 410, 'y': 320}, {'x': 390, 'y': 360}, {'x': 340, 'y': 390},
    {'x': 280, 'y': 400}, {'x': 220, 'y': 390}, {'x': 180, 'y': 350}, {'x': 160, 'y': 300},
    {'x': 170, 'y': 250}, {'x': 200, 'y': 210}, {'x': 250, 'y': 180}, {'x': 310, 'y': 170},
    {'x': 360, 'y': 190}, {'x': 390, 'y': 230}, {'x': 400, 'y': 280}, {'x': 390, 'y': 320},
    {'x': 360, 'y': 350}, {'x': 320, 'y': 370}, {'x': 270, 'y': 375}, {'x': 220, 'y': 360},
    {'x': 185, 'y': 330}, {'x': 170, 'y': 300}, {'x': 165, 'y': 270}, {'x': 170, 'y': 240},
    {'x': 185, 'y': 215}, {'x': 210, 'y': 195}, {'x': 245, 'y': 180}, {'x': 290, 'y': 170},
    {'x': 335, 'y': 175}, {'x': 370, 'y': 195}, {'x': 390, 'y': 225}, {'x': 395, 'y': 255},
    {'x': 390, 'y': 285}, {'x': 370, 'y': 310}, {'x': 340, 'y': 330}, {'x': 305, 'y': 340},
    {'x': 265, 'y': 345}, {'x': 225, 'y': 340}, {'x': 190, 'y': 325}, {'x': 170, 'y': 300},
    {'x': 165, 'y': 275}, {'x': 170, 'y': 250}, {'x': 185, 'y': 225}, {'x': 210, 'y': 205},
    {'x': 245, 'y': 190}, {'x': 290, 'y': 180}, {'x': 335, 'y': 185}, {'x': 370, 'y': 205},
    {'x': 390, 'y': 235}, {'x': 395, 'y': 265}, {'x': 390, 'y': 295}, {'x': 370, 'y': 320},
    {'x': 340, 'y': 335}, {'x': 305, 'y': 345}, {'x': 270, 'y': 350}, {'x': 235, 'y': 345},
    {'x': 205, 'y': 330}, {'x': 185, 'y': 305}, {'x': 175, 'y': 280}, {'x': 170, 'y': 255},
    {'x': 175, 'y': 230}, {'x': 190, 'y': 210}, {'x': 215, 'y': 195}, {'x': 250, 'y': 185},
    {'x': 290, 'y': 180}, {'x': 330, 'y': 185}, {'x': 360, 'y': 200}, {'x': 380, 'y': 225},
    {'x': 385, 'y': 255}, {'x': 380, 'y': 285}, {'x': 365, 'y': 310}, {'x': 345, 'y': 325},
    {'x': 320, 'y': 335}, {'x': 290, 'y': 340}, {'x': 260, 'y': 340}, {'x': 230, 'y': 330},
    {'x': 210, 'y': 315}, {'x': 195, 'y': 295}, {'x': 190, 'y': 275}, {'x': 190, 'y': 255},
    {'x': 195, 'y': 235}, {'x': 205, 'y': 215}, {'x': 220, 'y': 200}, {'x': 245, 'y': 185},
    {'x': 275, 'y': 175}, {'x': 310, 'y': 170}, {'x': 345, 'y': 175}, {'x': 370, 'y': 190},
    {'x': 385, 'y': 215}, {'x': 390, 'y': 240}, {'x': 385, 'y': 265}, {'x': 370, 'y': 290},
    {'x': 345, 'y': 310}, {'x': 315, 'y': 325}, {'x': 280, 'y': 335}, {'x': 245, 'y': 340},
    {'x': 210, 'y': 340}, {'x': 180, 'y': 325}, {'x': 160, 'y': 300}, {'x': 155, 'y': 270},
    {'x': 160, 'y': 240}, {'x': 175, 'y': 215}, {'x': 195, 'y': 195}, {'x': 225, 'y': 180},
    {'x': 260, 'y': 170}, {'x': 295, 'y': 170}, {'x': 330, 'y': 175}, {'x': 360, 'y': 190},
    {'x': 380, 'y': 215}, {'x': 390, 'y': 240}, {'x': 390, 'y': 265}, {'x': 380, 'y': 290},
    {'x': 360, 'y': 310}, {'x': 335, 'y': 325}, {'x': 305, 'y': 335}, {'x': 270, 'y': 340},
    {'x': 235, 'y': 340}, {'x': 200, 'y': 330}, {'x': 175, 'y': 305}, {'x': 160, 'y': 275},
    {'x': 155, 'y': 245}, {'x': 160, 'y': 215}, {'x': 175, 'y': 190}, {'x': 200, 'y': 175},
    {'x': 230, 'y': 165}, {'x': 265, 'y': 160}, {'x': 300, 'y': 160}, {'x': 335, 'y': 165},
    {'x': 365, 'y': 180}, {'x': 385, 'y': 205}, {'x': 395, 'y': 230}, {'x': 395, 'y': 255},
    {'x': 385, 'y': 280}, {'x': 365, 'y': 300}, {'x': 340, 'y': 315}, {'x': 310, 'y': 325},
    {'x': 280, 'y': 330}, {'x': 250, 'y': 330}, {'x': 220, 'y': 320}, {'x': 195, 'y': 300},
    {'x': 180, 'y': 275}, {'x': 175, 'y': 250}, {'x': 180, 'y': 220}, {'x': 195, 'y': 195},
    {'x': 220, 'y': 175}, {'x': 250, 'y': 165}, {'x': 285, 'y': 160}, {'x': 320, 'y': 160},
    {'x': 355, 'y': 170}, {'x': 380, 'y': 190}, {'x': 395, 'y': 215}, {'x': 400, 'y': 235},
    {'x': 395, 'y': 255}, {'x': 380, 'y': 275}, {'x': 355, 'y': 290}, {'x': 325, 'y': 305},
    {'x': 290, 'y': 315}, {'x': 255, 'y': 320}, {'x': 220, 'y': 320}, {'x': 190, 'y': 310},
    {'x': 170, 'y': 290}, {'x': 160, 'y': 265}, {'x': 160, 'y': 235}, {'x': 170, 'y': 205},
    {'x': 190, 'y': 180}, {'x': 220, 'y': 165}, {'x': 255, 'y': 155}, {'x': 290, 'y': 155},
    {'x': 325, 'y': 160}, {'x': 355, 'y': 170}, {'x': 380, 'y': 190}, {'x': 395, 'y': 210},
    {'x': 400, 'y': 230}, {'x': 395, 'y': 250}, {'x': 380, 'y': 270}, {'x': 355, 'y': 285},
    {'x': 325, 'y': 295}, {'x': 290, 'y': 305}, {'x': 255, 'y': 310}, {'x': 220, 'y': 310},
    {'x': 190, 'y': 300}, {'x': 170, 'y': 280}, {'x': 160, 'y': 255}, {'x': 160, 'y': 225},
    {'x': 170, 'y': 195}, {'x': 190, 'y': 175}, {'x': 220, 'y': 160}, {'x': 255, 'y': 150},
    {'x': 290, 'y': 150}, {'x': 325, 'y': 155}, {'x': 355, 'y': 165}, {'x': 380, 'y': 185},
    {'x': 395, 'y': 205}, {'x': 400, 'y': 225}, {'x': 395, 'y': 245}, {'x': 380, 'y': 265},
    {'x': 355, 'y': 280}, {'x': 325, 'y': 290}, {'x': 290, 'y': 300}, {'x': 255, 'y': 305},
    {'x': 220, 'y': 305}, {'x': 190, 'y': 295}, {'x': 170, 'y': 275}, {'x': 160, 'y': 250},
    {'x': 160, 'y': 220}, {'x': 170, 'y': 190}, {'x': 190, 'y': 170}, {'x': 220, 'y': 155},
    {'x': 255, 'y': 145}, {'x': 290, 'y': 145}, {'x': 325, 'y': 150}, {'x': 355, 'y': 160},
    {'x': 380, 'y': 180}, {'x': 395, 'y': 200}, {'x': 400, 'y': 220}, {'x': 395, 'y': 240},
    {'x': 380, 'y': 260}, {'x': 355, 'y': 275}, {'x': 325, 'y': 285}, {'x': 290, 'y': 295},
    {'x': 255, 'y': 300}, {'x': 220, 'y': 300}, {'x': 190, 'y': 290}, {'x': 170, 'y': 270},
    {'x': 160, 'y': 245}, {'x': 160, 'y': 215}, {'x': 170, 'y': 185}, {'x': 190, 'y': 165},
    {'x': 220, 'y': 150}, {'x': 255, 'y': 140}, {'x': 290, 'y': 140}, {'x': 325, 'y': 145},
    {'x': 355, 'y': 155}, {'x': 380, 'y': 175}, {'x': 395, 'y': 195}, {'x': 400, 'y': 215},
    {'x': 395, 'y': 235}, {'x': 380, 'y': 255}, {'x': 355, 'y': 270}, {'x': 325, 'y': 280},
    {'x': 290, 'y': 290}, {'x': 255, 'y': 295}, {'x': 220, 'y': 295}, {'x': 190, 'y': 285},
    {'x': 170, 'y': 265}, {'x': 160, 'y': 240}, {'x': 160, 'y': 210}, {'x': 170, 'y': 180},
    {'x': 190, 'y': 160}, {'x': 220, 'y': 145}, {'x': 255, 'y': 135}, {'x': 290, 'y': 135},
    {'x': 325, 'y': 140}, {'x': 355, 'y': 150}, {'x': 380, 'y': 170}, {'x': 395, 'y': 190},
    {'x': 400, 'y': 210}, {'x': 395, 'y': 230}, {'x': 380, 'y': 250}, {'x': 355, 'y': 265},
    {'x': 325, 'y': 275}, {'x': 290, 'y': 285}, {'x': 255, 'y': 290}, {'x': 220, 'y': 290},
    {'x': 190, 'y': 280}, {'x': 170, 'y': 260}, {'x': 160, 'y': 235}, {'x': 160, 'y': 205},
    {'x': 170, 'y': 175}, {'x': 190, 'y': 155}, {'x': 220, 'y': 140}, {'x': 255, 'y': 130},
    {'x': 290, 'y': 130}, {'x': 325, 'y': 135}, {'x': 355, 'y': 145}, {'x': 380, 'y': 165},
    {'x': 395, 'y': 185}, {'x': 400, 'y': 205}, {'x': 395, 'y': 225}, {'x': 380, 'y': 245},
    {'x': 355, 'y': 260}, {'x': 325, 'y': 270}, {'x': 290, 'y': 280}, {'x': 255, 'y': 285},
    {'x': 220, 'y': 285}, {'x': 190, 'y': 275}, {'x': 170, 'y': 255}, {'x': 160, 'y': 230},
    {'x': 160, 'y': 200}, {'x': 170, 'y': 170}, {'x': 190, 'y': 150}, {'x': 220, 'y': 135},
    {'x': 255, 'y': 125}, {'x': 290, 'y': 125}, {'x': 325, 'y': 130}, {'x': 355, 'y': 140},
    {'x': 380, 'y': 160}, {'x': 395, 'y': 180}, {'x': 400, 'y': 200}, {'x': 395, 'y': 220},
    {'x': 380, 'y': 240}, {'x': 355, 'y': 255}, {'x': 325, 'y': 265}, {'x': 290, 'y': 275},
    {'x': 255, 'y': 280}, {'x': 220, 'y': 280}, {'x': 190, 'y': 270}, {'x': 170, 'y': 250},
    {'x': 160, 'y': 225}, {'x': 160, 'y': 195}, {'x': 170, 'y': 165}, {'x': 190, 'y': 145},
    {'x': 220, 'y': 130}, {'x': 255, 'y': 120}, {'x': 290, 'y': 120}, {'x': 325, 'y': 125},
    {'x': 355, 'y': 135}, {'x': 380, 'y': 155}, {'x': 395, 'y': 175}, {'x': 400, 'y': 195},
    {'x': 395, 'y': 215}, {'x': 380, 'y': 235}, {'x': 355, 'y': 250}, {'x': 325, 'y': 260},
    {'x': 290, 'y': 270}, {'x': 255, 'y': 275}, {'x': 220, 'y': 275}, {'x': 190, 'y': 265},
    {'x': 170, 'y': 245}, {'x': 160, 'y': 220}, {'x': 160, 'y': 190}, {'x': 170, 'y': 160},
    {'x': 190, 'y': 140}, {'x': 220, 'y': 125}, {'x': 255, 'y': 115}, {'x': 290, 'y': 115},
    {'x': 325, 'y': 120}, {'x': 355, 'y': 130}, {'x': 380, 'y': 150}, {'x': 395, 'y': 170},
    {'x': 400, 'y': 190}, {'x': 395, 'y': 210}, {'x': 380, 'y': 230}, {'x': 355, 'y': 245},
    {'x': 325, 'y': 255}, {'x': 290, 'y': 265}, {'x': 255, 'y': 270}, {'x': 220, 'y': 270},
    {'x': 190, 'y': 260}, {'x': 170, 'y': 240}, {'x': 160, 'y': 215}, {'x': 160, 'y': 185},
    {'x': 170, 'y': 155}, {'x': 190, 'y': 135}, {'x': 220, 'y': 120}, {'x': 255, 'y': 110},
    {'x': 290, 'y': 110}, {'x': 325, 'y': 115}, {'x': 355, 'y': 125}, {'x': 380, 'y': 145},
    {'x': 395, 'y': 165}, {'x': 400, 'y': 185}, {'x': 395, 'y': 205}, {'x': 380, 'y': 225},
    {'x': 355, 'y': 240}, {'x': 325, 'y': 250}, {'x': 290, 'y': 260}, {'x': 255, 'y': 265},
    {'x': 220, 'y': 265}, {'x': 190, 'y': 255}, {'x': 170, 'y': 235}, {'x': 160, 'y': 210},
    {'x': 160, 'y': 180}, {'x': 170, 'y': 150}, {'x': 190, 'y': 130}, {'x': 220, 'y': 115},
    {'x': 255, 'y': 105}, {'x': 290, 'y': 105}, {'x': 325, 'y': 110}, {'x': 355, 'y': 120},
    {'x': 380, 'y': 140}, {'x': 395, 'y': 160}, {'x': 400, 'y': 180}, {'x': 395, 'y': 200},
    {'x': 380, 'y': 220}, {'x': 355, 'y': 235}, {'x': 325, 'y': 245}, {'x': 290, 'y': 255},
    {'x': 255, 'y': 260}, {'x': 220, 'y': 260}, {'x': 190, 'y': 250}, {'x': 170, 'y': 230},
    {'x': 160, 'y': 205}, {'x': 160, 'y': 175}, {'x': 170, 'y': 145}, {'x': 190, 'y': 125},
    {'x': 220, 'y': 110}, {'x': 255, 'y': 100}, {'x': 290, 'y': 100}, {'x': 325, 'y': 105},
    {'x': 355, 'y': 115}, {'x': 380, 'y': 135}, {'x': 395, 'y': 155}, {'x': 400, 'y': 175},
    {'x': 395, 'y': 195}, {'x': 380, 'y': 215}, {'x': 355, 'y': 230}, {'x': 325, 'y': 240},
    {'x': 290, 'y': 250}, {'x': 255, 'y': 255}, {'x': 220, 'y': 255}, {'x': 190, 'y': 245},
    {'x': 170, 'y': 225}, {'x': 160, 'y': 200}, {'x': 160, 'y': 170}, {'x': 170, 'y': 140},
    {'x': 190, 'y': 120}, {'x': 220, 'y': 105}, {'x': 255, 'y': 95}, {'x': 290, 'y': 95},
    {'x': 325, 'y': 100}, {'x': 355, 'y': 110}, {'x': 380, 'y': 130}, {'x': 395, 'y': 150},
    {'x': 400, 'y': 170}, {'x': 395, 'y': 190}, {'x': 380, 'y': 210}, {'x': 355, 'y': 225},
    {'x': 325, 'y': 235}, {'x': 290, 'y': 245}, {'x': 255, 'y': 250}, {'x': 220, 'y': 250},
    {'x': 190, 'y': 240}, {'x': 170, 'y': 220}, {'x': 160, 'y': 195}, {'x': 160, 'y': 165},
    {'x': 170, 'y': 135}, {'x': 190, 'y': 115}, {'x': 220, 'y': 100}, {'x': 255, 'y': 90},
    {'x': 290, 'y': 90}, {'x': 325, 'y': 95}, {'x': 355, 'y': 105}, {'x': 380, 'y': 125},
    {'x': 395, 'y': 145}, {'x': 400, 'y': 165}, {'x': 395, 'y': 185}, {'x': 380, 'y': 205},
    {'x': 355, 'y': 220}, {'x': 325, 'y': 230}, {'x': 290, 'y': 240}, {'x': 255, 'y': 245},
    {'x': 220, 'y': 245}, {'x': 190, 'y': 235}, {'x': 170, 'y': 215}, {'x': 160, 'y': 190},
    {'x': 160, 'y': 160}, {'x': 170, 'y': 130}, {'x': 190, 'y': 110}, {'x': 220, 'y': 95},
    {'x': 255, 'y': 85}, {'x': 290, 'y': 85}, {'x': 325, 'y': 90}, {'x': 355, 'y': 100},
    {'x': 380, 'y': 120}, {'x': 395, 'y': 140}, {'x': 400, 'y': 160}, {'x': 395, 'y': 180}
]


def sample_track_xy(dist, track=CHINA_TRACK, track_length_m=5400):
    if dist < 0:
        dist = 0.0
    frac = (dist % track_length_m) / track_length_m
    segments = []
    total = 0.0
    for i in range(len(track) - 1):
        x1, y1 = track[i]['x'], track[i]['y']
        x2, y2 = track[i + 1]['x'], track[i + 1]['y']
        seg_len = np.hypot(x2 - x1, y2 - y1)
        segments.append((x1, y1, x2, y2, seg_len))
        total += seg_len

    if total == 0:
        return {'x': track[0]['x'], 'y': track[0]['y']}

    target = frac * total
    acc = 0.0
    for x1, y1, x2, y2, seg_len in segments:
        if acc + seg_len >= target or seg_len == 0:
            if seg_len == 0:
                return {'x': x1, 'y': y1}
            ratio = (target - acc) / seg_len
            return {'x': x1 + (x2 - x1) * ratio, 'y': y1 + (y2 - y1) * ratio}
        acc += seg_len

    return {'x': track[-1]['x'], 'y': track[-1]['y']}


def generate_telemetry(lap_time,n_points=362,track_length_m=5400):
    dist=np.linspace(0,track_length_m,n_points)
    speed=track_length_m/lap_time
    time=dist/speed
    xys = [sample_track_xy(d, track=CHINA_TRACK, track_length_m=track_length_m) for d in dist]
    return pd.DataFrame({
        'distance_m': dist,
        't': time,
        'lap': np.ones_like(time, dtype=int),
        'x': [p['x'] for p in xys],
        'y': [p['y'] for p in xys],
    })


if __name__=='__main__':
    pre, metadata = extract_pre_race_features(YEAR,GP_EVENT)
    hist='historical_race_train.csv'
    if os.path.exists(hist):
        historical=pd.read_csv(hist)
        model=train_historical_model(historical)
    else:
        print('No historical CSV; generating synthetic historical training (demo only)')
        synt=[]
        for _,r in pre.iterrows():
            for lap in range(1,N_LAPS+1):
                base=r['q_best']*1.04+0.25*(lap-1)
                synt.append({'q_best':r['q_best'],'q_lap_mean':r['q_lap_mean'],'q_lap_std':r['q_lap_std'],
                             'fp_lap_mean':r['fp_lap_mean'],'fp_lap_std':r['fp_lap_std'],'fp_tyre':r['fp_tyre'],
                             'lap_time':base+np.random.normal(0,0.25)})
        model=train_historical_model(pd.DataFrame(synt))

    simulation=simulate_race(pre,model,N_LAPS,sc_laps=[17,32])
    final=simulation[simulation['lap']==N_LAPS].sort_values('cum_time').reset_index(drop=True)
    print('Projected race finish:')
    print(final[['position','Driver','cum_time']].head(22))

    # Build minimal frontend race payload from the simulated event
    race_mock = {
        'circuit': metadata.get('circuit_data') or {'outline': CHINA_TRACK, 'corners': [], 'rotation': 0},
        'drivers': metadata.get('drivers_data') or {},
        'laps': [],
        'detailed_laps': [],
        'session': metadata.get('session_data') or {'name': 'Simulated Session', 'event': 'Simulated GP', 'year': YEAR},
    }

    for _, row in simulation.iterrows():
        driver_name = row['Driver']
        driver_number = metadata['driver_name_map'].get(driver_name)
        if driver_number is None:
            continue

        lap_start = row['cum_time'] - row['lap_time']
        sector1 = row['lap_time'] * 0.30
        sector2 = row['lap_time'] * 0.32
        sector3 = row['lap_time'] - sector1 - sector2

        race_mock['laps'].append({
            'driver_number': int(driver_number),
            'lap_number': int(row['lap']),
            'lap_time': float(row['lap_time']),
            'position': int(row['position'])
        })

        race_mock['detailed_laps'].append({
            'driver_number': int(driver_number),
            'lap_number': int(row['lap']),
            'lap_time': float(row['lap_time']),
            'lap_time_str': str(pd.to_timedelta(row['lap_time'], unit='s')),
            'lap_start_time': float(lap_start),
            'lap_end_time': float(row['cum_time']),
            'sector1_time': float(sector1),
            'sector2_time': float(sector2),
            'sector3_time': float(sector3),
            'sector1_session_time': float(lap_start + sector1),
            'sector2_session_time': float(lap_start + sector1 + sector2),
            'sector3_session_time': float(lap_start + sector1 + sector2 + sector3),
            'compound': 'MEDIUM' if row['pit'] else 'SOFT',
            'tyre_life': 0 if row['pit'] else 1,
        })

    with open('frontend/public/race_mock.json', 'w') as f:
        json.dump(race_mock, f, indent=2)
    print('Generated frontend race_mock.json from simulated race event')

    # Compute lap start times
    lap_starts = {}
    for _, row in simulation.iterrows():
        driver = row['Driver']
        lap = row['lap']
        cum_time = row['cum_time']
        lap_time = row['lap_time']
        start_time = cum_time - lap_time
        if driver not in lap_starts:
            lap_starts[driver] = {}
        lap_starts[driver][lap] = start_time

    # Save lap starts to JSON
    with open('frontend/public/lap_starts.json', 'w') as f:
        json.dump(lap_starts, f, indent=2)

    # Generate telemetry for all drivers' first lap
    telemetry_data = {}
    for _, row in pre.iterrows():
        driver = row['Driver']
        lap1_data = simulation[(simulation['Driver'] == driver) & (simulation['lap'] == 1)]
        if not lap1_data.empty:
            lap_time = lap1_data.iloc[0]['lap_time']
            telemetry = generate_telemetry(lap_time)
            telemetry_data[driver] = telemetry.to_dict('records')  # list of dicts

    # Save telemetry to JSON
    with open('frontend/public/telemetry.json', 'w') as f:
        json.dump(telemetry_data, f, indent=2)

    print(f"Telemetry generated for {len(telemetry_data)} drivers and saved to frontend/public/telemetry.json")
    print("Lap starts saved to frontend/public/lap_starts.json")

    leader=final.iloc[0]['Driver']
    lap1=simulation[(simulation['Driver']==leader)&(simulation['lap']==1)].iloc[0]['lap_time']
    telemetry=generate_telemetry(lap1)
    print('Telem points for leader lap1:',len(telemetry))
