import json
import logging
import requests
from decimal import Decimal
from datetime import datetime


class UnknownAccountNumber(ValueError):
    pass


class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return round(float(obj), 2)

        return json.JSONEncoder.default(self, obj)


class TaxerSession:
    basename = "https://taxer.ua/api"

    _session = None
    _uid = None

    _common_headers = {
        "authority": "taxer.ua",
        "accept": "application/json, text/plain, */*",
        "dnt": "1",
        # ToDo: Identify ourselves? Will they be mad at us?
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/85.0.4183.121 Safari/537.36",
        "content-type": "application/json",
        "origin": "https://taxer.ua",
        "referer": "https://taxer.ua/uk/",
        "accept-language": "en-US,en;q=0.9",
    }
    logger = None

    def __init__(
        self, *, auth_data, basename=None, extra_headers=None, init_session=True
    ):
        """
        :param basename no trailing slashes!
        """
        self.logger = logging.Logger(
            f"{self.__class__.__module__}.{self.__class__.__name__}"
        )

        if basename is not None:
            self.basename = basename

        # `v` must be a string always, hence we delete common string
        # when extra value is none and add/update otherwise
        if extra_headers is not None:
            self._common_headers = self._common_headers.copy()
            for k, v in extra_headers.items():
                if v is None:
                    self._common_headers.pop(k, None)
                else:
                    self._common_headers[k] = v

        if init_session:
            self.init_session(auth_data)

    def init_session(self, auth_data):
        self._session = requests.session()

        r = self.request("post", "user/login/login/", body=auth_data)

        assert len(r["account"]["users"]) == 1, "More than one user?!!! NOT YET"

        self._uid = r["account"]["users"][0]["id"]

        return r

    def get_uid(self):
        assert self._uid is not None
        return self._uid

    def request(self, method, path, body, params=None):
        assert self._session is not None, (
            "You must call init_session explicitly," " if skippied upon initialization"
        )

        if params is None:
            params = {"lang": "uk"}

        self._last_response = r = self._session.request(
            method,
            self.make_url(path),
            headers=self._common_headers,
            data=json.dumps(body, cls=CustomJSONEncoder),
            params=params,
        )
        formatted = r.json()

        logging.debug(formatted)

        return formatted

    def make_url(self, path):
        return f"{self.basename}/{path}"

    def api(self, *args, **kwargs):
        return TaxerAPI(self, *args, **kwargs)


class TaxerAPI:
    def __init__(self, session: TaxerSession, dry_run=False):
        self.session = session
        self.dry_run = dry_run

    @staticmethod
    def make_timestamp(time: datetime):
        """
        Incoming timezone & format?
        As long as report was generated in the same timezone clock is running
        - we're good. But no clarity can be found there, cuz
        mono - doesn't provide timestamp explicitly or implicitly
        taxer uses JS' `Date.now() / 1000`
        # "timestamp": 1604434326,
        # 03.11.2020 22:12
        """
        return int(time.timestamp())

    def get_accounts(self):
        """
        Get list of the accounts
        """
        return self.session.request(
            "get",
            "finances/account/load",
            {},
            params={
                "params": json.dumps({
                    "userId": self.session._uid,
                    "pageNumber": 1,
                    "filters": {"filterArchived": 0},
                })
            },
        )

    def get_operations(self, date_to):
        return self.session.request(
            "get",
            "finances/operation/load",
            {
                "userId": self.session.get_uid(),
                "filters": {},
                "pageNumber": 1,
            },
        )

    def convert_iban_to_taxer_acc(self, account_number, response="for_operation"):
        if getattr(self, "_accounts_cache", None) is None:
            accounts_res = self.get_accounts()
            self._accounts_cache = accounts_res["accounts"]

        for acc in self._accounts_cache:
            if account_number == acc["num"]:
                if response == "for_operation":
                    return {
                        "id": acc["id"],
                        "currency": acc["currency"],
                        "title": acc["title"],
                    }
                elif response == "full":
                    return acc

        raise UnknownAccountNumber(
            f"Account number is not in the system {account_number}"
        )

    def add_operation(
        self,
        type_,
        time: datetime,
        data: dict,
        comment=None,
    ):
        assert type_ in {"FlowIncome", "CurrencyExchange"}, "Unsuported operation :("

        local_data = data.copy()
        local_data.update(
            {
                "id": None,
                "type": type_,
                "financeType": "custom",
                "contents": [],
                "timestamp": self.make_timestamp(time),
            }
        )
        local_data.setdefault("comment", comment)

        payload = {
            "operations": [
                {
                    "userId": self.session._uid,
                    "operation": local_data,
                },
            ],
        }

        print(f"Will be sending payload {payload}")

        if self.dry_run:
            return {"dry_run": True}

        return self.session.request(
            "post",
            "finances/operation/create",
            payload,
        )

    def add_income(self, amount: Decimal, account_to: str, time: datetime):
        """
        U got the moneyz, now note that in taxer m8
        """
        operation = {
            "payedSum": None,
            "account": self.convert_iban_to_taxer_acc(account_to),
            "total": amount,
        }
        return self.add_operation("FlowIncome", time, operation)

    def add_exchange(
        self,
        amount: Decimal,
        rate: Decimal,
        account_from: str,
        account_to: str,
        time: datetime,
    ):
        """
        Add money exchange operation
        """
        operation = {
            "outgoTotal": amount,
            "outgoAccount": self.convert_iban_to_taxer_acc(account_from),
            "incomeAccount": self.convert_iban_to_taxer_acc(account_to),
            "incomeCurrency": rate,
        }
        return self.add_operation("CurrencyExchange", time, operation)
