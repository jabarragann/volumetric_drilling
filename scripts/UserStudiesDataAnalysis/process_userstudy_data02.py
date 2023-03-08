"""
Script used for IROS 2023 submission

"""

import sys
sys.path.append(__file__)
from collections import defaultdict
import json
import pandas as pd
from pathlib import Path
from natsort import natsorted
# Custom
from pydrilling.DataUtils.Recording import Recording
from pydrilling.Metrics.PerformanceMetrics import PerformanceMetrics
from pydrilling.utils import ColorPrinting as cp, SimulatorDataParser



def add_total_unintended_voxels_removed(df: pd.DataFrame) -> pd.DataFrame:
    voxel_cols = [col for col in df.columns if "voxel" in col]
    voxel_cols.remove("Bone_voxels")
    errors_df = df[voxel_cols]
    df.insert(df.shape[1], "total_errors", errors_df.sum(axis=1).to_numpy())

    return df


def analyze_experiment():
    root = Path("/home/juan1995/research_juan/cisII_SDF_project/Data/UserStudy2_IROS/")

    if not root.exists():
        print("path does not exists")
        exit(0)

    participant_dict =  SimulatorDataParser.get_participants_recordings(root)

    # Calculate metrics
    results = []
    for participant_id, data_paths in participant_dict.items():
        for trial_idx, trial_path in enumerate(data_paths):
            trial_meta_data = SimulatorDataParser.load_meta_data(trial_idx, trial_path) 

            with Recording(trial_path, **trial_meta_data) as recording:
                print(f"Read {len(recording)} h5 files for participant {recording.participant_id}")
                metrics = PerformanceMetrics(recording, generate_first_vid=False)
                results.append(metrics.generate_summary_dataframe())

    results_df = pd.concat(results)
    results_df = results_df.reset_index(drop=True)

    # Add extra metrics
    results_df = add_total_unintended_voxels_removed(results_df)

    # Sort values and safe
    results_df = results_df.sort_values(["participant_id", "trial_idx", "anatomy"])
    results_df.to_csv(root / "results.csv", index=None)

    print(results_df)


if __name__ == "__main__":
    analyze_experiment()