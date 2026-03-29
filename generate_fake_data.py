"""Script to generate a larger, more realistic fake dataset."""

import pandas as pd
import numpy as np
import datetime
import itertools

def generate_fake_data(num_seasons: int, teams_per_season: int, output_path: str):
    """Generates and saves a fake football dataset."""

    print(f"Generating fake data for {num_seasons} seasons with {teams_per_season} teams...")

    team_names = [f"Team {chr(65 + i)}" for i in range(teams_per_season)]
    all_matches = []
    start_date = datetime.date(2021, 8, 1)

    for season_n in range(num_seasons):
        season_teams = team_names
        matchups = list(itertools.permutations(season_teams, 2))
        
        for home_team, away_team in matchups:
            match_date = start_date + datetime.timedelta(days=(season_n * 380) + len(all_matches))
            
            match_data = {
                "date": match_date.strftime("%Y-%m-%d"),
                "home_team": home_team,
                "away_team": away_team,
                "home_goals": np.random.randint(0, 5),
                "away_goals": np.random.randint(0, 4),
                "home_corners": np.random.randint(2, 15),
                "away_corners": np.random.randint(2, 12),
                "home_shots": np.random.randint(5, 25),
                "away_shots": np.random.randint(3, 20),
                "home_shots_on_target": np.random.randint(1, 10),
                "away_shots_on_target": np.random.randint(1, 8),
                "home_fouls": np.random.randint(5, 20),
                "away_fouls": np.random.randint(5, 20),
                "home_yellow_cards": np.random.randint(0, 5),
                "away_yellow_cards": np.random.randint(0, 5),
                "home_red_cards": np.random.randint(0, 2),
                "away_red_cards": np.random.randint(0, 2),
            }
            all_matches.append(match_data)

    df = pd.DataFrame(all_matches)
    df.to_csv(output_path, index=False)
    print(f"Successfully generated {len(df)} matches and saved to '{output_path}'")


if __name__ == "__main__":
    # Using 20 teams for 3 seasons will give 3 * (20*19) = 1140 rows.
    # This should be enough to handle rolling windows of 10.
    generate_fake_data(
        num_seasons=3,
        teams_per_season=20,
        output_path="data/raw/dataset.csv"
    )
