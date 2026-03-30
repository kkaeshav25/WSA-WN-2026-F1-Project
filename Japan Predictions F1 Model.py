import os
import fastf1
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error

YEAR = 2026
GP_EVENT = 3
N_LAPS = 53

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
    for label, sname in [('FP1','FP1'), ('FP2','FP2'), ('FP3', 'FP3'), ('Q','Q')]:
        try:
            s = fastf1.get_session(year, gp, sname)
            s.load(laps=True)
            sessions[label] = s
        except Exception as e:
            print(f'WARNING: cannot load {label}: {e}')
            sessions[label] = None

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

    return features


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


def generate_telemetry(lap_time,n_points=24,track_length_m=5400):
    dist=np.linspace(0,track_length_m,n_points)
    speed=track_length_m/lap_time
    time=dist/speed
    return pd.DataFrame({'distance_m':dist,'time_s':time})


if __name__=='__main__':
    pre=extract_pre_race_features(YEAR,GP_EVENT)
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

    leader=final.iloc[0]['Driver']
    lap1=simulation[(simulation['Driver']==leader)&(simulation['lap']==1)].iloc[0]['lap_time']
    telemetry=generate_telemetry(lap1)
    print('Telem points for leader lap1:',len(telemetry))
