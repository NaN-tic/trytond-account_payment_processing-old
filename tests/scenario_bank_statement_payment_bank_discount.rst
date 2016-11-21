=======================================
Account Bank Statement Payment Scenario
=======================================

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
    >>> from trytond.modules.account_invoice.tests.tools import \
    ...     set_fiscalyear_invoice_sequences, create_payment_term
    >>> today = datetime.date.today()
    >>> now = datetime.datetime.now()

Install account_payment_processing and account_bank_statement_payment::

    >>> config = activate_modules(['account_payment_processing',
    ...     'account_bank_statement_payment'])

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Reload the context::

    >>> User = Model.get('res.user')
    >>> config._context = User.get_preferences(True, config.context)

Create fiscal year::

    >>> fiscalyear = set_fiscalyear_invoice_sequences(
    ...     create_fiscalyear(company))
    >>> fiscalyear.click('create_period')

Create chart of accounts::

    >>> _ = create_chart(company)
    >>> accounts = get_accounts(company)
    >>> receivable = accounts['receivable']
    >>> revenue = accounts['revenue']
    >>> expense = accounts['expense']
    >>> cash = accounts['cash']
    >>> cash.bank_reconcile = True
    >>> cash.save()

Create processing and bank discount accounts::

    >>> Account = Model.get('account.account')
    >>> customer_processing_payments = Account()
    >>> customer_processing_payments.name = 'Customers Processing Payments'
    >>> customer_processing_payments.parent = receivable.parent
    >>> customer_processing_payments.kind = 'other'
    >>> customer_processing_payments.type = receivable.type
    >>> customer_processing_payments.bank_reconcile = True
    >>> customer_processing_payments.reconcile = True
    >>> customer_processing_payments.party_required = True
    >>> customer_processing_payments.deferral = True
    >>> customer_processing_payments.save()
    >>> customer_bank_discounts = Account()
    >>> customer_bank_discounts.name = 'Customers Bank Discount'
    >>> customer_bank_discounts.type = receivable.type
    >>> customer_bank_discounts.bank_reconcile = True
    >>> customer_bank_discounts.reconcile = True
    >>> customer_bank_discounts.deferral = True
    >>> customer_bank_discounts.parent = receivable.parent
    >>> customer_bank_discounts.kind = 'other'
    >>> customer_bank_discounts.save()

Create and get journals::

    >>> Sequence = Model.get('ir.sequence')
    >>> AccountJournal = Model.get('account.journal')
    >>> sequence = Sequence(name='Bank', code='account.journal',
    ...     company=company)
    >>> sequence.save()
    >>> bank_journal = AccountJournal(
    ...     name='Bank Statement',
    ...     type='cash',
    ...     credit_account=cash,
    ...     debit_account=cash,
    ...     sequence=sequence)
    >>> bank_journal.save()
    >>> revenue_journal, = AccountJournal.find([('code', '=', 'REV')])

Create payment journal::

    >>> PaymentJournal = Model.get('account.payment.journal')
    >>> payment_receivable_100_journal = PaymentJournal(
    ...     name='Manual receivable 100% discount',
    ...     process_method='manual',
    ...     clearing_journal=revenue_journal,
    ...     clearing_account=customer_bank_discounts,
    ...     processing_journal=revenue_journal,
    ...     processing_account=customer_processing_payments)
    >>> payment_receivable_100_journal.save()
    >>> payment_receivable_100_journal.clearing_percent
    Decimal('1')
    >>> payment_receivable_80_journal = PaymentJournal(
    ...     name='Manual receivable 80% discount',
    ...     process_method='manual',
    ...     clearing_journal=revenue_journal,
    ...     clearing_account=customer_bank_discounts,
    ...     clearing_percent=Decimal('0.8'),
    ...     processing_journal=revenue_journal,
    ...     processing_account=customer_processing_payments)
    >>> payment_receivable_80_journal.save()

Create statement journal::

    >>> StatementJournal = Model.get('account.bank.statement.journal')
    >>> statement_journal = StatementJournal(
    ...     name='Test',
    ...     journal=bank_journal)
    >>> statement_journal.save()

Create party::

    >>> Party = Model.get('party.party')
    >>> supplier = Party(name='Supplier')
    >>> supplier.save()
    >>> customer = Party(name='Customer')
    >>> customer.save()

