import csv
import re
from decimal import Decimal, InvalidOperation
from datetime import datetime

from .adaptor import Operation


class Monobank:
    _file = None
    _csvfile = None

    def __init__(self, f):
        self.validate(f)
        self._file = f
        self._csvfile = csv.reader(self._file)

    def validate(self, f):
        # ToDo:
        # 1. Extract IBAN _OR_ provide separately?
        # self._file.name
        # 2. Validate columns match the format
        # return list of row_number:error
        pass

    def process(self):
        acc_spec = next(self._csvfile)
        account_from = re.findall(u'рахунком (.*) за', acc_spec[0])[0]
        print(f'Processing {acc_spec[0]}\n(Account number: {account_from})')

        header = next(self._csvfile)
        print(f'Skipping header {header}')
        # ToDo: Must figure if submission order is any necessary to taxer
        # Or we could save up some resources and not load the whole CSV
        # into memory for the purpose of reversing
        for line in reversed(list(self._csvfile)):
            yield account_from, self.build_operation(line)

    def build_operation(self, line):
        rate = line[10]
        try:
            rate = Decimal(rate)
        except InvalidOperation:
            # If it's invalid - we leave rate as is and let
            # the downstream code deal with its validation
            # or fail miserably
            pass
        
        dt_raw = f'{line[0]} {line[1]}'
        return Operation(
            datetime=datetime.strptime(dt_raw, '%d.%m.%Y %H:%M:%S'),
            account_to=line[6],
            amount=Decimal(line[7]),
            target_amount=Decimal(line[8]),
            currency=line[9],
            rate=rate,
        )
