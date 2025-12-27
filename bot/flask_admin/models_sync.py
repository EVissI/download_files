"""
Provide a helper to register sync model classes for Flask-AppBuilder by
binding existing Table objects (from the async metadata) to Flask-SQLAlchemy
`db.Model` subclasses. This avoids duplicating column definitions.

Usage:
    from bot.flask_admin.models_sync import register_sync_models
    models = register_sync_models(db)
    User = models['User']
"""


def register_sync_models(db):
    # Reflect tables into Flask-SQLAlchemy metadata using the app-bound engine
    # Note: this function must be called after `db.init_app(app)` and inside
    # the application context so `db.engine` is available.
    db.metadata.reflect(bind=db.engine)

    table_map = {
        "User": "users",
        "UserGroup": "user_groups",
        "UserInGroup": "user_in_groups",
        "Promocode": "promocode",
        "PromocodeServiceQuantity": "promocode_service_quantities",
        "UserPromocode": "user_promocode",
        "UserPromocodeService": "user_promocode_services",
        "MessageForNew": "messages_for_new",
        "AnalizePayment": "analize_payments",
        "AnalizePaymentServiceQuantity": "analize_payment_service_quantities",
        "UserAnalizePayment": "user_analize_payments",
        "UserAnalizePaymentService": "user_analize_payment_services",
    }

    models = {}
    for cls_name, table_name in table_map.items():
        if table_name not in db.metadata.tables:
            # skip missing tables — admin can still start but that view won't work
            continue
        table = db.metadata.tables[table_name]
        model = type(
            cls_name,
            (db.Model,),
            {
                "__table__": table,
                "__repr__": lambda self: f"<{cls_name} {getattr(self, 'id', '')}>",
            },
        )
        models[cls_name] = model

    return models
