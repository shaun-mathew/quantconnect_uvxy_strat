# region imports
from AlgorithmImports import *
from datetime import timedelta
from datetime import datetime
import pandas as pd

# endregion


class Strategy1vixcalls(QCAlgorithm):
    def Initialize(self):
        self.SetStartDate(2018, 10, 1)  # Set Start Date
        self.SetEndDate(2023, 5, 10)  # Set Start Date
        self.SetCash(50000)  # Set Strategy Cash
        self.vix = self.AddIndex("VIX", resolution=Resolution.Hour).Symbol
        self.uvxy = self.AddEquity("UVXY", resolution=Resolution.Hour).Symbol

        self.four_month_indicator = self.MIN(
            "VIX", period=4*30, resolution=Resolution.Daily
        )

        option: Option = self.AddOption("UVXY", Resolution.Hour)

        self.uvxy_option = option.Symbol

        option.SetFilter(
            lambda option_filter_universe: option_filter_universe.IncludeWeeklys()
            .CallsOnly()
            .Expiration(29, 200)
        )

        # Strat Options
        self.strat_option: Option | None = None
        self.holding_percent = 0.0
        self.initial_percent = 0.03
        self.last_price = float("inf")
        self.initial_price = float("inf")
        self.number_of_stacks = 0
        self.exit_profit = 0.20
        self.option_dte = 120
        self.otm_distance = 0.01
        self.option_price_threshold = 0.15
        self.price_difference_w_low = 0.2

        # .Expiration(29, 36)

    def OnData(self, data: Slice):
        if not self.four_month_indicator.IsReady:
            return

        if self.uvxy not in data.Bars:
            return

        if self.strat_option and self.strat_option.Symbol not in data.Bars and self.strat_option.Symbol not in data.QuoteBars:
            return

        if data.Time >= datetime(day=24,month=5, year=2021) and data.Time <= datetime(day=27, month=5, year=2021):
            return

        current_vix_price = data.Bars[self.vix].Price
        four_month_low = self.four_month_indicator.Current.Value
        current_uvxy_price = data.Bars[self.uvxy].Price
        if (
            current_vix_price < 20
            and abs(four_month_low - current_vix_price) <= self.price_difference_w_low * four_month_low
        ):
            self.Log(f"{data.Time}: First condition hit: vix < 20 and within 5% of 4 month low. Current Vix Price: {current_vix_price}. 4 Month Low: {four_month_low}. Current UVXY Price: {current_uvxy_price}")
            # get atm option expiring in 30 days and return its iv
            iv_30d = self.GetIV(data.OptionChains.get(self.uvxy_option))

            if iv_30d < 1:
                self.Log(f"{data.Time}: Second condition hit: 30d iv less than 1. Implied Volatility: {iv_30d}")
                self.InitializeStrategy(data)

        if self.strat_option:

            current_price = data[self.strat_option.Symbol].Ask.Close

            # self.Log(f"{data.Time}: Logging {self.strat_option.Symbol} IV and Price. Implied Volatility: {iv_30d} and Price: {current_price}")
            self.ExecuteStrategy(data)
            self.ExitStrategy(data)

    def ExecuteStrategy(self, data: Slice):
        required_purchase_price = (
            1 - self.number_of_stacks * self.option_price_threshold
        ) * self.initial_price
        # current_price = self.Portfolio[self.strat_option.Symbol].Price
        current_price = data.QuoteBars[self.strat_option.Symbol].Ask.Close
                # num_options += security.Holdings.Quantity
        

        self.Log(f"{data.Time}: Executing Strategy. Checking if option has dropped {self.number_of_stacks*self.option_price_threshold*100} from Initial Price: {self.initial_price}. Required Purchase Price: {required_purchase_price}. Current Price of {self.strat_option.Symbol}: {current_price}. Current Price of VIX: {data.Bars[self.vix].Price}")
        if current_price <= required_purchase_price and current_price > 0:
            self.Log(f"{data.Time}: Executing Strategy. Threshold reached. {self.strat_option.Symbol} has dropped {self.number_of_stacks*self.option_price_threshold*100} from Initial Price: {self.initial_price}. Required Purchase Price: {required_purchase_price}. Current Price of {self.strat_option.Symbol}: {current_price}. Current Price of VIX: {data.Bars[self.vix].Price}")
            self.Log(f"Time: {data.Time}, Required Purchase Price: {required_purchase_price}, Initial Price: {self.initial_price}, Current Price: {current_price}")
            self.holding_percent *= 2

            ask_price = data.QuoteBars[self.strat_option.Symbol].Ask.Close
            num_to_purchase = self.holding_percent*self.Portfolio.Cash//(ask_price*100) #Not quite what we want since this will buy an additional x% not set the holdings to be x% of your portfolio
            self.LimitOrder(self.strat_option.Symbol, num_to_purchase, ask_price)
            # self.SetHoldings(self.strat_option.Symbol, percentage=self.holding_percent)
            #self.SetHoldings(self.strat_option.Symbol, self.holding_percent)
            self.last_price = ask_price
            self.number_of_stacks += 1
            # self.Log(f"{data.Time}: Purchased Options. Current number of stacks: {self.number_of_stacks}")

    def ExitStrategy(self, data: Slice):
        #use data to get bid price
        # current_price = data.Bars[self.strat_option.Symbol].Ask
        current_price = self.Portfolio[self.strat_option.Symbol].Price
        required_price = self.Portfolio[self.strat_option.Symbol].AveragePrice * (
            1 + self.exit_profit
        )

        quantity = self.Portfolio[self.strat_option.Symbol].Quantity

        self.Log(f"{data.Time}: Exit Strategy. Checking if total portfolio value has increased by {1 + self.exit_profit}x of Average Price: {self.Portfolio[self.strat_option.Symbol].AveragePrice}. Current Price of {self.strat_option.Symbol}: {current_price}. Required Exit Price: {required_price}. Current Price of VIX: {data.Bars[self.vix].Price}")
        if current_price >= required_price and required_price > 0 and quantity > 0:
            self.Log(f"{data.Time}: Exit Strategy. Threshold reached. Portfolio value has increased by {1 + self.exit_profit}x of Average Price: {self.Portfolio[self.strat_option.Symbol].AveragePrice}. Current Price of {self.strat_option.Symbol}: {current_price}. Required Exit Price: {required_price}. Current Price of VIX: {data.Bars[self.vix].Price}")
            # self.LimitOrder(self.strat_option.Symbol, -1*self.Portfolio[self.strat_option.Symbol].Quantity, required_price)
            self.Liquidate()
            self.holding_percent = 0.0
            self.last_price = float("inf")
            self.initial_price = float("inf")
            self.number_of_stacks = 0
            self.strat_option = None

            # self.Log(f"{data.Time}: Liquidated Portfolio and Reset Strategy to look for next buying opportunity. Total Portfolio Cash: {self.Portfolio.Cash}")

    def InitializeStrategy(self, data: Slice):
        """
        Allocate 1% of portfolio into an out of the money spy call and store the original price in a variable. Once
        the value of that call option drops by 10% of the original call's price, double down and keep doing this. If the worth
        of the portfolio exceeds 1.2x its original amount, unwind position and restart slab strat.
        """

        if not self.strat_option:
            chain = data.OptionChains.get(self.uvxy_option)
            ideal_date = self.Time + timedelta(days=self.option_dte)
            closest_expiry = sorted(
                chain, key=lambda x: abs((x.Expiry - ideal_date).days)
            )[0].Expiry
            closest_dates_otm = filter(
                lambda x: closest_expiry == x.Expiry
                and (x.Strike - chain.Underlying.Price) > 0,
                chain,
            )
            otm_calls_sorted = sorted(closest_dates_otm, key=lambda x: x.Strike)
            # otm_call: OptionContract = otm_calls_sorted[
            #     int(self.otm_distance * len(otm_calls_sorted))
            # ]
            target_price = chain.Underlying.Price*1.2

            if len(otm_calls_sorted) > 0:
                otm_call = sorted(otm_calls_sorted, key=lambda x: abs(x.Strike - target_price))[0]
                # otm_call: OptionContract = otm_calls_sorted[3]
                self.strat_option = otm_call
                self.holding_percent = self.initial_percent
                ask_price = data.QuoteBars[otm_call.Symbol].Ask.Close
                num_to_purchase = self.holding_percent*self.Portfolio.Cash//(ask_price*100) #This is not quite what we want (i.e. the holding percent)
                self.LimitOrder(otm_call.Symbol, num_to_purchase, ask_price)
                # self.SetHoldings(self.strat_option.Symbol, percentage=self.holding_percent)
                self.last_price = self.initial_price = ask_price
                self.number_of_stacks += 1

            self.Log(f"{data.Time}: Initializing Slab Strat. Allocating {self.holding_percent*100}% of portfolio to otm call {self.strat_option.Symbol} with Strike Price {self.strat_option.Strike} and Average Price {self.initial_price}.")

            ## self.Log(f"{data.Time}: Considered Call Options.")
            # for option in otm_calls_sorted:
            ##     self.Log(f"{data.Time}: Strike: {option.Strike}, Expiry: {option.Expiry}, Price: {option.AskPrice}, OpenInterest: {option.OpenInterest} ")
            #     self.Debug(f"Time diff: {option.Expiry - data.Time}")

    def GetIV(self, chain: OptionChain):
        # future_date = datetime(2023, 12, 31, 23, 59, 59).date().d
        if chain:
            ideal_date = self.Time + timedelta(days=30)
            closest_expiry = sorted(
                chain, key=lambda x: abs((x.Expiry - ideal_date).days)
            )[0].Expiry
            closest_dates = filter(lambda x: closest_expiry == x.Expiry, chain)
            nearest_option = sorted(
                closest_dates, key=lambda x: abs((x.Strike - chain.Underlying.Price))
            )[0]
            # self.Debug(f"Nearest Option: {nearest_option.Symbol.Value}, Strike: {nearest_option.Strike}, Ask Price: {nearest_option.AskPrice}, Expiry: {nearest_option.Expiry}")
            # df = pd.DataFrame(
            #     [[x.Right, x.Strike, x.Expiry, x.AskPrice, x.BidPrice, x.ImpliedVolatility] for x in chain],
            #     index=[x.Symbol.Value for x in chain],
            #     columns=["type(call 0, put 1)", "strike", "expiry", "ask price", "bid price", "iv"],
            # )

            return nearest_option.ImpliedVolatility

        return float("inf")
