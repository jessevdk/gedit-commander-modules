import commander.commands as commands
import commander.commands.completion
import commander.commands.result
import commander.commands.exceptions

import re
import os

__commander_module__ = True

class Argument:
    def __init__(self, typ, ptr, name):
        self.typ = re.sub('\s+', ' ', typ.strip())
        self.ptr = ptr
        self.name = name

    def typ_len(self):
        return len(self.typ)

    def name_len(self):
        return len(self.name)

    def ptr_len(self):
        return len(self.ptr)

class Declaration:
    def __init__(self, buf, start, match):
        self.match = match

        argre = re.compile('^(.+?)([ *]+)([a-z_][a-z0-9_]*)$')

        self.typ = re.sub('\s+', ' ', match.group(1).strip())
        self.ptr = match.group(2).strip()
        self.name = match.group(3).strip()
        self.args = [self.match_arg(argre, x.strip()) for x in match.group(4).split(',')]

        self.max_argtyp = max(self.args, key=lambda x: x.typ_len())
        self.max_argname = max(self.args, key=lambda x: x.name_len())
        self.max_argptr = max(self.args, key=lambda x: x.ptr_len())

        self.typ_marks = self.create_marks(buf, start, match, 1, 2, True)
        self.name_marks = self.create_marks(buf, start, match, 3, 3, False)
        self.args_marks = self.create_marks(buf, start, match, 4, 4, False)

    def match_arg(self, argre, arg):
        if arg == 'void':
            return Argument(arg, '', '')
        else:
            match = argre.match(arg)

            return Argument(match.group(1), match.group(2).replace(' ', ''), match.group(3))

    def ptr_len(self):
        return len(self.ptr)

    def typ_len(self):
        return len(self.typ)

    def name_len(self):
        return len(self.name)

    def argtyp_len(self):
        return self.max_argtyp.typ_len()

    def argname_len(self):
        return self.max_argname.name_len()

    def argptr_len(self):
        return self.max_argptr.ptr_len()

    def create_marks(self, buf, start, match, grps, grpe, linestart):
        start = start.copy()
        end = start.copy()

        start.forward_chars(match.start(grps))

        if linestart and not start.starts_line():
            start.set_line_offset(0)

        end.forward_chars(match.end(grpe))

        mstart = buf.create_mark(None, start, False)
        mend = buf.create_mark(None, end, False)

        return [mstart, mend]

    def replace(self, buf, marks, s):
        start = buf.get_iter_at_mark(marks[0])
        end = buf.get_iter_at_mark(marks[1])

        buf.delete(start, end)
        buf.insert(start, s)

        buf.delete_mark(marks[0])
        buf.delete_mark(marks[1])

    def align(self, buf, typlen, ptrlen, namelen, argtyplen, argptrlen, argnamelen):
        tlen = typlen.typ_len()

        typdiff = typlen.typ_len() - self.typ_len()
        ptrdiff = ptrlen.ptr_len() - self.ptr_len()
        namediff = namelen.name_len() - self.name_len()

        typ = '%s %s%s' % (self.typ, ' ' * (typdiff + ptrdiff), self.ptr)

        self.replace(buf, self.typ_marks, typ)

        name = '%s%s ' % (self.name, ' ' * namediff)

        self.replace(buf, self.name_marks, name)

        iter = buf.get_iter_at_mark(self.args_marks[0])
        offset = iter.get_line_offset()

        args = []

        atlen = argtyplen.argtyp_len()
        aplen = argptrlen.argptr_len()
        anlen = argnamelen.argname_len()

        for i in xrange(0, len(self.args)):
            a = self.args[i]
            arg = ''

            atypdiff = atlen - a.typ_len()
            aptrdiff = aplen - a.ptr_len()
            anamediff = anlen - a.name_len()

            if i != 0:
                arg += ' ' * offset

            if a.name:
                typ = '%s %s%s' % (a.typ, ' ' * (atypdiff + aptrdiff), a.ptr)
            else:
                typ = a.typ

            arg += typ + a.name
            args.append(arg)

        self.replace(buf, self.args_marks, os.linesep.join(args))

def _find_not_space(find):
    return not find.get_char().isspace()

def _find_not_char(ch, *ignore_classes):
    def _anon_generator(find):
        for c in ignore_classes:
            if find.get_buffer().iter_has_context_class(find, c):
                return False

        return find.get_char() != ch

    return _anon_generator

def _find_char(ch, *ignore_classes):
    def _anon_generator(find):
        for c in ignore_classes:
            if find.get_buffer().iter_has_context_class(find, c):
                return False

        return find.get_char() == ch

    return _anon_generator

