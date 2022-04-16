#!/home/pi/miniconda3/envs/dca/bin/python
# coding: utf-8
import matplotlib

matplotlib.use('Agg')

import datetime
import sys
import os
import configparser
import pandas as pd

from utils import send_email
from dca import gemini_dca
from utils import utils

import logging

logger = logging.getLogger("Exchange DCA - Gemini")
logging.basicConfig(level=logging.INFO)

#################
# Inputs #
print(sys.argv)
config_file = sys.argv[1]
run_mode = sys.argv[2]

# Read in Config File

# Config #
config = configparser.ConfigParser()
config.sections()
config.read(config_file)

# Read in input parameters

base_dir = config["setup"].get("base_dir")
amount = config["setup"].getfloat("amount")
currency = config["setup"].get("currency")
buy_currency = config["setup"].get("buy_currency")
market = config["setup"].get("market").lower()
send_to_email = config["email"].get("DESTINATION", "")
offset = config["setup"].get("base_dir")

tag = config["setup"].get("tag")

all_stages = utils.list2num([x[0] for x in config.items("stages")])
max_stage = max(all_stages)
gap_factor = config["stages"].getfloat("gap_factor")

record_csv = config["record"].get("record_csv")
record_path = os.path.join(base_dir, record_csv)

credentials_file = os.path.join(base_dir, config["setup"].get("credentials_file"))

# Input Parameters Print

##################
# Set up Logger #
time_now = datetime.datetime.now()
log_path = os.path.join(base_dir, "log", f"log_{time_now.strftime('%Y-%m-%d')}")
utils.make_new_dir(log_path, unmask=True)

log_file = os.path.join(log_path, f"log_{buy_currency.lower()}_{time_now.strftime('%Y-%m-%d:%H:%M:%S')}.log")
output_file_handler = logging.FileHandler(log_file)
stdout_handler = logging.StreamHandler(sys.stdout)
logger.addHandler(output_file_handler)
logger.addHandler(stdout_handler)
logger.info(f"------------- Start {time_now.strftime('%Y-%m-%d %H:%M:%S')} -------------")

logger.info(f"""
base_dir: {base_dir}
amount: {amount}
currency: {currency}
buy_currency: {buy_currency}
market: {market}
send_to_email: {send_to_email}

tag: {tag}

all_stages: {all_stages}
max_stage: {max_stage}
gap_factor: {gap_factor}

record_path: {record_path}
""")

# Read in records

if os.path.exists(record_path):
    record = pd.read_csv(record_path)
    last_record = record[record.tag == tag].sort_values(["time_run", "time", "stage"],
                                                        ascending=[False, False, False]
                                                        ).iloc[0].to_dict()
    stage = (last_record["stage"]) % (max_stage) + 1
    if stage > 1:
        str_hash = last_record.get("hash")
        hash_set_filled = last_record["filled"]
    else:
        str_hash = hex(int(time_now.timestamp()))
        hash_set_filled = False
else:
    stage = 1
    str_hash = hex(int(time_now.timestamp()))
    hash_set_filled = False
    last_record = {}

factor = config["stages"].getfloat(str(int(stage)))
stage_granuality = config["stages"].get("granuality")

limit_tag = f"{tag}_stage{stage}_{str_hash}"

is_max = (stage == max_stage)

logger.info(f"""
Stage: {stage}
Factor: {factor}
Stage Granularity: {stage_granuality}
Limit Tag: {limit_tag}
Order Sets Filled: {hash_set_filled}
str_hash: {str_hash}
is_max: {is_max}
""")

# Outputs #
if send_to_email is not "":
    plot_names = f"analysis_plots_{time_now.strftime('%Y-%m-%d:%H:%M:%S')}"
    plot_path = os.path.join(base_dir, "plots", f"plot_{time_now.strftime('%Y-%m-%d')}")
    utils.make_new_dir(plot_path, unmask=True)

# Gemini Class

