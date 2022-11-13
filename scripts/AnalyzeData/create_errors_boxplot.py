from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.pylab as pylab
import seaborn as sns

import matplotlib.pylab as pylab

params = {
    "legend.fontsize": "x-large",
    "figure.figsize": (9, 5),
    "axes.labelsize": "x-large",
    "axes.titlesize": "x-large",
    "xtick.labelsize": "x-large",
    "ytick.labelsize": "x-large",
}
pylab.rcParams.update(params)

adjust_params = dict(top=0.88, bottom=0.18, left=0.125, right=0.9, hspace=0.2, wspace=0.25)


def main():
    root = Path("/home/juan1995/research_juan/cisII_SDF_project/Data/RedCap/results.csv")
    df = pd.read_csv(root)

    voxel_cols = [col for col in df.columns if "voxel" in col]
    voxel_cols.remove("Bone_voxels")

    # Drop participants 1,2,3
    index_to_drop = df.loc[
        (df["participant_id"] == "Participant_1")
        | (df["participant_id"] == "Participant_2")
        | (df["participant_id"] == "Participant_3")
    ].index

    df.drop(index_to_drop, inplace=True)

    errors_df = df[voxel_cols]
    df.insert(df.shape[1], "total_errors", errors_df.sum(axis=1).to_numpy())

    # only use anatomy A and E
    df = df.loc[(df["anatomy"] == "A") | (df["anatomy"] == "E")]

    #######################
    ## errors plot
    #######################

    ax: plt.Axes
    fig, ax = plt.subplots(1)
    fig.subplots_adjust(**adjust_params)
    sns.boxplot(df, x="guidance", y="total_errors", hue="anatomy", ax=ax)
    sns.swarmplot(
        df, x="guidance", y="total_errors", hue="anatomy", dodge=True, palette="dark:black", ax=ax
    )

    # Remove repeated labels
    handles, labels = ax.get_legend_handles_labels()
    by_label = dict(zip(labels[:2], handles[:2]))
    ax.legend(by_label.values(), by_label.keys())
    ax.set_xlabel("Feedback modality", labelpad=10)
    ax.set_ylabel("Removed voxels", labelpad=10)

    #######################
    ## errors plot
    #######################
    ax: plt.Axes
    fig, ax = plt.subplots(1)
    fig.subplots_adjust(**adjust_params)
    sns.boxplot(df, x="guidance", y="completion_time", hue="anatomy", ax=ax)
    sns.swarmplot(
        df,
        x="guidance",
        y="completion_time",
        hue="anatomy",
        dodge=True,
        palette="dark:black",
        ax=ax,
    )

    # Remove repeated labels
    handles, labels = ax.get_legend_handles_labels()
    by_label = dict(zip(labels[:2], handles[:2]))
    ax.legend(by_label.values(), by_label.keys())
    ax.set_xlabel("Feedback modality", labelpad=10)
    ax.set_ylabel("Completion time (s)", labelpad=10)

    plt.show()


if __name__ == "__main__":
    main()
