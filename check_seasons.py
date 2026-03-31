import pandas as pd
from pathlib import Path

csv_path = 'data/raw/dataset.csv'
df = pd.read_csv(csv_path)

# Converter Date para datetime
df['Date'] = pd.to_datetime(df['Date'], format='mixed', dayfirst=True)

print('Dataset Info:')
print(f'Total de linhas: {len(df)}')
print(f'Data min: {df["Date"].min()}')
print(f'Data max: {df["Date"].max()}')
print()

# Agrupar por source_file para ver as temporadas
print('Temporadas disponíveis:')
agg_df = df.groupby('source_file').agg({
    'Date': ['min', 'max', 'count']
}).sort_values(('Date', 'min'), ascending=False)
print(agg_df)
print()

# Pegar temporada mais recente
most_recent = df['Date'].max()
recent_season_df = df[df['Date'] >= (most_recent - pd.Timedelta(days=365))]
print(f'Temporada mais recente: {most_recent}')
print(f'Total de jogos na temporada mais recente: {len(recent_season_df)}')
print()

# Sample aleatório de 50 jogos
if len(recent_season_df) >= 50:
    sample_df = recent_season_df.sample(n=50, random_state=42)
    print(f'Sample aleatória de 50 jogos da temporada mais recente:')
    print(f'Datas: {sample_df["Date"].min()} até {sample_df["Date"].max()}')
    print(f'Times: {sample_df["HomeTeam"].nunique()} home teams, {sample_df["AwayTeam"].nunique()} away teams')
else:
    print(f'Apenas {len(recent_season_df)} jogos na temporada mais recente (< 50)')
