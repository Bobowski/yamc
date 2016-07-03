# Author Adam Bobowski
#
# Machine registers


class Machine(object):
    def __init__(self):
        self.symtab = {}  # memory mapping
        self.blocks = {}  # block: line_no mapping
        self.code = []    # output code
        self.k = 0        # line_no

        self.regs = []    # machine registers
        self.regs = [None for _ in xrange(6)]

    # BASIC OPERATIONS

    # a <- number
    def num(self, number, a):
        self.cmd('RESET a', a=a)

        if number == 0:
            return a

        number = bin(number)[3:]  # skip 0b1[number]
        self.cmd('INC   a', a=a)
        for b in number:
            self.cmd('SHL   a', a=a)
            if b == '1':
                self.cmd('INC   a', a=a)
        return a

    # c <- a * b
    # consts: none  |   mutables: a, b, c
    # TODO add checking which is bigger !!
    def mul(self, a, b, c):
        mul = '''
                RESET   c
        $LOOP   JZERO   a   $END
                JODD    a   $ADD
                JUMP    $SHIFT
        $ADD    ADD     c   b
        $SHIFT  SHR     a
                SHL     b
                JUMP    $LOOP
        '''
        self.cmd(mul, a=a, b=b, c=c)

    # TODO % ONLY (4 registers only !!)
    # a - remainder

    # d <- a / b
    # consts: b     |   mutables: a, c, d, e
    def div(self, a, b, c, d, e):
        div = '''
                JZERO   b   $D_ZERO

                COPY    e   b
        $L1     COPY    d   e
                SUB     d   a
                JZERO   d   $SHL_E
                JUMP    $DIV
        $SHL_E  SHL     e
                JUMP    $L1

        $DIV    RESET   d

        $L2     COPY    c   e
                SUB     c   a
                JZERO   c   $ONE
                SHL     d
                SHR     e
                JUMP    $CHECK
        $ONE    SHL     d
                INC     d
                SUB     a   e
                SHR     e

        $CHECK  COPY    c   b
                SUB     c   e
                JZERO   c   $L2
                JUMP    $END

        $D_ZERO RESET   a
                RESET   d
        '''
        self.cmd(div, a=a, b=b, c=c, d=d, e=e)

    # COMMAND PARSING

    def cmd(self, code, **labels):
        code = [c.split() for c in code.splitlines()]
        code = [c for c in code if c]
        code = self.resolve_local_labels(code, labels)
        self.code.extend(code)
        self.k += len(code)

    def resolve_local_labels(self, code, glob_labels):
        def is_label(x): return x[0][0] == '$'
        labels = {l[0]: self.k + i for i, l in enumerate(code) if is_label(l)}
        labels['$END'] = self.k + len(code)
        labels.update(glob_labels)
        code = [c[1:] if is_label(c[0]) else c for c in code]

        def pack_commands(code):
            if c[-1] == 'blockjump':
                if c[0] == 'JZERO':
                    c[1] = str(labels.get(c[1], c[1]))
                c[-1] = labels.get('blockjump', 'blockjump')
                return c
            return ' '.join(str(x) for x in [labels.get(i, i) for i in code])
        code = [pack_commands(c) for c in code]

        return code

    def resolve_global_labels(self):
        for i, c in enumerate(self.code):
            if isinstance(c, list):
                c[-1] = self.blocks[c[-1]]
                self.code[i] = ' '.join(x for x in c)

    def end_of_block(self, next_block):
        for i, var in enumerate(self.regs):
            if var:
                self.store_reg(i)

    def alloregs(self, l_var, *r_vars):
        for var in r_vars:
            assert not isinstance(var, long)

        regs = [0]
        for var in r_vars:
            if var in self.regs:
                regs.append(self.regs.index(var))
            else:
                if None in self.regs:
                    a = self.regs.index(None)
                else:
                    excludes = list(r_vars)
                    excludes.append(l_var)
                    a = self.find_lru_reg(exclude=excludes)
                    self.store_reg(a)
                self.load_var(var, a)
                self.regs[a] = var
                regs.append(a)

        if l_var:
            if l_var in self.regs:
                regs[0] = self.regs.index(l_var)
            else:
                if None in self.regs:
                    a = self.regs.index(None)
                else:
                    a = self.find_lru_reg(exclude=r_vars)
                    self.store_reg(a)
                self.regs[a] = l_var
                regs[0] = a

        return tuple(regs) if len(regs) != 1 else regs[0]

    def find_lru_reg(self, exclude):
        for i, n in enumerate(self.regs):
            if n not in exclude:
                return i

    def store_reg(self, reg):
        variable = self.regs[reg]

        if is_int(variable):
            position = self.symtab[variable]
            self.num(position, 8)
            self.cmd('STORE reg 8', reg=reg)
            return

        if is_inttab(variable):
            variable, offset = variable
            position = self.symtab[variable]

            if is_number(offset):
                position += offset
                self.num(position, 9)
                self.cmd('STORE reg 9', reg=reg)
                return

            if offset in self.regs:
                i = self.regs.index(offset)
                self.num(position, 9)
                self.cmd('ADD   9   i', i=i)
                self.cmd('STORE reg 9', reg=reg)
            else:
                self.load_var(offset, 8)
                self.num(position, 9)
                self.cmd('ADD   9   8')
                self.cmd('STORE reg 9', reg=reg)

    def load_var(self, variable, reg):
        if is_int(variable):
            position = self.symtab[variable]
            self.num(position, 8)
            self.cmd('LOAD  reg 8', reg=reg)
            return

        if is_inttab(variable):
            variable, offset = variable
            position = self.symtab[variable]

            if is_number(offset):
                position += offset
                self.num(position, 9)
                self.cmd('LOAD  reg 9', reg=reg)
                return

            if offset in self.regs:
                i = self.regs.index(offset)
                self.num(position, 9)
                self.cmd('ADD   9   i', i=i)
                self.cmd('LOAD  reg 9', reg=reg)
            else:
                self.load_var(offset, 8)
                self.num(position, 9)
                self.cmd('ADD   9   8')
                self.cmd('LOAD  reg 9', reg=reg)

    def store_iterators(self, a):
        for i, variable in enumerate(self.regs):
            if is_inttab(variable):
                variable, offset = variable
                if a == offset:
                    self.store_reg(i)

    def load_iterators(self, a):
        for i, var in enumerate(self.regs):
            if is_inttab(var):
                variable, offset = var
                if a == offset:
                    self.load_var(var, i)

def is_number(a): return isinstance(a, long)
def is_int(a): return isinstance(a, str)
def is_inttab(a): return isinstance(a, tuple) and len(a) == 2
def is_operation(a): return isinstance(a, tuple) and len(a) == 3
