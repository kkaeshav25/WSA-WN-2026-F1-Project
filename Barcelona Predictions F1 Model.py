import os
import fastf1
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error
import json

YEAR = 2026
GP_EVENT = 7
N_LAPS = 66

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
    for label, sname in [('FP1','FP1'), ('FP2','FP2'),('FP3', 'FP3'), ('Q','Q')]:
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
            'outline': MONACO_TRACK,
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
    for label in ['FP1','FP2', 'FP3']:
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

MONACO_TRACK = [{
    "x": -2582.882453222831,
    "y": -3519.3348040317615
  },
  {
    "x": -2481.0470044907247,
    "y": -3444.496746105783
  },
  {
    "x": -2365.3197782553625,
    "y": -3312.015111017055
  },
  {
    "x": -2315.7052491323834,
    "y": -3227.519402111199
  },
  {
    "x": -2269.0,
    "y": -3057.0
  },
  {
    "x": -2259.5721515344057,
    "y": -3012.2342398558817
  },
  {
    "x": -2263.0,
    "y": -2902.0
  },
  {
    "x": -2276.0,
    "y": -2798.0
  },
  {
    "x": -2310.0,
    "y": -2678.0
  },
  {
    "x": -2353.0,
    "y": -2578.0
  },
  {
    "x": -2381.6099542524307,
    "y": -2521.3185959094303
  },
  {
    "x": -2502.233302452758,
    "y": -2350.9294843043044
  },
  {
    "x": -2573.6785974834434,
    "y": -2263.7739391544246
  },
  {
    "x": -2618.5483199692376,
    "y": -2205.64482851614
  },
  {
    "x": -2709.0,
    "y": -2077.0
  },
  {
    "x": -2736.7071760171293,
    "y": -2027.1775091202921
  },
  {
    "x": -2743.0,
    "y": -1980.0
  },
  {
    "x": -2742.5518983582137,
    "y": -1856.8135771368688
  },
  {
    "x": -2699.1342558587294,
    "y": -1704.5181647366117
  },
  {
    "x": -2647.0,
    "y": -1611.0
  },
  {
    "x": -2625.0,
    "y": -1576.0
  },
  {
    "x": -2570.0,
    "y": -1496.0
  },
  {
    "x": -2472.0,
    "y": -1375.0
  },
  {
    "x": -2403.0,
    "y": -1299.0
  },
  {
    "x": -2294.0,
    "y": -1179.0
  },
  {
    "x": -2261.0116601588234,
    "y": -1142.5984625798374
  },
  {
    "x": -2209.355819461227,
    "y": -1072.1295168760705
  },
  {
    "x": -2090.1939071343604,
    "y": -906.7079790662162
  },
  {
    "x": -2012.9862816388859,
    "y": -790.1087823242534
  },
  {
    "x": -1933.0,
    "y": -679.0
  },
  {
    "x": -1911.7633013696454,
    "y": -650.2241112708641
  },
  {
    "x": -1804.3780644510828,
    "y": -512.6062154117706
  },
  {
    "x": -1753.3433928856252,
    "y": -450.3831088028842
  },
  {
    "x": -1670.0,
    "y": -354.0
  },
  {
    "x": -1565.0,
    "y": -248.0
  },
  {
    "x": -1546.8700270454592,
    "y": -232.25384337748375
  },
  {
    "x": -1525.1415842380613,
    "y": -219.37797974816982
  },
  {
    "x": -1486.0,
    "y": -202.0
  },
  {
    "x": -1423.0,
    "y": -199.0
  },
  {
    "x": -1359.0,
    "y": -220.0
  },
  {
    "x": -1344.8722348148738,
    "y": -228.6683423261069
  },
  {
    "x": -1280.1074821577515,
    "y": -276.92003662748584
  },
  {
    "x": -1266.0,
    "y": -302.0
  },
  {
    "x": -1238.4027230468087,
    "y": -362.2337799758503
  },
  {
    "x": -1209.0604984518136,
    "y": -457.7708571685837
  },
  {
    "x": -1198.636315261516,
    "y": -504.83501643290595
  },
  {
    "x": -1183.9878773298153,
    "y": -559.9694529948215
  },
  {
    "x": -1147.0,
    "y": -678.0
  },
  {
    "x": -1092.0,
    "y": -814.0
  },
  {
    "x": -1032.9865154194772,
    "y": -933.6454529274965
  },
  {
    "x": -1023.0,
    "y": -950.0
  },
  {
    "x": -1009.0349824924501,
    "y": -972.04133954496
  },
  {
    "x": -968.1896471308899,
    "y": -1027.9437665315531
  },
  {
    "x": -939.9565124320292,
    "y": -1061.0576076282903
  },
  {
    "x": -894.6578194769512,
    "y": -1099.106375147784
  },
  {
    "x": -888.0,
    "y": -1103.0
  },
  {
    "x": -826.0,
    "y": -1130.0
  },
  {
    "x": -787.2247424743687,
    "y": -1133.6566734049761
  },
  {
    "x": -765.6990507180412,
    "y": -1122.4137389800676
  },
  {
    "x": -747.0,
    "y": -1107.0
  },
  {
    "x": -742.5209817746545,
    "y": -1099.3916294098965
  },
  {
    "x": -732.0,
    "y": -1067.0
  },
  {
    "x": -731.3417119068176,
    "y": -1038.4054849133786
  },
  {
    "x": -733.9512017005217,
    "y": -1016.6906608547246
  },
  {
    "x": -742.0,
    "y": -983.0
  },
  {
    "x": -747.0,
    "y": -969.0
  },
  {
    "x": -783.0,
    "y": -900.0
  },
  {
    "x": -808.370246366981,
    "y": -865.5306725711112
  },
  {
    "x": -838.0,
    "y": -832.0
  },
  {
    "x": -864.3258451079319,
    "y": -803.2047426461842
  },
  {
    "x": -876.0,
    "y": -791.0
  },
  {
    "x": -902.0,
    "y": -765.0
  },
  {
    "x": -960.0,
    "y": -702.0
  },
  {
    "x": -998.0579637073423,
    "y": -649.5864892497727
  },
  {
    "x": -1026.0,
    "y": -577.0
  },
  {
    "x": -1027.3031983141655,
    "y": -559.806008188815
  },
  {
    "x": -1026.5114527574822,
    "y": -503.9219906588846
  },
  {
    "x": -1011.0,
    "y": -459.0
  },
  {
    "x": -974.6888234185436,
    "y": -404.4559142959385
  },
  {
    "x": -947.4228338254164,
    "y": -378.27831139935375
  },
  {
    "x": -907.1651827081158,
    "y": -346.72348992397184
  },
  {
    "x": -861.9632470874785,
    "y": -319.5986703005276
  },
  {
    "x": -731.0,
    "y": -257.0
  },
  {
    "x": -663.0,
    "y": -229.0
  },
  {
    "x": -597.9287557553777,
    "y": -206.04063798228378
  },
  {
    "x": -496.0,
    "y": -178.0
  },
  {
    "x": -450.83701532830594,
    "y": -170.13920372119674
  },
  {
    "x": -403.419012937409,
    "y": -166.5883221002648
  },
  {
    "x": -333.32240345063894,
    "y": -184.48419569813936
  },
  {
    "x": -260.802066779949,
    "y": -226.48469661524342
  },
  {
    "x": -248.0,
    "y": -255.0
  },
  {
    "x": -230.0,
    "y": -292.0
  },
  {
    "x": -207.0,
    "y": -361.0
  },
  {
    "x": -187.23914587157293,
    "y": -475.3677659937432
  },
  {
    "x": -185.0,
    "y": -530.0
  },
  {
    "x": -184.69257931093594,
    "y": -585.4046164772328
  },
  {
    "x": -189.71499606022596,
    "y": -714.696576003668
  },
  {
    "x": -193.80419235420916,
    "y": -768.1977363401618
  },
  {
    "x": -204.60062218526235,
    "y": -861.545857930526
  },
  {
    "x": -213.38760298053919,
    "y": -938.3474105072778
  },
  {
    "x": -223.0,
    "y": -1021.0
  },
  {
    "x": -234.0,
    "y": -1119.0
  },
  {
    "x": -249.0,
    "y": -1257.0
  },
  {
    "x": -258.5200058298629,
    "y": -1350.011756277648
  },
  {
    "x": -274.0,
    "y": -1494.0
  },
  {
    "x": -286.0,
    "y": -1600.0
  },
  {
    "x": -303.0,
    "y": -1707.0
  },
  {
    "x": -362.0,
    "y": -1939.0
  },
  {
    "x": -397.0,
    "y": -2050.0
  },
  {
    "x": -454.0,
    "y": -2213.0
  },
  {
    "x": -491.14806728968364,
    "y": -2311.8243404086943
  },
  {
    "x": -591.0,
    "y": -2555.0
  },
  {
    "x": -655.8518873092846,
    "y": -2702.592764761525
  },
  {
    "x": -690.0,
    "y": -2772.0
  },
  {
    "x": -782.0,
    "y": -2939.0
  },
  {
    "x": -857.7637184518705,
    "y": -3041.537317202036
  },
  {
    "x": -1050.5177739076428,
    "y": -3270.074837694242
  },
  {
    "x": -1184.0,
    "y": -3364.0
  },
  {
    "x": -1312.0,
    "y": -3442.0
  },
  {
    "x": -1477.34198001083,
    "y": -3525.535557645151
  },
  {
    "x": -1654.0,
    "y": -3608.0
  },
  {
    "x": -1829.7660590000423,
    "y": -3694.23534927617
  },
  {
    "x": -1961.5167937237295,
    "y": -3760.555798056258
  },
  {
    "x": -2134.0,
    "y": -3849.0
  },
  {
    "x": -2372.0,
    "y": -3965.0
  },
  {
    "x": -2462.8877788540603,
    "y": -4007.9721198712646
  },
  {
    "x": -2589.0,
    "y": -4061.0
  },
  {
    "x": -2726.526868033895,
    "y": -4115.878430508181
  },
  {
    "x": -2962.0,
    "y": -4197.0
  },
  {
    "x": -3084.0,
    "y": -4233.0
  },
  {
    "x": -3255.0,
    "y": -4274.0
  },
  {
    "x": -3453.0,
    "y": -4308.0
  },
  {
    "x": -3732.212860095921,
    "y": -4341.410519883493
  },
  {
    "x": -3855.313669444537,
    "y": -4353.40082311757
  },
  {
    "x": -3943.0,
    "y": -4363.0
  },
  {
    "x": -3996.658680033867,
    "y": -4371.0096199299105
  },
  {
    "x": -4072.7447117120955,
    "y": -4387.0978910055055
  },
  {
    "x": -4136.0,
    "y": -4418.0
  },
  {
    "x": -4191.0,
    "y": -4489.0
  },
  {
    "x": -4235.307814874637,
    "y": -4568.163763560346
  },
  {
    "x": -4243.0,
    "y": -4579.0
  },
  {
    "x": -4273.0,
    "y": -4610.0
  },
  {
    "x": -4311.0,
    "y": -4633.0
  },
  {
    "x": -4384.0,
    "y": -4650.0
  },
  {
    "x": -4400.0,
    "y": -4651.0
  },
  {
    "x": -4471.720903251969,
    "y": -4645.1723721824355
  },
  {
    "x": -4513.893654551145,
    "y": -4639.002324641081
  },
  {
    "x": -4559.079134792451,
    "y": -4628.088416493025
  },
  {
    "x": -4613.0,
    "y": -4614.0
  },
  {
    "x": -4696.0,
    "y": -4601.0
  },
  {
    "x": -4734.600392680795,
    "y": -4601.435483691428
  },
  {
    "x": -4886.761675041641,
    "y": -4613.806924946266
  },
  {
    "x": -4937.5536454552985,
    "y": -4621.944576827427
  },
  {
    "x": -5012.532567791173,
    "y": -4632.87921732504
  },
  {
    "x": -5161.6025218109335,
    "y": -4655.922721905205
  },
  {
    "x": -5217.0,
    "y": -4664.0
  },
  {
    "x": -5340.474655762449,
    "y": -4679.959463695451
  },
  {
    "x": -5430.78623545115,
    "y": -4691.190919782371
  },
  {
    "x": -5618.0,
    "y": -4714.0
  },
  {
    "x": -5792.0,
    "y": -4734.0
  },
  {
    "x": -6001.131992614971,
    "y": -4756.071144055151
  },
  {
    "x": -6117.556023051203,
    "y": -4767.780357729716
  },
  {
    "x": -6181.018216271797,
    "y": -4772.6983943779915
  },
  {
    "x": -6507.0,
    "y": -4794.0
  },
  {
    "x": -6609.465407254149,
    "y": -4783.6022386736195
  },
  {
    "x": -6700.0,
    "y": -4834.0
  },
  {
    "x": -6837.721559612292,
    "y": -4915.242395590996
  },
  {
    "x": -6891.0,
    "y": -4982.0
  },
  {
    "x": -7010.266534001891,
    "y": -5144.180115136447
  },
  {
    "x": -7063.0,
    "y": -5242.0
  },
  {
    "x": -7096.761036316468,
    "y": -5315.451940714709
  },
  {
    "x": -7157.042107233681,
    "y": -5513.879851539491
  },
  {
    "x": -7187.4656817628775,
    "y": -5642.954160137357
  },
  {
    "x": -7195.162924727618,
    "y": -5705.303130929006
  },
  {
    "x": -7208.562700587217,
    "y": -5811.079977173168
  },
  {
    "x": -7216.4949840309455,
    "y": -5948.747497403498
  },
  {
    "x": -7216.234408117934,
    "y": -6186.806747806227
  },
  {
    "x": -7193.0,
    "y": -6277.0
  },
  {
    "x": -7048.49980340181,
    "y": -6475.553351968232
  },
  {
    "x": -6939.365611095303,
    "y": -6698.64057028153
  },
  {
    "x": -6915.0,
    "y": -6774.0
  },
  {
    "x": -6872.0,
    "y": -6921.0
  },
  {
    "x": -6756.0,
    "y": -7572.0
  },
  {
    "x": -6747.0,
    "y": -7693.0
  },
  {
    "x": -6746.0,
    "y": -7812.0
  },
  {
    "x": -6747.44313500645,
    "y": -7852.336387563173
  },
  {
    "x": -6771.0,
    "y": -7935.0
  },
  {
    "x": -6811.0,
    "y": -7983.0
  },
  {
    "x": -6891.0,
    "y": -8084.0
  },
  {
    "x": -6895.0,
    "y": -8234.0
  },
  {
    "x": -6880.955025722875,
    "y": -8325.37365733133
  },
  {
    "x": -6871.0,
    "y": -8365.0
  },
  {
    "x": -6850.0,
    "y": -8446.0
  },
  {
    "x": -6792.382397024002,
    "y": -8605.80942217179
  },
  {
    "x": -6763.746721244057,
    "y": -8674.260472770784
  },
  {
    "x": -6743.0,
    "y": -8713.0
  },
  {
    "x": -6681.0,
    "y": -8823.0
  },
  {
    "x": -6628.0,
    "y": -8901.0
  },
  {
    "x": -6544.931188315115,
    "y": -9007.121787005231
  },
  {
    "x": -6479.0,
    "y": -9077.0
  },
  {
    "x": -6404.0,
    "y": -9142.0
  },
  {
    "x": -6311.0,
    "y": -9201.0
  },
  {
    "x": -6164.386403735596,
    "y": -9281.401139279165
  },
  {
    "x": -6088.583504016554,
    "y": -9322.422747643446
  },
  {
    "x": -6033.43969307889,
    "y": -9357.60527025791
  },
  {
    "x": -5966.0,
    "y": -9419.0
  },
  {
    "x": -5944.0,
    "y": -9456.0
  },
  {
    "x": -5932.0,
    "y": -9496.0
  },
  {
    "x": -5930.0,
    "y": -9526.0
  },
  {
    "x": -5933.0,
    "y": -9562.0
  },
  {
    "x": -5935.517021982722,
    "y": -9582.480744038498
  },
  {
    "x": -5969.054819756142,
    "y": -9661.098087610875
  },
  {
    "x": -5979.065836525338,
    "y": -9681.898076002235
  },
  {
    "x": -6063.63382032707,
    "y": -9731.82713390521
  },
  {
    "x": -6101.0,
    "y": -9743.0
  },
  {
    "x": -6108.570994115235,
    "y": -9744.85785455037
  },
  {
    "x": -6175.337716686562,
    "y": -9758.547067177798
  },
  {
    "x": -6319.0,
    "y": -9771.0
  },
  {
    "x": -6396.0,
    "y": -9773.0
  },
  {
    "x": -6484.0,
    "y": -9772.0
  },
  {
    "x": -6518.611458591614,
    "y": -9769.548702614378
  },
  {
    "x": -6557.0,
    "y": -9764.0
  },
  {
    "x": -6635.03343375202,
    "y": -9748.795135874849
  },
  {
    "x": -6685.419634941761,
    "y": -9729.136217553172
  },
  {
    "x": -6739.419449910086,
    "y": -9684.692912031378
  },
  {
    "x": -6752.0,
    "y": -9668.0
  },
  {
    "x": -6778.0,
    "y": -9616.0
  },
  {
    "x": -6808.0,
    "y": -9502.0
  },
  {
    "x": -6813.953617735727,
    "y": -9458.72599570465
  },
  {
    "x": -6833.327963624302,
    "y": -9387.646709205874
  },
  {
    "x": -6863.0,
    "y": -9295.0
  },
  {
    "x": -6912.701090784288,
    "y": -9197.340274830509
  },
  {
    "x": -7004.0,
    "y": -9062.0
  },
  {
    "x": -7052.260503880414,
    "y": -8993.432755846326
  },
  {
    "x": -7098.073006236011,
    "y": -8924.489678313903
  },
  {
    "x": -7119.0,
    "y": -8890.0
  },
  {
    "x": -7191.0,
    "y": -8752.0
  },
  {
    "x": -7287.964562882814,
    "y": -8503.700851927804
  },
  {
    "x": -7311.1831789901225,
    "y": -8436.56654621297
  },
  {
    "x": -7347.838487144447,
    "y": -8316.712999582596
  },
  {
    "x": -7369.0,
    "y": -8246.0
  },
  {
    "x": -7402.0,
    "y": -8134.0
  },
  {
    "x": -7464.4075819745285,
    "y": -7908.881231558305
  },
  {
    "x": -7546.0,
    "y": -7591.0
  },
  {
    "x": -7570.898145696349,
    "y": -7482.002681457921
  },
  {
    "x": -7579.0,
    "y": -7437.0
  },
  {
    "x": -7616.0,
    "y": -7193.0
  },
  {
    "x": -7633.692658060263,
    "y": -7025.654341670865
  },
  {
    "x": -7654.619612902516,
    "y": -6738.860531348696
  },
  {
    "x": -7663.063390422336,
    "y": -6601.966109876188
  }
]

def sample_track_xy(dist, track=MONACO_TRACK, track_length_m=5400):
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


def generate_telemetry(lap_time,n_points=300,track_length_m=5400):
    dist=np.linspace(0,track_length_m,n_points)
    speed=track_length_m/lap_time
    time=dist/speed
    xys = [sample_track_xy(d, track=MONACO_TRACK, track_length_m=track_length_m) for d in dist]
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
        'circuit': metadata.get('circuit_data') or {'outline': MONACO_TRACK, 'corners': [], 'rotation': 0},
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