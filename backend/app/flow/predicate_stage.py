from app.infra.core.jobs_db import update_status
from app.knowledge.criteria.protocols import Context, DbLike
from app.knowledge.criteria.runner import run_predicates


def run(db: DbLike, ctx: Context, *, groups=None):
    # after evaluation
    update_status(job_id, status="running", progress=90, message="Evaluation complete")
    return run_predicates(db, ctx, groups=groups, fail_fast=True, raise_on_error=True)
