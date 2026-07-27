import sys


if sys.version_info >= (3, 12):
    from itertools import batched
else:
    from itertools import islice

    def batched(iterable, n, *, strict=False):
        """
        Backport of itertools.batched() for Python < 3.12.
        """
        if n < 1:
            raise ValueError('n must be at least one')
        iterator = iter(iterable)
        while batch := tuple(islice(iterator, n)):
            if strict and len(batch) != n:
                raise ValueError('batched(): incomplete batch')
            yield batch
