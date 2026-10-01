# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# Copyright (C) 1993-2007 Yukihiro Matsumoto
# SPDX-License-Identifier: BSD-2-Clause AND BSD-3-Clause-Clear

"""Adapt Ruby 3.4.10 Enumerable#sort_by's uniform intro-sort from enum.c.

Source: https://github.com/ruby/ruby/blob/v3_4_10/enum.c,
rb_uniform_heap_down_2/heapsort_2/quicksort_intro_2/intro_sort_2.
The preserved numeric-key tie ordering is Ruby >= 3.4 specific, not glibc
qsort_r's ordering. Ruby's BSD-2-Clause option is used; see adjacent NOTICE.
"""

from __future__ import annotations

from typing import Any


def _heap_sort(items: list[tuple[bool, str, Any]], start: int, stop: int) -> None:
    def heap_down(offset: int, last: int) -> None:
        value = items[start + offset]
        while 2 * offset + 1 <= last:
            child = 2 * offset + 1
            if child < last and items[start + child][0] < items[start + child + 1][0]:
                child += 1
            if value[0] >= items[start + child][0]:
                break
            items[start + offset] = items[start + child]
            offset = child
        items[start + offset] = value

    size = stop - start
    for offset in range(size // 2 - 1, -1, -1):
        heap_down(offset, size - 1)
    for last in range(size - 1, 0, -1):
        items[start], items[start + last] = items[start + last], items[start]
        heap_down(0, last - 1)


def property_order(properties: dict[str, Any], required: list[str]) -> list[tuple[str, Any]]:
    """Sort two priority classes with Ruby 3.4's numeric-key tie behavior.

    Ruby's optimized sort is not stable: unsorted tables longer than sixteen
    properties can reverse equal-priority fields. Stable Python sorting changes
    released MDX. The bounded binary-key partition below retains those bytes;
    already grouped inputs and small partitions preserve insertion order.
    """
    items = [(name not in required, name, schema) for name, schema in properties.items()]
    if any(items[index - 1][0] > items[index][0] for index in range(1, len(items))):
        pending = [(0, len(items), 2 * (len(items).bit_length() - 1))]
        while pending:
            start, stop, depth = pending.pop()
            if stop - start <= 16:
                for index in range(start + 1, stop):
                    value = items[index]
                    cursor = index
                    while cursor > start and value[0] < items[cursor - 1][0]:
                        items[cursor] = items[cursor - 1]
                        cursor -= 1
                    items[cursor] = value
                continue
            if depth == 0:
                _heap_sort(items, start, stop)
                continue
            pivot = sum((items[start][0], items[(start + stop) // 2][0], items[stop - 1][0])) >= 2
            left, right = start, stop - 1
            while left <= right:
                while items[left][0] < pivot:
                    left += 1
                while pivot < items[right][0]:
                    right -= 1
                if left <= right:
                    items[left], items[right] = items[right], items[left]
                    left += 1
                    right -= 1
            if left - start > 1:
                pending.append((start, left, depth - 1))
            if stop - (right + 1) > 1:
                pending.append((right + 1, stop, depth - 1))
    return [(name, schema) for _, name, schema in items]
