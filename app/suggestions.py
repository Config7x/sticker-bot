"""Suggestion engine for one wizard step (pure logic, unit-testable).

Implements the SPEC section 4 rules:
- suggestions come in multi-option batches, never one forced choice;
- "next batch" never repeats an item already shown in this step;
- everything shown is kept in a seen-history: the user can walk back and
  forth (prev/next, "پیشنهاد N از M") and pick ANY earlier item, e.g. the
  2nd of 5, from the "seen list";
- only an explicit 🚫 reject removes an item for good (per step session);
- bookmarked items (❤️) are tracked separately for later comparison.

The session is JSON-serializable so it can live inside aiogram FSM state.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field


@dataclass
class SuggestionSession:
    pool: list[dict] = field(default_factory=list)      # all candidates (dicts with "id")
    batch_size: int = 6
    seen: list[dict] = field(default_factory=list)      # shown so far, in order
    cursor: int = -1                                    # index into seen (single view)
    rejected: list = field(default_factory=list)        # ids rejected with 🚫
    bookmarked: list = field(default_factory=list)      # ids bookmarked with ❤️
    _pool_pos: int = 0                                  # next unseen pool index

    # -- batching ------------------------------------------------------------
    def next_batch(self) -> list[dict]:
        """Return the next batch of fresh items (no repeats, no rejected)."""
        batch: list[dict] = []
        seen_ids = {it["id"] for it in self.seen}
        while self._pool_pos < len(self.pool) and len(batch) < self.batch_size:
            item = self.pool[self._pool_pos]
            self._pool_pos += 1
            if item["id"] in self.rejected or item["id"] in seen_ids:
                continue
            batch.append(item)
            seen_ids.add(item["id"])
        self.seen.extend(batch)
        if batch:
            self.cursor = len(self.seen) - len(batch)
        return batch

    def has_more(self) -> bool:
        seen_ids = {it["id"] for it in self.seen}
        return any(
            it["id"] not in self.rejected and it["id"] not in seen_ids
            for it in self.pool[self._pool_pos:]
        )

    # -- single-item navigation over the seen history -------------------------
    def current(self) -> dict | None:
        if 0 <= self.cursor < len(self.seen):
            return self.seen[self.cursor]
        return None

    def go_prev(self) -> dict | None:
        if self.cursor > 0:
            self.cursor -= 1
        return self.current()

    def go_next(self) -> dict | None:
        if self.cursor < len(self.seen) - 1:
            self.cursor += 1
        return self.current()

    def position_label(self) -> str:
        if not self.seen:
            return "پیشنهادی نمایش داده نشده"
        return f"پیشنهاد {self.cursor + 1} از {len(self.seen)}"

    # -- picking / rejecting ---------------------------------------------------
    def pick_seen(self, index: int) -> dict | None:
        """Pick any previously seen item by its 0-based history index."""
        if 0 <= index < len(self.seen):
            self.cursor = index
            return self.seen[index]
        return None

    def reject(self, item_id) -> None:
        """🚫 reject: remove from seen and never show again in this session."""
        if item_id not in self.rejected:
            self.rejected.append(item_id)
        self.seen = [it for it in self.seen if it["id"] != item_id]
        if self.cursor >= len(self.seen):
            self.cursor = len(self.seen) - 1

    def toggle_bookmark(self, item_id) -> bool:
        if item_id in self.bookmarked:
            self.bookmarked.remove(item_id)
            return False
        self.bookmarked.append(item_id)
        return True

    def random_seen_or_batch(self) -> dict | None:
        """🎲 random pick: from what is seen, else pull a fresh batch."""
        if not self.seen:
            self.next_batch()
        if not self.seen:
            return None
        item = random.choice(self.seen)
        self.cursor = self.seen.index(item)
        return item

    # -- FSM (de)serialization --------------------------------------------------
    def to_dict(self) -> dict:
        return {
            "pool": self.pool,
            "batch_size": self.batch_size,
            "seen": self.seen,
            "cursor": self.cursor,
            "rejected": self.rejected,
            "bookmarked": self.bookmarked,
            "_pool_pos": self._pool_pos,
        }

    @classmethod
    def from_dict(cls, data: dict | None) -> "SuggestionSession":
        if not data:
            return cls()
        return cls(
            pool=data.get("pool", []),
            batch_size=data.get("batch_size", 6),
            seen=data.get("seen", []),
            cursor=data.get("cursor", -1),
            rejected=data.get("rejected", []),
            bookmarked=data.get("bookmarked", []),
            _pool_pos=data.get("_pool_pos", 0),
        )


def make_pool(items: list[dict], shuffle: bool = True) -> list[dict]:
    pool = list(items)
    if shuffle:
        random.shuffle(pool)
    return pool
