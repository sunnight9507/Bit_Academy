import pymysql
import numpy as np
import pandas as pd
from sklearn.preprocessing import MinMaxScaler
import sys

import Predict_stock

def pred(model, pred_x_data, y_true):
    '''
    수익률 계산을 위한 실제 주식값, 예측 주식값 생성
    '''
    x_scaler = MinMaxScaler()
    y_scaler = MinMaxScaler()

    pred_x_train_scaled = x_scaler.fit_transform(pred_x_data)
    pred_x = np.expand_dims(pred_x_train_scaled, axis=0)
    pred = model.predict(pred_x)

    y_true_scaled = y_scaler.fit_transform(y_true)
    pred_rescaled = y_scaler.inverse_transform(pred[0])
    pred = pred_rescaled[:, 0].astype(np.int)

    return y_true, pred

def create_DB_data(data, target_lst):
    print('---------   create DB data --------')
    target_name = target_lst[0]

    # date
    date = np.array((data[target_lst].reset_index()['date'][1:])).reshape(-1, 1)

    # com_name
    com_name = np.array([target_name for _ in range(len(date))]).reshape(-1, 1)
    # com_code
    com_code = np.array(['000001' for _ in range(len(date))]).reshape(-1, 1)
    # tod_price
    tod_price = np.array(data[target_name])[1:].reshape(-1, 1)

    # tod_status
    tod_status = np.array([0 for _ in range(len(date))]).reshape(-1, 1)
    sub = tod_price[1:] - tod_price[:-1]
    for idx, value in enumerate(sub):
        if value > 0:
            tod_status[idx + 1] = 1
        elif value < 0:
            tod_status[idx + 1] = -1

    # tom_price
    tom_price = np.array(data[target_name])[1:]
    tom_price[1:] += p[1:] - p[:-1]
    tom_price = tom_price.reshape(-1, 1)

    # tom_status
    # 오늘 종가로부터 상향, 하향, 유지
    tom_status = np.array([0 for _ in range(len(date))]).reshape(-1, 1)
    for idx, value in enumerate(tom_price - tod_price):
        if value > 0:
            tom_status[idx] = 1
        elif value < 0:
            tom_status[idx] = -1

    # match_status
    # 작일 예측 여부 확인
    match_status = np.array([True for _ in range(len(date))]).reshape(-1, 1)
    for idx, value in enumerate(tom_status[:-1] == tod_status[1:]):
        match_status[idx + 1] = value

    # price_error
    # 작일 예측값 - 금일 종가의 절댓값
    price_error = np.array([0 for _ in range(len(date))]).reshape(-1, 1)
    for idx, value in enumerate(tom_price[:-1] - tod_price[1:]):
        price_error[idx + 1] = abs(value)

    # return
    # 금일 수익률
    # 작일 tom_status > 0 => (금일 tod_price) - (작일 tod_price) 만큼 수익 발생
    # 작일 tom_status <= 0 => 수익 없음
    returns = np.array([1.0 for _ in range(len(date))]).reshape(-1, 1)

    for idx, value in enumerate(tom_status[:-1]):
        if value == 1:
            returns[idx] += (tod_price[idx + 1] - tod_price[idx]) / tod_price[idx]
    returns = np.round(returns, 3)

    DB_data = pd.DataFrame(np.concatenate(
        [com_name, com_code, date, tod_price, tod_status, tom_price, tom_status, match_status, price_error, returns],
        axis=1), columns=['com_name', 'com_code', 'date', 'tod_price', 'tod_status', 'tom_price', 'tom_status',
                          'match_status', 'price_error', 'return'])
    # com_name,date,tod_price,tod_status,tom_price,tom_status,match_status,price_error,returns

    print(np.prod(returns[-65:-1]))

    return DB_data

def db_to_database(DB_data):
    conn = pymysql.connect(host='192.168.1.23', user='root', password='1231',
                               db='bms_test', charset='utf8')

    curs = conn.cursor()

    sql = "delete from stock_predict where com_name=%s"
    curs.execute(sql, DB_data['com_name'][0])

    sql = '''INSERT INTO stock_predict VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)'''

    for data in DB_data.values:
        curs.execute(sql, (tuple(data)))

    conn.commit()

if __name__ == '__main__':
    # GPU 확인
    Predict_stock.init()

    # data_load
    data = Predict_stock.load_data()

    # data_processing
    target_lsts = Predict_stock.target_lsts


    for target_lst in target_lsts:
        x_train_scaled, x_test_scaled, y_train_scaled, y_test_scaled, num_x_y_xtrain = Predict_stock.data_processing(data, target_lst)

        # generator 생성
        generator = Predict_stock.batch_generator(batch_size=256, sequence_length=365, num_x_y_xtrain=num_x_y_xtrain)

        # model 생성
        model = Predict_stock.init_model(num_x_y_xtrain)
        # model 불러오기
        model.load_weights('model/' + str(target_lst).replace('\'', '') + '.h5')

        t, p = pred(model, data[target_lst].shift(1).values[1:], np.array(data[target_lst[0]].values[1:], dtype=np.float).reshape(-1,1))

        DB_data = create_DB_data(data, target_lst)

        print(DB_data.tail())

        db_to_database(DB_data)

        del model

    sys.exit()
