import logging
import csv
import time
from random import randint

import click

from taxer import TaxerSession
from source.monobank import Monobank

# ToDo: Check timezone returned by taxer.
# book-11.03-04.10.csv has pre-DST transition -1 hr time
# I.e. 03.10.2020 11:15:53 is 03.10.2020 11:15:53 in GMT+3
# Let's see whether it will change on DST
# Also, find out what will gonna happen to taxer date submission
# ---------------
# Seems like it's Kyiv timezone and works allright on my machine
# But packing to docker or doing web-version I should prolly relate on
# User's timezone or make him specify it explicitly

logger = logging.Logger(name=__name__)


@click.command()
@click.argument("statement_file")
@click.option("-e", "--email", help="Your account's email address")
@click.option("-p", "--password", help="Your account's password")
@click.option("--dry-run", is_flag=True)
@click.option(
    "--creds-file",
    default=".taxer-credentials",
    help="Path to file with credentials login:password",
)
def main(statement_file, creds_file, dry_run, email=None, password=None):
    """
    Make your operations flow from bank to taxer.ua
    """
    credentials = {
        "email": email,
        "password": password,
    }
    if not (all(credentials.values())):
        with open(creds_file, "r", encoding="utf-8") as f:
            raw_creds = f.read().strip()
            parsed_creds = raw_creds.split(":", 1)
            credentials = {
                "email": parsed_creds[0],
                "password": parsed_creds[1],
            }

    assert credentials["email"], "Email must be passed either through CLI or file"
    assert credentials["password"], "Password must be passed either through CLI or file"

    print(email, password, creds_file, credentials)

    taxer = TaxerSession(auth_data=credentials, init_session=False)
    taxer.init_session(credentials)

    taxer_api = taxer.api(dry_run=dry_run)

    with open(statement_file, "r", encoding="utf-8") as f:
        mono = Monobank(f)
        for account, op in mono.process():
            if op.amount > 0:
                result = taxer_api.add_income(
                    op.amount,
                    account,
                    op.datetime,
                )
                print(f"Taxer replied {result}")
            elif op.amount < 0:
                result = taxer_api.add_exchange(
                    abs(op.amount),
                    op.rate,
                    account,
                    op.account_to,
                    op.datetime,
                )
                print(f"Taxer replied {result}")
            else:
                print("Can't process operation with zero amount")
                exit(127)

            # Do not DUDOS taxer
            time.sleep(randint(1, 3))


if __name__ == "__main__":
    main()
