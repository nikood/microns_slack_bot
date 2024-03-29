import logging
import os
import re
import json
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from dotenv import load_dotenv
from neuvue_queue_task_assignment.summary_stats.plot_multi_neuron_counts import \
    plot_multi_neuron_counts
from neuvue_queue_task_assignment.summary_stats.update_before_and_after_nuclei_tables import \
    update_before_and_after_nuclei_tables
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from tabulate import tabulate

################ INITIATE BOT ##############################################################################################

# setting up the environment path
env_path = Path(__file__).parent.resolve() / ".env"
load_dotenv(dotenv_path=env_path)


SLACK_APP_TOKEN = os.environ["SLACK_APP_TOKEN"]
SLACK_BOT_TOKEN = os.environ["SLACK_BOT_TOKEN"]


app = App(token=SLACK_BOT_TOKEN, name='MICrONS Bot')
logger = logging.getLogger(__name__)

single_soma_before = None
single_soma_after = None
multi_soma_before = None
multi_soma_after = None
single_neuron_df_before = None
single_neuron_df_after = None
one_neuron_multi_soma_before = None
one_neuron_multi_soma_after = None
neuron_only_before = None
neuron_only_after = None
unique_before = None
counts_before = None
unique_after_match = None
counts_after_match = None

#################### FETCH UPDATED EXTENSION DATA #####################################################################################
def ext_update():
    with open("extension_update_date.json", "r") as f:
        data = json.load(f)
        return data

#################### THE GIVEN DATA (MULTI SOMA) ######################################################################################
def update_data():
    global single_soma_before
    global single_soma_after
    global multi_soma_before
    global multi_soma_after
    global single_neuron_df_before
    global single_neuron_df_after
    global one_neuron_multi_soma_before
    global one_neuron_multi_soma_after        
    global neuron_only_before
    global neuron_only_after
    global unique_before
    global counts_before
    global unique_after_match
    global counts_after_match
    global now_timestamp

    now_timestamp = datetime.utcnow()
    update_before_and_after_nuclei_tables(now_timestamp)

    nuclei_before = pd.read_pickle("/home/daliln1-a/MICRONS/neuron_table/filtered_updated_nuclei_table_before_proofreading_v272.pkl")
    nuclei_after = pd.read_pickle("/home/daliln1-a/MICRONS/neuron_table/filtered_updated_nuclei_table_after_proofreading.pkl")

    ###########
    # Multi Soma Counts
    ###########

    multi_soma_before = nuclei_before["pt_root_id"].value_counts()[nuclei_before["pt_root_id"].value_counts() >= 2]
    multi_soma_df_before = nuclei_before[nuclei_before["pt_root_id"].isin(multi_soma_before.keys())]

    multi_soma_after = nuclei_after["pt_root_id"].value_counts()[nuclei_after["pt_root_id"].value_counts() >= 2]
    multi_soma_df_after = nuclei_after[nuclei_after["pt_root_id"].isin(multi_soma_after.keys())]

    ###########
    # Single Soma Counts
    ###########
    single_soma_before = nuclei_before["pt_root_id"].value_counts()[nuclei_before["pt_root_id"].value_counts() < 2]
    print(single_soma_before)

    single_soma_df_before = nuclei_before[nuclei_before["pt_root_id"].isin(single_soma_before.keys())]

    single_soma_after = nuclei_after["pt_root_id"].value_counts()[nuclei_after["pt_root_id"].value_counts() < 2]
    single_soma_df_after = nuclei_after[nuclei_after["pt_root_id"].isin(single_soma_after.keys())]

    ###########
    # Single Neuron Counts
    ###########
    single_neuron_df_before = single_soma_df_before[single_soma_df_before['cell_type_to_use'] == 'neuron']
    single_neuron_df_after = single_soma_df_after[single_soma_df_after['cell_type_to_use'] == 'neuron']

    ###########
    # Single Neuron + Other Bodies Counts
    ###########

    # multi soma single neuron
    multi_neuron_df_before = multi_soma_df_before[multi_soma_df_before['cell_type_to_use'] == 'neuron']
    multi_neuron_df_after = multi_soma_df_after[multi_soma_df_after['cell_type_to_use'] == 'neuron']

    one_neuron_multi_soma_before = multi_neuron_df_before['pt_root_id'].value_counts(
    )[multi_neuron_df_before['pt_root_id'].value_counts() < 2]
    one_neuron_multi_soma_after = multi_neuron_df_after['pt_root_id'].value_counts(
    )[multi_neuron_df_after['pt_root_id'].value_counts() < 2]

    ###########
    # Multi Neuron Counts
    ###########
    neuron_only_before = multi_neuron_df_before['pt_root_id'].value_counts()[multi_neuron_df_before['pt_root_id'].value_counts() >= 2]
    neuron_only_after = multi_neuron_df_after['pt_root_id'].value_counts()[multi_neuron_df_after['pt_root_id'].value_counts() >= 2]

    newly_single_soma = single_soma_df_after[~single_soma_df_after['id'].isin(single_soma_df_before['id'])]

    master_table = pd.read_pickle("/home/daliln1-a/MICRONS/neuron_table/nuclei_neuron_table_master_table.pkl")
    master_table['APL_proofread'] = False
    master_table.loc[master_table['id'].isin(newly_single_soma['id']), 'APL_proofread_multi_soma'] = True
    # master_table.to_pickle(BOX_PATH + f'/nuclei_neuron_table_master_table_proofread_soma_{now_timestamp.strftime("%m_%d_%y")}.pkl' )

    neuron_before = nuclei_before[nuclei_before['cell_type']=='neuron']
    neuron_after = nuclei_after[nuclei_after['cell_type']=='neuron']

    unique_before, counts_before = np.unique(neuron_before['pt_root_id'].value_counts().values, return_counts=True)
    unique_after, counts_after = np.unique(neuron_after['pt_root_id'].value_counts().values, return_counts=True)

    after_dict = dict(zip(unique_after, counts_after))
    unique_after_match = []
    counts_after_match = []
    for key in unique_before:
        if key in after_dict.keys():
            unique_after_match.append(key)
            counts_after_match.append(after_dict[key])
        else:
            unique_after_match.append(key)
            counts_after_match.append(0)


