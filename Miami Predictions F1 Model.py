import os
import fastf1
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error
import json

YEAR = 2026
GP_EVENT = 4
N_LAPS = 57

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
            'outline': MIAMI_TRACK,
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

MIAMI_TRACK = [
  {
    "x": 3134.0,
    "y": -4267.0
  },
  {
    "x": 2916.104152594019,
    "y": -4281.82569952822
  },
  {
    "x": 2788.0,
    "y": -4279.0
  },
  {
    "x": 2553.0,
    "y": -4252.0
  },
  {
    "x": 2378.0,
    "y": -4213.0
  },
  {
    "x": 2163.0,
    "y": -4137.0
  },
  {
    "x": 2036.0,
    "y": -4079.0
  },
  {
    "x": 1879.2565947890896,
    "y": -3994.289509702069
  },
  {
    "x": 1746.6745532554426,
    "y": -3915.434417120803
  },
  {
    "x": 1409.478657667971,
    "y": -3702.414682632458
  },
  {
    "x": 1250.7919911766983,
    "y": -3600.633519494889
  },
  {
    "x": 1127.8945025761593,
    "y": -3522.951423446688
  },
  {
    "x": 1014.3896889042873,
    "y": -3450.1814710316876
  },
  {
    "x": 829.0,
    "y": -3331.0
  },
  {
    "x": 613.0,
    "y": -3193.0
  },
  {
    "x": 397.73646507306836,
    "y": -3060.8119651370102
  },
  {
    "x": 243.0,
    "y": -2975.0
  },
  {
    "x": -97.81270286190524,
    "y": -2798.4711945208987
  },
  {
    "x": -380.8960359041703,
    "y": -2704.350311195442
  },
  {
    "x": -544.3997750976642,
    "y": -2681.162366580158
  },
  {
    "x": -748.0,
    "y": -2685.0
  },
  {
    "x": -933.5725474906858,
    "y": -2717.444066940803
  },
  {
    "x": -1460.0,
    "y": -2988.0
  },
  {
    "x": -1541.575391038658,
    "y": -3026.970378066362
  },
  {
    "x": -1646.0,
    "y": -3063.0
  },
  {
    "x": -1793.690951692715,
    "y": -3089.2178328724403
  },
  {
    "x": -2000.0,
    "y": -3087.0
  },
  {
    "x": -2160.0,
    "y": -3045.0
  },
  {
    "x": -2324.0,
    "y": -2964.0
  },
  {
    "x": -2417.898706858879,
    "y": -2901.6210282601687
  },
  {
    "x": -2657.0,
    "y": -2706.0
  },
  {
    "x": -2817.0,
    "y": -2581.0
  },
  {
    "x": -2941.6960075521533,
    "y": -2514.6534247696427
  },
  {
    "x": -3076.5453769135424,
    "y": -2469.1851371750863
  },
  {
    "x": -3552.0,
    "y": -2467.0
  },
  {
    "x": -3634.1279842696486,
    "y": -2483.7125932092495
  },
  {
    "x": -3769.7101623160324,
    "y": -2537.4886152124614
  },
  {
    "x": -3992.8261485493454,
    "y": -2642.7103339217215
  },
  {
    "x": -4107.482112299592,
    "y": -2734.990584546373
  },
  {
    "x": -4279.0,
    "y": -2928.0
  },
  {
    "x": -4367.0,
    "y": -3091.0
  },
  {
    "x": -4401.108848495342,
    "y": -3203.8627405382563
  },
  {
    "x": -4413.714461201853,
    "y": -3275.374935458564
  },
  {
    "x": -4417.0,
    "y": -3435.0
  },
  {
    "x": -4407.0,
    "y": -3507.0
  },
  {
    "x": -4379.0,
    "y": -3604.0
  },
  {
    "x": -4326.0,
    "y": -3702.0
  },
  {
    "x": -4209.32258195591,
    "y": -3809.2544652808315
  },
  {
    "x": -4143.0,
    "y": -3842.0
  },
  {
    "x": -4017.8118620216183,
    "y": -3876.52947406206
  },
  {
    "x": -3839.8355115583945,
    "y": -3891.35345457712
  },
  {
    "x": -3680.622409066762,
    "y": -3894.5138509520566
  },
  {
    "x": -3446.0,
    "y": -3899.0
  },
  {
    "x": -3282.0,
    "y": -3911.0
  },
  {
    "x": -3110.0,
    "y": -3932.0
  },
  {
    "x": -2996.0,
    "y": -3949.0
  },
  {
    "x": -2784.6252981224116,
    "y": -3982.093372349733
  },
  {
    "x": -2691.0,
    "y": -3999.0
  },
  {
    "x": -2479.435473540727,
    "y": -4041.939065507866
  },
  {
    "x": -2375.3247390269903,
    "y": -4065.0514539377023
  },
  {
    "x": -2138.7953252369766,
    "y": -4114.289856730789
  },
  {
    "x": -1827.0,
    "y": -4142.0
  },
  {
    "x": -1758.926288988663,
    "y": -4145.318888645896
  },
  {
    "x": -1673.512517888314,
    "y": -4142.315635554908
  },
  {
    "x": -1302.954096389975,
    "y": -4130.4550391999755
  },
  {
    "x": -1233.8107670562076,
    "y": -4125.760374593088
  },
  {
    "x": -960.3145746593488,
    "y": -4113.02953640685
  },
  {
    "x": -800.994370568277,
    "y": -4107.154776143561
  },
  {
    "x": -433.0,
    "y": -4100.0
  },
  {
    "x": -202.94084471505775,
    "y": -4096.674912731486
  },
  {
    "x": 27.0,
    "y": -4094.0
  },
  {
    "x": 253.32842981599782,
    "y": -4090.636601987311
  },
  {
    "x": 445.0,
    "y": -4089.0
  },
  {
    "x": 713.3272021829468,
    "y": -4092.291709660186
  },
  {
    "x": 873.2145280164475,
    "y": -4103.897866953979
  },
  {
    "x": 1001.4242687721669,
    "y": -4121.713239255942
  },
  {
    "x": 1267.0,
    "y": -4185.0
  },
  {
    "x": 1489.0,
    "y": -4257.0
  },
  {
    "x": 1748.1345548103209,
    "y": -4349.636273675147
  },
  {
    "x": 1934.0,
    "y": -4415.0
  },
  {
    "x": 2183.6326074242593,
    "y": -4495.96929163182
  },
  {
    "x": 2698.300852826177,
    "y": -4648.2444716193
  },
  {
    "x": 2941.815370651528,
    "y": -4704.963271928631
  },
  {
    "x": 3187.831414017799,
    "y": -4747.188228925366
  },
  {
    "x": 3394.0,
    "y": -4774.0
  },
  {
    "x": 3766.209298098188,
    "y": -4793.417783984468
  },
  {
    "x": 3949.3897804780304,
    "y": -4794.112279364381
  },
  {
    "x": 4234.074137426416,
    "y": -4777.386616772425
  },
  {
    "x": 4475.327808409254,
    "y": -4758.589766153855
  },
  {
    "x": 4762.0,
    "y": -4719.0
  },
  {
    "x": 5041.0,
    "y": -4665.0
  },
  {
    "x": 5197.0,
    "y": -4626.0
  },
  {
    "x": 5517.6097896639385,
    "y": -4532.320592225473
  },
  {
    "x": 5922.307296874601,
    "y": -4397.544567541855
  },
  {
    "x": 6043.657131764779,
    "y": -4355.890340927214
  },
  {
    "x": 6389.6064376413415,
    "y": -4238.768469861498
  },
  {
    "x": 6790.071226293123,
    "y": -4102.480305008405
  },
  {
    "x": 7014.0,
    "y": -4024.0
  },
  {
    "x": 7201.0,
    "y": -3955.0
  },
  {
    "x": 7328.928691885734,
    "y": -3905.119367251256
  },
  {
    "x": 7564.718636560861,
    "y": -3808.1678191004667
  },
  {
    "x": 7766.112150462537,
    "y": -3721.384138858327
  },
  {
    "x": 8010.0,
    "y": -3611.0
  },
  {
    "x": 8226.0,
    "y": -3510.0
  },
  {
    "x": 8375.0,
    "y": -3439.0
  },
  {
    "x": 8623.0,
    "y": -3319.0
  },
  {
    "x": 8957.0,
    "y": -3148.0
  },
  {
    "x": 9082.0,
    "y": -3078.0
  },
  {
    "x": 9227.0,
    "y": -2993.0
  },
  {
    "x": 9373.0,
    "y": -2898.0
  },
  {
    "x": 9539.0,
    "y": -2757.0
  },
  {
    "x": 9594.0,
    "y": -2691.0
  },
  {
    "x": 9626.431738266981,
    "y": -2640.58171881602
  },
  {
    "x": 9661.926377514475,
    "y": -2565.325180327673
  },
  {
    "x": 9668.0,
    "y": -2419.0
  },
  {
    "x": 9644.0,
    "y": -2370.0
  },
  {
    "x": 9585.134653603549,
    "y": -2294.1997912826537
  },
  {
    "x": 9572.0,
    "y": -2281.0
  },
  {
    "x": 9507.0,
    "y": -2221.0
  },
  {
    "x": 9431.635073989995,
    "y": -2159.148177032588
  },
  {
    "x": 9397.953070897569,
    "y": -2131.7268744508865
  },
  {
    "x": 9330.846024494289,
    "y": -2075.2530060893077
  },
  {
    "x": 9262.29790105096,
    "y": -2006.8825063810298
  },
  {
    "x": 9175.758117931573,
    "y": -1892.863576869778
  },
  {
    "x": 9137.0,
    "y": -1801.0
  },
  {
    "x": 9120.602479727884,
    "y": -1705.1388492661074
  },
  {
    "x": 9119.430590004951,
    "y": -1641.8397788226894
  },
  {
    "x": 9148.0,
    "y": -1525.0
  },
  {
    "x": 9173.0,
    "y": -1467.0
  },
  {
    "x": 9199.449612847191,
    "y": -1421.439066897416
  },
  {
    "x": 9269.618531517948,
    "y": -1336.0033088458908
  },
  {
    "x": 9332.0,
    "y": -1287.0
  },
  {
    "x": 9416.403937575542,
    "y": -1243.1421924073682
  },
  {
    "x": 9473.613003495273,
    "y": -1224.613504301757
  },
  {
    "x": 9522.97528285728,
    "y": -1214.4047567410644
  },
  {
    "x": 9659.873799538713,
    "y": -1203.0811304269148
  },
  {
    "x": 9784.0,
    "y": -1202.0
  },
  {
    "x": 9906.0,
    "y": -1199.0
  },
  {
    "x": 9979.0,
    "y": -1193.0
  },
  {
    "x": 10069.0,
    "y": -1173.0
  },
  {
    "x": 10306.167501005151,
    "y": -1035.2962716593265
  },
  {
    "x": 10427.088274010124,
    "y": -904.611626434798
  },
  {
    "x": 10479.071218703284,
    "y": -819.3036177007007
  },
  {
    "x": 10503.068919391599,
    "y": -770.0256925623453
  },
  {
    "x": 10558.65495841749,
    "y": -601.4166007604514
  },
  {
    "x": 10565.437661197284,
    "y": -560.9975405544784
  },
  {
    "x": 10566.442082902557,
    "y": -522.6304623383727
  },
  {
    "x": 10522.817859334726,
    "y": -438.61823980558785
  },
  {
    "x": 10443.0,
    "y": -390.0
  },
  {
    "x": 10396.0,
    "y": -355.0
  },
  {
    "x": 10378.345901510522,
    "y": -268.6969960209809
  },
  {
    "x": 10390.202866065538,
    "y": -197.4167754174613
  },
  {
    "x": 10432.832285571578,
    "y": -31.42878701305421
  },
  {
    "x": 10461.839808877965,
    "y": 66.84306542960715
  },
  {
    "x": 10484.385994761271,
    "y": 137.53613278899698
  },
  {
    "x": 10503.790283329443,
    "y": 189.25851563769538
  },
  {
    "x": 10551.0,
    "y": 329.0
  },
  {
    "x": 10550.726193565533,
    "y": 441.81181271067817
  },
  {
    "x": 10534.736486416845,
    "y": 479.5257370170167
  },
  {
    "x": 10501.0,
    "y": 516.0
  },
  {
    "x": 10460.0,
    "y": 547.0
  },
  {
    "x": 10403.0,
    "y": 579.0
  },
  {
    "x": 10347.16648031777,
    "y": 603.1373076819357
  },
  {
    "x": 10276.859386212618,
    "y": 626.5028039857522
  },
  {
    "x": 10135.0,
    "y": 654.0
  },
  {
    "x": 10095.14856427045,
    "y": 658.123638414632
  },
  {
    "x": 10012.991360786793,
    "y": 664.1915092088897
  },
  {
    "x": 9888.927801394042,
    "y": 669.1512807210477
  },
  {
    "x": 9785.031137489575,
    "y": 671.7300991508583
  },
  {
    "x": 9602.0,
    "y": 677.0
  },
  {
    "x": 9477.178312750413,
    "y": 681.1237014981289
  },
  {
    "x": 9309.0,
    "y": 686.0
  },
  {
    "x": 9197.0,
    "y": 690.0
  },
  {
    "x": 8949.0,
    "y": 697.0
  },
  {
    "x": 8788.0,
    "y": 702.0
  },
  {
    "x": 8635.0,
    "y": 707.0
  },
  {
    "x": 8426.0,
    "y": 713.0
  },
  {
    "x": 8265.814875295691,
    "y": 716.9055861458355
  },
  {
    "x": 8034.736427000223,
    "y": 721.996739399447
  },
  {
    "x": 7863.195757979881,
    "y": 726.0784910171798
  },
  {
    "x": 7623.0,
    "y": 731.0
  },
  {
    "x": 7387.0,
    "y": 736.0
  },
  {
    "x": 7115.0,
    "y": 742.0
  },
  {
    "x": 6967.187575878978,
    "y": 745.5673612691695
  },
  {
    "x": 6745.0,
    "y": 750.0
  },
  {
    "x": 6604.0,
    "y": 753.0
  },
  {
    "x": 6061.0,
    "y": 766.0
  },
  {
    "x": 5915.0,
    "y": 770.0
  },
  {
    "x": 5752.0,
    "y": 775.0
  },
  {
    "x": 5506.0,
    "y": 784.0
  },
  {
    "x": 5076.0,
    "y": 799.0
  },
  {
    "x": 4912.425874799694,
    "y": 804.7106152324538
  },
  {
    "x": 4780.66768957157,
    "y": 809.2724031005939
  },
  {
    "x": 4571.055819560871,
    "y": 816.5114560734894
  },
  {
    "x": 4103.028686812613,
    "y": 833.2533308453428
  },
  {
    "x": 3911.7001849423614,
    "y": 839.9814103728118
  },
  {
    "x": 3811.0,
    "y": 843.0
  },
  {
    "x": 3600.0,
    "y": 851.0
  },
  {
    "x": 3245.0,
    "y": 863.0
  },
  {
    "x": 2977.0,
    "y": 872.0
  },
  {
    "x": 2756.60566188503,
    "y": 879.6959417865125
  },
  {
    "x": 2537.4484539232717,
    "y": 887.9941481718901
  },
  {
    "x": 2237.011382464407,
    "y": 899.0068833797898
  },
  {
    "x": 1985.024049346208,
    "y": 906.7217600101616
  },
  {
    "x": 1764.8069038256403,
    "y": 911.8668235686921
  },
  {
    "x": 1543.3326006882387,
    "y": 915.3957820474677
  },
  {
    "x": 1237.0,
    "y": 921.0
  },
  {
    "x": 987.8547816504081,
    "y": 925.602643766226
  },
  {
    "x": 765.3290365451766,
    "y": 930.3691911308507
  },
  {
    "x": 569.2719006559948,
    "y": 934.370736632668
  },
  {
    "x": 187.5689377770197,
    "y": 940.7266408979093
  },
  {
    "x": -164.0,
    "y": 948.0
  },
  {
    "x": -427.0,
    "y": 953.0
  },
  {
    "x": -636.906576728321,
    "y": 957.6994916242093
  },
  {
    "x": -938.6000243281726,
    "y": 971.0195050588025
  },
  {
    "x": -1274.447222234572,
    "y": 1001.6484918286342
  },
  {
    "x": -1521.9742917037097,
    "y": 1027.033054968623
  },
  {
    "x": -1753.9561482532072,
    "y": 1049.5626378423015
  },
  {
    "x": -1959.0,
    "y": 1069.0
  },
  {
    "x": -2112.636672003394,
    "y": 1078.8292162261896
  },
  {
    "x": -2210.5596759281902,
    "y": 1079.7467478288183
  },
  {
    "x": -2309.0,
    "y": 1074.0
  },
  {
    "x": -2428.9340715683693,
    "y": 1055.5981072617378
  },
  {
    "x": -2475.987000737964,
    "y": 1042.2805518755913
  },
  {
    "x": -2560.0,
    "y": 999.0
  },
  {
    "x": -2590.0,
    "y": 971.0
  },
  {
    "x": -2615.0,
    "y": 936.0
  },
  {
    "x": -2630.0,
    "y": 898.0
  },
  {
    "x": -2632.5110427093296,
    "y": 796.4286659613905
  },
  {
    "x": -2621.1304907419926,
    "y": 750.4678233958512
  },
  {
    "x": -2600.0,
    "y": 706.0
  },
  {
    "x": -2568.0,
    "y": 657.0
  },
  {
    "x": -2522.0,
    "y": 605.0
  },
  {
    "x": -2479.8982930063707,
    "y": 568.3130878867678
  },
  {
    "x": -2427.230265231654,
    "y": 527.7549927537468
  },
  {
    "x": -2304.0,
    "y": 451.0
  },
  {
    "x": -2183.100488123702,
    "y": 383.7654399077163
  },
  {
    "x": -2100.0,
    "y": 331.0
  },
  {
    "x": -2040.0,
    "y": 292.0
  },
  {
    "x": -1973.199378953981,
    "y": 250.77971694200625
  },
  {
    "x": -1790.4555999273696,
    "y": 151.1480673510933
  },
  {
    "x": -1559.1097275689883,
    "y": 95.34599745676445
  },
  {
    "x": -1366.0064019248,
    "y": 93.81987556140382
  },
  {
    "x": -1157.4574369309335,
    "y": 159.58936545260724
  },
  {
    "x": -1007.510493921922,
    "y": 226.52120270070577
  },
  {
    "x": -733.0,
    "y": 357.0
  },
  {
    "x": -576.0,
    "y": 433.0
  },
  {
    "x": -465.0,
    "y": 484.0
  },
  {
    "x": -156.46124612817624,
    "y": 584.2540506797968
  },
  {
    "x": 154.0,
    "y": 624.0
  },
  {
    "x": 374.0,
    "y": 632.0
  },
  {
    "x": 525.9975733410831,
    "y": 635.1576534583079
  },
  {
    "x": 873.0,
    "y": 565.0
  },
  {
    "x": 1036.0,
    "y": 514.0
  },
  {
    "x": 1269.0,
    "y": 432.0
  },
  {
    "x": 1482.0,
    "y": 336.0
  },
  {
    "x": 1594.0,
    "y": 275.0
  },
  {
    "x": 1894.7248422197545,
    "y": 91.8779461745925
  }
]


def sample_track_xy(dist, track=MIAMI_TRACK, track_length_m=5400):
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
    xys = [sample_track_xy(d, track=MIAMI_TRACK, track_length_m=track_length_m) for d in dist]
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
        'circuit': metadata.get('circuit_data') or {'outline': MIAMI_TRACK, 'corners': [], 'rotation': 0},
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
