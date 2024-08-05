# -*- coding: utf-8 -*-

from pathlib import Path

import polars as pl
from deltalake import DeltaTable

dir_here = Path(__file__).absolute().parent
dir_db = dir_here / "db"
dir_t_account = dir_here / "accounts"
dir_t_transactions = dir_here / "transactions"



dir_db.mkdir(exist_ok=True)
dir_t_account.mkdir(exist_ok=True)
dir_t_transactions.mkdir(exist_ok=True)

# account_type_enum_type = pl.Enum(["checking", "saving"])

account_schema = {
    "account_id": pl.Utf8(),
    "account_number": pl.Utf8(),
    # "account_type": account_type_enum_type,
    "account_type": pl.Utf8(),
    "description": pl.Utf8(),
}


def create_accounts_1():
    data = [
        {
            "account_id": "acc-1",
            "account_number": "1111-1111-1111",
            "account_type": "checking",
            "description": "Alice's Main checking account",
        },
        {
            "account_id": "acc-2",
            "account_number": "2222-2222-2222",
            "account_type": "checking",
            "description": "Bob's Main checking account",
        },
    ]
    df = pl.DataFrame(data, schema=account_schema)
    df.write_delta(f"{dir_t_account}")


def query_accounts_1():
    df = pl.read_parquet(f"{dir_t_account}/**/*.parquet")
    print(df)


def update_accounts():
    data = [
        {
            "account_id": "acc-2",
            "account_number": "2222-2222-2222",
            "account_type": "checking",
            "description": "Bob's Main checking account, updated",
        },
        {
            "account_id": "acc-3",
            "account_number": "3333-3333-3333",
            "account_type": "saving",
            "description": "Cathy's Main saving account",
        },
    ]
    df = pl.DataFrame(data, schema=account_schema)
    table_merger = df.write_delta(
        f"{dir_t_account}",
        mode="merge",
        delta_merge_options={
            "predicate": "s.account_id = t.account_id",
            "source_alias": "s",
            "target_alias": "t",
        },
    )
    (table_merger.when_matched_update_all().when_not_matched_insert_all().execute())


def query_accounts_2():
    df = pl.scan_delta(
        f"{dir_t_account}",
    )
    print(df.collect())


if __name__ == "__main__":
    """ """
    # create_accounts_1()
    # query_accounts_1()
    # update_accounts()
    query_accounts_2()
