"""Welcome to the find.py module."""

from collections.abc import Iterable
from typing import Generic, TypeVar

_T = TypeVar("_T")

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
        ...

def global_find(finder: Finder[_T]) -> _T:
    """Global find def docstring."""
    ...
