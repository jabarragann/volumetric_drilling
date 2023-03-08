"""
Script used for IPCAI 2023 submission

"""

from collections import defaultdict
import sys
import pandas as pd

from pydrilling.DataUtils.Recording import Recording

sys.path.append(__file__)

from pydrilling.Metrics.PerformanceMetrics import PerformanceMetrics
from pathlib import Path
from natsort import natsorted

# fmt:off

# Experiments Metadata
# Array indicating which anatomy was used in each trial
# Keys indicated the attempt number - values indicate the anatomy used. (In guidance dict, the anatomy and the modality are indicated.)

metadata = {"Participant_1": {"Baseline":{0:"D",1:"E",2:"A",3:"B",4:"C"},
                              "Guidance":{0:["B","Haptic"]}},
            "Participant_2": {"Baseline":{0:"D",1:"E"},
                              "Guidance":{0:["E","Haptic"]}},
            "Participant_3": {"Baseline":{0:"E",1:"A",2:"C"},
                              "Guidance":{0:["E","Haptic"],1:["A","Visual"]}},
            "Participant_4": {"Baseline":{0:"B"},
                              "Guidance":{0:["D","Audio"],1:["D","Visual"],2:["D","Baseline"],3:["D","Haptic"],
                                          4:["E","Baseline"],5:["E","Visual"],6:["E","Haptic"],7:["E","Audio"]}},
            "Participant_5": {"Baseline":{0:"B"},
                              "Guidance":{0:["A","Haptic"],1:["A","Baseline"],2:["A","Audio"],3:["E","Baseline"],
                                          4:["A","Visual"],5:["E","Visual"],6:["E","Haptic"],7:["E","Audio"]}},
            "Participant_6": {"Baseline":{0:"B"},
                              "Guidance":{0:["A","Visual"],1:["E","Audio"],2:["A","Haptic"],3:["E","Baseline"],
                                          4:["A","Audio"],5:["E","Haptic"],6:["A","Baseline"],7:["E","Visual"]}},
            "Participant_7": {"Baseline":{0:"B"},
                              "Guidance":{0:["E","Baseline"],1:["A","Visual"],2:["E","Visual"],3:["A","Baseline"],
                                          4:["A","Haptic"],5:["E","Haptic"],6:["A","Audio"],7:["E","Audio"],
                                          }}
                              }

# fmt:on
def add_total_unintended_voxels_removed(df: pd.DataFrame) -> pd.DataFrame:
    voxel_cols = [col for col in df.columns if "voxel" in col]
    voxel_cols.remove("Bone_voxels")
    errors_df = df[voxel_cols]
    df.insert(df.shape[1], "total_errors", errors_df.sum(axis=1).to_numpy())

    return df


def add_relative_metrics(df) -> pd.DataFrame:
    """Calculate metrics that are normalized using the baseline performance.
    For each metric and row substract the baseline.

    Parameters
    ----------
    df : pd.Dataframe
        df with metrics
    """
    # Calculate relative metrics
    df.insert(df.shape[1], "relative_completion_time", 0)
    df.insert(df.shape[1], "relative_total_errors", 0)

    for idx in df.index:
        anatomy = df.loc[idx]["anatomy"]
        participant = df.loc[idx]["participant_id"]
        # modality = df.iloc[idx]["guidance"]

        base = df.loc[
            (df["anatomy"] == anatomy)
            & (df["guidance"] == "Baseline")
            & (df["participant_id"] == participant)
        ]
        if base.shape[0] > 0:
            relative_time = df.loc[idx]["completion_time"] - base["completion_time"]
            relative_errors = df.loc[idx]["total_errors"] - base["total_errors"]
            df.at[idx, "relative_completion_time"] = relative_time
            df.at[idx, "relative_total_errors"] = relative_errors

    return df


def analyze_experiment():
    root = Path("/home/juan1995/research_juan/cisII_SDF_project/Data/RedCap")

    if not root.exists():
        print("path does not exists")
        exit(0)

    participant_dict = defaultdict(lambda: {"Guidance": [], "Baseline": []})

    for file in root.glob("*/*/*"):
        # File structure ~/path2data/RedCap/mode/partipant_id/
        participant_id = file.parent.name
        mode = file.parent.parent.name
        participant_dict[participant_id][mode].append(file)

    # Sort attempts
    participant_dict = dict(participant_dict)
    for k, v in participant_dict.items():
        v["Guidance"] = natsorted(v["Guidance"])
        v["Baseline"] = natsorted(v["Baseline"])

    # Calculate metrics
    results = []
    for participant_id, data_paths in participant_dict.items():
        for mode in ["Guidance", "Baseline"]:
            for trial_idx, trial_path in enumerate(data_paths[mode]):
                if mode == "Guidance":
                    anatomy, guidance_type = metadata[participant_id][mode][trial_idx]
                else:
                    anatomy = metadata[participant_id][mode][trial_idx]
                    guidance_type = mode

                trial_meta_data = {
                    "participant_id": participant_id,
                    "guidance_modality": guidance_type,
                    "anatomy": anatomy,
                    "trial_idx": trial_idx,
                }

                with Recording(trial_path, **trial_meta_data) as recording:
                    print(f"Read {len(recording)} h5 files for {recording.participant_id}")
                    metrics = PerformanceMetrics(recording, generate_first_vid=True)
                    results.append(metrics.generate_summary_dataframe())

    results_df = pd.concat(results)
    results_df = results_df.reset_index(drop=True)

    # Add extra metrics
    results_df = add_total_unintended_voxels_removed(results_df)
    results_df = add_relative_metrics(results_df)

    # Sort values and safe
    results_df = results_df.sort_values(["participant_id", "anatomy", "trial_idx"])
    results_df.to_csv(root / "results.csv", index=None)

    print(results_df)


if __name__ == "__main__":
    analyze_experiment()
