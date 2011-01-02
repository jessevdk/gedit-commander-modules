import commander.commands as commands
import commander.commands.completion
import commander.commands.result
import commander.commands.exceptions

__commander_module__ = True

def _search_paren(piter, search_for, skip_classes, last=None, stackon=None, stackoff=None):
    buf = piter.get_buffer()
    level = 0

    while True:
        if last and piter.compare(last) >= 0:
            return False

        ch = piter.get_char()

        if level == 0 and ch == search_for:
            break

        if ch == stackon:
            level += 1
        elif ch == stackoff:
            level -= 1

        if not piter.forward_char():
            return False

        for skip in skip_classes:
            if buf.iter_has_context_class(piter, skip):
                if not buf.iter_forward_to_context_class_toggle(piter, skip):
                    return False

    return True

def break_function(view):
    """Break function call over several lines

Break a C function call over seperate lines, indenting each line appropriately.
Execute with the cursor on the line where the function call starts."""

    buf = view.get_buffer()
    start = buf.get_iter_at_mark(buf.get_insert())

    start.set_line_offset(0)
    begin = start.copy()

    while start.get_char().isspace() and not start.ends_line():
        if not start.forward_char():
            return

    if start.ends_line():
        return

    wordstart = start.copy()
    indent = begin.get_text(start)
    skip_classes = ['comment', 'string']

    # Find open paren
    if not _search_paren(start, '(', skip_classes):
        return

    openparen = start.copy()
    start.forward_char()

    # Find close paren
    if not _search_paren(start, ')', skip_classes, None, '(', ')'):
        return

    closeparen = start.copy()
    breaks = []

    next = openparen.copy()
    next.forward_char()

    offset = openparen.get_offset()

    # Find seperators
    while True:
        if not _search_paren(next, ',', skip_classes, closeparen, '(', ')'):
            break

        breaks.append(next.get_offset() - offset)
        next = next.copy()

        if not next.forward_char():
            break

    if not breaks:
        return

    breaks.insert(0, 0)
    breaks.append(-1)

    end = closeparen.copy()
    end.forward_char()

    text = openparen.get_text(end)
    parts = []

    for i in range(1, len(breaks)):
        start = breaks[i - 1] + 1
        end = breaks[i]

        parts.append(text[start:end].strip())

    num_spaces = (openparen.get_offset() - wordstart.get_offset() + 1)

    openparen.backward_char()

    if openparen.get_char() != ' ':
        text = ' ('
        num_spaces += 1
    else:
        text = '('

    openparen.forward_char()

    spaces = ' ' * num_spaces
    indent += spaces

    buf.begin_user_action()

    text += (",\n%s" % (indent,)).join(parts)

    buf.delete(openparen, closeparen)
    buf.insert(openparen, text)
    buf.end_user_action()

# vi:ts=4:et
