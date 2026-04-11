"""
Script para preparar um subset realista: últimos 180 dias da temporada mais recente.
Garante histórico suficiente para rolling features.
"""
import pandas as pd
import shutil
from pathlib import Path
from datetime import datetime, timedelta

# Carregar dataset completo
csv_path = 'data/raw/dataset.csv'
df = pd.read_csv(csv_path)
df['Date'] = pd.to_datetime(df['Date'], format='mixed', dayfirst=True)

# Filtrar para temporada mais recente (PL25_26)
recent_season = df[df['source_file'] == 'PL25_26.csv'].copy()
print(f"Total de jogos em PL25_26: {len(recent_season)}")

# Get max date in this season
max_date = recent_season['Date'].max()
print(f"Data máxima: {max_date.date()}")

# Get data from last 180 days
cutoff_date = max_date - timedelta(days=180)
subset_180 = recent_season[recent_season['Date'] >= cutoff_date].copy()
print(f"Cutoff date: {cutoff_date.date()}")
print(f"Total de jogos nos últimos 180 dias: {len(subset_180)}")
print(f"Datas: {subset_180['Date'].min().date()} até {subset_180['Date'].max().date()}")
print(f"Times envolvidos: {subset_180['HomeTeam'].nunique()} home, {subset_180['AwayTeam'].nunique()} away")
print()

# Alternatively also include the season before to ensure enough historical context
if len(subset_180) < 60:
    print("⚠️  Menos de 60 jogos em 180 dias. Incluindo jogos anteriores para contexto histórico...")
    previous_season = df[df['source_file'] == 'PL24_25.csv'].copy()
    
    # Get all of last 100 matches from previous season + all of current
    all_recent = pd.concat([
        previous_season.tail(100),
        subset_180
    ]).sort_values('Date').reset_index(drop=True)
    print(f"Total com contexto: {len(all_recent)} jogos")
    print(f"Datas: {all_recent['Date'].min().date()} até {all_recent['Date'].max().date()}")
    print()
    subset_180 = all_recent

# Now sample 50 games from the continuous subset
if len(subset_180) >= 80:
    # Ensure we have at least some gap for training data
    # Use the first 70% for training context, last 30% for sampling
    first_part = subset_180.iloc[:int(len(subset_180)*0.7)]
    second_part = subset_180.iloc[int(len(subset_180)*0.7):]
    
    # Sample from second part only
    sample_50 = pd.concat([
        first_part,
        second_part.sample(n=min(50, len(second_part)), random_state=42)
    ]).sort_values('Date').reset_index(drop=True)
    print(f"✅ Sample de 50 jogos criada (com contexto histórico)")
else:
    sample_50 = subset_180
    print(f"⚠️  Usando todos os {len(sample_50)} jogos disponíveis")

print(f"Datas: {sample_50['Date'].min().date()} até {sample_50['Date'].max().date()}")
print(f"Times envolvidos: {sample_50['HomeTeam'].nunique()} home, {sample_50['AwayTeam'].nunique()} away")
print()

# Backup do dataset original
original_backup = 'data/raw/dataset_full_backup.csv'
if not Path(original_backup).exists():
    print(f"Criando backup do dataset completo em {original_backup}...")
    df.to_csv(original_backup, index=False)
    print(f"✅ Backup criado")

# Salvar sample como dataset temporário
test_dataset_path = 'data/raw/dataset_test_50matches.csv'
sample_50.to_csv(test_dataset_path, index=False)
print(f"✅ Dataset de teste salvo em {test_dataset_path}")

# Criar versão temporária do config para usar o dataset de teste
config_backup = 'config_backup.yml'
config_original = 'config.yml'

if not Path(config_backup).exists():
    shutil.copy(config_original, config_backup)
    print(f"✅ Config backup criado")

# Ler config e modificar para usar dataset de teste
with open(config_original, 'r') as f:
    config_content = f.read()

config_test = config_content.replace(
    'raw_path: "data/raw/dataset.csv"',
    'raw_path: "data/raw/dataset_test_50matches.csv"'
)

config_test_path = 'config_test_50matches.yml'
with open(config_test_path, 'w') as f:
    f.write(config_test)

print(f"✅ Config de teste criado: {config_test_path}")
print()
print("=" * 70)
print("PRÓXIMA AÇÃO: Execute o teste com:")
print("  python scripts/consensus_accuracy_report.py \\")
print("    --config config_test_50matches.yml \\")
print("    --n-models 30 \\")
print("    --seed-start 42")
print("=" * 70)
