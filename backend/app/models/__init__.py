# models package
# Import tất cả model để Alembic autogenerate nhận diện được
from app.models.user import User, Role, UserRole  # noqa: F401
from app.models.station import Station  # noqa: F401
from app.models.charge_point import ChargePoint, Connector  # noqa: F401
