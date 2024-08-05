# -*- coding: utf-8 -*-

from learn_delta_py import api


def test():
    _ = api


if __name__ == "__main__":
    from learn_delta_py.tests import run_cov_test

    run_cov_test(__file__, "learn_delta_py.api", preview=False)