# Initiate Gemini Class #
gemini_run = gemini_dca.GeminiClient(config_file=credentials_file, mode=run_mode, offset=offset)

# Read In Balance

# Print Start Balance #
start_balance = gemini_run.get_balance(currency=currency)
start_balance_str = f"Start Balance: {start_balance} {currency}"
logger.info(start_balance_str)

if start_balance < amount:
    if send_to_email is not "":
        error_subject = f"{time_now.strftime('%Y-%m-%d')}: Buy Crypto - {buy_currency} - {run_mode}"
        error_message = f"Error: Start Balance too low. {start_balance} < {amount}"
        logger.error(error_message)
        send_email.send_email_gmail(config, error_subject, error_message, send_to_email)
    exit()

# Print Start Buy Balance #
start_buy_balance = gemini_run.get_balance(currency=buy_currency)
start_buy_balance_str = f"Start Buy Balance: {start_buy_balance} {buy_currency}"
logger.info(start_buy_balance_str)

# Trigger Processes

#  Cancel current orders and find the appropriate factor to use
trade_progress = gemini_run.cancel_and_find_new_factor(factor=factor,
                                                       gap_factor=gap_factor,
                                                       last_record=last_record
                                                       )
# Trigger Market Order If applicable
trade_progress = gemini_run.trigger_market_order(amount,
                                                 market,
                                                 trade_progress,
                                                 limit_tag=limit_tag)
# Trigger Limit order if factor is given
trade_progress = gemini_run.trigger_limit_order(amount,
                                                market,
                                                trade_progress,
                                                limit_tag=limit_tag,
                                                stage_granuality=stage_granuality)

#  Log Trading Progress
logger.info(f"Trading Progress: \n{trade_progress}")

# Records

#  Write records to file
record_list = []
ll_dict = trade_progress.get("last_limit_order")
if ll_dict:
    hash_set_filled = True
    last_limit_suc_record = {"type": "limit_buy",
                             "client_order_id": ll_dict.get("client_order_id"),
                             "time": ll_dict.get("time_filled"),
                             "time_run": int(time_now.timestamp()),
                             "limit_price": ll_dict.get("price"),
                             "cost": round(float(ll_dict.get("executed_amount")) /
                                           float(ll_dict.get("avg_execution_price")), 6),
                             "market": ll_dict.get("symbol"),
                             "tag": tag,
                             "stage": last_record.get("stage"),
                             "filled": hash_set_filled,
                             "factor": last_record.get("factor"),
                             "hash": last_record.get("hash"),
                             "is_max": last_record.get("is_max")
                             }
    record_list.append(last_limit_suc_record)

mo_dict = trade_progress.get("market_order")
if mo_dict:
    hash_set_filled = True
    mo_dict_record = {"type": "market_buy",
                      "client_order_id": mo_dict.get("client_order_id"),
                      "time": mo_dict.get("timestamp"),
                      "time_run": int(time_now.timestamp()),
                      "limit_price": mo_dict.get("price"),
                      "cost": round(float(mo_dict.get("executed_amount")) /
                                    float(mo_dict.get("avg_execution_price")), 6),
                      "market": mo_dict.get("symbol"),
                      "tag": tag,
                      "stage": last_record.get("stage"),
                      "filled": hash_set_filled,
                      "factor": 0.,
                      "hash": last_record.get("hash"),
                      "is_max": last_record.get("is_max")
                      }
    record_list.append(mo_dict_record)

lo_dict = trade_progress.get("limit_order")
if lo_dict:
    set_limit_record = {"type": "limit",
                        "client_order_id": lo_dict.get("client_order_id"),
                        "time": lo_dict.get("timestamp"),
                        "time_run": int(time_now.timestamp()),
                        "limit_price": lo_dict.get("price"),
                        "cost": 0.,
                        "market": market,
                        "tag": tag,
                        "stage": stage,
                        "filled": hash_set_filled,
                        "factor": trade_progress.get("factor"),
                        "hash": str_hash,
                        "is_max": is_max
                        }
    record_list.append(set_limit_record)