def _forward_find_char(iter, cb, end=None):
    if not end:
        end = iter.get_buffer().get_end_iter()

    while iter.compare(end) < 0:
        if cb(iter):
            return True

        iter.forward_char()

    return False

def _indent_c(view, entry):
    buf = view.get_buffer()

    bounds = buf.get_selection_bounds()

    if not bounds:
        iter = buf.get_iter_at_mark(buf.get_insert())
        bounds = [iter, iter.copy()]

    if not bounds[0].starts_line():
        bounds[0].set_line_offset(0)

    if not bounds[1].ends_line():
        bounds[1].forward_to_line_end()

    # Find first thingie
    start = bounds[0].copy()

    if not _forward_find_char(start, _find_not_space, bounds[1]):
        raise commander.commands.exceptions.Execute('Nothing to indent')

    # Find where to indent on
    indenton = start.copy()

    if not _forward_find_char(indenton, _find_char('(', 'comment', 'string'), bounds[1]):
        raise commander.commands.exceptions.Execute('Nothing to indent')

    indenton.forward_char()

    # Find breakers
    ptr = indenton.copy()
    breakers = []

    while True:
        if not _forward_find_char(ptr, _find_char(',', 'comment', 'string'), bounds[1]):
            break

        breakers.append(ptr.get_offset() - bounds[0].get_offset())

        if not ptr.forward_char():
            break

    indent = bounds[0].get_text(start) + ((indenton.get_offset() - start.get_offset()) * ' ')
    text = bounds[0].get_text(bounds[1])

    if breakers:
        buf.begin_user_action()
        buf.delete(buf.get_iter_at_offset(breakers[0] + bounds[0].get_offset()), bounds[1])

        for br in range(1, len(breakers)):
            tt = text[breakers[br - 1] + 1:breakers[br]].strip()

            buf.insert(bounds[1], ',\n%s%s' % (indent, tt))

        buf.insert(bounds[1], text[breakers[-1] + 1:])
        buf.end_user_action()
    else:
        raise commander.commands.exceptions.Execute('Nothing to indent')

def _indent_chdr(view, entry):
    buf = view.get_buffer()

    bounds = buf.get_selection_bounds()

    if not bounds:
        start = buf.get_iter_at_mark(buf.get_insert())

        end = start.copy()

        if not _forward_find_char(end, _find_char(';', 'comment', 'string')):
            raise commander.commands.exceptions.Execute('Could not find end of line to indent')

        reselect = False
    else:
        start = bounds[0]
        end = bounds[1]

        reselect = True

    marks = [buf.create_mark(None, start, True),
             buf.create_mark(None, end, False)]

    if not start.starts_line():
        start.set_line_offset(0)

    if not end.ends_line():
        end.forward_to_line_end()

    r = re.compile('\s*([^(]+?)(\**)([a-z_][a-z0-9_]*\s*)\(([^)]*)\)[^;]*;\s*', re.M)

    text = start.get_text(end)
    repl = re.compile('\s+')

    typlen = None
    namelen = None
    ptrlen = None
    argtyplen = None
    argnamelen = None
    argptrlen = None

    decls = []

    for m in r.finditer(text):
        decl = Declaration(buf, start, m)

        if not typlen or decl.typ_len() > typlen.typ_len():
            typlen = decl

        if not ptrlen or decl.ptr_len() > ptrlen.ptr_len():
            ptrlen = decl

        if not namelen or decl.name_len() > namelen.name_len():
            namelen = decl

        if not argtyplen or decl.argtyp_len() > argtyplen.argtyp_len():
            argtyplen = decl

        if not argnamelen or decl.argname_len() > argnamelen.argname_len():
            argnamelen = decl

        if not argptrlen or decl.argptr_len() > argptrlen.argptr_len():
            argptrlen = decl

        decls.append(decl)

    buf.begin_user_action()

    # Replace everything
    for decl in decls:
        decl.align(buf, typlen, ptrlen, namelen, argtyplen, argptrlen, argnamelen)

    if reselect:
        buf.select_range(buf.get_iter_at_mark(marks[0]),
                         buf.get_iter_at_mark(marks[1]))
    else:
        buf.place_cursor(buf.get_iter_at_mark(marks[0]))

    buf.delete_mark(marks[0])
    buf.delete_mark(marks[1])

    buf.end_user_action()

_language_handlers = {
    'c': _indent_c,
    'cpp': _indent_c,
    'chdr': _indent_chdr
}

@commands.accelerator('<Control>i')
def __default__(view, entry):
    lang = view.get_buffer().get_language()

    if lang:
        lang = lang.get_id()

    if not lang in _language_handlers:
        raise commander.commands.exceptions.Execute('Indentation rules not available for this language')

    return _language_handlers[lang](view, entry)

# vi:ex:ts=4:et
