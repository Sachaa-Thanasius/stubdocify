import logging
from typing import TextIO, TypeVar

import libcst

_DocstringableNodeT = TypeVar("_DocstringableNodeT", libcst.FunctionDef, libcst.ClassDef)

_log = logging.getLogger("stubdocify")


def _create_docstring_node(docstring: str) -> libcst.SimpleStatementLine:
    return libcst.SimpleStatementLine(body=[libcst.Expr(libcst.SimpleString(value=f'"""{docstring}"""'))])


def _update_node_docstring(node: _DocstringableNodeT, new_docstring: str | None) -> _DocstringableNodeT:
    """Takes a libcst node that supports docstrings and modifies its docstring.

    It makes the assumption that the function/class/module will have at least one code line inside of it and be
    indented appropriately.

    Parameters
    ----------
    node: DocstringableNodeT
        A libcst node that supports having docstrings added to it, including a ClassDef, FunctionDef, or Module.
    new_docstring: str | None
        The docstring to add or replace the old one with, or None to remove the existing docstring.

    Raises
    ------
    ValueError
        Whether this node can have docstrings added to it.
    """

    # Assuming the class will have at least one code line inside it, and it should be indented.
    node_body = node.body.body
    first_child = node_body[0]

    match (first_child, new_docstring):
        case (libcst.SimpleStatementLine(body=[libcst.Expr(value=libcst.SimpleString()), *_]), str()):
            # Replace old docstrings with updated versions from source.
            return node.with_deep_changes(node.body, body=[_create_docstring_node(new_docstring), *node_body[1:]])

        case (libcst.SimpleStatementLine(body=[libcst.Expr(value=libcst.SimpleString()), *_]), None):
            # Remove a stub's existing docstring to match the source's removal.
            return node.with_deep_changes(node.body, body=node_body[1:])

        case (libcst.SimpleStatementLine(body=[libcst.Expr(value=libcst.Ellipsis()), *_]), str()):
            # Add the docstring, but don't save the body of the function if it only contains an indented ellipsis.
            return node.with_deep_changes(node.body, body=[_create_docstring_node(new_docstring)])

        case (libcst.SimpleStatementLine(body=[*_]), str()):
            # Add a docstring and save the body of the function otherwise.
            return node.with_deep_changes(node.body, body=[_create_docstring_node(new_docstring), *node_body])

        case (libcst.Expr(value=libcst.Ellipsis()), str()):
            # Don't save the ellipses if it's on the same line as the definition.
            return node.with_changes(body=libcst.IndentedBlock([_create_docstring_node(new_docstring)]))

        case _:
            msg = f"This function isn't equipped to handle docstrings in this type of node:\n{type(node)}"
            exc = ValueError(msg)
            exc.add_note(repr(node))
            raise exc


class DocstringCollector(libcst.CSTVisitor):
    """A libcst visitor that grabs docstrings from relevant nodes (e.g. modules, classes, functions).

    Attributes
    ----------
    stack: list[str], default=[]
        A list to keep track of locations based on depth of the tree. Stores names of classes and functions.
    docstrings: dict[tuple[str, ...], str | None], default={}
        A mapping to hold the docstrings for each node that has one, using the current stack as a key.
    """

    def __init__(self):
        self.stack: list[str] = []
        self.docstrings: dict[tuple[str, ...], str | None] = {}

    def visit_Module(self, node: libcst.Module) -> None:
        # Use the empty string to represent a module.
        self.docstrings[("",)] = node.get_docstring(clean=False)

    def visit_ClassDef(self, node: libcst.ClassDef) -> bool | None:
        self.stack.append(node.name.value)
        self.docstrings[tuple(self.stack)] = node.get_docstring(clean=False)

    def leave_ClassDef(self, original_node: libcst.ClassDef) -> None:
        self.stack.pop()

    def visit_FunctionDef(self, node: libcst.FunctionDef) -> bool | None:
        self.stack.append(node.name.value)
        self.docstrings[tuple(self.stack)] = node.get_docstring(clean=False)
        return False  # pyi files don't support inner functions, return False to stop the traversal.

    def leave_FunctionDef(self, original_node: libcst.FunctionDef) -> None:
        self.stack.pop()


class DocstringTransformer(libcst.CSTTransformer):
    """A libcst transformer that either adds, removes, or transforms docstrings based on a given docstring mapping.

    Parameters
    ----------
    docstrings: dict[tuple[str, ...], str | None]
        A mapping with the new docstrings for each relevant node, using the current stack as a key.

    Attributes
    ----------
    stack: list[str], default=[]
        A list to keep track of locations based on depth of the tree. Stores names of classes and functions.
    docstrings: dict[tuple[str, ...], str | None]
        A mapping with the new docstrings for each relevant node, using the current stack as a key.
    """

    def __init__(self, docstrings: dict[tuple[str, ...], str | None]):
        self.stack: list[str] = []
        self.docstrings: dict[tuple[str, ...], str | None] = docstrings

    def visit_ClassDef(self, node: libcst.ClassDef) -> bool | None:
        self.stack.append(node.name.value)

    def leave_ClassDef(self, original_node: libcst.ClassDef, updated_node: libcst.ClassDef) -> libcst.ClassDef:
        key = tuple(self.stack)
        self.stack.pop()

        if key not in self.docstrings:
            _log.error("Couldn't find source docstring for class definition '%r'. Skipping ...", ".".join(key))
            return updated_node

        new_docstring = self.docstrings[key]

        return _update_node_docstring(updated_node, new_docstring)

    def visit_FunctionDef(self, node: libcst.FunctionDef) -> bool | None:
        self.stack.append(node.name.value)
        return False  # pyi files don't support inner functions, return False to stop the traversal.

    def leave_FunctionDef(
        self,
        original_node: libcst.FunctionDef,
        updated_node: libcst.FunctionDef,
    ) -> libcst.FunctionDef:
        key = tuple(self.stack)
        self.stack.pop()
        if key not in self.docstrings:
            _log.error("Couldn't find source docstring for function definition '%r'. Skipping ...", ".".join(key))
            return updated_node

        new_docstring = self.docstrings[key]

        return _update_node_docstring(updated_node, new_docstring)


def collect_docstrings(code: str) -> dict[tuple[str, ...], str | None]:
    """Parse the given string of code and return a mapping of locations to docstrings."""

    source_tree = libcst.parse_module(code)
    visitor = DocstringCollector()
    source_tree.visit(visitor)
    return visitor.docstrings


def rewrite_docstrings(code: str, docstrings_map: dict[tuple[str, ...], str | None]) -> str:
    """Parse the given string of code and use a libcst transformer to edit the contained docstrings according to a
    given docstring mapping.
    """

    target_tree = libcst.parse_module(code)
    transformer = DocstringTransformer(docstrings_map)
    modified_tree = target_tree.visit(transformer)
    return modified_tree.code


def update_code_docstrings(source_code: str, target_code: str) -> str:
    """Edit target code to have the docstrings of the source code (wherever reasonable) and return the updated code."""

    docstrings_map = collect_docstrings(source_code)
    return rewrite_docstrings(target_code, docstrings_map)


def update_io_docstrings(source: TextIO, target: TextIO) -> None:
    """Edit target code to have the docstrings of the source code (wherever reasonable)."""

    results = update_code_docstrings(source.read(), target.read())
    target.write(results)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("source_filename")
    parser.add_argument("target_filename")
    args = parser.parse_args()

    with open(args.source_filename) as source, open(args.target_filename) as target:  # noqa: PTH123
        update_io_docstrings(source, target)


if __name__ == "__main__":
    raise SystemExit(main())