Create payment term::

    >>> payment_term = create_payment_term()
    >>> payment_term.save()

Create customer invoice::

    >>> Invoice = Model.get('account.invoice')
    >>> customer_invoice = Invoice(type='out')
    >>> customer_invoice.party = customer
    >>> customer_invoice.payment_term = payment_term
    >>> invoice_line = customer_invoice.lines.new()
    >>> invoice_line.quantity = 1
    >>> invoice_line.unit_price = Decimal('100')
    >>> invoice_line.account = revenue
    >>> invoice_line.description = 'Test'
    >>> customer_invoice.save()
    >>> customer_invoice.click('post')
    >>> customer_invoice.state
    u'posted'

Create customer invoice payment::

    >>> Payment = Model.get('account.payment')
    >>> line, = [l for l in customer_invoice.move.lines
    ...     if l.account == receivable]
    >>> pay_line = Wizard('account.move.line.pay', [line])
    >>> pay_line.form.journal = payment_receivable_100_journal
    >>> pay_line.execute('start')
    >>> payment, = Payment.find([('state', '=', 'draft')])
    >>> payment.amount
    Decimal('100.00')
    >>> payment.click('approve')
    >>> payment.state
    u'approved'
    >>> process_payment = Wizard('account.payment.process', [payment])
    >>> process_payment.execute('process')
    >>> payment.reload()
    >>> payment.state
    u'processing'

Check invoice is still pending to pay so the amount is in customer's debit account::

    >>> customer_invoice.reload()
    >>> customer_invoice.state
    u'paid'
    >>> receivable.reload()
    >>> receivable.balance
    Decimal('0.00')

Create and confirm bank statement::

    >>> BankStatement = Model.get('account.bank.statement')
    >>> statement = BankStatement(journal=statement_journal, date=now)
    >>> statement_line = statement.lines.new()
    >>> statement_line.date = now
    >>> statement_line.description = 'Customer Invoice Bank Discount reception'
    >>> statement_line.amount = Decimal('100.0')
    >>> statement.save()
    >>> statement.click('confirm')
    >>> statement.state
    u'confirmed'

Create transaction lines on statement line and post it::

    >>> statement_line, = statement.lines
    >>> st_move_line = statement_line.lines.new()
    >>> st_move_line.payment = payment
    >>> st_move_line.amount
    Decimal('100.00')
    >>> st_move_line.account.name
    u'Customers Bank Discount'
    >>> st_move_line.party.name
    u'Customer'
    >>> statement_line.save()
    >>> statement_line.click('post')

The statement's amount is in Customers Bank Discount account debit::

    >>> customer_bank_discounts.reload()
    >>> customer_bank_discounts.balance
    Decimal('-100.00')

When the invoice due date plus some margin days arrives, if the bank doesn't
substract the advanced amount is because the payment succeeded::

    >>> payment.click('succeed')
    >>> payment.clearing_move != None
    True

Now, the invoice is paid, the customer's due amount is zero, also owr due with
bank::

    >>> customer_invoice.reload()
    >>> customer_invoice.state
    u'paid'
    >>> receivable.reload()
    >>> receivable.balance
    Decimal('0.00')
    >>> customer_bank_discounts.reload()
    >>> customer_bank_discounts.balance
    Decimal('0.00')

But if after that, the bank substracts the advanced amount, we create the bank
statement::

    >>> statement2 = BankStatement(journal=statement_journal, date=now)
    >>> statement_line = statement2.lines.new()
    >>> statement_line.date = now
    >>> statement_line.description = 'Customer Invoice Bank Discount recover'
    >>> statement_line.amount = Decimal('-100.0')
    >>> statement2.save()
    >>> statement2.click('confirm')
    >>> statement2.state
    u'confirmed'

Create transaction lines on statement line and post it::

    >>> statement_line2, = statement2.lines
    >>> st_move_line = statement_line2.lines.new()
    >>> st_move_line.payment = payment
    >>> st_move_line.amount
    Decimal('-100.00')
    >>> st_move_line.account.name
    u'Customers Bank Discount'
    >>> st_move_line.party.name
    u'Customer'
    >>> statement_line2.save()
    >>> statement_line2.click('post')