####################### DM CHANELL UPDATE ##########################################################################

#give updates on the multi-soma cells
@app.message(re.compile("(update|Update|UPDATE)"))
def give_update(message, say):
    say(text="Processing your request now!")
    update_data()
    channel_type = message["channel_type"]
    if channel_type != "im":
        logger.info(f"Channel type is: {channel_type}")
        return

    dm_channel = message["channel"]
    user_id = message["user"]

    table_1 = [["Description", "Value"],
             ["single soma before", str(len(single_soma_before))],
             ["single soma after", str(len(single_soma_after))],
             ["single soma difference", str(len(single_soma_after) - len(single_soma_before))],
             ["multi soma before", str(len(multi_soma_before))],
             ["multi soma after", str(len(multi_soma_after))],
             ["multi soma difference", str(len(multi_soma_after) - len(multi_soma_before))],
             ]

    table_2 = [["Description", "Value"],
             ["completely single neuron before", str(len(single_neuron_df_before.pt_root_id.unique()))],
             ["completely single neuron after", str(len(single_neuron_df_after.pt_root_id.unique()))],
             ["completely single neuron difference", str(len(single_neuron_df_after.pt_root_id.unique()) - len(single_neuron_df_before.pt_root_id.unique()))],
             ["one neuron + other cells before", str(len(one_neuron_multi_soma_before))],
             ["one neuron + other cells after", str(len(one_neuron_multi_soma_after))],
             ["one neuron + other cells difference", str(len(one_neuron_multi_soma_after) - len(one_neuron_multi_soma_before))],
             ["multi neuron before", str(len(neuron_only_before))],
             ["multi neuron after", str(len(neuron_only_after))],
             ["multi neuron difference", str(len(neuron_only_after)-len(neuron_only_before))],
             ["number of neurons in multi neuron IDs before", str(neuron_only_before.values.sum())],
             ["number of neurons in multi neuron IDs after", str(neuron_only_after.values.sum())],
             ]


    update = (
        "```\n"
        + "Update as of: " + str(datetime.utcnow())
        + "```"
        "\n"
        "```\n"
        + tabulate(table_1, headers='firstrow',  tablefmt='fancy_grid')
        + "```"
        "\n"
        "```\n"
        + tabulate(table_2, headers='firstrow',  tablefmt='fancy_grid')
        + "```"
    )

    logger.info(f"Sent update < {update} > to {user_id} ")

    say(text=update, channel=dm_channel)

