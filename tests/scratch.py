import pathlib

import stubdocify

py_source = '''
"""Welcome to the find.py module."""

from collections.abc import Iterable
from typing import Generic, TypeVar

_T = TypeVar("_T")

class TestClass:
    """Thing here"""
    ...

class Finder(Generic[_T]):
    """Finder docstring, source code."""

    search_obj: _T
    """The object to search for."""

    def find_item(item: _T, iterable: Iterable[_T]) -> tuple[int, _T] | tuple[None, None]:
        """Finds the given item in an iterable.

        Parameters
        ----------
        item: _T
            The object to look for.
        iterable: Iterable[T]
            The iterable of objects to search within.

        Returns
        -------
        tuple[int, _T] | tuple[None, None]
            A two-tuple with the index of the object in the iterable and the object itself, if found, else a two-tuple
            of None.
        """

        return next(((index, it) for index, it in enumerate(iter(iterable)) if it == item), (None, None))


async def global_find(finder: Finder[_T]) -> _T:
    """Global find def docstring."""

    return finder.search_obj
'''

pyi_source = '''
from collections.abc import Iterable
from typing import Generic, TypeVar

_T = TypeVar("_T")

class TestClass: ...

class Finder(Generic[_T]):
    search_obj: _T
    """The object to search for."""

    def find_item(item: _T, iterable: Iterable[_T]) -> tuple[int, _T] | tuple[None, None]: ...

async def global_find(finder: Finder[_T]) -> _T:
    """Nonsense"""
    ...
'''


def test_input_files():
    source_path = pathlib.Path(__file__).parent.joinpath("data", "package1", "find.py")
    stub_path = pathlib.Path(__file__).parent.joinpath("data", "package1_stubs", "find.pyi")

    with source_path.open(encoding="utf-8") as sp, stub_path.open(encoding="utf-8") as sp2:
        stubdocify.update_io_docstrings(sp, sp2)


def test_input_strings():
    result = stubdocify.update_code_docstrings(py_source, pyi_source)
    print(result)


def display_check():
    import textwrap

    import libcst
    import libcst.tool

    test_source = """
    def func(a: int, b: str) -> str:
        '''Test function docstring'''
        ...
    """

    test_source2 = """
    def func(a: int, b: str) -> str: ...
    """

    test_source3 = """
    def func(a: int, b: str) -> str:
        ...
    """

    for source in (test_source, test_source2, test_source3):
        tree = libcst.parse_module(textwrap.dedent(source))
        print(libcst.tool.dump(tree, indent=" " * 4, show_whitespace=True, show_syntax=True))
        print("------------------------------------------")


if __name__ == "__main__":
    test_input_strings()
    # display_check()