The payment is failed, clearing move reverted so amount is due by customer and
we doesn't have cash::

    >>> payment.reload()
    >>> payment.state
    u'failed'
    >>> payment.clearing_move == None
    True
    >>> customer_invoice.reload()
    >>> customer_invoice.state
    u'posted'
    >>> receivable.reload()
    >>> receivable.balance
    Decimal('100.00')
    >>> customer_bank_discounts.reload()
    >>> customer_bank_discounts.balance
    Decimal('0.00')
    >>> cash.reload()
    >>> cash.balance
    Decimal('0.00')

But finally, the customer pays the invoice directly::

    >>> statement3 = BankStatement(journal=statement_journal, date=now)
    >>> statement_line = statement3.lines.new()
    >>> statement_line.date = now
    >>> statement_line.description = 'Customer Invoice payment'
    >>> statement_line.amount = Decimal('100.0')
    >>> statement3.save()
    >>> statement3.click('confirm')
    >>> statement3.state
    u'confirmed'

Create transaction lines on statement line and post it::

    >>> statement_line3, = statement3.lines
    >>> st_move_line = statement_line3.lines.new()
    >>> st_move_line.invoice = customer_invoice
    >>> st_move_line.amount
    Decimal('100.00')
    >>> st_move_line.account.name
    u'Main Receivable'
    >>> st_move_line.party.name
    u'Customer'
    >>> statement_line3.save()
    >>> statement_line3.click('post')

So the payment is succeeded, the invoice paid again and due amounts are 0::

    >>> customer_invoice.reload()
    >>> customer_invoice.state
    u'paid'
    >>> receivable.reload()
    >>> receivable.balance
    Decimal('0.00')
    >>> customer_bank_discounts.reload()
    >>> customer_bank_discounts.balance
    Decimal('0.00')

Create two customer invoices::

    >>> customer_invoice2 = Invoice(type='out')
    >>> customer_invoice2.party = customer
    >>> customer_invoice2.payment_term = payment_term
    >>> invoice_line = customer_invoice2.lines.new()
    >>> invoice_line.quantity = 1
    >>> invoice_line.unit_price = Decimal('200')
    >>> invoice_line.account = revenue
    >>> invoice_line.description = 'Test 2'
    >>> customer_invoice2.save()
    >>> customer_invoice2.click('post')
    >>> customer_invoice2.state
    u'posted'

    >>> customer_invoice3 = Invoice(type='out')
    >>> customer_invoice3.party = customer
    >>> customer_invoice3.payment_term = payment_term
    >>> invoice_line = customer_invoice3.lines.new()
    >>> invoice_line.quantity = 1
    >>> invoice_line.unit_price = Decimal('80')
    >>> invoice_line.account = revenue
    >>> invoice_line.description = 'Test 3'
    >>> customer_invoice3.save()
    >>> customer_invoice3.click('post')
    >>> customer_invoice3.state
    u'posted'

    >>> receivable.reload()
    >>> receivable.balance
    Decimal('280.00')

Create a payment with 80% bank discount for first of them::

    >>> line, = [l for l in customer_invoice2.move.lines
    ...     if l.account == receivable]
    >>> pay_line = Wizard('account.move.line.pay', [line])
    >>> pay_line.form.journal = payment_receivable_80_journal
    >>> pay_line.execute('start')
    >>> payment2, = Payment.find([('state', '=', 'draft')])
    >>> payment2.amount
    Decimal('200.00')
    >>> payment2.click('approve')
    >>> payment2.state
    u'approved'
    >>> process_payment = Wizard('account.payment.process', [payment2])
    >>> process_payment.execute('process')
    >>> payment2.reload()
    >>> payment2.state
    u'processing'

And another payment with 100% bank discount for the second one::

    >>> line, = [l for l in customer_invoice3.move.lines
    ...     if l.account == receivable]
    >>> pay_line = Wizard('account.move.line.pay', [line])
    >>> pay_line.form.journal = payment_receivable_100_journal
    >>> pay_line.execute('start')
    >>> payment3, = Payment.find([('state', '=', 'draft')])
    >>> payment3.amount
    Decimal('80.00')
    >>> payment3.click('approve')
    >>> payment3.state
    u'approved'
    >>> process_payment = Wizard('account.payment.process', [payment3])
    >>> process_payment.execute('process')
    >>> payment3.reload()
    >>> payment3.state
    u'processing'

