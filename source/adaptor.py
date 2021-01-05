from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass
class Operation:
    datetime: datetime
    # Operation amount
    amount: Decimal
    # Operation currency
    currency: str
    # Conversion rate
    rate: Decimal
    account_to: str
    target_amount: Decimal


class DataSource:
    pass
