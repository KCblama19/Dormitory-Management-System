
"""
Database row-locking utilities for coordinating accommodation resources.

Locking contract:
    Building -> Floor -> Room -> BedConfiguration -> Bed

Shared locks:
    Allow concurrent operations to read/use a parent resource while preventing
    conflicting updates to that parent.

Exclusive locks:
    Serialize operations that modify the same resource.

Important:
    Shared row locks require PostgreSQL. SQLite does not provide equivalent
    row-level locking behavior, so this module rejects shared-lock requests
    on unsupported database backends instead of silently weakening guarantees.

All locking functions must be called inside an active transaction.
"""

from collections.abc import Iterable
from typing import Literal

from django.db import connections, transaction
from django.db.models import Model


LockMode = Literal["shared", "exclusive"]


class LockingError(RuntimeError):
    """Raised when a row-locking operation violates the locking contract."""


def _get_connection(using: str):
    """
    Return the selected database connection and verify transaction state.

    Row locks must remain active until the surrounding transaction completes.
    Calling these utilities outside transaction.atomic() would release the lock
    immediately or fail to provide the guarantees expected by the services.
    """
    connection = connections[using]

    if not connection.in_atomic_block:
        raise LockingError(
            "Row locks must be acquired inside transaction.atomic()."
        )

    return connection


def _validate_lock_mode(
    connection,
    mode: LockMode,
) -> None:
    """
    Validate the requested lock mode against the database backend.

    PostgreSQL supports both shared and exclusive row locks.
    Other backends are not accepted for this locking contract.
    """
    if mode not in ("shared", "exclusive"):
        raise ValueError(
            f"Unsupported lock mode: {mode!r}"
        )

    if connection.vendor != "postgresql":
        raise LockingError(
            "This locking utility requires PostgreSQL. "
            "SQLite does not provide equivalent row-level locking guarantees."
        )

def get_locked_instance(
    model: type[Model],
    pk,
    *,
    mode: LockMode = "exclusive",
    using: str = "default",
) -> Model:
    """
    Acquire a row lock and return a fresh model instance.

    The lock is acquired before the instance is retrieved. The returned
    instance therefore reflects the database state visible after acquiring
    the lock, rather than relying on a potentially stale caller instance.

    The surrounding transaction must remain open while the instance is used.
    """
    connection = _get_connection(using)
    _validate_lock_mode(connection, mode)

    lock_row(
        model,
        pk,
        mode=mode,
        using=using,
    )

    try:
        return model.objects.using(using).get(pk=pk)
    except model.DoesNotExist as exc:
        raise LockingError(
            f"{model._meta.label} disappeared after its lock was acquired."
        ) from exc



def lock_row(
    model: type[Model],
    pk,
    *,
    mode: LockMode = "exclusive",
    using: str = "default",
) -> None:
    """
    Acquire a lock on one database row.

    Args:
        model:
            Django model class representing the table.

        pk:
            Primary key of the row to lock.

        mode:
            "shared" allows compatible concurrent readers/operations.
            "exclusive" serializes conflicting operations on the row.

        using:
            Django database alias.

    Raises:
        LockingError:
            If called outside a transaction or on an unsupported backend.

        model.DoesNotExist:
            If the requested row does not exist.

    Notes:
        The caller remains responsible for acquiring locks in the global
        resource order:

            Building -> Floor -> Room -> BedConfiguration -> Bed

        This function deliberately does not acquire ancestor locks
        automatically because each service has different resource requirements.
    """
    connection = _get_connection(using)
    _validate_lock_mode(connection, mode)

    # Table and column names come from Django model metadata and are quoted
    # through the active database backend. The primary key remains a parameter.
    table_name = connection.ops.quote_name(model._meta.db_table)
    pk_column = connection.ops.quote_name(model._meta.pk.column)

    lock_clause = (
        "FOR SHARE"
        if mode == "shared"
        else "FOR UPDATE"
    )

    sql = (
        f"SELECT {pk_column} "
        f"FROM {table_name} "
        f"WHERE {pk_column} = %s "
        f"{lock_clause}"
    )

    with connection.cursor() as cursor:
        cursor.execute(sql, [pk])
        row = cursor.fetchone()

    if row is None:
        raise model.DoesNotExist(
            f"{model._meta.label} with primary key {pk!r} does not exist."
        )


def lock_rows(
    model: type[Model],
    pks: Iterable,
    *,
    mode: LockMode = "exclusive",
    using: str = "default",
) -> None:
    """
    Acquire locks for multiple rows in deterministic primary-key order.

    Deterministic ordering reduces deadlock risk when multiple transactions
    need to lock the same collection of resources.

    Duplicate primary keys are removed before locking.

    Example:
        lock_rows(
            Building,
            affected_building_ids,
            mode="exclusive",
        )

    The caller must already hold any required ancestor locks.
    """
    connection = _get_connection(using)
    _validate_lock_mode(connection, mode)

    # Sorting ensures every service requests these locks in the same order.
    # Converting to a set also prevents accidentally locking one row twice.
    ordered_pks = sorted(set(pks))

    for pk in ordered_pks:
        lock_row(
            model,
            pk,
            mode=mode,
            using=using,
        )


def lock_instance(
    instance: Model,
    *,
    mode: LockMode = "exclusive",
    using: str | None = None,
) -> None:
    """
    Lock the database row represented by an existing model instance.

    This helper uses the instance's model and primary key only.
    It does not refresh the instance or guarantee that its in-memory
    field values reflect the latest committed database state.

    Services should fetch or refresh the instance after acquiring the
    appropriate locks when they need current field values.
    """
    if instance.pk is None:
        raise LockingError(
            "Cannot lock an unsaved model instance."
        )

    database_alias = using or instance._state.db or "default"

    lock_row(
        type(instance),
        instance.pk,
        mode=mode,
        using=database_alias,
    )