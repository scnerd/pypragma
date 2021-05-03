import ast
import tempfile

import astor


def save_or_return_source(f_file, f_mod, glbls, return_source, save_source):
    if return_source or save_source:
        try:
            source = astor.to_source(f_mod)
        except Exception as ex:  # pragma: nocover
            raise RuntimeError(astor.dump_tree(f_mod)) from ex
    else:
        source = None

    if return_source:
        return source

    f_mod = ast.fix_missing_locations(f_mod)
    if save_source:
        temp = tempfile.NamedTemporaryFile('w', delete=False)
        f_file = temp.name
    exec(compile(f_mod, f_file, 'exec'), glbls)
    func = glbls[f_mod.body[0].name]
    if save_source:
        func.__tempfile__ = temp
        # When there are other decorators, the co_firstlineno of *some* python distributions gets confused
        # and thinks they will be there even when they are not written to the file, causing readline overflow
        # So we put some empty lines to make them align
        temp.write(source)
        temp.write('\n' * func.__code__.co_firstlineno)
        temp.flush()
        temp.close()
    return func