################### GRAPH DM #######################################################################################

@app.message(re.compile("(graph|chart|plot|figure|draw|Graph|Chart|Plot|Figure|Draw)"))
def send_graph(message, say):
    say(text="Processing your request now!")
    update_data()
    plot_multi_neuron_counts(unique_before, counts_before, np.array(unique_after_match), np.array(counts_after_match),'seg_id_multi_soma_distr_all.png', now_timestamp) 

    # channel_type = message["channel_type"]
    # if channel_type != "im":
    #     logger.info(f"Channel type is: {channel_type}")
    #     return

    dm_channel = message["channel"]
    user_id = message["user"]

    update = app.client.files_upload(file="seg_id_multi_soma_distr_all.png" , channels=dm_channel)
    logger.info(f"Sent update seg_id_multi_soma_distr_all.png to {user_id} ")

    say(text=update, channel=dm_channel)

########################### EXTENSION TASK DM #####################################################################
@app.message(re.compile("(Extension|extension|Ext|ext)"))
def send_ext_update(message, say):
    say(text="Processing your request now!")
    ext_data = ext_update()

    table_1 = [["Description", "Value"],
             ["Number of extensions (merges) made: ", str(ext_data["merge_num"])],
             ["Total synapses reassigned :", str(ext_data["total_synapse_num"])],
             ]
             
    ext_update_table = (
          "```\n"
        + "Update as of: " + str(datetime.utcnow())
        + "```"
        "\n"
        "```\n"
        + tabulate(table_1, headers='firstrow',  tablefmt='fancy_grid')
        + "```"
    )

    dm_channel = message["channel"]
    user_id = message["user"]

    logger.info(f"Sent update on extension analysis to {user_id} ")

    say(text=ext_update_table, channel=dm_channel)

###################### GROUP CHANNEL UPDATE & GRAPH #############################################################################

@app.event("app_mention")
def give__mention_update(event, say):
    say(text="Processing your request now!")
    message = event["text"]

    channel = event["channel"]
    user_id = event['user']

    if re.search("(update|Update|UPDATE)", message):
        update_data()
        
        table_1 = [["Description", "Value"],
                ["single soma before", str(len(single_soma_before))],
                ["single soma after", str(len(single_soma_after))],
                ["single soma difference", str(len(single_soma_after) - len(single_soma_before))],
                ["multi soma before", str(len(multi_soma_before))],
                ["multi soma after", str(len(multi_soma_after))],
                ["multi soma difference", str(len(multi_soma_after) - len(multi_soma_before))],
                ]

        table_2 = [["Description", "Value"],
                ["completely single neuron before", str(len(single_neuron_df_before.pt_root_id.unique()))],
                ["completely single neuron after", str(len(single_neuron_df_after.pt_root_id.unique()))],
                ["completely single neuron difference", str(len(single_neuron_df_after.pt_root_id.unique()) - len(single_neuron_df_before.pt_root_id.unique()))],
                ["one neuron + other cells before", str(len(one_neuron_multi_soma_before))],
                ["one neuron + other cells after", str(len(one_neuron_multi_soma_after))],
                ["one neuron + other cells difference", str(len(one_neuron_multi_soma_after) - len(one_neuron_multi_soma_before))],
                ["multi neuron before", str(len(neuron_only_before))],
                ["multi neuron after", str(len(neuron_only_after))],
                ["multi neuron difference", str(len(neuron_only_after)-len(neuron_only_before))],
                ["number of neurons in multi neuron IDs before", str(neuron_only_before.values.sum())],
                ["number of neurons in multi neuron IDs after", str(neuron_only_after.values.sum())],
                ]

        update = (
            "```\n"
            + "Update as of: " + str(datetime.utcnow())
            + "```"
            "\n"
            "```\n"
            + tabulate(table_1, headers='firstrow',  tablefmt='fancy_grid')
            + "```"
            "\n"
            "```\n"
            + tabulate(table_2, headers='firstrow',  tablefmt='fancy_grid')
            + "```"
        )

        logger.info(f"Sent update < {update} > to {user_id}")

        say(text=update, channel=channel)

    if re.search("(graph|chart|plot|figure|draw|Graph|Chart|Plot|Figure|Draw)", message):
        update_data()
        plot_multi_neuron_counts(unique_before, counts_before, np.array(unique_after_match), np.array(counts_after_match),'seg_id_multi_soma_distr_all.png', now_timestamp) 
    
        update = app.client.files_upload(file="seg_id_multi_soma_distr_all.png" , channels=channel)
        logger.info(f"Sent update seg_id_multi_soma_distr_all.png to {user_id} ")

        say(text=update, channel=channel)

    if re.search("(Extension|extension|Ext|ext)", message):
        ext_data = ext_update()

        table_1 = [["Description", "Value"],
             ["Number of extensions (merges) made: ", str(ext_data["merge_num"])],
             ["Total synapses reassigned :", str(ext_data["total_synapse_num"])],
             ]
             
        ext_update_table = (
            "```\n"
            + "Update as of: " + str(datetime.utcnow())
            + "```"
            "\n"
            "```\n"
            + tabulate(table_1, headers='firstrow',  tablefmt='fancy_grid')
            + "```"
        )

        logger.info(f"Sent update on extension analysis to {user_id} ")

        say(text=ext_update_table, channel=channel)

