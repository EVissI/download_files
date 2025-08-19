from sqlalchemy.dialects.postgresql import ENUM
from alembic.autogenerate import comparators


@comparators.dispatch_for(ENUM)
def compare_enums(autogen_context, upgrade_ops, schema, tname, cname, col, orig_col):
    """
    Custom comparator for PostgreSQL ENUM types.
    Detects changes in ENUM values and generates appropriate migration operations.
    """
    if isinstance(col.type, ENUM) and isinstance(orig_col.type, ENUM):
        # Get the current and original ENUM values
        current_enum_values = set(col.type.enums)
        original_enum_values = set(orig_col.type.enums)

        # Detect added values
        added_values = current_enum_values - original_enum_values
        for value in added_values:
            upgrade_ops.ops.append(
                f"ALTER TYPE {col.type.name} ADD VALUE '{value}'"
            )

        # Detect removed values (PostgreSQL does not support removing ENUM values)
        removed_values = original_enum_values - current_enum_values
        if removed_values:
            raise ValueError(
                f"Cannot remove ENUM values in PostgreSQL: {removed_values}. "
                "You must manually handle this case."
            )