Create and confirm bank statement::

    >>> statement4 = BankStatement(journal=statement_journal, date=now)
    >>> statement_line = statement4.lines.new()
    >>> statement_line.date = now
    >>> statement_line.description = 'Bank Discount for second invoice'
    >>> statement_line.amount = Decimal('160.0')
    >>> statement_line = statement4.lines.new()
    >>> statement_line.date = now
    >>> statement_line.description = 'Bank Discount for third invoice'
    >>> statement_line.amount = Decimal('80.0')
    >>> statement4.save()
    >>> statement4.click('confirm')
    >>> statement4.state
    u'confirmed'

Create transaction lines on statement lines and post them::

    >>> statement_line4, statement_line5 = statement4.lines
    >>> st_move_line = statement_line4.lines.new()
    >>> st_move_line.payment = payment2
    >>> st_move_line.amount
    Decimal('160.00')
    >>> st_move_line.account.name
    u'Customers Bank Discount'
    >>> st_move_line.party.name
    u'Customer'
    >>> statement_line4.save()
    >>> statement_line4.click('post')
    >>> st_move_line = statement_line5.lines.new()
    >>> st_move_line.payment = payment2
    >>> st_move_line.amount
    Decimal('80.00')
    >>> st_move_line.account.name
    u'Customers Bank Discount'
    >>> st_move_line.party.name
    u'Customer'
    >>> statement_line5.save()
    >>> statement_line5.click('post')

All the amount is on cash account and as debit with bank::

    >>> cash.reload()
    >>> cash.balance
    Decimal('340.00')
    >>> customer_bank_discounts.reload()
    >>> customer_bank_discounts.balance
    Decimal('-240.00')

When the invoices due date arrives, the pending amount of second invoice is
paid by customer but bank substract the third invoice amount::

    >>> statement5 = BankStatement(journal=statement_journal, date=now)
    >>> statement_line = statement5.lines.new()
    >>> statement_line.date = now
    >>> statement_line.description = 'Pending payment of second invoice'
    >>> statement_line.amount = Decimal('40.0')
    >>> statement_line = statement5.lines.new()
    >>> statement_line.date = now
    >>> statement_line.description = 'Recover of Bank Discount for third invoice'
    >>> statement_line.amount = Decimal('-80.0')
    >>> statement5.save()
    >>> statement5.click('confirm')
    >>> statement5.state
    u'confirmed'

Create transaction line on statement line with pending amount of second
invoice, selecting the invoice and the payment::

    >>> statement_line6, statement_line7 = statement5.lines
    >>> st_move_line = statement_line6.lines.new()
    >>> st_move_line.invoice = customer_invoice2
    >>> st_move_line.payment == payment2
    True
    >>> st_move_line.amount
    Decimal('40.00')
    >>> st_move_line.account.name
    u'Main Receivable'
    >>> st_move_line.party.name
    u'Customer'
    >>> statement_line6.save()
    >>> statement_line6.click('post')

The payment of second customer invoice is succeeded::

    >>> payment2.reload()
    >>> payment2.state
    u'succeeded'
    >>> customer_invoice2.reload()
    >>> customer_invoice2.state
    u'paid'

Create transaction line on statement line with recovering of bank discount for
third invoice selecting the payment::

    >>> st_move_line = statement_line7.lines.new()
    >>> st_move_line.payment = payment3
    >>> st_move_line.amount
    Decimal('-80.00')
    >>> st_move_line.account.name
    u'Customers Bank Discount'
    >>> st_move_line.party.name
    u'Customer'
    >>> statement_line7.save()
    >>> statement_line7.click('post')

And the payment of third customer invoice is failed::

    >>> payment3.reload()
    >>> payment3.state
    u'failed'
    >>> customer_invoice3.reload()
    >>> customer_invoice3.state
    u'posted'

The third invoice amount is also owed, the due with bank is empty and the cash
do not have the third invoice amount::

    >>> receivable.reload()
    >>> receivable.balance
    Decimal('80.00')
    >>> customer_bank_discounts.reload()
    >>> customer_bank_discounts.balance
    Decimal('0.00')
    >>> cash.reload()
    >>> cash.balance
    Decimal('300.00')
