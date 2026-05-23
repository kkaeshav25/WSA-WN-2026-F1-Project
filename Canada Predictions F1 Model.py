import os
import fastf1
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error
import json

YEAR = 2026
GP_EVENT = 5
N_LAPS = 70

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
    for label, sname in [('FP1','FP1'), ('S','S'), ('Q','Q')]:
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
            'outline': CANADA_TRACK,
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
    for label in ['FP1','S']:
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

CANADA_TRACK = [
  {
    "x": 1758.0,
    "y": -1580.0
  },
  {
    "x": 1649.0,
    "y": -1496.0
  },
  {
    "x": 1529.0,
    "y": -1401.0
  },
  {
    "x": 1353.6891226011967,
    "y": -1259.2101661425215
  },
  {
    "x": 1247.598595093303,
    "y": -1173.5019771692398
  },
  {
    "x": 1098.0,
    "y": -1052.0
  },
  {
    "x": 998.6324020616354,
    "y": -965.3042919876725
  },
  {
    "x": 902.0,
    "y": -866.0
  },
  {
    "x": 840.7306324174972,
    "y": -790.4385439739198
  },
  {
    "x": 778.0,
    "y": -688.0
  },
  {
    "x": 746.0,
    "y": -592.0
  },
  {
    "x": 742.0,
    "y": -521.0
  },
  {
    "x": 748.2369285874938,
    "y": -445.42567587149904
  },
  {
    "x": 758.4750558214241,
    "y": -379.66010718710754
  },
  {
    "x": 768.202465376194,
    "y": -255.94877123463033
  },
  {
    "x": 762.8718842374452,
    "y": -137.27107053862582
  },
  {
    "x": 757.3960396637142,
    "y": -93.16037605228398
  },
  {
    "x": 743.8257769757686,
    "y": -31.22393516678005
  },
  {
    "x": 709.6989196124181,
    "y": 65.11959820386772
  },
  {
    "x": 627.0,
    "y": 202.0
  },
  {
    "x": 541.0,
    "y": 311.0
  },
  {
    "x": 409.0,
    "y": 475.0
  },
  {
    "x": 347.0,
    "y": 551.0
  },
  {
    "x": 325.9163522224239,
    "y": 576.5477948558247
  },
  {
    "x": 199.16340006665808,
    "y": 728.7377562714906
  },
  {
    "x": 116.0,
    "y": 820.0
  },
  {
    "x": -1.0,
    "y": 936.0
  },
  {
    "x": -207.14462920715638,
    "y": 1107.7447022639337
  },
  {
    "x": -280.0,
    "y": 1165.0
  },
  {
    "x": -418.0,
    "y": 1275.0
  },
  {
    "x": -474.4833633008367,
    "y": 1323.0406723724773
  },
  {
    "x": -552.9573162083041,
    "y": 1393.2003440988574
  },
  {
    "x": -713.3387365409673,
    "y": 1602.6268578167997
  },
  {
    "x": -802.6831900098755,
    "y": 1768.3249733326543
  },
  {
    "x": -846.0,
    "y": 1899.0
  },
  {
    "x": -895.0,
    "y": 2053.0
  },
  {
    "x": -928.7416654489111,
    "y": 2239.3133060287646
  },
  {
    "x": -943.0,
    "y": 2436.0
  },
  {
    "x": -943.6838738524061,
    "y": 2627.2729842974404
  },
  {
    "x": -940.3898062579685,
    "y": 2770.6675973019474
  },
  {
    "x": -935.0,
    "y": 2905.0
  },
  {
    "x": -926.0,
    "y": 3099.0
  },
  {
    "x": -915.0,
    "y": 3249.0
  },
  {
    "x": -911.0,
    "y": 3374.0
  },
  {
    "x": -911.0277778424218,
    "y": 3376.148121212792
  },
  {
    "x": -916.094806235974,
    "y": 3477.3523076538245
  },
  {
    "x": -930.0,
    "y": 3589.0
  },
  {
    "x": -960.0,
    "y": 3710.0
  },
  {
    "x": -989.0,
    "y": 3782.0
  },
  {
    "x": -1048.0,
    "y": 3873.0
  },
  {
    "x": -1125.0,
    "y": 3939.0
  },
  {
    "x": -1125.8216702652917,
    "y": 3939.4731076908856
  },
  {
    "x": -1181.6417938069796,
    "y": 3965.0470186244056
  },
  {
    "x": -1301.8458956092297,
    "y": 3986.1262036571316
  },
  {
    "x": -1335.0,
    "y": 3983.0
  },
  {
    "x": -1443.0,
    "y": 3976.0
  },
  {
    "x": -1566.036207595354,
    "y": 3967.9326673873056
  },
  {
    "x": -1767.5164654149878,
    "y": 4010.8209566296796
  },
  {
    "x": -1792.0,
    "y": 4019.0
  },
  {
    "x": -1866.0,
    "y": 4063.0
  },
  {
    "x": -1945.0378947385439,
    "y": 4128.926906731021
  },
  {
    "x": -2086.513710736651,
    "y": 4307.1654607477885
  },
  {
    "x": -2164.1493373673406,
    "y": 4442.746088799055
  },
  {
    "x": -2194.0,
    "y": 4528.0
  },
  {
    "x": -2228.597900139414,
    "y": 4639.195600378063
  },
  {
    "x": -2244.0,
    "y": 4705.0
  },
  {
    "x": -2274.0,
    "y": 4857.0
  },
  {
    "x": -2294.0,
    "y": 4990.0
  },
  {
    "x": -2323.0,
    "y": 5229.0
  },
  {
    "x": -2331.9718221352323,
    "y": 5303.355538234976
  },
  {
    "x": -2359.125520481684,
    "y": 5564.610117724053
  },
  {
    "x": -2373.5192922300125,
    "y": 5710.464995310026
  },
  {
    "x": -2384.6628834436474,
    "y": 5839.123157504237
  },
  {
    "x": -2392.732080330463,
    "y": 5941.19201813737
  },
  {
    "x": -2406.0,
    "y": 6114.0
  },
  {
    "x": -2414.0,
    "y": 6217.0
  },
  {
    "x": -2426.5930126903986,
    "y": 6426.348233877769
  },
  {
    "x": -2433.1253915824664,
    "y": 6550.710590020551
  },
  {
    "x": -2445.900193441335,
    "y": 6878.02194458102
  },
  {
    "x": -2448.0,
    "y": 6997.0
  },
  {
    "x": -2448.1658153750323,
    "y": 7249.4099537465045
  },
  {
    "x": -2447.0380070849646,
    "y": 7363.4125630658355
  },
  {
    "x": -2439.4956076393682,
    "y": 7551.461858652972
  },
  {
    "x": -2430.931634816756,
    "y": 7722.019667898192
  },
  {
    "x": -2419.0,
    "y": 7884.0
  },
  {
    "x": -2397.0,
    "y": 8132.0
  },
  {
    "x": -2382.993186061295,
    "y": 8272.658492054632
  },
  {
    "x": -2359.0,
    "y": 8449.0
  },
  {
    "x": -2344.1746616239234,
    "y": 8551.396783327087
  },
  {
    "x": -2292.0,
    "y": 8868.0
  },
  {
    "x": -2248.0,
    "y": 9086.0
  },
  {
    "x": -2207.0,
    "y": 9270.0
  },
  {
    "x": -2159.0,
    "y": 9470.0
  },
  {
    "x": -2138.0403589428415,
    "y": 9557.45316773855
  },
  {
    "x": -2100.3268262191787,
    "y": 9714.502456517446
  },
  {
    "x": -2049.3947641796944,
    "y": 9939.39524476926
  },
  {
    "x": -1995.9436677786011,
    "y": 10168.22402554202
  },
  {
    "x": -1966.4296113483238,
    "y": 10279.002666156324
  },
  {
    "x": -1922.0,
    "y": 10390.0
  },
  {
    "x": -1854.0,
    "y": 10493.0
  },
  {
    "x": -1817.9968976271693,
    "y": 10525.617525144586
  },
  {
    "x": -1775.7764258564325,
    "y": 10543.07147812593
  },
  {
    "x": -1679.1532530152467,
    "y": 10574.414310872005
  },
  {
    "x": -1581.3085444169456,
    "y": 10597.263635499681
  },
  {
    "x": -1504.0,
    "y": 10626.0
  },
  {
    "x": -1380.7575226661006,
    "y": 10696.58128377451
  },
  {
    "x": -1307.0,
    "y": 10756.0
  },
  {
    "x": -1226.0,
    "y": 10844.0
  },
  {
    "x": -1157.0,
    "y": 10945.0
  },
  {
    "x": -1088.0,
    "y": 11082.0
  },
  {
    "x": -1013.1555033174915,
    "y": 11290.681751484068
  },
  {
    "x": -982.0,
    "y": 11408.0
  },
  {
    "x": -958.0,
    "y": 11498.0
  },
  {
    "x": -954.4976744205624,
    "y": 11511.674180344038
  },
  {
    "x": -931.8747649030845,
    "y": 11603.946904590337
  },
  {
    "x": -886.0,
    "y": 11795.0
  },
  {
    "x": -833.8519626082004,
    "y": 12007.524761156785
  },
  {
    "x": -797.0,
    "y": 12177.0
  },
  {
    "x": -770.7927467861646,
    "y": 12312.966849675844
  },
  {
    "x": -735.6157884278041,
    "y": 12503.714959642552
  },
  {
    "x": -719.0,
    "y": 12599.0
  },
  {
    "x": -696.0,
    "y": 12739.0
  },
  {
    "x": -647.2921460324977,
    "y": 13055.711517684587
  },
  {
    "x": -615.8023492223464,
    "y": 13286.81761841081
  },
  {
    "x": -590.0,
    "y": 13516.0
  },
  {
    "x": -574.5229330750783,
    "y": 13702.297211739946
  },
  {
    "x": -565.4744135607868,
    "y": 13851.710432425029
  },
  {
    "x": -562.0,
    "y": 13930.0
  },
  {
    "x": -554.0,
    "y": 14211.0
  },
  {
    "x": -552.0,
    "y": 14412.0
  },
  {
    "x": -554.6928903523733,
    "y": 14672.233545688201
  },
  {
    "x": -558.6676174111528,
    "y": 14794.144613038427
  },
  {
    "x": -574.265211855134,
    "y": 14974.237947786387
  },
  {
    "x": -603.0,
    "y": 15180.0
  },
  {
    "x": -605.895889385881,
    "y": 15197.57014617456
  },
  {
    "x": -675.1519065215368,
    "y": 15520.89614613808
  },
  {
    "x": -726.7986593583282,
    "y": 15740.370690544612
  },
  {
    "x": -768.0,
    "y": 15917.0
  },
  {
    "x": -798.1425811634558,
    "y": 16050.928403000282
  },
  {
    "x": -842.0,
    "y": 16258.0
  },
  {
    "x": -869.6606388585684,
    "y": 16409.360153522477
  },
  {
    "x": -871.0,
    "y": 16419.0
  },
  {
    "x": -879.0,
    "y": 16495.0
  },
  {
    "x": -876.3680910986347,
    "y": 16584.330580856964
  },
  {
    "x": -841.8100758041757,
    "y": 16691.727270257215
  },
  {
    "x": -800.0,
    "y": 16727.0
  },
  {
    "x": -719.0,
    "y": 16759.0
  },
  {
    "x": -688.4008023996823,
    "y": 16763.318546346603
  },
  {
    "x": -672.4195028015803,
    "y": 16759.514075579653
  },
  {
    "x": -632.0,
    "y": 16749.0
  },
  {
    "x": -598.3547258932185,
    "y": 16729.462587440383
  },
  {
    "x": -557.0928452614438,
    "y": 16691.424273696786
  },
  {
    "x": -526.0,
    "y": 16645.0
  },
  {
    "x": -498.0,
    "y": 16590.0
  },
  {
    "x": -481.0,
    "y": 16548.0
  },
  {
    "x": -472.134529656739,
    "y": 16520.97362873177
  },
  {
    "x": -440.0566629327645,
    "y": 16409.753772961994
  },
  {
    "x": -420.0,
    "y": 16292.0
  },
  {
    "x": -409.0,
    "y": 16189.0
  },
  {
    "x": -398.9399803960133,
    "y": 16064.55863728951
  },
  {
    "x": -392.93749899010584,
    "y": 15991.532152247986
  },
  {
    "x": -380.1496601525837,
    "y": 15871.858238768935
  },
  {
    "x": -372.0,
    "y": 15813.0
  },
  {
    "x": -346.0,
    "y": 15684.0
  },
  {
    "x": -294.0,
    "y": 15508.0
  },
  {
    "x": -209.02119472633663,
    "y": 15282.27225409822
  },
  {
    "x": -181.4587979115727,
    "y": 15215.09150325119
  },
  {
    "x": -137.0,
    "y": 15109.0
  },
  {
    "x": -71.0,
    "y": 14954.0
  },
  {
    "x": -23.010286880275196,
    "y": 14841.885617709078
  },
  {
    "x": 11.0,
    "y": 14758.0
  },
  {
    "x": 121.03782807737066,
    "y": 14501.599040012918
  },
  {
    "x": 199.0,
    "y": 14321.0
  },
  {
    "x": 257.0,
    "y": 14189.0
  },
  {
    "x": 298.0,
    "y": 14095.0
  },
  {
    "x": 410.16814992527617,
    "y": 13837.859524913198
  },
  {
    "x": 482.0,
    "y": 13672.0
  },
  {
    "x": 536.0,
    "y": 13546.0
  },
  {
    "x": 595.0,
    "y": 13404.0
  },
  {
    "x": 726.0,
    "y": 13084.0
  },
  {
    "x": 792.0,
    "y": 12921.0
  },
  {
    "x": 879.0,
    "y": 12695.0
  },
  {
    "x": 929.0,
    "y": 12557.0
  },
  {
    "x": 978.0,
    "y": 12417.0
  },
  {
    "x": 1024.0,
    "y": 12275.0
  },
  {
    "x": 1080.0,
    "y": 12094.0
  },
  {
    "x": 1129.0,
    "y": 11930.0
  },
  {
    "x": 1183.0,
    "y": 11734.0
  },
  {
    "x": 1223.2713494865134,
    "y": 11582.800597872592
  },
  {
    "x": 1286.0,
    "y": 11336.0
  },
  {
    "x": 1290.9679775688398,
    "y": 11315.950045685455
  },
  {
    "x": 1351.0,
    "y": 11067.0
  },
  {
    "x": 1427.81146117894,
    "y": 10745.169077982198
  },
  {
    "x": 1459.0310656706945,
    "y": 10612.590091151764
  },
  {
    "x": 1512.0,
    "y": 10386.0
  },
  {
    "x": 1556.0,
    "y": 10196.0
  },
  {
    "x": 1633.0,
    "y": 9867.0
  },
  {
    "x": 1633.638135356898,
    "y": 9864.261814531908
  },
  {
    "x": 1677.0,
    "y": 9676.0
  },
  {
    "x": 1726.0,
    "y": 9466.0
  },
  {
    "x": 1804.0,
    "y": 9134.0
  },
  {
    "x": 1843.0491372426013,
    "y": 8965.936761765473
  },
  {
    "x": 1917.189778113861,
    "y": 8640.776372609731
  },
  {
    "x": 2001.953233646484,
    "y": 8266.489273301928
  },
  {
    "x": 2005.0,
    "y": 8253.0
  },
  {
    "x": 2053.0,
    "y": 8042.0
  },
  {
    "x": 2132.0,
    "y": 7706.0
  },
  {
    "x": 2207.253669968876,
    "y": 7387.761360178929
  },
  {
    "x": 2242.3889670443714,
    "y": 7240.469918611547
  },
  {
    "x": 2288.0,
    "y": 7051.0
  },
  {
    "x": 2343.434954682636,
    "y": 6821.050177758044
  },
  {
    "x": 2372.0,
    "y": 6698.0
  },
  {
    "x": 2456.0,
    "y": 6347.0
  },
  {
    "x": 2484.0,
    "y": 6228.0
  },
  {
    "x": 2534.0,
    "y": 6012.0
  },
  {
    "x": 2563.0,
    "y": 5886.0
  },
  {
    "x": 2583.3739345650797,
    "y": 5785.924796921879
  },
  {
    "x": 2605.3913444043064,
    "y": 5621.487205612824
  },
  {
    "x": 2606.0,
    "y": 5595.0
  },
  {
    "x": 2597.0,
    "y": 5484.0
  },
  {
    "x": 2572.0,
    "y": 5406.0
  },
  {
    "x": 2493.0,
    "y": 5266.0
  },
  {
    "x": 2444.0,
    "y": 5178.0
  },
  {
    "x": 2415.0,
    "y": 5098.0
  },
  {
    "x": 2395.0,
    "y": 4952.0
  },
  {
    "x": 2391.8037655840244,
    "y": 4916.7495546187365
  },
  {
    "x": 2395.079402281717,
    "y": 4854.9176745141995
  },
  {
    "x": 2403.8374626567247,
    "y": 4744.0327194986
  },
  {
    "x": 2431.0,
    "y": 4566.0
  },
  {
    "x": 2470.592452367938,
    "y": 4384.390559102793
  },
  {
    "x": 2494.4554537220283,
    "y": 4286.934758578777
  },
  {
    "x": 2525.2806483760287,
    "y": 4178.51052728247
  },
  {
    "x": 2551.0,
    "y": 4089.0
  },
  {
    "x": 2600.0,
    "y": 3922.0
  },
  {
    "x": 2642.0,
    "y": 3778.0
  },
  {
    "x": 2679.475489835382,
    "y": 3642.377734470717
  },
  {
    "x": 2707.0,
    "y": 3539.0
  },
  {
    "x": 2728.0,
    "y": 3461.0
  },
  {
    "x": 2780.7941085365123,
    "y": 3256.476717294279
  },
  {
    "x": 2787.0,
    "y": 3232.0
  },
  {
    "x": 2815.0,
    "y": 3121.0
  },
  {
    "x": 2875.0,
    "y": 2882.0
  },
  {
    "x": 2913.7863939358267,
    "y": 2730.528915597647
  },
  {
    "x": 2973.0,
    "y": 2504.0
  },
  {
    "x": 3031.0,
    "y": 2280.0
  },
  {
    "x": 3115.0,
    "y": 1960.0
  },
  {
    "x": 3121.6911471852277,
    "y": 1934.6709849319457
  },
  {
    "x": 3160.0,
    "y": 1790.0
  },
  {
    "x": 3201.0,
    "y": 1633.0
  },
  {
    "x": 3277.6451735898695,
    "y": 1314.6425110152531
  },
  {
    "x": 3316.808350707005,
    "y": 1129.0907233546125
  },
  {
    "x": 3347.844104417261,
    "y": 955.6791349893957
  },
  {
    "x": 3361.722028395422,
    "y": 861.7152039141881
  }
]


def sample_track_xy(dist, track=CANADA_TRACK, track_length_m=5400):
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
    xys = [sample_track_xy(d, track=CANADA_TRACK, track_length_m=track_length_m) for d in dist]
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
        'circuit': metadata.get('circuit_data') or {'outline': CANADA_TRACK, 'corners': [], 'rotation': 0},
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