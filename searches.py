import dbm.dumb
import json
import logging
import shelve
from datetime import date, timedelta
from enum import Enum, auto
from itertools import cycle
from random import random, randint
from time import sleep
from typing import Final

import requests
from selenium.webdriver.common.by import By

from src.browser import Browser
from src.utils import CONFIG, makeRequestsSession, getProjectRoot

LOAD_DATE_KEY = "loadDate"


class RetriesStrategy(Enum):
    """
    method to use when retrying
    """

    EXPONENTIAL = auto()
    """
    an exponentially increasing `base_delay_in_seconds` between attempts
    """
    CONSTANT = auto()
    """
    the default; a constant `base_delay_in_seconds` between attempts
    """


class Searches:
    maxRetries: Final[int] = CONFIG.get("retries").get("max")
    """
    the max amount of retries to attempt
    """
    baseDelay: Final[float] = CONFIG.get("retries").get("base_delay_in_seconds")
    """
    how many seconds to delay
    """
    # retriesStrategy = Final[  # todo Figure why doesn't work with equality below
    retriesStrategy = RetriesStrategy[CONFIG.get("retries").get("strategy")]

    def __init__(self, browser: Browser):
        self.browser = browser
        self.webdriver = browser.webdriver

        dumbDbm = dbm.dumb.open((Utils.getProjectRoot() / "google_trends").__str__())
        self.googleTrendsShelf: shelve.Shelf = shelve.Shelf(dumbDbm)
        logging.debug(f"googleTrendsShelf.__dict__ = {self.googleTrendsShelf.__dict__}")
        logging.debug(f"google_trends = {list(self.googleTrendsShelf.items())}")
        loadDate: date | None = None
        if LOAD_DATE_KEY in self.googleTrendsShelf:
            loadDate = self.googleTrendsShelf[LOAD_DATE_KEY]

        if loadDate is None or loadDate < date.today():
            self.googleTrendsShelf.clear()
            self.googleTrendsShelf[LOAD_DATE_KEY] = date.today()
            trends = self.getGoogleTrends(
                browser.getRemainingSearches(desktopAndMobile=True).getTotal()
            )
            random.shuffle(trends)
            for trend in trends:
                self.googleTrendsShelf[trend] = None
            logging.debug(
                f"google_trends after load = {list(self.googleTrendsShelf.items())}"
            )

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.googleTrendsShelf.__exit__(None, None, None)

    def getGoogleTrends(self, wordsCount: int) -> list[str]:
        # Function to retrieve Google Trends search terms
        searchTerms: list[str] = []
        i = 0
        session = Utils.makeRequestsSession()
        while len(searchTerms) < wordsCount:
            i += 1
            # Fetching daily trends from Google Trends API
            r = session.get(
                f"https://trends.google.com/trends/api/dailytrends?hl={self.browser.localeLang}"
                f'&ed={(date.today() - timedelta(days=i)).strftime("%Y%m%d")}&geo={self.browser.localeGeo}&ns=15'
            )
            assert r.status_code == requests.codes.ok
            trends = json.loads(r.text[6:])
            for topic in trends["default"]["trendingSearchesDays"][0][
                "trendingSearches"
            ]:
                searchTerms.append(topic["title"]["query"].lower())
                searchTerms.extend(
                    relatedTopic["query"].lower()
                    for relatedTopic in topic["relatedQueries"]
                )
            searchTerms = list(set(searchTerms))
        del searchTerms[wordsCount : (len(searchTerms) + 1)]
        return searchTerms

    def getRelatedTerms(self, term: str) -> list[str]:
        # Function to retrieve related terms from Bing API
        relatedTerms: list[str] = (
            makeRequestsSession()
            .get(
                f"https://api.bing.com/osjson.aspx?query={term}",
                headers={"User-agent": self.browser.userAgent},
            )
            .json()[1]
        )  # todo Wrap if failed, or assert response?
        if not relatedTerms:
            return [term]
        return relatedTerms

    def bingSearches(self) -> None:
        # Function to perform Bing searches
        logging.info(
            f"[BING] Starting {self.browser.browserType.capitalize()} Edge Bing searches..."
        )

        self.browser.utils.goToSearch()

        remainingSearches = self.browser.getRemainingSearches()
        for searchCount in range(1, remainingSearches + 1):
            # todo Disable cooldown for first 3 searches (Earning starts with your third search)
            logging.info(f"[BING] {searchCount}/{remainingSearches}")
            self.bingSearch()
            sleep(randint(200, 300))

        logging.info(
            f"[BING] Finished {self.browser.browserType.capitalize()} Edge Bing searches !"
        )

    def bingSearch(self) -> None:
        # Function to perform a single Bing search
        pointsBefore = self.browser.utils.getAccountPoints()

        rootTerm = list(self.googleTrendsShelf.keys())[1]
        terms = self.getRelatedTerms(rootTerm)
        logging.debug(f"terms={terms}")
        termsCycle: cycle[str] = cycle(terms)
        baseDelay = Searches.baseDelay
        logging.debug(f"rootTerm={rootTerm}")

        # todo If first 3 searches of day, don't retry since points register differently, will be a bit quicker
        for i in range(self.maxRetries + 1):
            if i != 0:
                sleepTime: float
                if Searches.retriesStrategy == Searches.retriesStrategy.EXPONENTIAL:
                    sleepTime = baseDelay * 2 ** (i - 1)
                elif Searches.retriesStrategy == Searches.retriesStrategy.CONSTANT:
                    sleepTime = baseDelay
                else:
                    raise AssertionError
                sleepTime += baseDelay * random()  # Add jitter
                logging.debug(
                    f"[BING] Search attempt not counted {i}/{Searches.maxRetries}, sleeping {sleepTime}"
                    f" seconds..."
                )
                sleep(sleepTime)

            searchbar = self.browser.utils.waitUntilClickable(
                By.ID, "sb_form_q", timeToWait=40
            )
            searchbar.clear()
            term = next(termsCycle)
            logging.debug(f"term={term}")
            sleep(1)
            searchbar.send_keys(term)
            sleep(1)
            searchbar.submit()

            pointsAfter = self.browser.utils.getAccountPoints()
            if pointsBefore < pointsAfter:
                # todo Make configurable
                sleep(randint(30, 60))
                return

            # todo
            # if i == (maxRetries / 2):
            #     logging.info("[BING] " + "TIMED OUT GETTING NEW PROXY")
            #     self.webdriver.proxy = self.browser.giveMeProxy()
        logging.error("[BING] Reached max search attempt retries")
