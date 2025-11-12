from app.knowledge.criteria.protocols import Context, DbLike
from app.knowledge.criteria.runner import run_predicates


def run(db: DbLike, ctx: Context, *, groups=None):
    return run_predicates(db, ctx, groups=groups, fail_fast=True, raise_on_error=True)