gap_dict = trade_progress.get("continued_gap_order")
if gap_dict:
    set_limit_record = {"type": "limit",
                        "client_order_id": gap_dict.get("client_order_id"),
                        "time": gap_dict.get("timestamp"),
                        "time_run": int(time_now.timestamp()),
                        "limit_price": gap_dict.get("price"),
                        "cost": 0.,
                        "market": market,
                        "tag": tag,
                        "stage": stage,
                        "filled": hash_set_filled,
                        "factor": gap_factor,
                        "hash": str_hash,
                        "is_max": is_max
                        }
    record_list.append(set_limit_record)

if len(record_list) == 0:
    no_order_record = {"type": "None",
                       "client_order_id": "None",
                       "time": int(time_now.timestamp()),
                       "time_run": int(time_now.timestamp()),
                       "limit_price": "None",
                       "cost": 0.,
                       "market": market,
                       "tag": tag,
                       "stage": stage,
                       "filled": hash_set_filled,
                       "factor": gap_factor,
                       "hash": str_hash,
                       "is_max": is_max
                       }
    record_list.append(no_order_record)

if len(record_list) > 0:
    full_record = pd.DataFrame(record_list)
    if os.path.exists(record_path):
        full_record.to_csv(record_path, index=False, mode='a', header=False)
    else:
        utils.make_new_dir(os.path.dirname(record_path), unmask=True)
        full_record.to_csv(record_path, index=False, mode='w', header=True)
    #  Logger for full records
    logger.info(full_record.tail().to_string())

#  End Balances
# Print End Balance #
end_balance = gemini_run.get_balance(currency=currency)
end_balance_str = f"End Balance: {end_balance} {currency}"
logger.info(end_balance_str)

# Print End Buy Balance #
end_buy_balance = gemini_run.get_balance(currency=buy_currency)
end_buy_balance_str = f"End Buy Balance: {end_buy_balance} {buy_currency}"
logger.info(end_buy_balance_str)

# Send Email Test

if (stage == 1) and last_record:
    if send_to_email is not "":
        record = pd.read_csv(record_path)
        hash_record = record[record.hash == last_record.get("hash")]
        embed_plots = gemini_run.plot_purchase(filename=plot_names,
                                               path=plot_path,
                                               product=market,
                                               record=hash_record)

        # Find time Now and create Email Message #
        subject = f"{time_now.strftime('%Y-%m-%d')}: Buy Crypto - {buy_currency} - {run_mode}"
        message = f"""
        <b>Time</b>:         {time_now.strftime('%Y-%m-%d %H:%M:%S')}<br>
        <b>Exchange</b>:       Gemini<br>
        <b>Amount</b>:       {amount}<br>
        <b>Currency</b>:     {currency}<br>
        <b>Buy Currency</b>: {buy_currency}<br>
        <b>Market</b>:       {market}<br>
        <b>Run Mode</b>:     {run_mode}<br>
        <b>Trade Info</b>:     {trade_progress}<br>
        <b>Start Base Balance</b>:  {start_balance_str}<br>
        <b>Start Buy Balance</b>:   {start_buy_balance_str}<br>
        <br>
        <b>End Base Balance</b>:    {end_balance_str}<br>
        <b>End Buy Balance</b>:     {end_buy_balance_str}<br>
        <br>
        <br>
        <b>Record</b>:              {hash_record.to_html()}
        <br>
        """
        send_email.send_email_gmail_with_images(config,
                                                subject,
                                                message,
                                                send_to_email,
                                                attactments=[],
                                                embedded=embed_plots)
        logger.info(f"Running Email Test: {time_now}")
    else:
        logger.info(f"No Email Send: {time_now}")

#
logger.info(f"------------- End {time_now.strftime('%Y-%m-%d %H:%M:%S')} -------------")

##################
