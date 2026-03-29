"""
update_pipeline.py
Orquestrador de MLOps para atualizar dados e retreinar o Ensemble de 30 Modelos.
"""
import logging
import shutil
import yaml
from pathlib import Path
import pandas as pd

from japredictbet.config import PipelineConfig
from japredictbet.data.ingestion import load_historical_dataset
from japredictbet.models.train import train_and_save_ensemble
from japredictbet.pipeline.mvp_pipeline import _ensure_season_column, _build_temporal_split, _build_recency_weights

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("MLOps_Pipeline")

def backup_artifacts(models_dir: Path):
    """Faz backup dos modelos antigos caso o novo treino fique ruim."""
    backup_dir = Path("artifacts/backup_models")
    if models_dir.exists():
        if backup_dir.exists():
            shutil.rmtree(backup_dir)
        shutil.copytree(models_dir, backup_dir)
        logger.info(f"Backup dos modelos antigos salvo em: {backup_dir}")

def main(new_dataset_path: str):
    logger.info("=== INICIANDO PIPELINE DE ATUALIZAÇÃO (CONTINUOUS TRAINING) ===")
    
    # 1. Carregar Configuração
    with open("config.yml", "r") as f:
        config_dict = yaml.safe_load(f)
    config = PipelineConfig(**config_dict)
    
    raw_path = Path(config.data.raw_path)
    models_dir = Path("artifacts/models")
    
    # 2. Atualizar a Planilha
    new_data_file = Path(new_dataset_path)
    if not new_data_file.exists():
        logger.error(f"Nova planilha não encontrada em {new_data_file}")
        return
    
    logger.info("Substituindo dataset antigo pelo novo...")
    shutil.copy(new_data_file, raw_path)
    
    # 3. Preparar Dados para Treino
    logger.info("Carregando e validando o novo dataset...")
    data = load_historical_dataset(raw_path, config.data.date_column)
    data = _ensure_season_column(data, config.data.date_column)
    
    # Nota: Aqui você deve rodar as funções de feature engineering (rolling, ELO, etc) 
    # idênticas ao mvp_pipeline.py para gerar o dataframe X final.
    # Por brevidade, assumimos que 'data_features' é o DF já com as rolling features.
    
    # 4. Fazer Backup dos Modelos Antigos
    backup_artifacts(models_dir)
    
    # 5. Retreinar os 30 Modelos com os Novos Dados
    logger.info("Iniciando treinamento dos 60 novos modelos (30 Home / 30 Away)... isso pode demorar.")
    
    # Gerar pesos de recência para dar mais importância aos jogos que acabaram de ser adicionados
    weights = _build_recency_weights(data["season"]) 
    
    models, specs, paths = train_and_save_ensemble(
        features=data, # Substitua pelo DF com features geradas
        home_target="home_corners",
        away_target="away_corners",
        output_dir=models_dir,
        algorithms=("xgboost", "lightgbm", "randomforest"),
        ensemble_size=30,
        sample_weight=weights,
        random_state=42
    )
    
    logger.info(f"✅ Sucesso! {len(paths)} novos modelos de consenso foram treinados e salvos em {models_dir}.")
    logger.info("=== PIPELINE DE ATUALIZAÇÃO CONCLUÍDO ===")
    
    # Próximo passo sugerido: Chamar a função do smoke_test.py automaticamente aqui!

if __name__ == "__main__":
    # Exemplo de uso: python update_pipeline.py caminho/para/planilha_baixada_hoje.csv
    import sys
    if len(sys.argv) > 1:
        main(sys.argv[1])
    else:
        print("Por favor, forneça o caminho da nova planilha. Ex: python update_pipeline.py downloads/novo_ds.csv")