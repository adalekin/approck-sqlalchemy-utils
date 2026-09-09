from alembic.script import ScriptDirectory


def process_revision_directives(context, revision, directives):
    # extract Migration
    migration_script = directives[0]
    # extract current head revision
    head_revision = ScriptDirectory.from_config(context.config).get_current_head()

    if head_revision is None:
        # edge case with first migration
        new_rev_id = 1
    else:
        # This scheme assumes a single linear history of zero-padded numeric ids
        # (0001, 0002, …). A non-numeric head (e.g. a hash id or a merge revision)
        # cannot be incremented; fail with a clear message instead of an opaque
        # ValueError from int().
        try:
            last_rev_id = int(head_revision.lstrip("0"))
        except ValueError as exc:
            raise ValueError(
                f"Cannot derive the next revision id from head {head_revision!r}: "
                "humanreadable numbering requires a linear numeric history"
            ) from exc
        new_rev_id = last_rev_id + 1
    # fill zeros up to 4 digits: 1 -> 0001
    migration_script.rev_id = f"{new_rev_id:04}"
