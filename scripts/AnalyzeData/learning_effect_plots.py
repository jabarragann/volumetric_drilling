
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.pylab as pylab
import seaborn as sns

import matplotlib.pylab as pylab



def main():
    root = Path("/home/juan1995/research_juan/cisII_SDF_project/Data/RedCap/final_objective_metrics.csv")
    df = pd.read_csv(root)

    fig, axes = plt.subplots(4,1)

    metric_to_analyze = "total_errors"
    # metric_to_analyze = "completion_time"

    participants = ['Participant_4','Participant_5','Participant_6','Participant_7']
    df = df.loc[df["participant_id"].isin(participants)]

    for ax, m in zip(axes.squeeze(),["Baseline","Audio","Haptic","Visual"]):
        df_A = df.loc[(df["anatomy"]=="A") &(df["guidance"]==m)]
        learning_data_A = df_A[["trial_idx",metric_to_analyze]].to_numpy()

        df_E = df.loc[(df["anatomy"]=="E") &(df["guidance"]==m)]
        learning_data_E = df_E[["trial_idx",metric_to_analyze]].to_numpy()

        # print(learning_data_E)
        ax.plot(learning_data_A[:,0],learning_data_A[:,1], "ro", label="A-"+m)
        ax.plot(learning_data_E[:,0],learning_data_E[:,1], "bo", label="E-"+m)
        ax.set_xlim([-0.5,8])
        ax.legend()
    plt.show()


if __name__ =="__main__":
    main()