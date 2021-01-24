from datetime import date
from io import StringIO

from seleniumwire import webdriver
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import pandas as pd
import yaml


class MoneyPuck:
    """A tiny program that uses Selenium Wire to capture MoneyPuck data.

    Since a lot of data can already be downloaded from moneypuck.com/data.htm, this program only fills in the gaps of what is available on that page.

    This was originally conceived as scraper of win probabilities in order to find value in-play moneyline bets.

    As stated on the download page, please clearly credit MoneyPuck.com in all cases where you are showing anything using their data as an input.
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

    def _gen_iso(self, iso_date=None):
        if iso_date is None:
            return date.today().isoformat()
        else:
            return iso_date

    def _find_request(self, regex, url=None):
        """
        Find files matching search term that were requested by the browser.

        Raises:
            error if url bad *
        """
        # self._gen_driver()
        if url is not None:
            del self.driver.requests
            self.driver.get(url)

        return self.driver.wait_for_request(regex)

    def _gen_dataframe(self, byte_str):
        csv_str = byte_str.decode("utf-8")
        return pd.read_csv(StringIO(csv_str))

    def _go_to_date(self, iso_date=None):
        iso_date = self._gen_iso(iso_date)
        self.driver.get(f"{self.base_url}/index.html?date={iso_date}")

    def _go_to_game(self, home, away, iso_date=None):
        """Go to game indicated by home, away, and iso_date.

        Raises:
            some error if not clickable
            some other error if 404 *
            error if iso date not correct *
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

    def _game_data(self, home, away, iso_date, csv_fn):
        """
        Raises:
            IndexError: If game_url is not correctly formed.
        """
        self._go_to_game(home, away, iso_date)

        game_id = self.driver.current_url.split("=").pop()
        f_name = csv_fn(game_id)

        match = self._find_request(f_name)
        return self._gen_dataframe(match.response.body)

    def _data(self, regex, url):
        match = self._find_request(regex, url)
        return self._gen_dataframe(match.response.body)

    def _gen_stats_regex(self, game_id):
        return f"moneypuck.com/moneypuck/playerData/games/.*/{game_id}.csv"

    def _gen_events_regex(self, game_id):
        return f"moneypuck.com/moneypuck/gameData/.*/{game_id}.csv"

    def win_probs(self, iso_date=None):
        """Get all win probabilities for a given day."""

        def _process_percent(el):
            chance = el.find_element_by_tag_name("h2").text
            return float(chance.strip("%")) / 100

        def _process_logo(el):
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

        # table_rows = self.driver.find_elements_by_css_selector(
        #     "div#includedContent tbody > tr"
        # )
        for row in table_rows:
            els = row.find_elements_by_tag_name("td")
            away_prob = _process_percent(els[0])
            away_name = _process_logo(els[1])
            home_prob = _process_percent(els[4])
            home_name = _process_logo(els[3])

            wp.append({away_name: away_prob, home_name: home_prob})
        return wp

    def game(self, home, away, iso_date=None):
        """Get both individual stats and events for a game."""
        return {
            "stats": self._game_data(home, away, iso_date, self._gen_stats_regex),
            "events": self._game_data(home, away, iso_date, self._gen_events_regex),
        }

    def game_stats(self, home, away, iso_date=None):
        """Get a game's individual stats.

        Game must be either completed or in play.

        Captured .csv file is ....

        Returns:
            Dict: Dictionary containing ....

        Raises:
            ValueError: If generated game URL is invalid.
        """
        return self._game_data(home, away, iso_date, self._gen_stats_regex)

    def game_events(self, home, away, iso_date=None):
        """Get a game's events."""
        return self._game_data(home, away, iso_date, self._gen_events_regex)

    def power_rankings(self):
        """Get MoneyPuck's current power rankings.

        Returns:
            pd.DataFrame: The power rankings.
        """
        return self._data(
            "moneypuck.com/moneypuck/powerRankings/rankings.csv",
            "http://moneypuck.com/power.htm",
        )

    def playoff_odds(self):
        """Get MoneyPuck's current playoff odds for each team.

        Returns:
            pd.DataFrame: The playoff odds for each team.
        """
        return self._data(
            "moneypuck.com/moneypuck/simulations/simulations_recent.csv",
            "http://moneypuck.com/predictions.htm",
        )

    def season_skaters(self):
        pass

    def season_goalies(self):
        pass

    def season_lines(self):
        pass

    def season_teams(self):
        pass
