import pandas as pd

df = pd.read_excel('W1.xlsx')
print(f'列数: {len(df.columns)}')
print('\n所有列名:')
for i, col in enumerate(df.columns):
    print(f'{i}: {col}')

print('\n前5行数据:')
print(df.head())
