# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from trytond.model import Workflow, fields
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Bool, Eval

__all__ = ['Journal', 'Payment']


class Journal:
    __name__ = 'account.payment.journal'
    __metaclass__ = PoolMeta
    processing_account = fields.Many2One('account.account',
        'Processing Account', states={
            'required': Bool(Eval('processing_journal')),
            },
        depends=['processing_journal'])
    processing_journal = fields.Many2One('account.journal',
        'Processing Journal', states={
            'required': Bool(Eval('processing_account')),
            },
        depends=['processing_account'])


class Payment:
    __name__ = 'account.payment'
    __metaclass__ = PoolMeta
    processing_move = fields.Many2One('account.move', 'Processing Move',
        readonly=True)

    @classmethod
    @Workflow.transition('processing')
    def process(cls, payments, group):
        pool = Pool()
        Move = pool.get('account.move')

        group = super(Payment, cls).process(payments, group)

        moves = []
        for payment in payments:
            move = payment.create_processing_move()
            if move:
                moves.append(move)
        if moves:
            moves = Move.create([m._save_values for m in moves])
            cls.write(*sum((([m.origin], {'processing_move': m.id})
                        for m in moves), ()))
            Move.post(moves)
        return group

    def create_processing_move(self):
        pool = Pool()
        Move = pool.get('account.move')
        Line = pool.get('account.move.line')
        Period = pool.get('account.period')
        Date = pool.get('ir.date')

        if not self.line:
            return
        if (not self.journal.processing_account
                or not self.journal.processing_journal):
            return
        if self.processing_move:
            return self.processing_move

        date = Date.today()
        period = Period.find(self.company.id, date=date)

        move = Move(
            journal=self.journal.processing_journal,
            origin=self,
            date=date,
            period=period)

        line = Line()
        if self.kind == 'payable':
            line.debit, line.credit = self.amount, 0
        else:
            line.debit, line.credit = 0, self.amount
        line.account = self.line.account
        line.amount_second_currency = (-self.line.amount_second_currency
            if self.line.amount_second_currency else None)
        line.second_currency = self.line.second_currency
        line.party = (self.line.party
            if self.line.account.party_required else None)

        counterpart = Line()
        if self.kind == 'payable':
            counterpart.debit, counterpart.credit = 0, self.amount
        else:
            counterpart.debit, counterpart.credit = self.amount, 0
        counterpart.account = self.journal.processing_account
        counterpart.party = (self.line.party
            if self.journal.processing_account.party_required else None)
        counterpart.amount_second_currency = self.line.amount_second_currency
        counterpart.second_currency = self.line.second_currency
        move.lines = (line, counterpart)
        return move

    def create_clearing_move(self, date=None):
        move = super(Payment, self).create_clearing_move(date=date)
        if move and self.processing_move:
            for line in move.lines:
                if line.account == self.journal.clearing_account:
                    line.account = self.journal.processing_account
                    line.party = (self.line.party
                        if line.account.party_required else None)
        return move
