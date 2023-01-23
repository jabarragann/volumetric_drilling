
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.pylab as pylab
import seaborn as sns

import matplotlib.pylab as pylab

PARTICIPANTS = ['Participant_4','Participant_5','Participant_6','Participant_7']
MODALITIES = ["Baseline","Audio","Haptic","Visual"]

def create_fig(n,title, metric_to_analyze):
    fontsize = 14
    fig, axes = plt.subplots(4,1,sharex=True,figsize=(13,7))
    fig.suptitle(title, fontsize=fontsize)
    for ax in axes.squeeze():
        ax.grid()
        ax.set_xlim([-0.5,8])

    axes[-1].set_xlabel("Trial idx", fontsize=fontsize) 

    fig.text(0.06, 0.5, metric_to_analyze, va='center', rotation='vertical',fontsize=fontsize)

    return fig, axes 

def learning_plots_by_modality(df:pd.DataFrame, metric_to_analyze:str):
    title = f"Learning effect plots - {metric_to_analyze} (aggregated by modality)"
    fig,axes = create_fig(4,title, metric_to_analyze)    

    for ax, m in zip(axes.squeeze(),MODALITIES):
        df_A = df.loc[(df["anatomy"]=="A") &(df["guidance"]==m)]
        learning_data_A = df_A[["trial_idx",metric_to_analyze]].to_numpy()

        df_E = df.loc[(df["anatomy"]=="E") &(df["guidance"]==m)]
        learning_data_E = df_E[["trial_idx",metric_to_analyze]].to_numpy()

        # print(learning_data_E)
        ax.plot(learning_data_A[:,0],learning_data_A[:,1], "ro", label="A-"+m)
        ax.plot(learning_data_E[:,0],learning_data_E[:,1], "bo", label="E-"+m)
        ax.legend()
    plt.show()

def learning_plots_by_user(df:pd.DataFrame, metric_to_analyze:str):
    
    title = f"Learning effect plots - {metric_to_analyze} (aggregated by user)"
    fig,axes = create_fig(4,title, metric_to_analyze)    

    for ax, p in zip(axes.squeeze(), PARTICIPANTS):
        df_A = df.loc[(df["anatomy"]=="A") &(df["participant_id"]==p)]
        learning_data_A = df_A[["trial_idx",metric_to_analyze]].to_numpy()

        df_E = df.loc[(df["anatomy"]=="E") &(df["participant_id"]==p)]
        learning_data_E = df_E[["trial_idx",metric_to_analyze]].to_numpy()

        # print(learning_data_E)
        ax.plot(learning_data_A[:,0],learning_data_A[:,1], "ro", label="A-"+p)
        ax.plot(learning_data_E[:,0],learning_data_E[:,1], "bo", label="E-"+p)
        ax.set_xlim([-0.5,8])
        ax.legend()
    plt.show()


def main():
    root = Path("/home/juan1995/research_juan/cisII_SDF_project/Data/RedCap/final_objective_metrics.csv")
    df = pd.read_csv(root)

    df = df.loc[df["participant_id"].isin(PARTICIPANTS)]

    # metric = "total_errors"
    metric = "completion_time"
    learning_plots_by_modality(df, metric_to_analyze=metric)
    learning_plots_by_user(df,metric)



if __name__ =="__main__":
    main()