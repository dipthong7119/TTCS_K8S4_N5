# models/__init__.py
# Import tat ca model de Alembic autogenerate phat hien duoc toan bo schema

from app.models.user import Role, User, user_roles  # noqa: F401
from app.models.station import Station              # noqa: F401
from app.models.charge_point import ChargePoint, Connector  # noqa: F401
