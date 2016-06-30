# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from trytond.pool import Pool
from .payment import *
from .statement import *


def register():
    Pool.register(
        Journal,
        Payment,
        StatementMoveLine,
        module='account_payment_processing', type_='model')
