import streamlit as st
import yfinance as yf
import requests
from bs4 import BeautifulSoup
import pandas as pd

pd.options.display.float_format = '{:,.2f}'.format

def get_parameters(page, size):
    # page * size만큼 offset 전진 (size는 25로 예상)
    return {
        "tm": 77609, # 레버리지/인버스 필터링 코드
        "offset": (page - 1) * size,
        # 기본적으로 3개월 평균 거래량으로 정렬
        "sort": "three_month_average_volume",
        "order": "desc" # 내림차순 (큰 것이 먼저)
    }

def get_symbols():
    url = "https://etfdb.com/data_set/"
    page, size = 1, 25 # 한 번에 전체 조회가 불가능하므로 page를 증가시키면서 조회해야함
    symbols = [] # 검색된 레버리지 코드들
    while True: # 계속 반복
        if (page == 3): return symbols
        params = get_parameters(page, size) # 조회된 size만큼 전진해서 요청
        response = requests.get(url, params=params).json()
        # json 포맷으로 데이터 받아옴
        rows = response['rows'] # 받아온 데이터 요소들
        # print(rows)
        if len(rows) == 0: return symbols # 값이 없으면 반복 종료
        # 받은 데이터가 태그로 덮여있는데 BS로 태그 제거하고 텍스트만 남기기
        symbol_mapper = lambda x: BeautifulSoup(x['symbol'], features='lxml').text
        # 텍스트로 된 새로운 코드 리스트를 앞서 정의한 코드 리스트에 연결
        items = [symbol_mapper(r) for r in rows]
        # print(items)
        symbols.extend(items)
        page+=1 # 다음 장으로

def get_momentum(df, days=(3, 5, 8, 13)):
    get_er = lambda x: (x[-1] / x[0]) - 1
    return pd.concat(
        [df['Open'].rolling(d).apply(get_er) for d in days], axis=1
        ).mean(axis=1).iloc[-1]

def find_item(count=5):
    exclude = [
                'SSG', 'TTT', 'SRTY', 'REW', 'TECS',
                'TBT', 'QID', 'SPXU', 'SPXS', 'TWM',
                'SDOW', 'DXD', 'UDOW', 'SSO', 'UWM',
                'JNUG'
              ]
    momentums = [(s, get_momentum(yf.Ticker(s).history()))
    for s in get_symbols() if s not in exclude]
    df_m = pd.DataFrame(momentums, columns=['symbol', 'momentum']
                    ).sort_values('momentum', ascending=False
                    ).set_index('symbol')
    return df_m.head(count)

def get_score(ticker: str, limit=0.02, ma_days=(3, 5, 8, 13)):
    df = yf.Ticker(ticker).history()
    df['Range'] = df['High'] - df['Low']
    df['Noise'] = abs(df['Close'] - df['Open']) / df['Range']
    df['Noise13'] = df['Noise'].rolling(13).mean()
    df['TargetP'] = df['Open'] + (df['Range'] * df['Noise13']).shift(1)
    df['Volatility'] = df['Range'] / df['Close']
    df['TargetV'] = limit / df['Volatility'].shift(1)
    ma = lambda d: df['Open'].rolling(d).mean() <= df['Open']
    df['MA'] = sum([ma(d) for d in ma_days])
    df['Price'] = df['TargetP']
    df['Score'] = df['MA'] * df['TargetV']
    # print(df)
    return df.iloc[-1]

default_budget = 20000000
budget = st.number_input('투자금',
min_value=1000000, value=default_budget, step=1000000)

default_currency = 1200.0
currency = st.number_input('환율',
min_value=1000.0, value=default_currency, step=0.1)

if st.button('데이터 불러오기'):
    with st.spinner('데이터 로딩 중'):
        item = find_item(10)
        
        score = pd.concat([get_score(i) for i in item.index], axis=1)

        st.header('시가 기준일')
        st.write(score.columns.tolist())
        score.columns = item.index

        score_t = score.transpose()
        score_t['Amount'] = (budget * score_t['Score'] * 0.02).apply(int) 
        score_t['Currency'] = (score_t['Amount'] / currency).apply(int)
        # st.write(score_t.index)
        # print(score_t.index)
        sum_amount = int(score_t['Amount'].sum() / 10000 + 1) * 10000

        st.header('베팅 총액')
        st.write(sum_amount)

        st.header('목표가 및 비중')
        st.write(score_t[['Price', 'Amount', 'Currency']])