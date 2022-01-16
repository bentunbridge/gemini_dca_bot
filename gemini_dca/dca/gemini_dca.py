import os
from typing import List, Optional, Dict, Any
import configparser
import numpy as np
import pandas as pd
import requests
import json
import base64
import hmac
import hashlib
import datetime, time
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from mplfinance.original_flavor import candlestick_ohlc

from utils import utils
import logging

logger = logging.getLogger("DCA")


class GeminiClient:
    def __init__(self,
                 config_file: str,
                 mode: str = "production",
                 offset: int = 1):
        config = configparser.ConfigParser()
        config.sections()
        config.read(config_file)
        self.mode = mode

        self.config = config[self.mode]
        self.offset = offset

        self._public_key = self.config.get("API_KEY")
        self._private_key = self.config.get("SECRET_KEY").encode()
        self.puplic_url = 'https://api.gemini.com'
        if self.mode == "production":
            self._base_url = 'https://api.gemini.com'
        else:
            self._base_url = 'https://api.sandbox.gemini.com'

        # self._refresh()

    def _refresh(self):
        balance = self._get_balances()
        if len(balance) >= 1:
            self.balances = balance
        else:
            logger.error(f"Failed to get Balances")

    @staticmethod
    def _get_time(format: Optional[str] = None):
        time_now = datetime.datetime.now()
        if format:
            time_now = time_now.strftime(format)
        return time_now

    def _make_nonce(self):
        time_now = self._get_time()
        payload_nonce = str(int(time.mktime(time_now.timetuple()) * self.offset))
        time.sleep(2)
        return payload_nonce

    def get_symbols(self):
        #  Get Symbols
        response = requests.get(self.puplic_url + "/v1/symbols")
        symbols = response.json()
        return symbols

    def get_market_details(self, symbol: str):
        #  Get BTCUSD data
        response = requests.get(self.puplic_url + f"/v1/symbols/details/{symbol.lower()}")
        market_details = response.json()
        return market_details

    def get_ticker(self, symbol: str):
        #  Get ticker - Combine version 1 and 2 of the ticket
        response = requests.get(self.puplic_url + f"/v1/pubticker/{symbol.lower()}")
        market_data_v1 = response.json()
        response = requests.get(self.puplic_url + f"/v2/ticker/{symbol.lower()}")
        market_data_v2 = response.json()
        market_data = {**market_data_v1, **market_data_v2}
        return market_data

    def _price_stats(self, symbol: str):
        response = requests.get(self.puplic_url + "/v1/pricefeed")
        price_changes = response.json()
        price_change = next(x for x in price_changes if x.get("pair").lower() == symbol.lower())
        return price_change

    ###########################################################

    def _send_payload(self,
                      payload: Dict[str, Any],
                      url: str) -> Dict[str, Any]:
        encoded_payload = json.dumps(payload).encode()
        b64 = base64.b64encode(encoded_payload)
        signature = hmac.new(self._private_key, b64, hashlib.sha384).hexdigest()

        request_headers = {'Content-Type': "text/plain",
                           'Content-Length': "0",
                           'X-GEMINI-APIKEY': self._public_key,
                           'X-GEMINI-PAYLOAD': b64,
                           'X-GEMINI-SIGNATURE': signature,
                           'Cache-Control': "no-cache"}

        response = requests.post(url,
                                 data=None,
                                 headers=request_headers)
        time.sleep(1)
        response_json = response.json()

        return response_json

    def _get_balances(self):
        endpoint = "/v1/balances"
        url = self._base_url + endpoint
        #  active orders
        payload = {"nonce": self._make_nonce(),
                   "request": endpoint}
        balances = self._send_payload(payload, url)

        return balances

    def get_balance(self,
                    currency: str):
        attempts = 0
        balance = 0
        while attempts < 6:
            try:
                balances = self._get_balances()
                balance = next(x for x in balances if x.get("currency").lower() == currency.lower())["available"]
                break
            except Exception as error:
                attempts += 1
                time.sleep(3)
                logger.info(f"Attempt {attempts}: Get Balances failed. Error: {error}")
                logger.info(f"Balances: {balances}")

        return float(balance)

    def _get_active_orders(self):
        endpoint = "/v1/orders"
        url = self._base_url + endpoint

        #  active orders
        payload = {"nonce": self._make_nonce(),
                   "request": endpoint
                   }

        active_orders = self._send_payload(payload, url)

        return active_orders

    def get_active_order(self,
                         client_order_id: str,
                         error_log: bool = True) -> Dict[str, Any]:
        active_orders = self._get_active_orders()
        try:
            active_order = next(x for x in active_orders if x.get("client_order_id") == client_order_id)
        except Exception as error:
            active_order = {}
            if error_log:
                logger.error(f"No active Orders available: {error} - {active_order}")
        return active_order

    def _get_past_trades(self,
                         product: str) -> Dict[str, Any]:
        endpoint = "/v1/mytrades"
        url = self._base_url + endpoint

        #  active orders
        payload = {"nonce": self._make_nonce(),
                   "request": endpoint,
                   "symbol": product.lower()
                   }

        trade_orders = self._send_payload(payload, url)
        return trade_orders

    def get_past_trade(self,
                       client_order_id: str,
                       product: str,
                       error_log: bool = True) -> Dict[str, Any]:
        trade_orders = self._get_past_trades(product)
        try:
            trade_order = next(x for x in trade_orders if x.get("client_order_id") == client_order_id)
        except Exception as error:
            trade_order = {}
            if error_log:
                logger.error(f"No Trades Orders available: {error} - {trade_order}")
        return trade_order

    def get_order_status(self,
                         client_order_id: str,
                         include_trades: bool = True) -> Dict[str, Any]:
        endpoint = "/v1/order/status"
        url = self._base_url + endpoint
        order_status = {}

        try:
            payload = {"request": endpoint,
                       "nonce": self._make_nonce(),
                       "client_order_id": client_order_id,
                       "include_trades": include_trades
                       }
            order_status = self._send_payload(payload, url)
        except Exception as error:
            logger.error(f"No Order Status available: {error} - {order_status}")

        return order_status

    ###############################

    def cancel_order(self,
                     order_id: str) -> Dict[str, Any]:
        endpoint = "/v1/order/cancel"
        url = self._base_url + endpoint
        cancel_status = {}

        try:
            payload = {"request": endpoint,
                       "nonce": self._make_nonce(),
                       "order_id": order_id
                       }
            cancel_status = self._send_payload(payload, url)
            time.sleep(2)
        except Exception as error:
            logger.error(f"Cancel Failed: {error} - {cancel_status}")
        return cancel_status

    def create_market_order(self,
                            amount: float,
                            product: str = "btcgbp",
                            tag: str = "") -> Dict[str, Any]:
        """
        The API doesn't directly support market orders because they provide you with no price protection.
        Instead, use the “immediate-or-cancel” order execution option, coupled with an aggressive limit price
        (i.e. very high for a buy order or very low for a sell order), to achieve the same result.
        """
        logger.info(f"Buying {amount} {product} ...")

        endpoint = "/v1/order/new"
        url = self._base_url + endpoint

        # Times upper cap to current candle y 2 to create and aggressive limit price
        aggressive_factor = 2
        aggressive_limit_price = float(self.get_ticker(product)["bid"]) * aggressive_factor

        client_order_id = f'market_buy_{tag}_{self._get_time(format="%Y-%m-%d:%H:%M:%S")}'
        logger.info(f"Setting up Market Order: {client_order_id}")

        crypto_amount = (amount / aggressive_limit_price) * aggressive_factor
        logger.info(f"Requested Crypto Amount: {crypto_amount} at price: {aggressive_limit_price}")

        # Maker
        # Use immediate-or-cancel and set the price to be very large
        payload = {
            "request": endpoint,
            "nonce": self._make_nonce(),
            "client_order_id": client_order_id,
            "symbol": product.lower(),
            "amount": f"{np.around(crypto_amount, 6):.6f}",
            "price": f"{np.around(aggressive_limit_price, 2):.2f}",
            "side": "buy",
            "type": "exchange limit",
            "options": ["immediate-or-cancel"]
        }

        market_order_result = self._send_payload(payload, url)

        logger.debug(f"  order_result: {market_order_result}")

        try:
            while market_order_result["is_live"]:
                time.sleep(5)
                market_order_result = self.get_active_order(client_order_id=client_order_id)
                logger.debug(f"  order_result: {market_order_result}")
        except Exception as error:  # pylint: disable=broad-except
            logger.error(
                f"Buy {product} failed, error: {error}; order_result: {market_order_result}"
            )
        time.sleep(5)
        return market_order_result

    def create_limit_order(self,
                           amount: float,
                           price: float,
                           product: str = "btcgbp",
                           tag: str = "") -> Dict[str, Any]:
        """
        """
        logger.info(f"Buying {amount} {product} ...")

        endpoint = "/v1/order/new"
        url = self._base_url + endpoint

        client_order_id = f'limit_buy_{tag}_{self._get_time(format="%Y-%m-%d:%H:%M:%S")}'
        logger.info(f"Setting up Limit Order: {client_order_id}")

        crypto_amount = (amount / price)
        logger.info(f"Requested Crypto Amount: {crypto_amount} at price: {price}")

        # Limit
        payload = {
            "request": endpoint,
            "nonce": self._make_nonce(),
            "client_order_id": client_order_id,
            "symbol": product.lower(),
            "amount": f"{np.around(crypto_amount, 6):.6f}",
            "price": f"{np.around(price, 2):.2f}",
            "side": "buy",
            "type": "exchange limit"
        }

        limit_order_result = self._send_payload(payload, url)

        logger.debug(f"  order_result: {limit_order_result}")

        return limit_order_result

    def set_limit_price(self,
                        product: str,
                        factor: float = 0.1,
                        granuality: str = "1m") -> float:

        recent_data = self._get_candle_data(product=product, granuality=granuality)

        price_stats = self._price_stats(symbol=product)

        recent_high = recent_data.high.max()
        recent_low = recent_data.low.min()

        recent_range = recent_high - recent_low

        current_price = float(price_stats["price"])
        # ptc_change = float(price_stats["percentChange24h"])

        set_price = current_price - (factor * recent_range)
        if set_price < 0.:
            while set_price < 0.:
                factor = factor * 0.9
                set_price = current_price - ((factor) * recent_range)

        return set_price

    def cancel_and_find_new_factor(self,
                                   factor: float,
                                   gap_factor: float = 3.0,
                                   last_record: Optional[Dict[str, Any]] = None
                                   ) -> Dict[str, Any]:
        """
        Cancel Order If still live.
        Return next factor for limit order
        If not still live set a new order at a very low level.
        if the previous run was the last stage - cancel order. Set market buy to True
            then return first factor for limit order.
        """
        trade_info = {}
        last_id = last_record.get("client_order_id")
        hash_order_filled = last_record.get("filled")
        prev_max = last_record.get("is_max")
        if last_id and (last_id != "None"):
            #  Id Last ID Exists check for status
            last_order = next(x for x in self.get_order_status(last_id) if x.get("client_order_id") == last_id)
            order_id = last_order["order_id"]
            order_is_live = last_order["is_live"]
            order_trades = last_order["trades"]
            logger.info(f"{last_id}: Order {order_id} is live: {order_is_live}")
            if (order_is_live or last_order["is_cancelled"]) and (not hash_order_filled or prev_max):
                # If Order is still live, cancel and set and set new limit price
                # Cancel Previous Order
                cancel_status = self.cancel_order(last_order["order_id"])
                time.sleep(2)
                order_is_cancel = cancel_status['is_cancelled']
                logger.info(f"Order Cancelled: {order_is_cancel}")
                if order_is_cancel:
                    # If order is cancelled set new limit price
                    trade_info["factor"] = factor
                    if (not hash_order_filled and prev_max):
                        trade_info["time_for_market_order"] = True
                        logger.info("Time for Market Order")
                else:
                    logger.error(f"Order {order_id} unable to be cancelled")
            elif order_is_live and hash_order_filled:
                trade_info["continued_gap_order"] = last_order
                logger.info(f"Gap Order {order_id} is still live, no need to replace.")
            elif (not order_is_live) and ((type(order_trades) is list) and (len(order_trades) >= 1)):
                # Order is no longer live and trades have occurred.
                # Most likely this has been filled.
                last_order["time_filled"] = np.max([int(trades.get("timestamp")) for trades in last_order["trades"]] +
                                                   [int(last_order.get("timestamp"))])
                trade_info["last_limit_order"] = last_order

                trade_info["factor"] = gap_factor
            elif last_order["is_cancelled"]:
                logger.error(f"Order {order_id} Was Cancelled. \nSee log:\n\n{last_order}")
            else:
                logger.error(f"Order {order_id} Unknown Status \nSee log:\n\n{last_order}")
        else:
            trade_info["factor"] = factor
        return trade_info

    def trigger_market_order(self,
                             amount: float,
                             market: str,
                             trade_info: Dict[str, Any],
                             limit_tag: str = "") -> Dict[str, Any]:
        """
        This function takes the trade setup infor and if applicable sets up a market order.

        :param amount:
        :param market:
        :param trade_info:
        :return:
        """
        if trade_info.get("time_for_market_order"):
            market_order = self.create_market_order(amount, product=market, tag=limit_tag)
            trade_info["market_order"] = market_order
            logger.info(f"""
            Market Order Setup:
            Amount: {amount}
            Executed Price: {market_order["executed_amount"]}
            """)
        return trade_info

    def trigger_limit_order(self,
                            amount: float,
                            market: str,
                            trade_info: Dict[str, Any],
                            limit_tag: str = "limit_order",
                            stage_granuality: str = "1m") -> Dict[str, Any]:
        """
        This function sets up a limit order using the factor indicated in the trade_info dict

        :param amount:
        :param market:
        :param trade_info:
        :param stage_granuality:
        :return:
        """

        if trade_info.get("factor"):
            # Get New Limit Price
            limit_price = self.set_limit_price(market,
                                               factor=trade_info.get("factor"),
                                               granuality=stage_granuality)

            current_price = self._price_stats(symbol=market)["price"]
            trade_info["factor_used"] = trade_info.get("factor")
            trade_info["current_price"] = current_price
            trade_info["limit_price"] = limit_price
            logger.info(f"""
            Limit Order Setup:
            Factor Used: {trade_info.get("factor")}
            Current Price: {current_price}
            Limit Price: {limit_price}
            """)

            limit_order = self.create_limit_order(amount=amount,
                                                  price=limit_price,
                                                  product=market,
                                                  tag=limit_tag)
            if limit_order.get("result") != "error":
                trade_info["limit_order"] = limit_order
                trade_info["new_limit_setup"] = True
                logger.info(f"""
                Limit Order Setup:
                Amount: {amount}
                """)
            else:
                logger.error(f"""
                Limit Order Failed: \nSee Log: \n\n{limit_order}
                """)

        else:
            trade_info["new_limit_setup"] = False
            logger.info(f"""
            No Limit Order Needed
            """)

        return trade_info

    ###############################

    def plot_purchase(self,
                      filename: str,
                      product: str,
                      path: str = "./",
                      record: Dict[str, Any] = None) -> List[str]:
        """
        # 1m: 1 minute
        # 5m: 5 minutes
        # 15m: 15 minutes
        # 30m: 30 minutes
        # 1hr: 1 hour
        # 6hr: 6 hours
        # 1day: 1 day
        :param filename:
        :param product:
        :param path:
        :param market_rate:
        :return:
        """
        utils.make_new_dir(path)
        #  candles
        #  Always use api.gemini.com (not sandbox) for plot
        rates_1_df = self._get_candle_data(product, granuality="1m")
        rates_2_df = self._get_candle_data(product, granuality="15m")

        try:
            fig1 = self.build_candle_plot(rates_1_df,
                                          title="1 Minute Intervals",
                                          record=record,
                                          time_col="time")
            fig2 = self.build_candle_plot(rates_2_df,
                                          title="15 Minute Intervals",
                                          record=record,
                                          time_col="time")

            # Save File 1
            png_path1 = os.path.join(path, f"{filename}_1min.png")
            fig1.savefig(png_path1)
            plt.close(fig1)
            # Save File 2
            png_path2 = os.path.join(path, f"{filename}_15min.png")
            fig2.savefig(png_path2)
            plt.close(fig2)
            png_paths = [png_path1, png_path2]

            return png_paths

        except Exception as error:
            logger.error(
                f"Plot failed, error: {error}"
            )
            return None

    @staticmethod
    def printOrderResult(order_result: Dict[str, Any]) -> str:
        cost = round(
            float(order_result["executed_amount"]) / float(order_result["Price"]), 2
        )
        price = round(float(order_result["price"]), 2)
        datetime_obj = datetime.datetime.utcfromtimestamp(order_result['timestamp'])
        date_string = datetime_obj.strftime('%Y-%m-%d')
        time_string = datetime_obj.strftime('%H:%M:%S')
        print_string = f"""
          Cost: \t{cost}
          Original Amount: \t{order_result['original_amount']}
          Executed Amount: \t{order_result['executed_amount']}
          Remaining Amount: \t{order_result['remaining_amount']}
          Price: \t{price}
          Fee: \t{order_result['fill_fees']}
          Date: \t{date_string}
          Time: \t{time_string}

        """
        logger.info(f"{print_string}")
        return print_string

    @staticmethod
    def _get_candle_data(product: str, granuality: str = "1m") -> pd.DataFrame:
        response = requests.get(f"https://api.gemini.com/v2/candles/{product}/{granuality}")
        candle_data = response.json()
        headers = ["time_ms", "open", "high", "low", "close", "volume"]
        rates_df = pd.DataFrame(candle_data, columns=headers)
        rates_df["time"] = rates_df["time_ms"] / 1000.
        return rates_df

    @staticmethod
    def build_candle_plot(df: pd.DataFrame,
                          title: str = "",
                          record: Optional[Dict[str, Any]] = None,
                          time_col: str = "time"):
        """

        :param df:
        :param title:
        :param market_rate:
        :param time_col:
        :return:
        """
        df["datetime"] = df[time_col].map(lambda x: datetime.datetime.utcfromtimestamp(int(x)))
        plt.style.use('seaborn')

        df['mdate'] = [mdates.date2num(d) for d in df['datetime']]

        ohlc = df[['mdate', 'open', 'high', 'low', 'close']]

        fig, ax = plt.subplots(figsize=(10, 5))
        candlestick_ohlc(ax, ohlc.values, width=0.001, colorup='g', colordown='r')

        xmin, xmax = ax.get_xlim()
        ymin, ymax = ax.get_ylim()

        if type(record) is pd.DataFrame:
            title = f"{title}: Limit Filled = {record.is_max.max()}"
            record.loc[:, "datetime"] = record.loc[:, time_col].map(
                lambda x: datetime.datetime.utcfromtimestamp(int(x)))
            record['mdate'] = [mdates.date2num(d) for d in record['datetime']]
            record = record.astype({"limit_price": float}).sort_values("datetime", ascending=True)
            record_last = pd.DataFrame({"datetime": [df.datetime.max()],
                                        "time": [df.time.max()],
                                        "mdate": [df.mdate.max()],
                                        "limit_price": [record.iloc[-1].limit_price]})
            print("Test: Pre-concat run")
            limit_record = pd.concat([record[(record.type == "limit")], record_last])
            print("Test: Post-concat run")
            print(f"Test: record dtypes = {record.dtypes}")
            if len(limit_record) > 0:
                ax.step(limit_record["mdate"], limit_record["limit_price"], where='post',
                        ls="--", lw=2., c="b", zorder=1)
            limit_purchase_record = record[(record.type == "limit_buy")]
            market_purchase_record = record[(record.type == "market_buy")]
            print("Test: Pre-axis lines")
            for (colour, buy_rec) in {"purple": limit_purchase_record,
                                      "red": market_purchase_record}.items():
                if len(buy_rec) > 0:
                    buy_rec.plot(kind="scatter",
                                 x="mdate",
                                 y="limit_price",
                                 marker="*", s=300, c=colour,
                                 zorder=3,
                                 ax=ax)
                    for index, row in buy_rec.iterrows():
                        plt.axvline(x=row.mdate, color=colour, linestyle=':', lw=1., zorder=2)
                        plt.axhline(y=float(row.limit_price), color=colour, linestyle=':', lw=1., zorder=2)

        ax.set_title(title)
        ax.set_xlabel("DateTime")
        ax.set_ylabel("Price GBP")
        ax.set_xlim(xmin, xmax)
        ax.set_ylim(ymin, ymax)
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%d-%m-%y %H:%M'))
        ax.xaxis.set_major_locator(plt.MaxNLocator(16))
        plt.xticks(rotation=60)

        fig.autofmt_xdate()
        fig.tight_layout()

        return fig
