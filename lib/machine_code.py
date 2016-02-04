# Author Adam Bobowski
#
# Machine code generation

from machine import Machine
from machine import is_number
from machine import is_int
from machine import is_inttab
from machine import is_operation


class MachineCode(Machine):
    def __init__(self):
        Machine.__init__(self)
        self.graph = None
        self.memtab = {}  # symbol table

    def gen(self, graph, symtab):
        self.graph = graph
        self.symtab = symtab
        #print self.symtab
        self.gen_code(graph)

        return self.code

    def gen_code(self, graph):
        for i, b in enumerate(graph):
            self.blocks[i] = str(len(self.code))
            self.gen_block(b)

        self.resolve_global_labels()

    def gen_block(self, block):
        added = False
        for i in block:
            if i[0] == 'if':
                added = True
                self.end_of_block(None)
            if i[0] == 'goto':
                added = True
                self.end_of_block(None)
            getattr(self, "gen_" + i[0])(i)
        if not added:
            self.end_of_block(None)
        self.regs = [None for _ in xrange(6)]

        #print self.regs


    def gen_assign(self, cmd):
        # TODO check if a is not interator of table stored
        _, a, b = cmd

        self.store_iterators(a)

        assignment = {
            is_number: self.assign_number,
            is_int: self.assign_variable,
            is_inttab: self.assign_variable,
            is_operation: self.assign_operation
        }

        for check, assign in assignment.iteritems():
            if check(b):
                assign(a, b)
                break

        self.load_iterators(a)

    def assign_number(self, a, b):
        a = self.alloregs(a)
        self.num(b, a)

    def assign_variable(self, a, b):
        a, b = self.alloregs(a, b)
        if a != b:
            self.cmd('COPY  a   b', a=a, b=b)

    def assign_operation(self, a, b):
        op, b, c = b
        operations = {
            '+': self.assign_plus,
            '-': self.assign_minus,
            '*': self.assign_times,
            '/': self.assign_divide,
            '%': self.assign_modulo
        }
        operations[op](a, b, c)

    def assign_plus(self, a, b, c):
        if is_number(b) or a == c:
            b, c = c, b

        # a := b + number
        if is_number(c):
            a, b = self.alloregs(a, b)
            if a != b:
                self.cmd('COPY  a   b', a=a, b=b)
            if c <= 5:  # small number addition
                for c in xrange(c):
                    self.cmd('INC   a', a=a)
            else:
                c = self.num(c, 9)
                self.cmd('ADD   a   c', a=a, c=c)
            return

        a, b, c = self.alloregs(a, b, c)
        if a != b:
            self.cmd('COPY  a   b', a=a, b=b)

        if b == c:
            # a := b + b
            self.cmd('SHL   a', a=a)
        else:
            # a := b + c
            self.cmd('ADD   a   c', a=a, c=c)

    def assign_minus(self, a, b, c):
        # a := b - number
        if is_number(c):
            a, b = self.alloregs(a, b)
            if a != b:
                self.cmd('COPY  a   b', a=a, b=b)
            if c <= 5:  # small number subtraction
                for c in xrange(c):
                    self.cmd('DEC   a', a=a)
            else:
                c = self.num(c, 9)
                self.cmd('SUB   a   c', a=a, c=c)
            return

        # a := number - c
        if is_number(b):
            a, c = self.alloregs(a, c)
            if a == c:
                self.cmd('COPY  9   c', c=c)
                c = 9
            b = self.num(b, a)
            self.cmd('SUB   b   c', b=b, c=c)
            return

        a, b, c = self.alloregs(a, b, c)
        if b == c:
            # a := b - b
            self.cmd('RESET a', a=a)
            return

        if a == c:
            # a := b - a
            self.cmd('COPY  9   c', c=c)
            c = 9

        if a != b:
            self.cmd('COPY  a   b', a=a, b=b)
        self.cmd('SUB   a   c', a=a, c=c)

    def assign_times(self, a, b, c):
        if is_number(b):
            b, c = c, b

        if is_number(c):  # todo << and *1 multiplication
            a, b = self.alloregs(a, b)
            c = self.num(c, 9)
            self.cmd('COPY  8   b', b=b)
        else:
            a, b, c = self.alloregs(a, b, c)
            self.cmd('COPY  9   c', c=c)
            self.cmd('COPY  8   b', b=b)

        self.mul(8, 9, a)

    def assign_divide(self, a, b, c):
        if is_number(b):
            a, c = self.alloregs(a, c)
            self.num(b, 6)
            self.cmd('COPY  7   c', c=c)
        elif is_number(c):
            a, b = self.alloregs(a, b)
            self.num(c, 7)
            self.cmd('COPY  6   b', b=b)
        else:
            a, b, c = self.alloregs(a, b, c)
            self.cmd('COPY  6   b', b=b)
            self.cmd('COPY  7   c', c=c)

        self.div(6, 7, 8, a, 9)

    def assign_modulo(self, a, b, c):
        if is_number(b):
            a, c = self.alloregs(a, c)
            self.cmd('COPY  6   c', c=c)
            b = self.num(b, a)
        elif is_number(c):
            a, b = self.alloregs(a, b)
            if a != c:
                self.cmd('COPY  a   b', a=a, b=b)
            c = self.num(c, 6)
        else:
            a, b, c = self.alloregs(a, b, c)
            self.cmd('COPY  6   c', c=c)
            self.cmd('COPY  a   b', a=a, b=b)

        self.div(a, 6, 7, 8, 9)

    def gen_if(self, cmd):
        _, cond, block_jump = cmd
        cond, a, b = cond
        condition = {
            '=': self.if_eq,
            '!=': self.if_neq,
            '<=': self.if_leq,
            '>=': self.if_geq,
            '<': self.if_lt,
            '>': self.if_gt
        }
        condition[cond](a, b, block_jump)


    def if_eq(self, a, b, block_jump):
        if is_number(a) and is_number(b) and a != b:
            return

        if a == b:
            # a = b always true
            self.cmd('JUMP  blockjump', blockjump=block_jump)
            return

        if is_number(a):
            a, b = b, a

        if is_number(b):
            _, a = self.alloregs(a, a)
            if b == 0:
                self.cmd('JZERO a   blockjump', a=a, blockjump=block_jump)
                return
            b = self.num(b, 9)
            self.cmd('COPY  8   a', a=a)
        else:
            _, a, b = self.alloregs(a, a, b)
            self.cmd('COPY  8   a', a=a)
            self.cmd('COPY  9   b', b=b)

        self.cmd('''
                    SUB     8    b
                    JZERO   8   $CHECK
                    JUMP    $END
            $CHECK  SUB     9   a
                    JZERO   9   blockjump
        ''', a=a, b=b, blockjump=block_jump)

    def if_neq(self, a, b, block_jump):
        if is_number(a) and is_number(b) and a == b:
            return

        if a == b:
            # a != a always false
            return

        if is_number(a):
            a, b = b, a

        if is_number(b):
            _, a = self.alloregs(a, a)
            if b == 0:
                self.cmd('''
                    JZERO a   $END
                    JUMP  blockjump
                ''', a=a, blockjump=block_jump)
                return
            b = self.num(b, 9)
            self.cmd('COPY  8   a', a=a)
        else:
            _, a, b = self.alloregs(a, a, b)
            self.cmd('COPY  8   a', a=a)
            self.cmd('COPY  9   b', b=b)

        self.cmd('''
                    SUB     8    b
                    JZERO   8   $CHECK
                    JUMP    blockjump
            $CHECK  SUB     9   a
                    JZERO   9   $END
                    JUMP    blockjump
        ''', a=a, b=b, blockjump=block_jump)

    def if_leq(self, a, b, block_jump):
        if is_number(a) and is_number(b):
            if a <= b:
                self.cmd('JUMP  blockjump', blockjump=block_jump)
            return

        if a == b:
            # a <= a always true
            self.cmd('JUMP  blockjump', blockjump=block_jump)
            return

        if is_number(a):
            _, b = self.alloregs(b, b)
            a = self.num(a, 8)
        elif is_number(b):
            _, a = self.alloregs(a, a)
            if b == 0:
                self.cmd('JZERO a   blockjump', a=a, blockjump=block_jump)
                return
            self.cmd('COPY  8   a', a=a)
            b = self.num(b, 9)
        else:
            _, a, b = self.alloregs(a, a, b)
            self.cmd('COPY  8   a', a=a)

        self.cmd('''
                    SUB     8   b
                    JZERO   8   blockjump
        ''', b=b, blockjump=block_jump)

    def if_geq(self, a, b, block_jump):
        if is_number(a) and is_number(b):
            if a >= b:
                self.cmd('JUMP  blockjump', blockjump=block_jump)
            return

        if a == b:
            # a >= a always true
            self.cmd('JUMP  blockjump', blockjump=block_jump)
            return

        if is_number(a):
            _, b = self.alloregs(b, b)
            self.cmd('COPY  9   b', b=b)
            a = self.num(a, 8)
        elif is_number(b):
            _, a = self.alloregs(a, a)
            b = self.num(b, 9)
        else:
            _, a, b = self.alloregs(a, a, b)
            self.cmd('COPY  9   b', b=b)

        self.cmd('''
                    SUB     9   a
                    JZERO   9   blockjump
        ''', a=a, blockjump=block_jump)

    def if_lt(self, a, b, block_jump):
        if is_number(a) and is_number(b):
            if a < b:
                self.cmd('JUMP  blockjump', blockjump=block_jump)
            return

        if a == b:
            # a > a always false
            return

        if is_number(a):
            _, b = self.alloregs(b, b)
            self.cmd('COPY  9   b', b=b)
            a = self.num(a, 8)
        elif is_number(b):
            _, a = self.alloregs(a, a)
            b = self.num(b, 9)
        else:
            _, a, b = self.alloregs(a, a, b)
            self.cmd('COPY  9   b', b=b)

        self.cmd('''
                    SUB     9   a
                    JZERO   9   $END
                    JUMP    blockjump
        ''', a=a, blockjump=block_jump)

    def if_gt(self, a, b, block_jump):
        if is_number(a) and is_number(b):
            if a > b:
                self.cmd('JUMP  blockjump', blockjump=block_jump)
            return

        if a == b:
            # a > a always false
            return

        if is_number(a):
            _, b = self.alloregs(b, b)
            a = self.num(a, 8)
        elif is_number(b):
            _, a = self.alloregs(a, a)
            self.cmd('COPY  8   a', a=a)
            b = self.num(b, 9)
        else:
            _, a, b = self.alloregs(a, a, b)
            self.cmd('COPY  8   a', a=a)

        self.cmd('''
                    SUB     8   b
                    JZERO   8   $END
                    JUMP    blockjump
        ''', b=b, blockjump=block_jump)

    def gen_get(self, cmd):
        _, a = cmd
        a = self.alloregs(a)
        self.cmd('READ  a', a=a)

    def gen_put(self, cmd):
        _, a = cmd
        if is_number(a):
            a = self.num(a, 9)
        else:
            _, a = self.alloregs(a, a)

        self.cmd('WRITE a', a=a)

    def gen_goto(self, cmd):
        _, block_jump = cmd
        self.cmd('JUMP  blockjump', blockjump=block_jump)

    def gen_halt(self, cmd):
        self.cmd('HALT')
