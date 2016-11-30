===================================
Account Payment Processing Scenario
===================================

Imports::


    >>> import datetime
    >>> from dateutil.relativedelta import relativedelta
    >>> from decimal import Decimal
    >>> from proteus import Model, Wizard
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import create_company, \
    ...     get_company
    >>> from trytond.modules.account.tests.tools import create_fiscalyear, \
    ...     create_chart, get_accounts, create_tax
    >>> today = datetime.date.today()
    >>> now = datetime.datetime.now()

Install account_payment_processing::

    >>> config = activate_modules('account_payment_processing')

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Create fiscal year::

    >>> fiscalyear = create_fiscalyear(company)
    >>> fiscalyear.click('create_period')
    >>> period = fiscalyear.periods[0]

Create chart of accounts::

    >>> _ = create_chart(company)
    >>> accounts = get_accounts(company)
    >>> receivable = accounts['receivable']
    >>> revenue = accounts['revenue']
    >>> expense = accounts['expense']
    >>> cash = accounts['cash']

Create processing accounts::

    >>> Account = Model.get('account.account')
    >>> processing = Account()
    >>> processing.name = 'Customers Processing Payments'
    >>> processing.parent = receivable.parent
    >>> processing.kind = 'receivable'
    >>> processing.type = receivable.type
    >>> processing.reconcile = True
    >>> processing.party_required = True
    >>> processing.deferral = True
    >>> processing.save()

Get journals::

    >>> Journal = Model.get('account.journal')
    >>> journal_revenue, = Journal.find([
    ...         ('code', '=', 'REV'),
    ...         ])
    >>> journal_cash, = Journal.find([
    ...         ('code', '=', 'CASH'),
    ...         ])

Create payment journal::

    >>> PaymentJournal = Model.get('account.payment.journal')
    >>> payment_journal = PaymentJournal(
    ...     name='Processing',
    ...     process_method='manual',
    ...     clearing_journal=journal_cash,
    ...     clearing_account=cash,
    ...     processing_journal=journal_revenue,
    ...     processing_account=processing)
    >>> payment_journal.save()

Create party::

    >>> Party = Model.get('party.party')
    >>> customer = Party(name='Customer')
    >>> customer.save()

Create moves to pay for the customer::

    >>> Move = Model.get('account.move')
    >>> move = Move()
    >>> move.period = period
    >>> move.journal = journal_revenue
    >>> move.date = period.start_date
    >>> line = move.lines.new()
    >>> line.account = revenue
    >>> line.credit = Decimal(100)
    >>> line = move.lines.new()
    >>> line.account = receivable
    >>> line.debit = Decimal(100)
    >>> line.party = customer
    >>> move.click('post')
    >>> receivable.reload()
    >>> receivable.balance
    Decimal('100.00')
    >>> customer.receivable
    Decimal('100')

Create customer payment::

    >>> Payment = Model.get('account.payment')
    >>> line, = [l for l in move.lines if l.account == receivable]
    >>> pay_line = Wizard('account.move.line.pay', [line])
    >>> pay_line.form.journal = payment_journal
    >>> pay_line.execute('start')
    >>> payment, = Payment.find([('state', '=', 'draft')])
    >>> payment.amount
    Decimal('100')
    >>> payment.click('approve')
    >>> payment.state
    u'approved'
    >>> process_payment = Wizard('account.payment.process', [payment])
    >>> process_payment.execute('process')
    >>> payment.reload()
    >>> payment.state
    u'processing'

Amount have moved to the processing account but related to customer::

    >>> receivable.reload()
    >>> receivable.balance
    Decimal('0.00')
    >>> processing.reload()
    >>> processing.balance
    Decimal('100.00')
    >>> customer.reload()
    >>> customer.receivable
    Decimal('100')

Once the payment is succeed there is no any receivable due amount::

    >>> payment.click('succeed')
    >>> receivable.reload()
    >>> receivable.balance
    Decimal('0.00')
    >>> processing.reload()
    >>> processing.balance
    Decimal('0.00')
    >>> customer.reload()
    >>> customer.receivable
    Decimal('0.0')

Test that all the lines have been reconciled::

    >>> MoveLine = Model.get('account.move.line')
    >>> to_reconcile = MoveLine.find([
    ...     ('account.reconcile', '=', True),
    ...     ('reconciliation', '=', None),
    ...     ])
    >>> len(to_reconcile)
    0

If we fail the payment the balances are moved back to the receivable account::

    >>> payment.click('fail')
    >>> receivable.reload()
    >>> receivable.balance
    Decimal('100.00')
    >>> processing.reload()
    >>> processing.balance
    Decimal('0.00')
    >>> customer.reload()
    >>> customer.receivable
    Decimal('100')
    >>> to_reconcile, = MoveLine.find([
    ...     ('account.reconcile', '=', True),
    ...     ('reconciliation', '=', None),
    ...     ])
    >>> to_reconcile.party == customer
    True

And marking the payment as success again clears all the balances::

    >>> payment.click('succeed')
    >>> receivable.reload()
    >>> receivable.balance
    Decimal('0.00')
    >>> processing.reload()
    >>> processing.balance
    Decimal('0.00')
    >>> customer.reload()
    >>> customer.receivable
    Decimal('0.0')
    >>> MoveLine = Model.get('account.move.line')
    >>> to_reconcile = MoveLine.find([
    ...     ('account.reconcile', '=', True),
    ...     ('reconciliation', '=', None),
    ...     ])
    >>> len(to_reconcile)
    0
