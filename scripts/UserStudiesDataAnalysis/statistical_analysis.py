from collections import defaultdict
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.pylab as pylab
import seaborn as sns

import matplotlib.pylab as pylab
from scipy.stats import f_oneway
from statsmodels.stats.multicomp import pairwise_tukeyhsd

params = {
    "legend.fontsize": "x-large",
    "figure.figsize": (9, 5),
    "axes.labelsize": "xx-large",
    "axes.titlesize": "x-large",
    "xtick.labelsize": "xx-large",
    "ytick.labelsize": "xx-large",
}
pylab.rcParams.update(params)

adjust_params = dict(top=0.88, bottom=0.18, left=0.125, right=0.9, hspace=0.2, wspace=0.25)


def create_plots(df):
    #######################
    ## errors plot
    #######################

    ax: plt.Axes
    fig, ax = plt.subplots(1)
    fig.set_tight_layout(True)
    fig.subplots_adjust(**adjust_params)
    sns.boxplot(df, x="guidance", y="total_errors", ax=ax)
    sns.swarmplot(df, x="guidance", y="total_errors", color="black", ax=ax)

    # Remove repeated labels
    # handles, labels = ax.get_legend_handles_labels()
    # by_label = dict(zip(labels[:2], handles[:2]))
    # ax.legend(by_label.values(), by_label.keys())
    ax.set_xlabel("Feedback modality", labelpad=10)
    ax.set_ylabel("# of unintended voxels removed", labelpad=10)
    ax.grid(color="black", alpha=0.5, axis="y")

    #######################
    ## errors plot
    #######################
    ax: plt.Axes
    fig, ax = plt.subplots(1)
    fig.set_tight_layout(True)
    fig.subplots_adjust(**adjust_params)
    sns.boxplot(df, x="guidance", y="completion_time", ax=ax)
    sns.swarmplot(
        df,
        x="guidance",
        y="completion_time",
        # hue="anatomy",
        # dodge=True,
        color="black",
        ax=ax,
    )

    # Remove repeated labels
    # handles, labels = ax.get_legend_handles_labels()
    # by_label = dict(zip(labels[:2], handles[:2]))
    # ax.legend(by_label.values(), by_label.keys())
    ax.set_xlabel("Feedback modality", labelpad=10)
    ax.set_ylabel("Completion time (s)", labelpad=10)
    ax.grid(color="black", alpha=0.5, axis="y")

    plt.show()


def main():
    root = Path("/home/juan1995/research_juan/cisII_SDF_project/Data/RedCap/final_objective_metrics.csv")
    df = pd.read_csv(root)

    # Drop participants 1,2,3
    index_to_drop = df.loc[
        (df["participant_id"] == "Participant_1")
        | (df["participant_id"] == "Participant_2")
        | (df["participant_id"] == "Participant_3")
        | (df["participant_id"] == "Participant_6")
    ].index

    df.drop(index_to_drop, inplace=True)

    # only use anatomy A, E , B
    df = df.loc[(df["anatomy"] == "A") | (df["anatomy"] == "E") | (df["anatomy"] == "B")]

    # create_plots(df)

    # statistical analysis
    data_dict = dict(total_errors=defaultdict(list), completion_time=defaultdict(list))
    for metric in data_dict:
        for modality in ["Baseline", "Haptic", "Visual", "Audio"]:
            points = df.loc[(df["guidance"] == modality)][metric].to_numpy().tolist()
            data_dict[metric][modality] += points

    fig, ax =plt.subplots(2)
    plt.boxplot(np.array(data_dict["total_errors"]["Baseline"]))
    plt.boxplot(np.array(data_dict["total_errors"]["Haptic"]))

    x = [v for k, v in data_dict["total_errors"].items()]
    print(f_oneway(*x))

    x = [v for k, v in data_dict["completion_time"].items()]
    print(f_oneway(*x))

    plt.show()


if __name__ == "__main__":
    main()
