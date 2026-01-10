import pandas as pd

df = pd.read_excel('W1.xlsx')
print('前2行所有数据:')
print(df.iloc[:2].to_string())
print('\n第2行的所有值:')
for i, val in enumerate(df.iloc[1]):
    print(f'列{i}: {val}')
