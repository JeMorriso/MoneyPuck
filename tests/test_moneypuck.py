from seleniumwire import webdriver
from selenium.common.exceptions import NoSuchElementException, TimeoutException
import pytest
import pandas as pd

from moneypuck.moneypuck import MoneyPuck


class TestMoneyPuck(MoneyPuck):
    def __init__(self):
        super().__init__()

        # sw_opts = {"disable_encoding": True}
        # self.driver = webdriver.Chrome(seleniumwire_options=sw_opts)
        self.driver = webdriver.Chrome()


@pytest.mark.parametrize(
    "home, away, iso_date",
    [
        ("cbj", "tbl", "2021-01-23"),
        ("tbl", "cbj", "2021-01-23"),
        ("det", "chi", "2021-01-22"),
    ],
)
def test_go_to_game(home, away, iso_date):
    with TestMoneyPuck() as mp:
        mp._go_to_game(home, away, iso_date)


def test_game_doesnt_exist():
    with pytest.raises(NoSuchElementException), TestMoneyPuck() as mp:
        mp._go_to_game("cbj", "tor", "2021-01-23")


def test_game_not_ready():
    # Must have future game to work
    with pytest.raises(TimeoutException), TestMoneyPuck() as mp:
        mp._go_to_game("nyi", "njd", "2021-01-24")


def test_game_stats():
    with TestMoneyPuck() as mp:
        df = mp.game_stats("mtl", "van", "2021-01-23")
        assert isinstance(df, pd.DataFrame) and len(df) > 0


def test_game_events():
    with TestMoneyPuck() as mp:
        df = mp.game_events("mtl", "van", "2021-01-23")
        assert isinstance(df, pd.DataFrame) and len(df) > 0


def test_game_current_win_prob():
    with TestMoneyPuck() as mp:
        d = mp.game_current_win_prob("van", "mtl", "2021-01-23")
        assert isinstance(d, dict) and len(d) > 0


def test_power_rankings():
    with TestMoneyPuck() as mp:
        df = mp.power_rankings()
        assert isinstance(df, pd.DataFrame) and len(df) > 0


def test_playoff_odds():
    with TestMoneyPuck() as mp:
        df = mp.playoff_odds()
        assert isinstance(df, pd.DataFrame) and len(df) > 0


@pytest.mark.parametrize(
    "iso_date", [("2021-01-21"), ("2021-01-22"), ("2021-01-23"), ("2021-01-24")]
)
def test_win_probs(iso_date):
    with TestMoneyPuck() as mp:
        l_ = mp.win_probs(iso_date)
        assert isinstance(l_, list) and len(l_) > 0
