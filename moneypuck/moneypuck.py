from datetime import date
from io import StringIO
from typing import Optional, Callable, List, Dict

import seleniumwire
from seleniumwire import webdriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import pandas as pd
import yaml


class MoneyPuck:
    """A small program that uses Selenium Wire to capture MoneyPuck data.

    Since a lot of data can already be downloaded from moneypuck.com/data.htm, this
    program only fills in the gaps of what is available on that page.

    This was originally conceived as scraper of win probabilities in order to find
    value in-play moneyline bets.

    As stated on the download page, please clearly credit MoneyPuck.com in all cases
    where you are showing anything using their data as an input.

    Attributes:
        base_url: Base MoneyPuck URL.
        driver: Selenium Wire WebDriver instance.
        teams: Dict with key as team abbreviation, value as full name.
        teams_inv: Inverse of teams.
    """

    def __init__(self):
        self.base_url = "http://moneypuck.com"

        opts = webdriver.ChromeOptions()
        sw_opts = {"disable_encoding": True}
        opts.add_argument("--headless")
        self.driver = webdriver.Chrome(options=opts, seleniumwire_options=sw_opts)

        with open("nhl_teams.yaml", "r") as f:
            self.teams = yaml.load(f, Loader=yaml.FullLoader)

        self.teams_inv = {v: k for k, v in self.teams.items()}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.driver.quit()

    def _gen_iso(self, iso_date: Optional[str] = None) -> str:
        """Generate an ISO date string representing today's date if parameter is None.
        Otherwise, return the parameter (which should be an ISO date string).

        Args:
            iso_date: ISO date string.

        Returns:
            ISO date string.
        """
        if iso_date is None:
            return date.today().isoformat()
        else:
            return iso_date

    def _find_request(
        self, regex: str, url: Optional[str] = None
    ) -> seleniumwire.proxy.request.Request:
        """
        Find request matching search term from list of request requested by the browser.

        Args:
            regex: Regex search term.
            url: URL to go to.

        Returns:
            The matching request.

        Raises:
            TimeOutException: If regex doesn't lead to any matches.
        """
        if url is not None:
            del self.driver.requests
            self.driver.get(url)

        return self.driver.wait_for_request(regex)

    def _gen_dataframe(self, byte_str: bytes) -> pd.DataFrame:
        """Generate a dataframe from a csv encoded as bytes.

        Args:
            byte_str: The bytes to decode.

        Returns:
            DataFrame created from decoded bytes (csv).
        """
        csv_str = byte_str.decode("utf-8")
        return pd.read_csv(StringIO(csv_str))

    def _go_to_date(self, iso_date: Optional[str] = None):
        """Go to MoneyPuck page for date.

        Args:
            iso_date: ISO date string.
        """
        iso_date = self._gen_iso(iso_date)
        self.driver.get(f"{self.base_url}/index.html?date={iso_date}")

    def _go_to_game(self, home: str, away: str, iso_date: Optional[str] = None):
        """Go to game indicated by home, away, and iso_date.

        home and away are case-insensitive, and it doesn't matter if home is actually
        away or vice versa.

        Args:
            home: 3-letter NHL abbreviation for home team.
            away: 3-letter NHL abbreviation for away team.
            iso_date: ISO date string.

        Raises:
            TimeOutException: If game is not in a clickable state (hasn't started yet).
            NoSuchElementException: If game and date combination doesn't exist.
        """
        self._go_to_date(iso_date)

        # Easiest way to find game is using a team image alt attribute.
        home = WebDriverWait(self.driver, 10).until(
            EC.element_to_be_clickable(
                (By.XPATH, f'//a/img[@alt="{self.teams[home].upper()}"]')
            )
        )
        container = home.find_element_by_xpath("./../../..")
        try:
            away = container.find_element_by_xpath(
                f'//img[@alt="{self.teams[away].upper()}"]'
            )
        except NoSuchElementException:
            # self.driver.quit()
            raise NoSuchElementException("Requested game does not exist.")

        del self.driver.requests
        home.click()

    def _game_data(
        self, home: str, away: str, iso_date: str, csv_fn: Callable
    ) -> pd.DataFrame:
        """
        Go to game page, find csv of interest, and turn it into a dataframe.

        Args:
            home: 3-letter NHL abbreviation for home team.
            away: 3-letter NHL abbreviation for away team.
            iso_date: ISO date string.
            csv_fn: The function to call to get the regex to search for a request with.

        Returns:
            The DataFrame created from the matching request's body.
        """
        self._go_to_game(home, away, iso_date)

        game_id = self.driver.current_url.split("=").pop()
        f_name = csv_fn(game_id)

        match = self._find_request(f_name)
        return self._gen_dataframe(match.response.body)

    def _data(self, regex: str, url: str) -> pd.DataFrame:
        """
        Go to url, find csv of interest, and turn it into a dataframe.

        Args:
            regex: Regex to search for request with.
            url: URL to search browser requests for.

        Returns:
            The DataFrame created from the matching request's body.
        """
        match = self._find_request(regex, url)
        return self._gen_dataframe(match.response.body)

    def _gen_stats_regex(self, game_id: int) -> str:
        """Regex string for finding a game's individual stats.

        Args:
            game_id: Game ID like found in MoneyPuck game URL.

        Returns:
            The generated regex string that will find the individual stats csv.
        """
        return f"moneypuck.com/moneypuck/playerData/games/.*/{game_id}.csv"

    def _gen_events_regex(self, game_id: int) -> str:
        """Regex string for finding a game's events and win probabilities.

        Args:
            game_id: Game ID like found in MoneyPuck game URL.

        Returns:
            The generated regex string that will find the events / win probabilities
            csv.
        """
        return f"moneypuck.com/moneypuck/gameData/.*/{game_id}.csv"

    def win_probs(self, iso_date: Optional[str] = None) -> List[Dict[str, float]]:
        """Get all win probabilities for a given day.

        Args:
            iso_date: ISO date string.

        Returns:
            List of Dict where keys are team abbreviations, and values are win
            probabilities.
        """

        def _process_percent(el: WebElement) -> float:
            """Find chance element in table row and get its probability."""
            chance = el.find_element_by_tag_name("h2").text
            return float(chance.strip("%")) / 100

        def _process_logo(el: WebElement) -> str:
            """Find logo element in table row and get its associated team."""
            return self.teams_inv[
                el.find_element_by_tag_name("img").get_attribute("alt").lower()
            ].upper()

        wp = []
        self._go_to_date(iso_date)

        table_rows = WebDriverWait(self.driver, 10).until(
            EC.presence_of_all_elements_located(
                (By.CSS_SELECTOR, "div#includedContent tbody > tr")
            )
        )
        for row in table_rows:
            els = row.find_elements_by_tag_name("td")
            away_prob = _process_percent(els[0])
            away_name = _process_logo(els[1])
            home_prob = _process_percent(els[4])
            home_name = _process_logo(els[3])

            wp.append({away_name: away_prob, home_name: home_prob})
        return wp

    def game(
        self, home: str, away: str, iso_date: Optional[str] = None
    ) -> Dict[str, pd.DataFrame]:
        """Get both individual stats and events / win probabilities for a game.

        Game must be either completed or in play.

        Returns:
            Dict containing DataFrames for individual stats and events for a game.
        """
        return {
            "stats": self._game_data(home, away, iso_date, self._gen_stats_regex),
            "events": self._game_data(home, away, iso_date, self._gen_events_regex),
        }

    def game_stats(
        self, home: str, away: str, iso_date: Optional[str] = None
    ) -> pd.DataFrame:
        """Get a game's individual stats.

        Game must be either completed or in play.

        Returns:
            DataFrame with the stats.
        """
        return self._game_data(home, away, iso_date, self._gen_stats_regex)

    def game_events(
        self, home: str, away: str, iso_date: Optional[str] = None
    ) -> pd.DataFrame:
        """Get a game's events / win probabilities.

        Game must be either completed or in play.

        Returns:
            DataFrame with the events.
        """
        return self._game_data(home, away, iso_date, self._gen_events_regex)

    def game_current_win_prob(
        self, home: str, away: str, iso_date: Optional[str] = None
    ) -> Dict[str, float]:
        """Get the current win probability for each team in a game.

        Game must be either completed or in play.

        Returns:
            Dict where keys are team abbreviations and values are current win
            probabilities.
        """
        game_df = self.game_events(home, away, iso_date)
        curr = game_df.iloc[-1]

        return {home: curr["homeWinProbability"], away: 1 - curr["homeWinProbability"]}

    def power_rankings(self) -> pd.DataFrame:
        """Get MoneyPuck's current power rankings.

        Returns:
            DataFrame of the power rankings.
        """
        return self._data(
            "moneypuck.com/moneypuck/powerRankings/rankings.csv",
            "http://moneypuck.com/power.htm",
        )

    def playoff_odds(self) -> pd.DataFrame:
        """Get MoneyPuck's current playoff odds for each team.

        Returns:
            DataFrame of the playoff odds for each team.
        """
        return self._data(
            "moneypuck.com/moneypuck/simulations/simulations_recent.csv",
            "http://moneypuck.com/predictions.htm",
        )
