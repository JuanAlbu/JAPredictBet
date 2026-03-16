import os

# Diretório dos arquivos
folder = r"data/processed"

# Mapeamento dos nomes antigos para os novos
rename_map = {
    "E0.csv": "PL25_26.csv",
    "E0 (1).csv": "PL24_25.csv",
    "E0 (2).csv": "PL23_24.csv",
    "E0 (3).csv": "PL22_23.csv",
    "E0 (4).csv": "PL21_22.csv",
    "E0 (5).csv": "PL20_21.csv",
    "E0 (6).csv": "PL19_20.csv",
    "E0 (7).csv": "PL18_19.csv",
    "E0 (8).csv": "PL17_18.csv",
    "E0 (9).csv": "PL16_17.csv",
    "E0 (10).csv": "PL15_16.csv"
}

for old_name, new_name in rename_map.items():
    old_path = os.path.join(folder, old_name)
    new_path = os.path.join(folder, new_name)
    if os.path.exists(old_path):
        os.rename(old_path, new_path)
        print(f"Renomeado: {old_name} -> {new_name}")
    else:
        print(f"Arquivo não encontrado: {old_name}")