########################### SCHEDULUED MESSAGES ################################################################

def send_scheduled_update():
    update_data()
    table_3 = [["Description", "Value"],
        ["single soma before", str(len(single_soma_before))],
        ["single soma after", str(len(single_soma_after))],
        ["single soma difference", str(len(single_soma_after) - len(single_soma_before))],
        ["multi soma before", str(len(multi_soma_before))],
        ["multi soma after", str(len(multi_soma_after))],
        ["multi soma difference", str(len(multi_soma_after) - len(multi_soma_before))],
        ]

    table_4 = [["Description", "Value"],
        ["completely single neuron before", str(len(single_neuron_df_before.pt_root_id.unique()))],
        ["completely single neuron after", str(len(single_neuron_df_after.pt_root_id.unique()))],
        ["completely single neuron difference", str(len(single_neuron_df_after.pt_root_id.unique()) - len(single_neuron_df_before.pt_root_id.unique()))],
        ["one neuron + other cells before", str(len(one_neuron_multi_soma_before))],
        ["one neuron + other cells after", str(len(one_neuron_multi_soma_after))],
        ["one neuron + other cells difference", str(len(one_neuron_multi_soma_after) - len(one_neuron_multi_soma_before))],
        ["multi neuron before", str(len(neuron_only_before))],
        ["multi neuron after", str(len(neuron_only_after))],
        ["multi neuron difference", str(len(neuron_only_after)-len(neuron_only_before))],
        ["number of neurons in multi neuron IDs before", str(neuron_only_before.values.sum())],
        ["number of neurons in multi neuron IDs after", str(neuron_only_after.values.sum())],
        ]

    scheduled_update = (
        "```\n"
        + "Daily Update - " + str(datetime.utcnow())
        + "```"
        "\n"
        "```\n"
        + tabulate(table_3, headers='firstrow',  tablefmt='fancy_grid')
        + "```"
        "\n"
        "```\n"
        + tabulate(table_4, headers='firstrow',  tablefmt='fancy_grid')
        + "```"
    )

    result = app.client.chat_postMessage(channel = "C03NRFB19D3", text = scheduled_update)
    
    logger.info(result)
    

########################### CLOSING LINES #######################################################################

def main():
    handler = SocketModeHandler(app, SLACK_APP_TOKEN)
    handler.start()


if __name__ == "__main__":
    logging.basicConfig(format='%(levelname)s:%(message)s',
                        level=logging.DEBUG)
    main()

